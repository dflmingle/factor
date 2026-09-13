#!/usr/bin/env python3
"""Diagnose platform/local semantics using the archived size-only factor run.

The platform run is read-only: this script never creates or runs a PandaAI
factor.  Tushare daily_basic snapshots are cached locally so the comparison can
be repeated without querying the data source again.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tushare_factor_recheck import (  # noqa: E402
    GROUPS,
    REBALANCE_DAYS,
    RECHECK_ROOT,
    load_daily_batches,
)


DEFAULT_PLATFORM_RESULT = RECHECK_ROOT / "platform_size_only_result.json"
DEFAULT_PRICE_ROOT = RECHECK_ROOT / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = RECHECK_ROOT / "daily_basic"
DEFAULT_OUTPUT = RECHECK_ROOT / "reports" / "platform_alignment"
DEFAULT_START = pd.Timestamp("2021-09-07")
DEFAULT_END = pd.Timestamp("2026-09-07")
_thread_state = threading.local()


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(value, format="%Y%m%d" if len(value) == 8 else None)).normalize()


def platform_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if "results" in payload:
        return payload["results"]
    return payload


def chart_series(chart: dict[str, Any]) -> tuple[list[str], list[list[float]]]:
    dates = chart["x"][0]["data"]
    values = [series["data"] for series in chart["y"]]
    return dates, values


def read_platform_run(path: Path) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    payload = platform_payload(path)
    fa = payload["factor_analysis"]
    date_values, return_values = chart_series(fa["query_return_chart"])
    _, excess_values = chart_series(fa["query_factor_excess_chart"])
    _, rank_ic_values = chart_series(fa["query_rank_ic_sequence_chart"])
    dates = pd.to_datetime(date_values).normalize()

    period = pd.DataFrame({"date": dates, "platform_rank_ic": rank_ic_values[0]})
    for group in range(1, GROUPS + 1):
        period[f"platform_group_{group}"] = return_values[group - 1]
        period[f"platform_excess_{group}"] = excess_values[group - 1]

    metrics = {
        str(row["indicator"]): row.get("factor1")
        for row in fa["query_factor_analysis_data"]
    }
    top = fa.get("query_last_date_top_factor", [])
    return period, metrics, top


def tushare_client(token: str) -> Any:
    client = getattr(_thread_state, "client", None)
    if client is None:
        import tushare as ts

        client = ts.pro_api(token)
        _thread_state.client = client
    return client


def cap_path(date: pd.Timestamp, cap_root: Path) -> Path:
    return cap_root / f"daily_basic_{day_text(date)}.parquet"


def fetch_cap(date: pd.Timestamp, token: str, retries: int = 5) -> pd.DataFrame:
    last_error = ""
    for attempt in range(retries):
        try:
            raw = tushare_client(token).daily_basic(
                trade_date=day_text(date),
                fields="ts_code,trade_date,total_mv,circ_mv,close",
            )
            if raw is None or raw.empty:
                raise RuntimeError(f"empty daily_basic response for {day_text(date)}")
            result = raw.rename(columns={"ts_code": "instrument"}).copy()
            result["date"] = pd.Timestamp(date)
            for column in ["total_mv", "circ_mv", "close"]:
                result[column] = pd.to_numeric(result[column], errors="coerce")
            result["instrument"] = result["instrument"].astype(str)
            return result[["date", "instrument", "total_mv", "circ_mv", "close"]]
        except Exception as exc:  # Tushare transient failures are common.
            last_error = " ".join(str(exc).split())[:400]
            if attempt + 1 < retries:
                time.sleep(min(30.0, 1.5 * (2**attempt)) + random.random() * 0.5)
    raise RuntimeError(f"daily_basic failed for {day_text(date)}: {last_error}")


def download_caps(dates: list[pd.Timestamp], token: str, cap_root: Path, workers: int) -> dict[str, int]:
    cap_root.mkdir(parents=True, exist_ok=True)
    missing = [date for date in dates if not cap_path(date, cap_root).exists()]
    downloaded = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch_cap, date, token): date for date in missing}
        for number, future in enumerate(as_completed(futures), start=1):
            date = futures[future]
            frame = future.result()
            temporary = cap_path(date, cap_root).with_suffix(".parquet.tmp")
            frame.to_parquet(temporary, index=False)
            temporary.replace(cap_path(date, cap_root))
            downloaded += 1
            print(f"downloaded {number}/{len(missing)} {day_text(date)} rows={len(frame)}", flush=True)
    return {"requested": len(dates), "reused": len(dates) - len(missing), "downloaded": downloaded}


def load_caps(dates: list[pd.Timestamp], cap_root: Path) -> pd.DataFrame:
    frames = []
    for date in dates:
        path = cap_path(date, cap_root)
        if not path.exists():
            raise FileNotFoundError(f"Missing market-cap snapshot: {path}")
        frames.append(pd.read_parquet(path))
    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    for column in ["total_mv", "circ_mv", "close"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.drop_duplicates(["date", "instrument"], keep="last")


def assign_groups(values: pd.Series) -> pd.Series:
    return np.ceil(values.rank(method="first") * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def evaluate_local(
    prices: pd.DataFrame,
    caps: pd.DataFrame,
    dates: list[pd.Timestamp],
    cap_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    price = prices.copy().sort_values(["instrument", "date"])
    price["future_close"] = price.groupby("instrument", sort=False, observed=True)["close"].shift(-REBALANCE_DAYS)
    price["forward_return"] = price["future_close"].div(price["close"]).sub(1.0)
    signal = price[price["date"].isin(dates)].merge(
        caps[["date", "instrument", cap_column]], on=["date", "instrument"], how="left"
    )
    signal = signal.replace([np.inf, -np.inf], np.nan)
    evaluation = signal.dropna(subset=[cap_column, "forward_return"])

    periods: list[dict[str, Any]] = []
    previous_members: dict[int, set[str]] = {}
    for date in dates:
        current = evaluation[evaluation["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = assign_groups(current[cap_column])
        benchmark = float(current["forward_return"].mean())
        rank_ic = current[cap_column].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        row: dict[str, Any] = {
            "date": date,
            "stock_count": int(len(current)),
            "benchmark": benchmark,
            "rank_ic": float(rank_ic) if pd.notna(rank_ic) else np.nan,
        }
        for group in range(1, GROUPS + 1):
            members = set(current.loc[current["group"].eq(group), "instrument"])
            row[f"group_{group}"] = float(current.loc[current["group"].eq(group), "forward_return"].mean())
            row[f"excess_{group}"] = row[f"group_{group}"] - benchmark
            previous = previous_members.get(group)
            row[f"turnover_{group}"] = (
                float(1.0 - len(members.intersection(previous)) / len(members)) if previous else np.nan
            )
            previous_members[group] = members
        periods.append(row)
    return pd.DataFrame(periods), signal


def compare_series(local: pd.Series, platform: pd.Series) -> dict[str, float | None]:
    joined = pd.concat([local.rename("local"), platform.rename("platform")], axis=1).dropna()
    if joined.empty:
        return {"n": 0, "corr": None, "mean_delta": None, "rmse": None}
    delta = joined["local"] - joined["platform"]
    return {
        "n": int(len(joined)),
        "corr": float(joined["local"].corr(joined["platform"])) if len(joined) > 1 else None,
        "mean_delta": float(delta.mean()),
        "rmse": float(np.sqrt(np.mean(delta**2))),
    }


def add_cumulative_series(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("date").copy()
    benchmark_growth = (1.0 + result["benchmark"]).cumprod() - 1.0
    for group in range(1, GROUPS + 1):
        cumulative_return = (1.0 + result[f"group_{group}"]).cumprod() - 1.0
        result[f"cumulative_group_{group}"] = cumulative_return
        result[f"cumulative_excess_{group}"] = cumulative_return - benchmark_growth
    return result


def top_overlap(top: list[dict[str, Any]], signal: pd.DataFrame, date: pd.Timestamp) -> dict[str, Any]:
    platform_symbols = [
        str(row["symbol"])
        for row in top
        if row.get("date") and pd.Timestamp(row["date"]).normalize() == date
    ]
    latest = signal[signal["date"].eq(date)].sort_values("total_mv", ascending=False)
    local_symbols = latest["instrument"].head(len(platform_symbols)).astype(str).tolist()
    platform_set = set(platform_symbols)
    local_set = set(local_symbols)
    return {
        "date": day_text(date),
        "platform_top_n": len(platform_symbols),
        "local_top_n": len(local_symbols),
        "overlap": len(platform_set & local_set),
        "overlap_pct": len(platform_set & local_set) / len(platform_set) if platform_set else None,
        "platform_symbols": platform_symbols,
        "local_symbols": local_symbols,
        "platform_only": sorted(platform_set - local_set),
        "local_only": sorted(local_set - platform_set),
    }


def run_diagnosis(
    platform_path: Path,
    price_root: Path,
    cap_root: Path,
    output_root: Path,
    market: str = "all",
) -> dict[str, Any]:
    platform_period, platform_metrics, platform_top = read_platform_run(platform_path)
    dates = [pd.Timestamp(value).normalize() for value in platform_period["date"]]
    top_dates = [pd.Timestamp(row["date"]).normalize() for row in platform_top if row.get("date")]
    top_date = max(top_dates) if top_dates else dates[-1]
    cap_dates = sorted(set(dates + [top_date]))
    prices = load_daily_batches(DEFAULT_START, DEFAULT_END, price_root, market=market)
    caps = load_caps(cap_dates, cap_root)

    signal_dates = sorted(set(dates + [top_date]))
    local_total, signal = evaluate_local(prices, caps, signal_dates, "total_mv")
    local_circ, _ = evaluate_local(prices, caps, signal_dates, "circ_mv")
    total = add_cumulative_series(local_total).merge(platform_period, on="date", how="inner")
    circ = add_cumulative_series(local_circ).merge(platform_period, on="date", how="inner")

    comparisons: dict[str, Any] = {}
    for label, frame in [("total_mv", total), ("circ_mv", circ)]:
        comparisons[label] = {
            "rank_ic": compare_series(frame["rank_ic"], frame["platform_rank_ic"]),
            "group_1_return": compare_series(frame["cumulative_group_1"], frame["platform_group_1"]),
            "group_1_excess": compare_series(frame["cumulative_excess_1"], frame["platform_excess_1"]),
            "group_10_return": compare_series(frame["cumulative_group_10"], frame["platform_group_10"]),
            "stock_count": {
                "local_mean": float(frame["stock_count"].mean()),
                "local_min": int(frame["stock_count"].min()),
                "local_max": int(frame["stock_count"].max()),
            },
            "turnover_group_1_mean": float(frame["turnover_1"].mean()),
        }

    overlap = top_overlap(platform_top, signal, top_date)
    platform_top_values = [
        {"symbol": str(row.get("symbol")), "factor": row.get("factor1")}
        for row in platform_top
        if row.get("date") and pd.Timestamp(row["date"]).normalize() == top_date
    ]

    output_root.mkdir(parents=True, exist_ok=True)
    local_total.to_csv(output_root / "local_total_mv_periods.csv", index=False, encoding="utf-8-sig")
    local_circ.to_csv(output_root / "local_circ_mv_periods.csv", index=False, encoding="utf-8-sig")
    total.to_csv(output_root / "aligned_total_mv_periods.csv", index=False, encoding="utf-8-sig")
    signal[signal["date"].eq(top_date)].sort_values("total_mv", ascending=False).head(20).to_csv(
        output_root / "local_latest_top20_total_mv.csv", index=False, encoding="utf-8-sig"
    )

    result = {
        "settings": {
            "platform_result": str(platform_path),
            "price_root": str(price_root),
            "cap_root": str(cap_root),
            "platform_periods": len(dates),
            "price_mode": (
                "raw"
                if price_root.resolve() == (RECHECK_ROOT / "daily_batches").resolve()
                else "qfq"
            ),
            "rebalance_days": REBALANCE_DAYS,
            "groups": GROUPS,
            "market": market,
        },
        "platform_metrics": platform_metrics,
        "comparisons": comparisons,
        "latest_top20_overlap": overlap,
        "platform_latest_top20": platform_top_values,
    }
    (output_root / "diagnosis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    write_report(result, output_root / "diagnosis.md")
    return result


def write_report(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Platform/local alignment diagnosis",
        "",
        "This report reads the archived `RANK(MARKET_CAP)` run and compares it with Tushare `daily_basic`; it does not run a new PandaAI factor.",
        "",
        "## Platform reference",
        "",
        f"- periods: {result['settings']['platform_periods']}",
        f"- local price mode: {result['settings']['price_mode']}",
        f"- local market filter: {result['settings']['market']}",
        f"- Rank IC: {result['platform_metrics'].get('Rank_IC')}",
        f"- IC mean: {result['platform_metrics'].get('IC_mean')}",
        f"- IC IR: {result['platform_metrics'].get('IC_IR')}",
        "",
        "## Period alignment",
        "",
        "The platform return/excess charts are cumulative curves; local group returns are compounded before comparison.",
        "",
        "| local cap field | Rank IC corr | cumulative group 1 corr | cumulative group 1 excess corr | cumulative group 10 corr | local group 1 turnover | local stock count |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for field, comparison in result["comparisons"].items():
        def value(key: str) -> str:
            item = comparison[key]
            number = item.get("corr") if key != "stock_count" else item.get("local_mean")
            return "n/a" if number is None else f"{number:.4f}"

        lines.append(
            f"| {field} | {value('rank_ic')} | {value('group_1_return')} | {value('group_1_excess')} | {value('group_10_return')} | {comparison['turnover_group_1_mean']:.2%} | {comparison['stock_count']['local_mean']:.0f} |"
        )
    overlap = result["latest_top20_overlap"]
    lines.extend(
        [
            "",
            "## Latest top-20 check",
            "",
            f"- date: {overlap['date']}",
            f"- overlap: {overlap['overlap']}/{overlap['platform_top_n']} ({overlap['overlap_pct']:.1%})",
            f"- platform only: {', '.join(overlap['platform_only'])}",
            f"- local only: {', '.join(overlap['local_only'])}",
            "",
            "Platform top-20 symbols:",
            ", ".join(row["symbol"] for row in result["platform_latest_top20"]),
            "",
            "The key diagnostic is whether Rank IC stays aligned while group returns do not. If so, the remaining mismatch is in the return label, price adjustment, missing-row handling, or portfolio construction rather than the market-cap ranking itself.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["download", "analyze", "all"], default="all")
    parser.add_argument("--platform-result", default=str(DEFAULT_PLATFORM_RESULT))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--market", choices=["all", "hs"], default="all")
    args = parser.parse_args()

    platform_path = Path(args.platform_result)
    platform_period, _, platform_top = read_platform_run(platform_path)
    dates = [pd.Timestamp(value).normalize() for value in platform_period["date"]]
    top_dates = [pd.Timestamp(row["date"]).normalize() for row in platform_top if row.get("date")]
    dates = sorted(set(dates + top_dates))
    cap_root = Path(args.cap_root)
    if args.mode in {"download", "all"}:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            raise SystemExit("TUSHARE_TOKEN is required for download/all mode")
        print(json.dumps(download_caps(dates, token, cap_root, args.workers), ensure_ascii=False), flush=True)
    if args.mode in {"analyze", "all"}:
        result = run_diagnosis(
            platform_path, Path(args.price_root), cap_root, Path(args.output), market=args.market
        )
        print(f"report={Path(args.output) / 'diagnosis.md'}")
        for field, comparison in result["comparisons"].items():
            print(
                f"{field}: rank_ic_corr={comparison['rank_ic']['corr']:.4f} "
                f"group1_return_corr={comparison['group_1_return']['corr']:.4f} "
                f"group1_excess_corr={comparison['group_1_excess']['corr']:.4f}",
                flush=True,
            )
        overlap = result["latest_top20_overlap"]
        print(f"latest_top20_overlap={overlap['overlap']}/{overlap['platform_top_n']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
