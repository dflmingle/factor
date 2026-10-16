"""Audit existing results and validate proposed signal code without backtesting."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / "research_reports/platform_alignment/tree-incumbent-veto-20261012"
TREE = ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results = pd.read_csv(OLD / "pool_results.csv")
    selected = results[results.candidate.ne("BASE")].copy()
    selected["delta_C_weighted"] = .45 * selected.mean_delta_NC
    selected["delta_A_weighted_proxy"] = .20 * selected.delta_NA_proxy
    selected["delta_AC_corrected_proxy"] = selected.delta_A_weighted_proxy + selected.delta_C_weighted
    np.testing.assert_allclose(selected.delta_AC_corrected_proxy,
                               selected.mean_delta_Comb_AC_proxy_with_A)
    np.testing.assert_allclose(selected.delta_C_weighted, selected.mean_delta_Comb_AC_proxy)
    selected["full_official_delta_comb"] = np.nan
    selected["baseline_implementation_fidelity"] = "unstandardized changed-seat penalty; archived-universe diagnostic"
    selected.to_csv(HERE / "saved_result_score_audit.csv", index=False)
    # Resample already-saved paired periods; no new strategy is backtested.
    uncertainty = []
    bootstrap_rng = np.random.default_rng(20261012)
    for row in selected.itertuples():
        base = pd.read_csv(OLD / f"BASE_{row.window}_periods.csv")
        new = pd.read_csv(OLD / f"{row.candidate}_{row.window}_periods.csv")
        pairs = base.merge(new, on="date", suffixes=("_base", "_new"), validate="one_to_one")
        assert len(pairs) == len(base) == len(new)
        gross = (pairs.gross_excess_new - pairs.gross_excess_base).to_numpy()
        turnover = (pairs.turnover_new - pairs.turnover_base)
        adjustment = len(pairs) / turnover.notna().sum()
        diff = gross - .006 * turnover.fillna(0).to_numpy() * adjustment
        point = float(diff.mean() * 25.2)
        np.testing.assert_allclose(point, row.delta_net, rtol=1e-9, atol=1e-10)
        n = len(diff)
        block = 6 if row.window == "formal_5y" else 3
        starts = bootstrap_rng.integers(0, n, size=(5000, int(np.ceil(n / block))))
        ix = ((starts[:, :, None] + np.arange(block)) % n).reshape(5000, -1)[:, :n]
        draws = diff[ix].mean(axis=1) * 25.2
        lo, hi = np.quantile(draws, [.025, .975])
        uncertainty.append({"candidate": row.candidate, "window": row.window,
                            "periods": n, "block_periods": block,
                            "delta_net": point, "bootstrap_95_low": lo,
                            "bootstrap_95_high": hi,
                            "note": "descriptive paired circular block bootstrap; viewed data and selected strategies, no selection correction"})
    pd.DataFrame(uncertainty).to_csv(HERE / "saved_result_uncertainty.csv", index=False)

    spec = importlib.util.spec_from_file_location("prepared_candidates", HERE / "candidates.py")
    code = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(code)
    rng = np.random.default_rng(20261012)
    f = rng.normal(size=(120, 512))
    tree = rng.normal(size=f.shape)
    f[:4, :8] = np.nan
    tree[8:12, 10:15] = np.nan
    full = code.corrections(f, tree)
    prefix_checks = []
    for cutoff in (24, 72, 100):
        prefix = code.corrections(f[:cutoff], tree[:cutoff])
        changed_f, changed_tree = f.copy(), tree.copy()
        changed_f[cutoff:] = 123456.
        changed_tree[cutoff:] = -98765.
        altered = code.corrections(changed_f, changed_tree)
        for name in full:
            np.testing.assert_array_equal(full[name][:cutoff], prefix[name])
            np.testing.assert_array_equal(full[name][:cutoff], altered[name][:cutoff])
            np.testing.assert_allclose(np.nanmean(full[name], axis=1), 0., atol=1e-12)
            np.testing.assert_allclose(np.nanstd(full[name], axis=1), 1., atol=1e-12)
            np.testing.assert_array_equal(np.isfinite(full[name]), np.isfinite(f))
        prefix_checks.append(cutoff)

    # Signal-state sanity: enter below .15, retain in [.15,.25], exit above .25.
    # No outcome labels or candidate returns are read or generated here.
    qcheck = np.array([.10, .20, .30, .20, .10, .20, .20])[:, None]
    validcheck = np.ones(qcheck.shape, bool)
    validcheck[5] = False
    np.testing.assert_array_equal(code.hysteresis(qcheck, validcheck).ravel(),
                                  [True, True, False, False, True, False, False])
    dates = pd.DatetimeIndex(pd.read_csv(TREE / "NL02_formal_5y_periods.csv").date)
    axes = json.loads((TREE / "axes.json").read_text())
    folds = json.loads((TREE / "folds.json").read_text())
    assert all(pd.Timestamp(x["latest_training_label_exit"]) < pd.Timestamp(x["test_first"]) for x in folds)
    for file in ("NL01_signal.npy", "NL02_signal.npy"):
        signal = np.load(TREE / file, mmap_mode="r")
        assert signal.shape == (len(dates), len(axes["stocks"]))
    # Cached market axes are inspected solely for data availability, not returns.
    market_path = ROOT / "research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl"
    with market_path.open("rb") as handle:
        calendar, stocks, _ = pickle.load(handle)
    assert list(stocks) == axes["stocks"]
    positions = pd.DatetimeIndex(calendar).get_indexer(dates)
    assert (positions >= 0).all()
    exits = pd.DatetimeIndex(calendar)[positions + 11]
    # Check actual candidate construction and date/stock mapping too, without
    # ever calculating outcomes or selecting candidates by performance.
    with (ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl").open("rb") as handle:
        frame, *_ = pickle.load(handle)
    with (ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl").open("rb") as handle:
        scores = pickle.load(handle)["scores"]
    frame = frame.reset_index(drop=True).copy()
    frame["f"] = scores["book_to_market_lf_plus_impact"].to_numpy()
    f_actual = frame.pivot(index="date", columns="instrument", values="f").reindex(index=dates, columns=stocks).to_numpy(float)
    tree_actual = np.load(TREE / "NL02_signal.npy")
    actual = code.corrections(f_actual, tree_actual)
    for cutoff in (48, 96):
        prefix_actual = code.corrections(f_actual[:cutoff], tree_actual[:cutoff])
        for name, values in actual.items():
            np.testing.assert_array_equal(values[:cutoff], prefix_actual[name])
            np.testing.assert_array_equal(np.isfinite(values), np.isfinite(f_actual))
            np.testing.assert_allclose(np.nanmean(values, axis=1), 0., atol=1e-12)
            np.testing.assert_allclose(np.nanstd(values, axis=1), 1., atol=1e-12)
    verification = {
        "new_backtests_run": 0, "platform_runs": 0,
        "saved_score_algebra_checked": True,
        "candidate_normalization_and_validity_checked": True,
        "actual_cached_signal_prefix_cutoffs": [48, 96],
        "hysteresis_state_entry_exit_missing_reset_checked": True,
        "synthetic_truncation_and_future_perturbation_cutoffs": prefix_checks,
        "synthetic_checks_prove_saved_model_training_causality": False,
        "saved_fold_label_purge_checked": True,
        "saved_signal_first": str(dates.min().date()),
        "saved_signal_last": str(dates.max().date()),
        "saved_label_exit_last": str(exits.max().date()),
        "local_market_last": str(pd.DatetimeIndex(calendar).max().date()),
        "recent_periods": int((dates >= "2026-01-01").sum()),
        "recent_is_latest_local": bool(exits.max() == pd.DatetimeIndex(calendar).max()),
        "last_mature_date_on_saved_rebalance_grid": str(pd.DatetimeIndex(calendar)[np.arange(positions[0], len(calendar)-11, 10)][-1].date()),
        "old_results_sha256": digest(OLD / "pool_results.csv"),
        "old_implementation_sha256": digest(ROOT / "scripts/tree_incumbent_veto_20261012.py"),
        "candidate_implementation_sha256": digest(HERE / "candidates.py"),
    }
    (HERE / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    print(selected[["candidate", "window", "delta_A_weighted_proxy", "delta_C_weighted",
                    "delta_AC_corrected_proxy"]].to_string(index=False))
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
