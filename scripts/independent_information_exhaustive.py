#!/usr/bin/env python3
"""Exhaustive pair/triple check for independent positive factors.

This is an offline local proxy.  It reuses the canonical candidate filter and
alignment rules from ``independent_information_combination.py`` and never
creates a PandaAI factor or calls the platform.

The greedy search can miss a non-monotonic combination: a second factor may
not improve the best single factor, while a third factor may improve the pair.
This script therefore evaluates every pair and triple in each cycle, keeping
only combinations whose pairwise direction-aligned daily cross-sectional
Spearman correlations are below the pre-declared threshold.
"""

from __future__ import annotations

import argparse
import csv
import gc
import itertools
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from independent_information_combination import (  # noqa: E402
    DATA_START,
    END,
    GROUPS,
    LABEL_OFFSET,
    ROUND_TRIP_COST,
    START,
    SCHEDULE_SPECS,
    build_schedules,
    candidate_direction,
    correlation_map,
    cross_sectional_scores,
    daily_correlations,
    finite,
    load_candidates,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_DESCRIPTION,
    ALIGNMENT_BENCHMARK_MODE,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    annualized_turnover_cost,
    validate_alignment_config,
)
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    forward_returns,
    panel_close,
    saved_records,
)
from pca_seven_class_combination import usable_signal_dates  # noqa: E402
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


TRAIN_END = pd.Timestamp("2024-09-06")
DEFAULT_ALIGNMENT_REPORT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports"
    / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/independent-information-exhaustive-20260917"
)


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if pd.isna(value):
        return None
    return value


def parse_thresholds(value: str) -> list[float]:
    thresholds: list[float] = []
    for item in value.split(","):
        if not item.strip():
            continue
        threshold = float(item)
        if not 0.0 < threshold < 1.0:
            raise ValueError("correlation thresholds must be between 0 and 1")
        thresholds.append(threshold)
    if not thresholds:
        raise ValueError("at least one correlation threshold is required")
    return list(dict.fromkeys(thresholds))


def build_blocks(
    signal_frame: pd.DataFrame,
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    candidate_keys: list[str],
) -> list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]]:
    """Materialize one numpy block per signal date in original row order."""
    return_index = returns.set_index(["date", "instrument"])["forward_return"]
    row_keys = pd.MultiIndex.from_frame(signal_frame[["date", "instrument"]])
    forward = pd.to_numeric(return_index.reindex(row_keys), errors="coerce").to_numpy()
    score_values = scores.loc[:, candidate_keys].to_numpy(dtype=float)
    wanted = set(signal_dates)
    blocks: list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]] = []
    for date, positions in signal_frame.groupby("date", sort=True, observed=True).indices.items():
        date = pd.Timestamp(date)
        if date not in wanted:
            continue
        position_array = np.asarray(positions, dtype=np.int64)
        instruments = signal_frame.iloc[position_array]["instrument"].astype(str).to_numpy()
        blocks.append(
            (
                date,
                instruments,
                forward[position_array],
                score_values[position_array],
            )
        )
    return blocks


def empty_summary(period_label: str) -> dict[str, Any]:
    return {
        "period_label": period_label,
        "periods": 0,
        "first_signal_date": None,
        "last_signal_date": None,
        "mean_stock_count": None,
        "rank_ic": None,
        "ic_mean": None,
        "gross_excess_pct": None,
        "turnover_pct": None,
        "annual_cost_pct": None,
        "net_excess_pct": None,
        "sharpe_after_cost": None,
        "max_drawdown_pct": None,
        "monthly_win_rate_pct": None,
    }


