#!/usr/bin/env python3
"""Download point-in-time Tushare financial tables for the local factor pool.

The downloader is resumable and keeps credentials out of the repository.  It
uses the VIP endpoints because they accept a batch of stock codes and return
up to 5,000 rows per request.  The raw tables are kept separate so the factor
rebuild can choose the appropriate statement and announcement-date policy.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
FINANCIAL_ROOT = DATA_ROOT / "financial"

ENDPOINTS: dict[str, dict[str, str]] = {
    "fina_indicator": {
        "api": "fina_indicator_vip",
        "fields": ",".join(
            [
                "ts_code",
                "ann_date",
                "end_date",
                "report_type",
                "comp_type",
                "end_type",
                "roe",
                "roe_dt",
                "roa",
                "roa_yearly",
                "roa2_yearly",
                "roic",
                "grossprofit_margin",
                "current_ratio",
                "debt_to_assets",
                "assets_turn",
                "ocf_to_debt",
                "netprofit_margin",
                "assets_yoy",
                "netprofit_yoy",
                "op_yoy",
                "ocf_yoy",
                "q_roe",
                "q_dt_roe",
                "q_npta",
                "q_ocf_to_sales",
                "basic_eps",
                "eps",
                "dt_eps",
                "ocfps",
                "cfps",
                "update_flag",
            ]
        ),
    },
    "income": {
        "api": "income_vip",
        "fields": ",".join(
            [
                "ts_code",
                "ann_date",
                "f_ann_date",
                "end_date",
                "report_type",
                "comp_type",
                "end_type",
                "total_revenue",
                "revenue",
                "operate_profit",
                "n_income",
                "n_income_attr_p",
                "update_flag",
            ]
        ),
    },
    "balancesheet": {
        "api": "balancesheet_vip",
        "fields": ",".join(
            [
                "ts_code",
                "ann_date",
                "f_ann_date",
                "end_date",
                "report_type",
                "comp_type",
                "end_type",
                "total_assets",
                "total_liab",
                "total_hldr_eqy_exc_min_int",
                "total_hldr_eqy_inc_min_int",
                "total_share",
                "update_flag",
            ]
        ),
    },
    "cashflow": {
        "api": "cashflow_vip",
        "fields": ",".join(
            [
                "ts_code",
                "ann_date",
                "f_ann_date",
                "end_date",
                "report_type",
                "comp_type",
                "end_type",
                "net_profit",
                "n_cashflow_act",
                "free_cashflow",
                "update_flag",
            ]
        ),
    },
}

_thread_state = threading.local()


def day_text(value: str | pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def tushare_client(token: str) -> Any:
    client = getattr(_thread_state, "client", None)
    if client is None:
        import tushare as ts

        client = ts.pro_api(token)
        _thread_state.client = client
    return client


def batch_path(endpoint: str, batch_number: int) -> Path:
    return FINANCIAL_ROOT / endpoint / f"batch_{batch_number:04d}.parquet"


def fetch_batch(
    endpoint: str,
    api_name: str,
    fields: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    retries: int,
) -> pd.DataFrame:
    last_error = ""
    for attempt in range(retries):
        try:
            data = getattr(tushare_client(os.environ["TUSHARE_TOKEN"]), api_name)(
                ts_code=",".join(codes),
                start_date=start_date,
                end_date=end_date,
                fields=fields,
                limit=5000,
            )
            if data is None:
                raise RuntimeError(f"empty {endpoint} response")
            result = data.copy()
            if not result.empty and "ts_code" in result:
                result["ts_code"] = result["ts_code"].astype(str)
            return result
        except Exception as exc:  # Tushare transient failures are common.
            last_error = " ".join(str(exc).split())[:400]
            if attempt + 1 < retries:
                time.sleep(min(30.0, 1.5 * (2**attempt)) + random.random() * 0.5)
    raise RuntimeError(f"{endpoint} batch failed: {last_error}")


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.parquet")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def download_endpoint(
    endpoint: str,
    codes_batches: list[list[str]],
    start_date: str,
    end_date: str,
    workers: int,
    retries: int,
    refresh: bool,
) -> dict[str, int]:
    spec = ENDPOINTS[endpoint]
    endpoint_root = FINANCIAL_ROOT / endpoint
    endpoint_root.mkdir(parents=True, exist_ok=True)
    pending = [
        (number, codes)
        for number, codes in enumerate(codes_batches, start=1)
        if refresh or not batch_path(endpoint, number).exists()
    ]
    reused = len(codes_batches) - len(pending)
    downloaded = 0
    rows = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                fetch_batch,
                endpoint,
                spec["api"],
                spec["fields"],
                codes,
                start_date,
                end_date,
                retries,
            ): (number, codes)
            for number, codes in pending
        }
        for future in as_completed(futures):
            number, codes = futures[future]
            frame = future.result()
            write_parquet(batch_path(endpoint, number), frame)
            downloaded += 1
            rows += len(frame)
            print(
                f"{endpoint}: downloaded {downloaded}/{len(pending)} batch={number} "
                f"codes={len(codes)} rows={len(frame)}",
                flush=True,
            )
    return {
        "batches": len(codes_batches),
        "reused": reused,
        "downloaded": downloaded,
        "rows_downloaded": rows,
    }


def load_pool() -> list[str]:
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from stfilter_local_recheck import load_pool as load_local_pool

    return sorted(str(value) for value in load_local_pool())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="20180101")
    parser.add_argument("--end-date", default="20260907")
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise SystemExit("TUSHARE_TOKEN is required; keep it in the local environment only")
    if args.batch_size < 1 or args.batch_size > 100:
        raise SystemExit("--batch-size must be between 1 and 100")

    codes = load_pool()
    batches = [codes[offset : offset + args.batch_size] for offset in range(0, len(codes), args.batch_size)]
    print(f"pool={len(codes)} batches={len(batches)} batch_size={args.batch_size}", flush=True)
    summary: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "start_date": day_text(args.start_date),
        "end_date": day_text(args.end_date),
        "pool_count": len(codes),
        "batch_size": args.batch_size,
        "endpoints": {},
    }
    for endpoint in ENDPOINTS:
        summary["endpoints"][endpoint] = download_endpoint(
            endpoint,
            batches,
            day_text(args.start_date),
            day_text(args.end_date),
            args.workers,
            args.retries,
            args.refresh,
        )
    manifest = FINANCIAL_ROOT / "manifest.json"
    manifest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest={manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
