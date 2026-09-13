#!/usr/bin/env python3
"""Download full-A daily turnover and market-cap snapshots.

The cache is one parquet file per trading date so interrupted downloads can
resume without touching the existing sampled daily_basic cache.
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
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
CACHE_ROOT = Path(os.environ.get("FACTOR_RESEARCH_CACHE_ROOT", str(DEFAULT_CACHE_ROOT))).expanduser()
RECHECK_ROOT = CACHE_ROOT / "tushare_factor_recheck"
DEFAULT_OUTPUT_ROOT = RECHECK_ROOT / "daily_basic_full_a"
DEFAULT_START = "20190701"
DEFAULT_END = "20260907"
API_INTERVAL_SECONDS = 0.65

DAILY_COLUMNS = ["date", "instrument", "turnover", "total_mv", "circ_mv", "close"]
_thread_state = threading.local()
_api_rate_lock = threading.Lock()
_next_api_call = 0.0


def day_text(value: str | pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def parse_day(value: str) -> pd.Timestamp:
    text = str(value).strip()
    return pd.Timestamp(pd.to_datetime(text, format="%Y%m%d" if len(text) == 8 else None)).normalize()


def tushare_client(token: str) -> Any:
    client = getattr(_thread_state, "client", None)
    if client is None:
        import tushare as ts

        client = ts.pro_api(token)
        _thread_state.client = client
    return client


def wait_for_api_slot() -> None:
    global _next_api_call
    with _api_rate_lock:
        wait = _next_api_call - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _next_api_call = time.monotonic() + API_INTERVAL_SECONDS


def normalize(raw: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise RuntimeError(f"empty daily_basic response for {day_text(date)}")
    required = {"ts_code", "turnover_rate", "total_mv", "circ_mv", "close"}
    missing = required.difference(raw.columns)
    if missing:
        raise RuntimeError(f"daily_basic response is missing columns: {sorted(missing)}")
    result = raw[["ts_code", "turnover_rate", "total_mv", "circ_mv", "close"]].copy()
    result = result.rename(
        columns={
            "ts_code": "instrument",
            "turnover_rate": "turnover",
        }
    )
    result["instrument"] = result["instrument"].astype(str)
    result = result[result["instrument"].str.endswith((".SH", ".SZ"))]
    result["date"] = pd.Timestamp(date)
    for column in ["turnover", "total_mv", "circ_mv", "close"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.drop_duplicates(["date", "instrument"], keep="last")
    if result.empty:
        raise RuntimeError(f"daily_basic returned no .SH/.SZ rows for {day_text(date)}")
    return result[DAILY_COLUMNS].sort_values("instrument", ignore_index=True)


def fetch_one_day(date: pd.Timestamp, token: str, retries: int) -> pd.DataFrame:
    last_error = ""
    for attempt in range(retries):
        try:
            client = tushare_client(token)
            wait_for_api_slot()
            raw = client.daily_basic(
                trade_date=day_text(date),
                fields="ts_code,trade_date,turnover_rate,total_mv,circ_mv,close",
            )
            return normalize(raw, date)
        except Exception as exc:
            last_error = " ".join(str(exc).replace(token, "<redacted>").split())[:500]
            if attempt + 1 < retries:
                time.sleep(min(30.0, 1.5 * (2**attempt)) + random.random() * 0.5)
    raise RuntimeError(f"daily_basic failed for {day_text(date)}: {last_error}")


def data_path(root: Path, date: pd.Timestamp) -> Path:
    return root / f"daily_basic_{day_text(date)}.parquet"


def meta_path(root: Path, date: pd.Timestamp) -> Path:
    return root / f"daily_basic_{day_text(date)}.json"


def complete(root: Path, date: pd.Timestamp) -> bool:
    path = data_path(root, date)
    meta = meta_path(root, date)
    if not path.exists() or not meta.exists():
        return False
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("status") == "complete" and payload.get("date") == day_text(date)


def atomic_write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def load_trade_dates(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    from tushare_factor_recheck import load_trade_dates as load_cached_trade_dates

    return load_cached_trade_dates(start, end)


def download(
    dates: list[pd.Timestamp],
    token: str,
    root: Path,
    workers: int,
    retries: int,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    pending = [date for date in dates if not complete(root, date)]
    reused = len(dates) - len(pending)
    downloaded = 0
    rows = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(fetch_one_day, date, token, retries): date
            for date in pending
        }
        for future in as_completed(futures):
            date = futures[future]
            frame = future.result()
            path = data_path(root, date)
            atomic_write(frame, path)
            meta_path(root, date).write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "source": "tushare.daily_basic",
                        "date": day_text(date),
                        "rows": int(len(frame)),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            downloaded += 1
            rows += len(frame)
            print(f"downloaded {downloaded}/{len(pending)} {day_text(date)} rows={len(frame)}", flush=True)
    return {
        "requested_dates": len(dates),
        "reused_dates": reused,
        "downloaded_dates": downloaded,
        "rows_downloaded": rows,
        "output_root": str(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise SystemExit("TUSHARE_TOKEN is required; keep it in the local environment only")
    start = parse_day(args.start)
    end = parse_day(args.end)
    if start > end:
        raise SystemExit("Require start <= end")
    dates = load_trade_dates(start, end)
    result = download(dates, token, Path(args.output_root), max(1, args.workers), max(1, args.retries))
    manifest = Path(args.output_root) / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "start": day_text(start),
                "end": day_text(end),
                **result,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
