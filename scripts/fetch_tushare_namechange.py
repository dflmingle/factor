#!/usr/bin/env python3
"""Fetch Tushare namechange history for a point-in-time ST flag.

The local universe currently knows only each stock's *current* name, so a
stock that was ST during the backtest but has since recovered is not filtered,
and one that became ST later is filtered retrospectively.  The platform drops
ST names from its portfolio universe, which is worth several percentage points
for small-cap-heavy portfolios, so the local pipeline needs the dated history.

Usage:
    TUSHARE_TOKEN=... python3 scripts/fetch_tushare_namechange.py --output <path.parquet>

The token is read from the environment and never written to the repository.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

FIELDS = "ts_code,name,start_date,end_date,ann_date,change_reason"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "quantlab/.quantlab/cache/research/cn_equity/stock_basic/namechange.parquet"
        ),
    )
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=pd.Timestamp.today().year)
    args = parser.parse_args()

    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise SystemExit("TUSHARE_TOKEN is not set")
    import tushare as ts

    pro = ts.pro_api(token)
    frames = []
    for year in range(args.start_year, args.end_year + 1):
        frame = pro.namechange(
            start_date=f"{year}0101", end_date=f"{year}1231", fields=FIELDS
        )
        if frame is not None and not frame.empty:
            frames.append(frame)
            print(f"{year}: {len(frame)} rows", flush=True)
        else:
            print(f"{year}: empty", flush=True)
        time.sleep(0.35)
    if not frames:
        raise SystemExit("no namechange rows returned")

    table = pd.concat(frames, ignore_index=True).drop_duplicates()
    table["start_date"] = pd.to_datetime(table["start_date"], format="%Y%m%d", errors="coerce")
    table["end_date"] = pd.to_datetime(table["end_date"], format="%Y%m%d", errors="coerce")
    table["ann_date"] = pd.to_datetime(table["ann_date"], format="%Y%m%d", errors="coerce")
    table = table.dropna(subset=["start_date"]).sort_values(["ts_code", "start_date"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(args.output, index=False)
    print(f"wrote {len(table)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
