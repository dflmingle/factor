"""Run exactly the three locally approved, frozen incumbent-F corrections.

No platform APIs, model fitting, search, or live pool changes.  New results
are isolated from the audit and all historical result directories.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "research_reports/platform_alignment/pool-incumbent-corrections-20261012"
TREE = ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012"
OLD = ROOT / "research_reports/platform_alignment/tree-incumbent-veto-20261012"
MARKET = ROOT / "research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl"
SF = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
CACHE = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
sys.path.insert(0, str(ROOT / "scripts"))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from platform_score_rules import PLATFORM_SEAT_FIXTURE, SCORE_RULE_VERSION, seat_stats, score_na

STARTED = time.monotonic()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def log(message):
    print(f"[{time.monotonic()-STARTED:.1f}s] {message}", flush=True)


def chosen_names(signal, y, cap):
    result = []
    for i in range(len(signal)):
        ids = np.flatnonzero(np.isfinite(signal[i]) & np.isfinite(y[i]) & np.isfinite(cap[i]))
        ordered = ids[np.argsort(signal[i, ids], kind="stable")]
        groups = np.ceil(np.arange(1, len(ids) + 1) * 10 / len(ids)).astype(int)
        result.append(set(ordered[groups == 10]))
    return result


def bootstrap_delta(base, new, seed):
    pairs = base.merge(new, on="date", suffixes=("_base", "_new"), validate="one_to_one")
    turnover = pairs.turnover_new - pairs.turnover_base
    adjustment = len(pairs) / turnover.notna().sum()
    net = (pairs.gross_excess_new - pairs.gross_excess_base).to_numpy() \
        - .006 * turnover.fillna(0).to_numpy() * adjustment
    n = len(net)
    block = 6 if n >= 100 else 3
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(5000, int(np.ceil(n / block))))
    ix = ((starts[:, :, None] + np.arange(block)) % n).reshape(5000, -1)[:, :n]
    draws = net[ix].mean(axis=1) * 25.2
    lo, hi = np.quantile(draws, [.025, .975])
    return dict(block_periods=block, bootstrap_draws=5000, delta_net=net.mean()*25.2,
                bootstrap_95_low=float(lo), bootstrap_95_high=float(hi))


def main():
    # Freeze approved definitions and every source hash before observing outcomes.
    protocol = json.loads((HERE / "protocol.json").read_text())
    checks = json.loads((HERE / "verification.json").read_text())
    if OUT.exists():
        raise RuntimeError(f"Refuse to overwrite {OUT}")
    assert checks["candidate_implementation_sha256"] == digest(HERE / "candidates.py")
    assert protocol["candidate_count"] == 3 and protocol["platform_runs"] == 0
    config = alignment_config_snapshot()
    validate_alignment_config(config)
    OUT.mkdir()
    sources = [HERE / "protocol.json", HERE / "candidates.py", Path(__file__),
               TREE / "run.py", TREE / "NL02_signal.npy", TREE / "axes.json",
               TREE / "folds.json", SF, CACHE, MARKET]
    write_json("execution_protocol.json", dict(
        user_authorization="User confirmed P01-P03 local round after listed formulas and zero platform budget",
        approved_protocol=protocol, status="running", candidate_count=3,
        platform_runs=0, source_hashes={str(p.relative_to(ROOT)): digest(p) for p in sources},
        alignment_rule=ALIGNMENT_RULE_VERSION, score_rule=SCORE_RULE_VERSION,
        core_alignment=config,
        scope="archived common-universe diagnostic; no official full-universe pool equivalence",
        daily_path="reuse locked archived evaluator with factor_valid benchmark, drift weights and two-sided cost",
        A_scope="sum of individual seat RankIC-derived S_i, never pool-composite S_i",
        B_scope="unknown; show necessary delta_NB and explicit sensitivity only"))
    code = load_module("approved_corrections", HERE / "candidates.py")
    src = load_module("archived_evaluator", TREE / "run.py")
    with MARKET.open("rb") as handle:
        calendar, stocks, fields = pickle.load(handle)
    calendar, stocks = pd.DatetimeIndex(calendar), pd.Index(stocks)
    dates = pd.DatetimeIndex(pd.read_csv(TREE / "NL02_formal_5y_periods.csv").date)
    axes = json.loads((TREE / "axes.json").read_text())
    assert list(stocks) == axes["stocks"]
    assert all(str(s).endswith((".SH", ".SZ")) for s in stocks)
    positions = calendar.get_indexer(dates)
    assert (positions >= 0).all() and (positions + 11 < len(calendar)).all()
    close = np.asarray(fields["close"], dtype=np.float32)
    cap = np.asarray(fields["cap"], dtype=np.float32)[positions]
    y = close[positions + 11] / close[positions + 1] - 1.
    y[~np.isfinite(cap) | ~np.isfinite(y)] = np.nan
    del fields
    baseline = src.baseline_panels(dates, stocks)
    seats = list(baseline)
    f_name = "book_to_market_lf_plus_impact"
    common = np.logical_and.reduce([np.isfinite(v) for v in baseline.values()]) & np.isfinite(cap)
    base = sum(baseline.values()) / 5
    base[~common] = np.nan
    # f uses the same archived score input validated during the preparation.
    with SF.open("rb") as handle:
        frame, *_ = pickle.load(handle)
    with CACHE.open("rb") as handle:
        scores = pickle.load(handle)["scores"]
    frame = frame.reset_index(drop=True).copy()
    frame["f"] = scores[f_name].to_numpy()
    f = frame.pivot(index="date", columns="instrument", values="f").reindex(index=dates, columns=stocks).to_numpy(float)
    del frame, scores
    tree = np.load(TREE / "NL02_signal.npy")
    corrected = code.corrections(f, tree)
    assert len(corrected) == 3 and list(corrected) == [k for k in protocol["definitions"] if k.startswith("P0")]
    # Validate actual signals again, including future-value perturbation, before labels score candidates.
    for cutoff in (48, 96):
        ff, tt = f.copy(), tree.copy()
        ff[cutoff:], tt[cutoff:] = 123456., -98765.
        altered = code.corrections(ff, tt)
        for name in corrected:
            np.testing.assert_array_equal(corrected[name][:cutoff], altered[name][:cutoff])
            np.testing.assert_array_equal(np.isfinite(corrected[name]), np.isfinite(f))
    pools = {"BASE": base}
    for name, value in corrected.items():
        composite = (sum(v for k, v in baseline.items() if k != f_name) + value) / 5
        composite[~common] = np.nan
        np.testing.assert_array_equal(np.isfinite(composite), np.isfinite(base))
        pools[name] = composite
    log("Frozen formulas and hashes; real-prefix checks pass; scoring one baseline + exactly three candidates")

    result_rows, monthly_rows, annual_rows, uncertainty, correlation_rows, sensitivity = [], [], [], [], [], []
    official_f_si = next(float(v["s_i_a"]) for v in PLATFORM_SEAT_FIXTURE if "VERIFY10-F" in str(v["factor_name"]))
    for window, mask in (("formal_5y", np.ones(len(dates), dtype=bool)),
                         ("recent_2026", dates >= "2026-01-01")):
        d, yy, cc = dates[mask], y[mask], cap[mask]
        old_seat_si = {name: seat_stats(src.spearman(v[mask], yy)).s_i_a for name, v in baseline.items()}
        base_na = score_na(np.mean(list(old_seat_si.values())))
        baseheld = chosen_names(base[mask], yy, cc)
        bstats = bperiods = bmonthly = None
        for name, value in pools.items():
            signal = value[mask]
            stats, periods, groups = src.metrics(signal, yy, cc, d)
            daily, monthly, turns = src.daily_path(signal, yy, cc, d, calendar, close)
            stats.update(src.nav_metrics(daily))
            neutral, _, _ = src.metrics(src.size_neutral(signal, cc), yy, cc, d)
            stats["size_neutral_net"] = neutral["net_excess"]
            stats["weight_drift_turnover_mean_including_initial_half"] = float(turns.turnover.mean())
            stats["weight_drift_turnover_mean_excluding_initial"] = float(turns.turnover.iloc[1:].mean())
            stats["portfolio_si_is_not_pool_A"] = True
            stats["candidate"], stats["window"] = name, window
            held = chosen_names(signal, yy, cc)
            overlaps = [len(a & b) / len(a) for a, b in zip(baseheld, held)]
            stats["held_overlap_with_base_mean"] = float(np.mean(overlaps))
            stats["held_overlap_with_base_min"] = float(np.min(overlaps))
            for year, frame_year in periods.groupby(pd.to_datetime(periods.date).dt.year):
                annual_rows.append(dict(candidate=name, window=window, year=int(year),
                    periods=len(frame_year), gross_excess=float(frame_year.gross_excess.mean()*25.2),
                    turnover=float(frame_year.turnover.mean()),
                    net_excess=float(frame_year.gross_excess.mean()*25.2-frame_year.turnover.mean()*.006*25.2),
                    rank_ic=float(frame_year.rank_ic.mean())))
            periods.to_csv(OUT / f"{name}_{window}_periods.csv", index=False)
            groups.to_csv(OUT / f"{name}_{window}_groups.csv", index=False)
            daily.to_csv(OUT / f"{name}_{window}_daily.csv")
            monthly.to_csv(OUT / f"{name}_{window}_monthly.csv", index=False)
            turns.to_csv(OUT / f"{name}_{window}_weight_turnover.csv", index=False)
            if name == "BASE":
                expected = pd.read_csv(OLD / "pool_results.csv")
                expected = expected[(expected.window == window) & (expected.candidate == "BASE")].iloc[0]
                for key in ("net_excess", "turnover", "corr_size", "size_neutral_net", "daily_net_nav_max_dd"):
                    np.testing.assert_allclose(stats[key], expected[key], rtol=1e-9, atol=1e-10)
                bstats, bperiods, bmonthly = stats.copy(), periods, monthly
                stats.update(na_seat_mean_proxy=base_na, delta_NA_proxy=0., mean_delta_AC_proxy=0.)
            else:
                new_si = seat_stats(src.spearman(corrected[name][mask], yy)).s_i_a
                new_na = score_na((sum(old_seat_si.values())-old_seat_si[f_name]+new_si)/5)
                dna = new_na - base_na
                paired = bmonthly.merge(monthly, on="month", suffixes=("_base", "_new"), validate="one_to_one")
                paired = paired[~paired.partial_base & ~paired.partial_new].copy()
                paired["candidate"], paired["window"] = name, window
                paired["delta_E"] = paired.rex_new - paired.rex_base
                paired["delta_T"] = paired.turnover_new - paired.turnover_base
                paired["delta_NC"] = paired.nc_new - paired.nc_base
                paired["delta_NA_proxy"] = dna
                paired["delta_AC_proxy"] = .20*dna + .45*paired.delta_NC
                paired["delta_B_unknown"] = np.nan
                paired["full_official_deltaComb_unavailable"] = np.nan
                monthly_rows.append(paired)
                ci = bootstrap_delta(bperiods, periods, seed=20261012)
                np.testing.assert_allclose(ci["delta_net"], stats["net_excess"]-bstats["net_excess"], rtol=1e-9, atol=1e-10)
                uncertainty.append(dict(candidate=name, window=window, **ci))
                stats.update(delta_net=stats["net_excess"]-bstats["net_excess"],
                    delta_turnover=stats["turnover"]-bstats["turnover"],
                    delta_dd=stats["daily_net_nav_max_dd"]-bstats["daily_net_nav_max_dd"],
                    delta_abs_size_rho=abs(stats["corr_size"])-abs(bstats["corr_size"]),
                    delta_size_neutral_net=stats["size_neutral_net"]-bstats["size_neutral_net"],
                    base_F_si_proxy=old_seat_si[f_name], new_F_si_proxy=new_si,
                    na_seat_mean_proxy=new_na, delta_NA_proxy=dna,
                    mean_delta_E=float(paired.delta_E.mean()), mean_delta_T=float(paired.delta_T.mean()),
                    mean_delta_NC=float(paired.delta_NC.mean()), mean_delta_AC_proxy=float(paired.delta_AC_proxy.mean()),
                    months=int(len(paired)), monthly_AC_positive_share=float((paired.delta_AC_proxy>0).mean()),
                    base_full_C_months=int((paired.nc_base>=1.-1e-12).sum()),
                    new_full_C_months=int((paired.nc_new>=1.-1e-12).sum()),
                    lost_base_full_C_months=int(((paired.nc_base>=1.-1e-12)&(paired.nc_new<1.-1e-12)).sum()),
                    size_guard=abs(stats["corr_size"])<=abs(bstats["corr_size"])+1e-9 and stats["size_neutral_net"]>=bstats["size_neutral_net"]-1e-9,
                    bootstrap_95_low=ci["bootstrap_95_low"], bootstrap_95_high=ci["bootstrap_95_high"])
                stats["minimum_delta_NB_for_breakeven"] = -stats["mean_delta_AC_proxy"]/.35
                stats["required_official_candidate_F_si_if_B_unchanged"] = official_f_si-.9*stats["mean_delta_NC"]
                stats["official_required_F_si_is_conditional_on_local_C_and_unsaturated_A"] = True
                for dnb in (-.10, -.05, -.02, 0., .02, .05):
                    sensitivity.append(dict(candidate=name, window=window, assumed_delta_NB=dnb,
                        deltaComb_scenario=stats["mean_delta_AC_proxy"]+.35*dnb,
                        note="explicit hypothetical NB difference; not observed B or predicted official points"))
                for seat, original in baseline.items():
                    rho = src.spearman(corrected[name][mask], original[mask])
                    correlation_rows.append(dict(candidate=name, window=window, reference_seat=seat,
                        rho=float(np.nanmean(rho)), valid_dates=int(np.isfinite(rho).sum()),
                        scope="saved signal-date cross-sectional Spearman, not every trading day"))
            result_rows.append(stats)
            log(f"{name} {window}: net={stats['net_excess']*100:.4f}%, turn={stats['turnover']*100:.4f}%, DD={stats['daily_net_nav_max_dd']*100:.4f}%")
    result = pd.DataFrame(result_rows)
    result.to_csv(OUT / "pool_results.csv", index=False)
    pd.concat(monthly_rows).to_csv(OUT / "pool_monthly_deltas.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(OUT / "annual_results.csv", index=False)
    pd.DataFrame(uncertainty).to_csv(OUT / "paired_uncertainty.csv", index=False)
    pd.DataFrame(correlation_rows).to_csv(OUT / "seat_correlations.csv", index=False)
    pd.DataFrame(sensitivity).to_csv(OUT / "B_sensitivity.csv", index=False)
    write_json("verification.json", dict(status="complete", candidate_count=3, platform_runs=0,
        no_parameter_search=True, approved_candidate_sha256=digest(HERE / "candidates.py"),
        actual_future_perturbation_bitwise_equal=True, cutoff_indices=[48,96],
        previous_saved_baseline_reproduced=True, universe_identical_for_all_pools=True,
        member_cost_and_bootstrap_delta_reconciled=True,
        A_computed_from_seat_IC_not_pool_IC=True, full_official_deltaComb_available=False,
        formal_periods=len(dates), recent_periods=int((dates>="2026-01-01").sum()),
        elapsed_seconds=time.monotonic()-STARTED))
    log("Completed approved round; no additional candidates or platform calls")


if __name__ == "__main__":
    main()
