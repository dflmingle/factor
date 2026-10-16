#!/usr/bin/env python3
"""Local pool test: use shallow-tree signals only as vetoes inside incumbents.

This is a fixed, zero-platform-cost experiment.  The incumbent five-seat pool
is the baseline; each candidate changes exactly one seat by removing the
bottom 20% of a precomputed tree signal and otherwise keeps that seat's score
ordering.  No fitting, threshold search, or platform call happens here.
"""
from __future__ import annotations

import importlib.util
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012/run.py"
spec = importlib.util.spec_from_file_location("nonlinear_run", SRC_PATH)
src = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(src)

OUT = ROOT / "research_reports/platform_alignment/tree-incumbent-veto-20261012"
OUT.mkdir(parents=True, exist_ok=True)
MARKET = ROOT / "research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl"
TREE = ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012"
SEATS = ["size_only", "impact60", "t10_size_plus_impact_bm",
         "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]


def load_market():
    with MARKET.open("rb") as f:
        calendar, stocks, fields = pickle.load(f)
    return pd.DatetimeIndex(calendar), pd.Index(stocks), fields


def labels_for(calendar, fields, signal_dates):
    anchor = calendar.get_loc(signal_dates[0])
    positions = np.arange(anchor % 10, len(calendar) - 11, 10)
    positions = positions[calendar[positions] >= pd.Timestamp("2019-01-01")]
    dates = calendar[positions]
    assert dates[dates >= pd.Timestamp("2021-09-07")][: len(signal_dates)].equals(signal_dates)
    positions = positions[dates >= pd.Timestamp("2021-09-07")]
    dates = calendar[positions]
    dates = dates[: len(signal_dates)]
    positions = positions[: len(signal_dates)]
    close = np.asarray(fields["close"], dtype=np.float32)
    cap = np.asarray(fields["cap"], dtype=np.float32)[positions]
    y = close[positions + 11] / close[positions + 1] - 1.0
    y[~np.isfinite(cap) | ~np.isfinite(y)] = np.nan
    return positions, dates, cap, y


def gate_seat(seat: np.ndarray, tree: np.ndarray, veto_fraction: float = 0.20) -> np.ndarray:
    """Keep incumbent score order, push tree-vetoed names below the universe."""
    out = seat.copy().astype(np.float32)
    for i in range(len(out)):
        ok = np.isfinite(out[i]) & np.isfinite(tree[i])
        if ok.sum() < 100:
            continue
        threshold = float(np.nanquantile(tree[i, ok], veto_fraction))
        veto = ok & (tree[i] < threshold)
        out[i, veto] = -10.0
    return out


def evaluate_pool(name, signal, y, cap, dates, calendar, close, baseline=None):
    stats, periods, groups = src.metrics(signal, y, cap, dates)
    daily, monthly, turns = src.daily_path(signal, y, cap, dates, calendar, close)
    stats.update(src.nav_metrics(daily))
    neutral, _, _ = src.metrics(src.size_neutral(signal, cap), y, cap, dates)
    stats["size_neutral_net"] = neutral["net_excess"]
    stats["candidate"] = name
    if baseline is not None:
        bstats, bmonthly = baseline
        paired = bmonthly.merge(monthly, on="month", suffixes=("_base", "_new"))
        paired = paired[~paired.partial_base & ~paired.partial_new].copy()
        paired["candidate"] = name
        paired["delta_E"] = paired.rex_new - paired.rex_base
        paired["delta_T"] = paired.turnover_new - paired.turnover_base
        paired["delta_NC"] = paired.nc_new - paired.nc_base
        # B is unavailable in a local archived-pool ledger; this is explicitly
        # an A+C diagnostic and is never presented as official DeltaComb.
        paired["delta_Comb_AC_proxy"] = 0.45 * paired.delta_NC
        stats.update({
            "delta_net": stats["net_excess"] - bstats["net_excess"],
            "delta_turnover": stats["turnover"] - bstats["turnover"],
            "delta_dd": stats["daily_net_nav_max_dd"] - bstats["daily_net_nav_max_dd"],
            "delta_abs_size_rho": abs(stats["corr_size"]) - abs(bstats["corr_size"]),
            "delta_size_neutral_net": stats["size_neutral_net"] - bstats["size_neutral_net"],
            "mean_delta_E": float(paired.delta_E.mean()),
            "mean_delta_T": float(paired.delta_T.mean()),
            "mean_delta_NC": float(paired.delta_NC.mean()),
            "mean_delta_Comb_AC_proxy": float(paired.delta_Comb_AC_proxy.mean()),
        })
        return stats, periods, monthly, turns, paired
    return stats, periods, monthly, turns, None


def main():
    calendar, stocks, fields = load_market()
    signal_dates = pd.DatetimeIndex(pd.read_csv(TREE / "NL02_formal_5y_periods.csv")["date"])
    positions, dates, cap, y = labels_for(calendar, fields, signal_dates)
    assert dates.equals(signal_dates)
    close = np.asarray(fields["close"], dtype=np.float32)
    baseline_panels = src.baseline_panels(dates, stocks)
    common = np.logical_and.reduce([np.isfinite(v) for v in baseline_panels.values()]) & np.isfinite(cap)
    base = sum(baseline_panels.values()) / len(SEATS)
    base[~common] = np.nan
    tree01 = np.load(TREE / "NL01_signal.npy")
    tree02 = np.load(TREE / "NL02_signal.npy")
    assert tree01.shape == base.shape == tree02.shape

    specs = {
        "V01_SWAP_VERIFY_F_NL02": ("book_to_market_lf_plus_impact", tree02),
        "V02_SWAP_VERIFY_E_NL01": ("book_to_market_lf_minus_size", tree01),
        "V03_SWAP_H03_NL02": ("impact60", tree02),
    }
    protocol = {
        "experiment": "shallow-tree veto inside incumbent seat",
        "candidates": list(specs),
        "threshold": "bottom 20% of tree score per signal date",
        "changed_seat": {k: v[0] for k, v in specs.items()},
        "incumbent_seats": SEATS,
        "formal_window": ["2021-09-07", "2026-09-07"],
        "recent_window": ["2026-01-01", "latest local"],
        "cycle": 10,
        "label": "close(t+1)->close(t+11)",
        "universe": "full SH/SZ A, qfq, total_mv",
        "one_way_cost": 0.003,
        "platform_runs": 0,
        "parameter_search": False,
        "official_pool_delta_comb": False,
        "historical_data_previously_viewed": True,
    }
    (OUT / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")

    all_rows = []
    monthly_rows = []
    for window, mask in (("formal_5y", np.ones(len(dates), dtype=bool)),
                         ("recent_2026", dates >= pd.Timestamp("2026-01-01"))):
        bstats, bperiods, bmonthly, bturns, _ = evaluate_pool(
            "BASE", base[mask], y[mask], cap[mask], dates[mask], calendar, close)
        bperiods.to_csv(OUT / f"BASE_{window}_periods.csv", index=False)
        bmonthly.to_csv(OUT / f"BASE_{window}_monthly.csv", index=False)
        bturns.to_csv(OUT / f"BASE_{window}_turnover.csv", index=False)
        all_rows.append({"window": window, **bstats})
        base_seat_si = {
            seat: src.metrics(baseline_panels[seat][mask], y[mask], cap[mask], dates[mask])[0]["s_i"]
            for seat in SEATS
        }
        for name, (seat, tree) in specs.items():
            changed = gate_seat(baseline_panels[seat], tree)
            candidate = base.copy()
            candidate = candidate - baseline_panels[seat] / len(SEATS) + changed / len(SEATS)
            candidate[~common] = np.nan
            stats, periods, monthly, turns, paired = evaluate_pool(
                name, candidate[mask], y[mask], cap[mask], dates[mask], calendar, close,
                baseline=(bstats, bmonthly))
            periods.to_csv(OUT / f"{name}_{window}_periods.csv", index=False)
            monthly.to_csv(OUT / f"{name}_{window}_monthly.csv", index=False)
            turns.to_csv(OUT / f"{name}_{window}_turnover.csv", index=False)
            paired.to_csv(OUT / f"{name}_{window}_monthly_delta.csv", index=False)
            stats["changed_seat"] = seat
            stats["veto_fraction"] = 0.20
            stats["base_s_i_changed_seat"] = base_seat_si[seat]
            stats["new_s_i_changed_seat"] = src.metrics(changed[mask], y[mask], cap[mask], dates[mask])[0]["s_i"]
            # Local A proxy: replace one seat in the equal-weight five-seat
            # average.  This mirrors the existing archived-pool diagnostic;
            # it is not the official platform A/B/C ledger.
            new_si = stats["new_s_i_changed_seat"]
            old_si = stats["base_s_i_changed_seat"]
            delta_na = min((np.mean([v for k, v in base_seat_si.items() if k != seat] + [new_si])) / .08, .70) \
                - min(np.mean(list(base_seat_si.values())) / .08, .70)
            stats["delta_NA_proxy"] = float(delta_na)
            stats["mean_delta_Comb_AC_proxy_with_A"] = float(.20 * delta_na + .45 * stats["mean_delta_NC"])
            stats["size_guard"] = (abs(stats["corr_size"]) <= abs(bstats["corr_size"]) + 1e-9
                                    and stats["size_neutral_net"] >= bstats["size_neutral_net"] - 1e-9)
            all_rows.append({"window": window, **stats})
            monthly_rows.append(paired.assign(window=window))

    result = pd.DataFrame(all_rows)
    result.to_csv(OUT / "pool_results.csv", index=False)
    pd.concat(monthly_rows, ignore_index=True).to_csv(OUT / "pool_monthly_deltas.csv", index=False)
    (OUT / "verification.json").write_text(json.dumps({
        "tree_signals_reused": True,
        "future_labels_used_in_construction": False,
        "candidate_count": 3,
        "thresholds_searched": False,
        "platform_runs": 0,
        "formal_periods": int(np.ones(len(dates), dtype=bool).sum()),
        "recent_periods": int((dates >= pd.Timestamp("2026-01-01")).sum()),
    }, ensure_ascii=False, indent=2) + "\n")
    print(result[["candidate", "window", "changed_seat", "net_excess", "turnover", "daily_net_nav_max_dd",
                  "corr_size", "size_neutral_net", "delta_net", "delta_turnover", "delta_size_neutral_net",
                  "size_guard", "mean_delta_NC", "mean_delta_Comb_AC_proxy"]].to_string(index=False))


if __name__ == "__main__":
    main()