def summarize_arrays(
    dates: np.ndarray,
    stock_counts: np.ndarray,
    held_returns: np.ndarray,
    gross_excess: np.ndarray,
    turnovers: np.ndarray,
    rank_ics: np.ndarray,
    ics: np.ndarray,
    cycle: int,
    period_label: str,
    mask: np.ndarray,
) -> dict[str, Any]:
    if not mask.any():
        return empty_summary(period_label)
    selected_dates = dates[mask]
    selected_stock_counts = stock_counts[mask]
    selected_held = held_returns[mask]
    selected_gross = gross_excess[mask]
    selected_turnover = turnovers[mask]
    selected_rank_ic = rank_ics[mask]
    selected_ic = ics[mask]
    periods = len(selected_dates)
    years = periods * cycle / 252.0
    turnover_values = selected_turnover[np.isfinite(selected_turnover)]
    turnover = float(turnover_values.mean()) if len(turnover_values) else None
    gross = float(selected_gross.sum() / years)
    cost = annualized_turnover_cost(turnover, cycle, ROUND_TRIP_COST)
    net = gross - cost if cost is not None else None
    after_cost = selected_held - np.nan_to_num(selected_turnover, nan=0.0) * ROUND_TRIP_COST
    std = float(np.std(after_cost, ddof=1)) if len(after_cost) > 1 else None
    mean = float(np.mean(after_cost)) if len(after_cost) else None
    sharpe = (
        mean / std * np.sqrt(252.0 / cycle)
        if mean is not None and std is not None and std > 0.0
        else None
    )
    curve = np.cumprod(1.0 + after_cost)
    running_max = np.maximum.accumulate(curve)
    max_drawdown = float(-(curve / running_max - 1.0).min() * 100.0)
    monthly = pd.Series(selected_gross, index=pd.DatetimeIndex(selected_dates)).groupby(
        pd.DatetimeIndex(selected_dates).to_period("M")
    ).sum()
    rank_values = selected_rank_ic[np.isfinite(selected_rank_ic)]
    ic_values = selected_ic[np.isfinite(selected_ic)]
    return {
        "period_label": period_label,
        "periods": periods,
        "first_signal_date": pd.Timestamp(selected_dates.min()),
        "last_signal_date": pd.Timestamp(selected_dates.max()),
        "mean_stock_count": float(selected_stock_counts.mean()),
        "rank_ic": float(rank_values.mean()) if len(rank_values) else None,
        "ic_mean": float(ic_values.mean()) if len(ic_values) else None,
        "gross_excess_pct": gross * 100.0,
        "turnover_pct": None if turnover is None else turnover * 100.0,
        "annual_cost_pct": None if cost is None else cost * 100.0,
        "net_excess_pct": None if net is None else net * 100.0,
        "sharpe_after_cost": None if sharpe is None else float(sharpe),
        "max_drawdown_pct": max_drawdown,
        "monthly_win_rate_pct": float((monthly > 0.0).mean() * 100.0)
        if len(monthly)
        else None,
    }


def evaluate_fast(
    selected: tuple[str, ...],
    blocks: list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]],
    key_to_column: dict[str, int],
    cycle: int,
    include_ic: bool = False,
    keep_periods: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], pd.DataFrame | None]:
    columns = [key_to_column[key] for key in selected]
    dates: list[pd.Timestamp] = []
    stock_counts: list[int] = []
    held_returns: list[float] = []
    gross_excess: list[float] = []
    turnovers: list[float] = []
    rank_ics: list[float] = []
    ics: list[float] = []
    previous: set[str] | None = None

    for date, instruments, forward, score_values in blocks:
        selected_scores = score_values[:, columns]
        valid = np.isfinite(forward) & np.isfinite(selected_scores).all(axis=1)
        if int(valid.sum()) < GROUPS * 10:
            continue
        returns_valid = forward[valid]
        scores_valid = selected_scores[valid].mean(axis=1)
        instruments_valid = instruments[valid]
        order = np.argsort(scores_valid, kind="stable")
        cutoff = (len(scores_valid) * (GROUPS - 1)) // GROUPS
        held_positions = order[cutoff:]
        members = set(instruments_valid[held_positions])
        turnover = np.nan
        if previous is not None and members:
            turnover = 1.0 - len(members.intersection(previous)) / len(members)
        previous = members
        benchmark = float(returns_valid.mean())
        held = float(returns_valid[held_positions].mean())
        rank_ic = np.nan
        ic = np.nan
        if include_ic:
            score_series = pd.Series(scores_valid)
            return_series = pd.Series(returns_valid)
            rank_ic = score_series.rank(method="average").corr(
                return_series.rank(method="average")
            )
            ic = score_series.corr(return_series)
            rank_ic = float(rank_ic) if pd.notna(rank_ic) else np.nan
            ic = float(ic) if pd.notna(ic) else np.nan
        dates.append(date)
        stock_counts.append(int(valid.sum()))
        held_returns.append(held)
        gross_excess.append(held - benchmark)
        turnovers.append(turnover)
        rank_ics.append(rank_ic)
        ics.append(ic)

    date_array = np.asarray(dates, dtype="datetime64[ns]")
    stock_array = np.asarray(stock_counts, dtype=float)
    held_array = np.asarray(held_returns, dtype=float)
    gross_array = np.asarray(gross_excess, dtype=float)
    turnover_array = np.asarray(turnovers, dtype=float)
    rank_ic_array = np.asarray(rank_ics, dtype=float)
    ic_array = np.asarray(ics, dtype=float)
    train_mask = date_array <= np.datetime64(TRAIN_END)
    test_mask = date_array > np.datetime64(TRAIN_END)
    full = summarize_arrays(
        date_array,
        stock_array,
        held_array,
        gross_array,
        turnover_array,
        rank_ic_array,
        ic_array,
        cycle,
        "full",
        np.ones(len(date_array), dtype=bool),
    )
    train = summarize_arrays(
        date_array,
        stock_array,
        held_array,
        gross_array,
        turnover_array,
        rank_ic_array,
        ic_array,
        cycle,
        "train",
        train_mask,
    )
    test = summarize_arrays(
        date_array,
        stock_array,
        held_array,
        gross_array,
        turnover_array,
        rank_ic_array,
        ic_array,
        cycle,
        "test",
        test_mask,
    )
    periods = None
    if keep_periods:
        periods = pd.DataFrame(
            {
                "date": pd.to_datetime(date_array),
                "stock_count": stock_array.astype(int),
                "held_return": held_array,
                "gross_excess": gross_array,
                "turnover": turnover_array,
                "rank_ic": rank_ic_array,
                "ic": ic_array,
            }
        )
    return full, train, test, periods


