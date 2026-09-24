#!/usr/bin/env python3
"""Fill the missing high/low/amount fields in the local qfq price cache.

The cached qfq batches only carry open/close/volume for the early years, so
factors that need HIGH, LOW or AMOUNT silently fell back to open/close-range
and volume-average-price proxies.  Tushare's raw ``daily`` endpoint provides
low/high/vol/amount; the per-stock adjustment factor is recovered from
``qfq_close / raw_close`` so the new high/low stay on the same qfq basis as the
existing close series.

Usage:
    TUSHARE_TOKEN=... python3 scripts/build_rich_price_cache.py
"""
from __future__ import annotations

import argparse
import glob
import os
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(
    "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
)
RAW_ROOT = Path(
    "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/raw_daily"
)
OUTPUT_ROOT = Path(
    "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq_rich/daily_batches"
)
FIELDS = "ts_code,trade_date,low,high,close,vol,amount"


def local_dates() -> list[str]:
    dates: set[pd.Timestamp] = set()
    for path in sorted(SOURCE_ROOT.glob("batch_*.parquet")):
        frame = pd.read_parquet(path, columns=["date"])
        dates.update(pd.to_datetime(frame["date"]).dt.normalize().unique())
    return [value.strftime("%Y%m%d") for value in sorted(dates)]


def fetch_raw(dates: list[str]) -> None:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise SystemExit("TUSHARE_TOKEN is not set")
    import tushare as ts

    pro = ts.pro_api(token)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    pending = [
        day
        for day in dates
        if not (RAW_ROOT / f"raw_{day}.parquet").exists()
    ]
    print(f"{len(dates)} dates, {len(pending)} to fetch", flush=True)
    for index, day in enumerate(pending, start=1):
        frame = pro.daily(trade_date=day, fields=FIELDS)
        if frame is None or frame.empty:
            print(f"  {day}: empty", flush=True)
            continue
        frame.to_parquet(RAW_ROOT / f"raw_{day}.parquet", index=False)
        if index % 200 == 0:
            print(f"  fetched {index}/{len(pending)}", flush=True)
        time.sleep(0.02)


def build_rich() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(RAW_ROOT.glob("raw_*.parquet"))
    raw = pd.concat([pd.read_parquet(path) for path in raw_files], ignore_index=True)
    raw = raw.rename(
        columns={
            "ts_code": "instrument",
            "trade_date": "date",
            "vol": "raw_volume",
            "amount": "raw_amount",
            "low": "raw_low",
            "high": "raw_high",
            "close": "raw_close",
        }
    )
    raw["date"] = pd.to_datetime(raw["date"], format="%Y%m%d").dt.normalize()
    raw = raw.drop_duplicates(["date", "instrument"], keep="last")
    print(f"raw rows {len(raw)}", flush=True)

    for path in sorted(SOURCE_ROOT.glob("batch_*.parquet")):
        frame = pd.read_parquet(path)
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame["instrument"] = frame["instrument"].astype(str)
        merged = frame.merge(
            raw[["date", "instrument", "raw_low", "raw_high", "raw_close", "raw_amount", "raw_volume"]],
            on=["date", "instrument"],
            how="left",
        )
        ratio = merged["close"] / merged["raw_close"].replace(0.0, pd.NA)
        merged["high_qfq"] = merged["raw_high"] * ratio
        merged["low_qfq"] = merged["raw_low"] * ratio
        merged["amount"] = merged["raw_amount"]
        if "volume" in merged.columns:
            merged["volume"] = merged["volume"].fillna(merged["raw_volume"])
        keep = [
            column
            for column in [
                "date",
                "instrument",
                "open",
                "close",
                "volume",
                "high_qfq",
                "low_qfq",
                "amount",
                # Raw (unadjusted) fields are kept so factors whose platform
                # definition uses unadjusted prices can select them explicitly.
                "raw_low",
                "raw_high",
                "raw_close",
                "raw_amount",
                "raw_volume",
            ]
            if column in merged.columns
        ]
        merged[keep].to_parquet(OUTPUT_ROOT / path.name, index=False)
    print(f"wrote rich cache to {OUTPUT_ROOT}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()
    if not args.skip_fetch:
        fetch_raw(local_dates())
    build_rich()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
