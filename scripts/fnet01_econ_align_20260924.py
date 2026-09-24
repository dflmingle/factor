"""F-NET01 local reproduction: which convention matches the saved platform numbers?

The platform's saved charts/display keep ST names (its 2026-09-07 top-20 is 14 ST
names, all pinned at one identical value), while the qualitygate3 local panel drops
ST names and recent listings.  qualitygate3 also switched from summed to compounded
annualisation.  This script crosses both switches and compares gross/net/turnover
against the two saved platform runs (cycle 5 and cycle 10).

Output: research_reports/platform_alignment/fnet01-alignment-20260924/econ_alignment.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FACTOR_LOCAL_UNIVERSE_FILTER", "off")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import apply_trading_universe_filter, load_full_a_data  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import annualized_turnover_cost  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    GROUPS,
    assign_groups,
    forward_returns,
    rolling_weighted_mean,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck"
PRICE_ROOT = CACHE / "qfq_rich/daily_batches"
CAP_ROOT = CACHE / "daily_basic_full_a"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
RUNS = {
    "cycle5": PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json",
    "cycle10": PROJECT_ROOT / "cluster-singletons-t10-20260921-candidates.results/6ab0f3d7ecb163ea7228ded7.json",
}


def main() -> int:
    platforms = {name: read_platform_run(path) for name, path in RUNS.items()}
    # load through the last cached bar so every cycle-5/10 forward target exists
    end = max(pd.Timestamp(d).normalize() for p in platforms.values() for d in p["dates"])
    end = max(end, pd.Timestamp("2026-09-07"))
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, pd.Timestamp("2018-01-01"), end,
                             market_cap_field="total_mv")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print("unfiltered rows", len(frame), flush=True)
    filtered = apply_trading_universe_filter(frame)
    keep = pd.Series(False, index=frame.index)
    keep.loc[filtered.index] = True
    print("filter keeps", int(keep.sum()), "of", len(frame), flush=True)

    raw = 1.0 / frame["raw_low"].pow(2) / frame["raw_volume"]
    frame["_factor"] = rolling_weighted_mean(frame, raw, 40).to_numpy(dtype=float)
    print("factor built", flush=True)
    calendar = list(pd.Index(sorted(frame["date"].unique())))
    close = frame.pivot(index="date", columns="instrument", values="close_qfq").reindex(calendar)
    factor_frame = frame[["date", "instrument", "_factor"]].copy()

    report: dict[str, object] = {"universe_rows": {"unfiltered": int(len(frame)), "filtered": int(keep.sum())}}
    for name, platform in platforms.items():
        dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
        cycle = int(platform.get("cycle") or platform.get("configured_cycle") or 5)
        direction = int(platform.get("direction") or 1)
        selected_group = GROUPS if direction == 1 else 1
        returns = forward_returns(close, calendar, dates, cycle, 1)
        data = factor_frame[factor_frame["date"].isin(dates)].merge(returns, on=["date", "instrument"], how="left")
        data = data.replace([np.inf, -np.inf], np.nan)
        data["_keep"] = keep.reindex(data.index) if False else None
        kept = pd.Series(keep.to_numpy()[data.index.to_numpy()], index=data.index)
        entry = {"cycle": cycle, "direction": direction, "n_signal_dates": len(dates),
                 "platform": {"rank_ic": platform["metrics"].get("Rank_IC"),
                              "ic_mean": platform["metrics"].get("IC_mean"),
                              "gross": platform["group_metrics"].get(selected_group, {}).get("excessAnnualized"),
                              "turnover": platform["group_metrics"].get(selected_group, {}).get("turnoverRate")},
                 "universes": {}}
        entry["platform"]["net"] = (
            entry["platform"]["gross"] - annualized_turnover_cost(entry["platform"]["turnover"], cycle)
            if entry["platform"]["gross"] is not None and entry["platform"]["turnover"] is not None else None
        )
        for universe, mask in (("st_filtered", kept), ("unfiltered", pd.Series(True, index=data.index))):
            sub = data[mask].dropna(subset=["_factor", "forward_return"])
            previous: dict[int, set[str]] = {}
            arithmetic, compound, turnovers = [], [], []
            rank_ics = []
            for date in dates:
                current = sub[sub["date"].eq(date)]
                if len(current) < GROUPS * 10:
                    continue
                current = current.copy()
                current["group"] = assign_groups(current["_factor"], None)
                held = current[current["group"].eq(selected_group)]
                benchmark = float(current["forward_return"].mean())
                held_return = float(held["forward_return"].mean())
                arithmetic.append(held_return - benchmark)
                compound.append((held_return + 1.0, benchmark + 1.0))
                members = set(held["instrument"])
                old = previous.get(selected_group)
                if old:
                    turnovers.append(1.0 - len(members & old) / len(members))
                previous[selected_group] = members
                rank_ics.append(float(current["_factor"].rank().corr(current["forward_return"].rank())))
            years = len(arithmetic) * cycle / 252.0
            arith_excess = float(np.sum(arithmetic)) / years
            held_wealth = float(np.prod([h for h, _ in compound]))
            bench_wealth = float(np.prod([b for _, b in compound]))
            compound_excess = held_wealth ** (1 / years) - bench_wealth ** (1 / years)
            turnover = float(np.mean(turnovers)) if turnovers else None
            cost = annualized_turnover_cost(turnover, cycle)
            entry["universes"][universe] = {
                "n_periods": len(arithmetic),
                "stocks_per_date_mean": float(sub.groupby("date").size().mean()),
                "mean_rank_ic": float(np.nanmean(rank_ics)),
                "gross_arithmetic": arith_excess,
                "gross_compounded": compound_excess,
                "net_arithmetic": arith_excess - cost if cost else None,
                "net_compounded": compound_excess - cost if cost else None,
                "turnover": turnover,
                "annual_cost": cost,
            }
            u = entry["universes"][universe]
            print("%-7s %-12s n=%3d stocks=%6.0f rankIC=%.4f grossA=%.4f grossC=%.4f turn=%.4f netA=%.4f netC=%.4f" % (
                name, universe, u["n_periods"], u["stocks_per_date_mean"], u["mean_rank_ic"],
                u["gross_arithmetic"], u["gross_compounded"], u["turnover"] or float("nan"),
                u["net_arithmetic"], u["net_compounded"]), flush=True)
        report[name] = json.loads(json.dumps(entry, default=float))
        print("   platform: gross=%s turnover=%s net=%s rankIC=%s" % (
            entry["platform"]["gross"], entry["platform"]["turnover"], entry["platform"]["net"], entry["platform"]["rank_ic"]), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "econ_alignment.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "econ_alignment.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