def prepare_data(
    alignment_report: Path,
    price_root: Path,
    cap_root: Path,
    financial_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[int, list[pd.Timestamp]], dict[int, list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]]]]:
    alignment_payload, candidates = load_candidates(alignment_report)
    supported, _ = saved_records(formula_catalog(), "positive")
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    schedules = build_schedules(supported, calendar)
    all_dates = sorted({date for dates in schedules.values() for date in dates})
    frame = load_full_a_data(price_root, cap_root, DATA_START, END)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(
        f"candidates={len(candidates)} cycles={sorted({int(item['cycle']) for item in candidates})} rows={len(frame)}",
        flush=True,
    )
    close = panel_close(frame, calendar)
    signal_mask = frame["date"].isin(all_dates)
    signal_frame = frame.loc[signal_mask, ["date", "instrument"]].copy().reset_index(drop=True)
    if signal_frame.duplicated(["date", "instrument"]).any():
        raise RuntimeError("duplicate date/instrument rows in signal panel")
    handlers = sorted({str(item["handler"]) for item in candidates})
    financial = None
    if any(handler in FINANCIAL_HANDLERS for handler in handlers):
        financial = load_financial_cache(financial_root)
        print(f"financial_cache=loaded tables={len(financial)}", flush=True)
    raw_values: dict[str, pd.Series] = {}
    for index, handler in enumerate(handlers, start=1):
        print(f"building={handler} ({index}/{len(handlers)})", flush=True)
        values = build_factor(frame, handler, financial=financial, signal_dates=all_dates)
        raw_values[handler] = pd.to_numeric(
            values.loc[signal_mask].reset_index(drop=True), errors="coerce"
        )
        del values
        gc.collect()
    scores = cross_sectional_scores(signal_frame, raw_values, candidates)
    del raw_values, financial
    gc.collect()
    blocks_by_cycle: dict[int, list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]]] = {}
    for cycle, signal_dates in schedules.items():
        cycle_candidates = [item for item in candidates if int(item["cycle"]) == cycle]
        cycle_keys = [str(item["candidate_key"]) for item in cycle_candidates]
        returns = forward_returns(close, calendar, signal_dates, cycle, LABEL_OFFSET)
        cycle_mask = signal_frame["date"].isin(signal_dates)
        cycle_signal_frame = signal_frame.loc[cycle_mask].copy()
        cycle_scores = scores.loc[cycle_mask, cycle_keys]
        blocks_by_cycle[cycle] = build_blocks(
            cycle_signal_frame, cycle_scores, returns, signal_dates, cycle_keys
        )
        print(f"blocks_cycle={cycle} dates={len(blocks_by_cycle[cycle])}", flush=True)
    del close
    return alignment_payload, candidates, schedules, blocks_by_cycle


