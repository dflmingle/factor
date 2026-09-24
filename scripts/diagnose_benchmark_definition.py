"""Test whether the local benchmark definition explains the systematic gap.

The local pipeline uses the equal-weighted mean forward return of the valid
cross-section as the benchmark.  The platform documents 中证全指 (a cap-weighted
index) as its benchmark for the competition ledger.  A cap-weighted benchmark
would rise less than an equal-weighted one whenever small caps outperform, which
is exactly the direction of the systematic local-understates-platform gap.

This script recomputes a few saved factor records under both benchmark
definitions and prints the resulting annualized excess.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402

SIGNALS = Path("research_reports/platform_alignment/pool-screen-20260921/signals.pkl")
PLATFORM = {"SIZE": 21.43, "H03": 16.44, "RET40": 1.03, "CHIP250": 4.28, "ASSET_GROWTH": 0.76}
GROUPS = 10
CYCLE = 10


def main() -> None:
    sf, raw, returns, dates = pickle.load(SIGNALS.open("rb"))
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, e.DATA_START, e.END)
    frame = e.select_market_cap(frame, "total_mv")
    cap = frame[["date", "instrument", "total_mv"]]
    data = sf.merge(returns, on=["date", "instrument"], how="left").merge(
        cap, on=["date", "instrument"], how="left"
    )

    handlers = {"SIZE": ("size_only", 0), "H03": ("impact60", 1), "RET40": ("reversal40", 1),
                "CHIP250": ("chip250", 1), "ASSET_GROWTH": ("asset_growth", 0)}
    print(f"{'factor':14s} {'platform':>9s} {'EW bench':>9s} {'MV bench':>9s} {'EW-MV diff':>10s}")
    for key, (handler, direction) in handlers.items():
        values = pd.to_numeric(raw[handler], errors="coerce").to_numpy(dtype=float)
        if direction == 0:
            values = -values
        data["score"] = values
        valid = data.dropna(subset=["score", "forward_return"]).copy()
        rows = []
        for date, group in valid.groupby("date", sort=True):
            n = len(group)
            if n < GROUPS * 10:
                continue
            rank = group["score"].rank(ascending=False, method="first")
            top = group[rank <= n / GROUPS]
            group_ret = float(top["forward_return"].mean())
            ew = float(group["forward_return"].mean())
            weights = group["total_mv"].clip(lower=0)
            mv = float(np.average(group["forward_return"], weights=weights)) if weights.sum() > 0 else np.nan
            rows.append((group_ret - ew, group_ret - mv, group_ret, ew, mv))
        table = pd.DataFrame(rows, columns=["ex_ew", "ex_mv", "gross", "bench_ew", "bench_mv"])
        years = len(table) * CYCLE / 252.0
        ex_ew = table["ex_ew"].sum() / years * 100
        ex_mv = table["ex_mv"].sum() / years * 100
        bench_ew = table["bench_ew"].sum() / years * 100
        bench_mv = table["bench_mv"].sum() / years * 100
        print(
            f"{key:14s} {PLATFORM[key]:8.2f}% {ex_ew:8.2f}% {ex_mv:8.2f}% {ex_ew - ex_mv:+9.2f}pp"
            f"   | 本地等权基准 {bench_ew:6.2f}%  市值加权基准 {bench_mv:6.2f}%  平台隐含基准 11.30%"
        )


if __name__ == "__main__":
    main()