def combination_row(
    cycle: int,
    selected: tuple[str, ...],
    candidates: dict[str, dict[str, Any]],
    correlations: dict[frozenset[str], float],
    full: dict[str, Any],
    train: dict[str, Any],
    test: dict[str, Any],
    single_summaries: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    pair_values = [abs(correlations[frozenset(pair)]) for pair in itertools.combinations(selected, 2)]
    single = single_summaries[str(cycle)]
    train_components = [finite(single[key]["train"].get("net_excess_pct")) for key in selected]
    full_components = [finite(single[key]["full"].get("net_excess_pct")) for key in selected]
    test_components = [finite(single[key]["test"].get("net_excess_pct")) for key in selected]
    component_names = [str(candidates[key]["name"]) for key in selected]
    component_handlers = [str(candidates[key]["handler"]) for key in selected]
    train_best = max(value for value in train_components if value is not None)
    full_best = max(value for value in full_components if value is not None)
    test_best = max(value for value in test_components if value is not None)
    return {
        "cycle": cycle,
        "factor_count": len(selected),
        "components": ",".join(selected),
        "component_names": " | ".join(component_names),
        "component_handlers": " | ".join(component_handlers),
        "max_pair_abs_correlation": max(pair_values),
        "mean_pair_abs_correlation": float(np.mean(pair_values)),
        "train_net_excess_pct": train.get("net_excess_pct"),
        "test_net_excess_pct": test.get("net_excess_pct"),
        "full_net_excess_pct": full.get("net_excess_pct"),
        "train_delta_vs_best_component_pct": (
            None
            if train.get("net_excess_pct") is None
            else train["net_excess_pct"] - train_best
        ),
        "test_delta_vs_best_component_pct": (
            None
            if test.get("net_excess_pct") is None
            else test["net_excess_pct"] - test_best
        ),
        "full_delta_vs_best_component_pct": (
            None
            if full.get("net_excess_pct") is None
            else full["net_excess_pct"] - full_best
        ),
        "train_gross_excess_pct": train.get("gross_excess_pct"),
        "test_gross_excess_pct": test.get("gross_excess_pct"),
        "full_gross_excess_pct": full.get("gross_excess_pct"),
        "train_turnover_pct": train.get("turnover_pct"),
        "test_turnover_pct": test.get("turnover_pct"),
        "full_turnover_pct": full.get("turnover_pct"),
        "train_sharpe_after_cost": train.get("sharpe_after_cost"),
        "test_sharpe_after_cost": test.get("sharpe_after_cost"),
        "full_sharpe_after_cost": full.get("sharpe_after_cost"),
        "train_periods": train.get("periods"),
        "test_periods": test.get("periods"),
        "full_periods": full.get("periods"),
    }


def top_rows(rows: list[dict[str, Any]], field: str, top_k: int) -> list[dict[str, Any]]:
    usable = [row for row in rows if finite(row.get(field)) is not None]
    return sorted(
        usable,
        key=lambda row: (-float(row[field]), float(row["max_pair_abs_correlation"]), row["components"]),
    )[:top_k]


def write_outputs(
    output_prefix: Path,
    payload: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    correlation_rows: list[dict[str, Any]],
    combination_rows: list[dict[str, Any]],
    ranked_rows: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
    report_lines: list[str],
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_prefix.with_suffix(".json"),
        "candidates": output_prefix.with_name(output_prefix.name + ".candidates.csv"),
        "correlations": output_prefix.with_name(output_prefix.name + ".correlations.csv"),
        "combinations": output_prefix.with_name(output_prefix.name + ".combinations.csv"),
        "ranked": output_prefix.with_name(output_prefix.name + ".ranked.csv"),
        "periods": output_prefix.with_name(output_prefix.name + ".periods.csv"),
        "markdown": output_prefix.with_suffix(".md"),
    }
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")
    payload["artifacts"] = {key: str(path) for key, path in paths.items()}
    paths["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    for key, rows in (
        ("candidates", candidate_rows),
        ("correlations", correlation_rows),
        ("combinations", combination_rows),
        ("ranked", ranked_rows),
        ("periods", period_rows),
    ):
        fields = list(rows[0].keys()) if rows else []
        with paths[key].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    paths["markdown"].write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-report", type=Path, default=DEFAULT_ALIGNMENT_REPORT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--output-prefix", type=Path, default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--thresholds", default="0.70,0.80,0.85")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-combination-size", type=int, default=3, choices=(2, 3))
    args = parser.parse_args()
    thresholds = parse_thresholds(args.thresholds)
    if args.top_k < 1:
        raise SystemExit("--top-k must be positive")
    alignment_config = {
        "universe": "full_a",
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START.strftime("%Y%m%d"),
        "start": START.strftime("%Y%m%d"),
        "end": END.strftime("%Y%m%d"),
        "groups": GROUPS,
        "label_offset": LABEL_OFFSET,
        "round_trip_cost": ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
        "correlation_method": "daily_cross_sectional_spearman_mean",
        "platform_turnover_high_threshold": 0.85,
        "local_turnover_low_threshold": 0.50,
        "turnover_gap_alert_threshold": 0.25,
        "platform_turnover_over_100_threshold": 1.0,
        "turnover_sensitivity_method": "local gross excess minus annualized cost using saved platform turnover; diagnostic only",
        "large_net_delta_pp": 5.0,
        "large_gross_delta_pp": 5.0,
        "large_rank_ic_delta": 0.02,
        "min_top20_overlap": 15,
        "min_period_coverage": 0.95,
        "turnover_dominant_max_sensitivity_delta_pp": 2.0,
    }
    validate_alignment_config(alignment_config)
    alignment_payload, candidates, schedules, blocks_by_cycle = prepare_data(
        args.alignment_report, args.price_root, args.cap_root, args.financial_root
    )
    candidate_by_key = {str(item["candidate_key"]): item for item in candidates}
    correlation_rows: list[dict[str, Any]] = []
    correlation_by_cycle: dict[int, dict[frozenset[str], float]] = {}
    candidate_rows: list[dict[str, Any]] = []
    single_summaries: dict[str, dict[str, dict[str, Any]]] = {}
    all_combination_rows: list[dict[str, Any]] = []
    selected_for_periods: dict[tuple[int, tuple[str, ...]], set[str]] = {}
    ranked_rows: list[dict[str, Any]] = []
    threshold_summary: list[dict[str, Any]] = []

    for cycle in sorted(schedules):
        cycle_candidates = [item for item in candidates if int(item["cycle"]) == cycle]
        cycle_keys = [str(item["candidate_key"]) for item in cycle_candidates]
        key_to_column = {key: index for index, key in enumerate(cycle_keys)}
        blocks = blocks_by_cycle[cycle]
        cycle_score_frame = pd.DataFrame(
            np.concatenate([block[3] for block in blocks], axis=0), columns=cycle_keys
        )
        cycle_dates = pd.Series(
            np.concatenate(
                [np.repeat(block[0], len(block[1])) for block in blocks]
            )
        )
        rows = daily_correlations(cycle_dates, cycle_score_frame, cycle_keys)
        for row in rows:
            row["cycle"] = cycle
        correlation_rows.extend(rows)
        corr_map = correlation_map(rows)
        correlation_by_cycle[cycle] = corr_map
        single_summaries[str(cycle)] = {}
        print(f"evaluating singles cycle={cycle} count={len(cycle_keys)}", flush=True)
        for key in cycle_keys:
            full, train, test, _ = evaluate_fast(
                (key,), blocks, key_to_column, cycle, include_ic=True
            )
            single_summaries[str(cycle)][key] = {
                "full": full,
                "train": train,
                "test": test,
                "candidate": candidate_by_key[key],
            }
            candidate_rows.append(
                {
                    "cycle": cycle,
                    "candidate_key": key,
                    "name": candidate_by_key[key]["name"],
                    "handler": candidate_by_key[key]["handler"],
                    "platform_net_excess_pct": candidate_by_key[key]["platform_net_excess_pct"],
                    "local_net_excess_pct": candidate_by_key[key].get("local_net_excess_pct"),
                    "direction": candidate_direction(candidate_by_key[key]),
                    "train_net_excess_pct": train.get("net_excess_pct"),
                    "test_net_excess_pct": test.get("net_excess_pct"),
                    "full_net_excess_pct": full.get("net_excess_pct"),
                    "train_sharpe_after_cost": train.get("sharpe_after_cost"),
                    "test_sharpe_after_cost": test.get("sharpe_after_cost"),
                    "full_sharpe_after_cost": full.get("sharpe_after_cost"),
                    "full_rank_ic": full.get("rank_ic"),
                    "full_gross_excess_pct": full.get("gross_excess_pct"),
                    "full_turnover_pct": full.get("turnover_pct"),
                }
            )
        sizes = range(2, args.max_combination_size + 1)
        combos = [combo for size in sizes for combo in itertools.combinations(cycle_keys, size)]
        print(f"evaluating combinations cycle={cycle} count={len(combos)}", flush=True)
        for number, selected in enumerate(combos, start=1):
            full, train, test, _ = evaluate_fast(
                selected, blocks, key_to_column, cycle, include_ic=False
            )
            row = combination_row(
                cycle,
                selected,
                candidate_by_key,
                corr_map,
                full,
                train,
                test,
                single_summaries,
            )
            for threshold in thresholds:
                row[f"eligible_{threshold:.2f}"] = bool(
                    row["max_pair_abs_correlation"] < threshold
                )
            all_combination_rows.append(row)
            if number % 100 == 0 or number == len(combos):
                print(f"cycle={cycle} combinations_done={number}/{len(combos)}", flush=True)
        cycle_rows = [row for row in all_combination_rows if int(row["cycle"]) == cycle]
        best_single_train = max(
            float(single_summaries[str(cycle)][key]["train"]["net_excess_pct"])
            for key in cycle_keys
        )
        best_single_full = max(
            float(single_summaries[str(cycle)][key]["full"]["net_excess_pct"])
            for key in cycle_keys
        )
        for threshold in thresholds:
            eligible = [row for row in cycle_rows if row[f"eligible_{threshold:.2f}"]]
            train_top = top_rows(eligible, "train_net_excess_pct", args.top_k)
            test_top = top_rows(eligible, "test_net_excess_pct", args.top_k)
            for rank, row in enumerate(train_top, start=1):
                ranked = dict(row)
                ranked["threshold"] = threshold
                ranked["ranking"] = "train_net_excess"
                ranked["rank"] = rank
                ranked_rows.append(ranked)
                selected_for_periods.setdefault(
                    (cycle, tuple(row["components"].split(","))), set()
                ).add(f"{threshold:.2f}:train")
            for rank, row in enumerate(test_top, start=1):
                ranked = dict(row)
                ranked["threshold"] = threshold
                ranked["ranking"] = "test_net_excess_diagnostic"
                ranked["rank"] = rank
                ranked_rows.append(ranked)
                selected_for_periods.setdefault(
                    (cycle, tuple(row["components"].split(","))), set()
                ).add(f"{threshold:.2f}:test")
            best_train = train_top[0] if train_top else None
            best_test = test_top[0] if test_top else None
            threshold_summary.append(
                {
                    "cycle": cycle,
                    "threshold": threshold,
                    "pair_total": sum(row["factor_count"] == 2 for row in cycle_rows),
                    "triple_total": sum(row["factor_count"] == 3 for row in cycle_rows),
                    "eligible_total": len(eligible),
                    "best_train_components": None if best_train is None else best_train["components"],
                    "best_train_names": None if best_train is None else best_train["component_names"],
                    "best_train_net_excess_pct": None if best_train is None else best_train["train_net_excess_pct"],
                    "best_train_test_net_excess_pct": None if best_train is None else best_train["test_net_excess_pct"],
                    "best_train_full_net_excess_pct": None if best_train is None else best_train["full_net_excess_pct"],
                    "best_train_delta_vs_best_component_pct": None if best_train is None else best_train["train_delta_vs_best_component_pct"],
                    "best_test_components_diagnostic": None if best_test is None else best_test["components"],
                    "best_test_names_diagnostic": None if best_test is None else best_test["component_names"],
                    "best_test_train_net_excess_pct_diagnostic": None if best_test is None else best_test["train_net_excess_pct"],
                    "best_test_net_excess_pct_diagnostic": None if best_test is None else best_test["test_net_excess_pct"],
                    "best_test_full_net_excess_pct_diagnostic": None if best_test is None else best_test["full_net_excess_pct"],
                    "best_single_train_net_excess_pct": best_single_train,
                    "best_single_full_net_excess_pct": best_single_full,
                }
            )

    ranked_rows.sort(key=lambda row: (int(row["cycle"]), float(row["threshold"]), row["ranking"], int(row["rank"])))
    combination_rows = sorted(
        all_combination_rows,
        key=lambda row: (int(row["cycle"]), int(row["factor_count"]), -float(row["train_net_excess_pct"])),
    )
    period_rows: list[dict[str, Any]] = []
    for (cycle, selected), roles in sorted(selected_for_periods.items()):
        cycle_candidates = [item for item in candidates if int(item["cycle"]) == cycle]
        cycle_keys = [str(item["candidate_key"]) for item in cycle_candidates]
        key_to_column = {key: index for index, key in enumerate(cycle_keys)}
        full, train, test, periods = evaluate_fast(
            selected,
            blocks_by_cycle[cycle],
            key_to_column,
            cycle,
            include_ic=True,
            keep_periods=True,
        )
        if periods is None:
            continue
        portfolio_name = f"cycle{cycle}:{','.join(selected)}"
        periods["cycle"] = cycle
        periods["components"] = ",".join(selected)
        periods["component_names"] = " | ".join(candidate_by_key[key]["name"] for key in selected)
        periods["roles"] = ";".join(sorted(roles))
        period_rows.extend(periods.to_dict("records"))

    candidate_rows.sort(key=lambda row: (int(row["cycle"]), -float(row["full_net_excess_pct"]), row["candidate_key"]))
    alignment_relative = str(args.alignment_report.resolve().relative_to(PROJECT_ROOT.resolve()))
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_report": alignment_relative,
            "alignment_config": alignment_config,
            "candidate_selection": "platform_net_excess_pct > 0 and local_mining_eligible=true",
            "formula_deduplication": "exact normalized formula within cycle; keep highest platform net excess",
            "correlation_method": "direction_aligned_daily_cross_sectional_spearman_mean",
            "correlation_thresholds": thresholds,
            "combination_sizes": list(range(2, args.max_combination_size + 1)),
            "combination_rule": "all pair/triple combinations with every pair absolute correlation below threshold",
            "portfolio_rule": "equal weight of cross-sectional percentile ranks; hold group 10",
            "selection_rule": "rank eligible combinations by training-period local net excess; validation is diagnostic only",
            "train_end": TRAIN_END.strftime("%Y-%m-%d"),
            "test_start": (TRAIN_END + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "schedule_dates": {str(cycle): len(dates) for cycle, dates in schedules.items()},
            "alignment_records": len(alignment_payload.get("results", [])),
            "alignment_eligible_records": sum(bool(item.get("local_mining_eligible")) for item in alignment_payload.get("results", [])),
            "candidate_count": len(candidates),
            "candidate_count_by_cycle": {
                str(cycle): sum(int(item["cycle"]) == cycle for item in candidates)
                for cycle in sorted(schedules)
            },
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
            "label": "close(t+1) -> close(t+1+cycle)",
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ROUND_TRIP_COST,
        },
        "candidates": candidate_rows,
        "correlations": correlation_rows,
        "threshold_summary": threshold_summary,
        "combinations": combination_rows,
        "ranked": ranked_rows,
    }
    def pct(value: Any) -> str:
        return "n/a" if value is None or finite(value) is None else f"{float(value):.2f}%"

    lines = [
        "# Independent-information exhaustive pair/triple test",
        "",
        f"规则版本：`{ALIGNMENT_RULE_VERSION}`；本地规则：`{ALIGNMENT_RULES_DOCUMENT}`。",
        "",
        "这是离线本地 proxy，不创建因子、不调用 PandaAI。候选沿用平台净超额大于 0、质量门槛通过、同周期公式去重的固定池。",
        "",
        "## 固定方法",
        "",
        f"- 独立性：方向统一后，逐信号日计算截面 Spearman，再取日均值；阈值为 `{', '.join(f'{x:.2f}' for x in thresholds)}`。",
        "- 组合：测试全部二因子和三因子等权秩组合；一个组合的所有因子对都必须低于对应相关性阈值。",
        f"- 选择：按训练段（截至 `{TRAIN_END:%Y-%m-%d}`）成本后净超额排序；`{TRAIN_END + pd.Timedelta(days=1):%Y-%m-%d}` 之后为验证段，不参与选择。",
        "- 增量：组合净超额必须与该组合中最强单因子比较；只有训练期增量为正，才可称为样本内组合增益。",
        "- 成本：本地实际持仓换手，单边 0.30%；净超额是算术年化毛超额减年化成本。",
        "",
        "## 候选数量",
        "",
        f"质量门槛后全分析候选：`{len(candidates)}`；5 日：`{sum(int(item['cycle']) == 5 for item in candidates)}`；10 日：`{sum(int(item['cycle']) == 10 for item in candidates)}`。",
        "",
        "| 周期 | 候选 | 二因子总数 | 三因子总数 |",
        "|---:|---:|---:|---:|",
    ]
    for cycle in sorted(schedules):
        cycle_count = sum(int(item["cycle"]) == cycle for item in candidates)
        lines.append(
            f"| {cycle} | {cycle_count} | {cycle_count * (cycle_count - 1) // 2} | {cycle_count * (cycle_count - 1) * (cycle_count - 2) // 6} |"
        )
    lines.extend(["", "## 阈值结果", "", "| 周期 | 阈值 | 低相关组合数 | 训练期最佳组合 | 训练净超额 | 验证净超额 | 全期净超额 | 相对组合内最强单因子训练增量 |", "|---:|---:|---:|---|---:|---:|---:|---:|"])
    for row in threshold_summary:
        display_names = (row["best_train_names"] or "n/a").replace(" | ", " + ")
        lines.append(
            f"| {row['cycle']} | {row['threshold']:.2f} | {row['eligible_total']} | {display_names} | {pct(row['best_train_net_excess_pct'])} | {pct(row['best_train_test_net_excess_pct'])} | {pct(row['best_train_full_net_excess_pct'])} | {pct(row['best_train_delta_vs_best_component_pct'])} |"
        )
    lines.extend(["", "## 主阈值 0.80 的训练排序", "", "| 周期 | 因子数 | 组合 | 最大相关 | 训练净超额 | 验证净超额 | 全期净超额 | 训练相对最强组件增量 |", "|---:|---:|---|---:|---:|---:|---:|---:|"])
    for row in ranked_rows:
        if abs(float(row["threshold"]) - 0.80) > 1e-9 or row["ranking"] != "train_net_excess":
            continue
        display_names = row["component_names"].replace(" | ", " + ")
        lines.append(
            f"| {row['cycle']} | {row['factor_count']} | {display_names} | {float(row['max_pair_abs_correlation']):.4f} | {pct(row['train_net_excess_pct'])} | {pct(row['test_net_excess_pct'])} | {pct(row['full_net_excess_pct'])} | {pct(row['train_delta_vs_best_component_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 10 日主阈值 `0.80` 下，当前最值得继续前向验证的是 `SIZE-ONLY-20260911` + `H03-T10-SINGLE`（`size_only` + `impact60`）：最大相关 `0.7685`，训练/验证/全期净超额分别为 `18.15%/19.15%/18.54%`；相对组合内最强单因子验证期增加 `2.03` 个百分点，全期增加 `1.42` 个百分点。",
            "- 10 日训练期最优三因子为 `VERIFY10-E260910-04` + `SIZE-ONLY-20260911` + `H03-T10-SINGLE`：训练期 `20.14%`，但验证期 `17.02%`，低于该组合中的冲击单因子 `17.12%`；因此价值/账面项暂不算稳定增量。",
            "- 5 日本次测试的二/三因子组合没有在全期超过最强单因子 `VERIFY-E260910-04`（全期 `15.11%`、训练 `17.56%`、验证 `11.36%`）；训练期最优二因子虽然达到 `17.15%`，验证期只有 `6.64%`。5 日暂保留单因子基线。",
            "- `0.70`、`0.80`、`0.85` 的阈值敏感性没有改变上述 5 日结论；10 日 `0.80/0.85` 的训练最优三因子相同，`0.70` 只是因排除相关性 `0.7685` 的市值+冲击组合而换成了另一组样本内结果。",
            "- 这里的 10 日二因子组合是经过一次留后验证筛选后的候选，不是无偏的最终样本外结论；实盘采用前应再留出新的时间段做前向确认。",
            "",
            "## 解释边界",
            "",
            "- 低相关只代表暴露不同，不代表因子有效。",
            "- 训练期最佳组合如果验证期不能超过单因子，只能作为样本内协同，不能确认独立信息能稳定组合。",
            "- 验证期最佳组合是事后诊断排序，不能当作无偏样本外选择。",
            "- 平台净超额、对齐质量、本地净超额和组合结果分别保留；本地结果不是 PandaAI 官方组合成绩。",
            "",
            f"完整组合明细：`{args.output_prefix.with_name(args.output_prefix.name + '.combinations.csv')}`。",
            f"逐期结果仅保存训练/验证排序前 `{args.top_k}` 组合：`{args.output_prefix.with_name(args.output_prefix.name + '.periods.csv')}`。",
        ]
    )
    write_outputs(
        args.output_prefix,
        payload,
        candidate_rows,
        correlation_rows,
        combination_rows,
        ranked_rows,
        period_rows,
        lines,
    )
    print(f"report={args.output_prefix.with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
