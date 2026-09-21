#!/usr/bin/env python3
"""Offline local reproduction for three Quantocracy-sourced candidates.

The script reads only the cached Tushare qfq/full-A snapshots.  It never
contacts Tushare or PandaAI.  Candidates are run one per process so the full
panel can be released before the next candidate starts.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from machine_profile import resolve_machine_profile  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_START,
    alignment_config_snapshot,
    annualized_turnover_cost,
    validate_alignment_config,
)
from positive_factor_local_compare import (  # noqa: E402
    compact_full_a_frame,
    grouped_rolling,
    panel_close,
    rolling_rsquare,
)
from qtld60_local_reproduction import (  # noqa: E402
    detect_cache_end,
    load_calendar,
    memory_guard,
)


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
FORMAL_START = pd.Timestamp(ALIGNMENT_START)
FORMAL_END = pd.Timestamp(ALIGNMENT_END)
RECENT_START = pd.Timestamp("20260101")
MID_START = pd.Timestamp("20260601")
CYCLE = 10
GROUPS = ALIGNMENT_GROUPS
MONTH_DAYS = 21
SKIP_RECENT_DAYS = 21
FORMATION_DAYS = 231
MOMENTUM_BUCKETS = 5
MAX_RSS_GB = 2.60
MIN_AVAILABLE_GB = 3.00

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "quantocracy-local-reproduction-20260920"
)


CANDIDATES: dict[str, dict[str, Any]] = {
    "price_path_convexity": {
        "formula": (
            "(((P_first + P_last) / 2) - MEAN(P_daily)) "
            "/ ((P_first + P_last) / 2)"
        ),
        "evaluation_formula": "-price_path_convexity (low source value is long)",
        "direction": 0,
        "source": "https://aligrithm.com/price-path-convexity-a-new-cross-sectional-anomaly-45bp-per-s-2/",
        "note": (
            "The source is monthly and uses daily dollar closes. The local "
            "10-day evaluator uses a trailing 21-trading-day path as the "
            "one-month proxy; the source low-convexity side is held long."
        ),
    },
    "trend_clarity_momentum": {
        "formula": "MOM12-1 = CLOSE[t-21]/CLOSE[t-252]-1; TC = rolling R2(CLOSE,231).shift(21)",
        "evaluation_formula": "5 momentum buckets, then TC percentile as a tie-break proxy",
        "direction": 1,
        "source": "https://alphaarchitect.com/2024/05/momentum-and-the-clarity-of-the-trend/",
        "note": (
            "The source double-sorts momentum and trend clarity. The local "
            "scalar proxy keeps the five momentum buckets primary and uses "
            "TC percentile within each bucket, so it is not a byte-level "
            "reproduction of the source two-way portfolio table."
        ),
    },
    "frog_in_pan_momentum": {
        "formula": "FIP = (N_up - N_down) / N_total with MOM12-1",
        "evaluation_formula": "5 momentum buckets, then FIP percentile as a tie-break proxy",
        "direction": 1,
        "source": "https://alphaarchitect.com/2015/11/23/frog-in-the-pan-identifying-the-highest-quality-momentum-stocks/",
        "note": (
            "FIP is the sign-reversed information-discreteness measure. The "
            "local proxy combines it with the same MOM12-1 five-bucket "
            "primary sort and reports high-FIP/high-momentum names."
        ),
    },
}


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if value is pd.NA:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number * 100.0 if np.isfinite(number) else None


def grouped_shift(frame: pd.DataFrame, values: pd.Series, periods: int) -> pd.Series:
    return values.groupby(frame["instrument"], sort=False, observed=True).shift(periods)


def rolling_sum(frame: pd.DataFrame, values: pd.Series, window: int) -> pd.Series:
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")
    return grouped_rolling(work, "_value", window, "sum")


def generated_signal_dates(
    calendar: list[pd.Timestamp], start: pd.Timestamp, end: pd.Timestamp
) -> list[pd.Timestamp]:
    positions = {date: index for index, date in enumerate(calendar)}
    if start not in positions:
        raise RuntimeError(f"Signal anchor is not a trading day: {start.date()}")
    anchor = positions[start]
    dates: list[pd.Timestamp] = []
    for position in range(anchor, len(calendar), CYCLE):
        date = calendar[position]
        if date > end:
            break
        if position + ALIGNMENT_LABEL_OFFSET + CYCLE < len(calendar):
            dates.append(date)
    return dates


def signal_rank(
    frame: pd.DataFrame, values: pd.Series, signal_dates: list[pd.Timestamp]
) -> pd.Series:
    mask = frame["date"].isin(signal_dates)
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    selected = pd.to_numeric(values.loc[mask], errors="coerce")
    ranked = selected.groupby(
        frame.loc[mask, "date"], sort=False, observed=True
    ).rank(method="average", pct=True)
    result.loc[mask] = ranked.to_numpy(dtype=float)
    return result


def build_momentum_quality_proxy(
    frame: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    quality: str,
) -> tuple[pd.Series, dict[str, Any]]:
    close = pd.to_numeric(frame["close_qfq"], errors="coerce")
    lag_one = grouped_shift(frame, close, 1)
    lag_skip = grouped_shift(frame, close, SKIP_RECENT_DAYS)
    lag_start = grouped_shift(frame, close, SKIP_RECENT_DAYS + FORMATION_DAYS)
    momentum = lag_skip.div(lag_start).sub(1.0)

    if quality == "trend_clarity_momentum":
        quality_raw = rolling_rsquare(frame, close, FORMATION_DAYS)
        quality_raw = grouped_shift(frame, quality_raw, SKIP_RECENT_DAYS)
        quality_name = "TC rolling price-vs-time R2"
    elif quality == "frog_in_pan_momentum":
        returns = close.div(lag_one).sub(1.0)
        up = returns.gt(0).astype(float)
        down = returns.lt(0).astype(float)
        valid = returns.notna().astype(float)
        up_count = rolling_sum(frame, up, FORMATION_DAYS)
        down_count = rolling_sum(frame, down, FORMATION_DAYS)
        valid_count = rolling_sum(frame, valid, FORMATION_DAYS)
        quality_raw = grouped_shift(
            frame,
            up_count.sub(down_count).div(valid_count.replace(0.0, np.nan)),
            SKIP_RECENT_DAYS,
        )
        quality_name = "FIP=(N_up-N_down)/N_total"
        del returns, up, down, valid, up_count, down_count, valid_count
    else:
        raise ValueError(f"Unsupported quality proxy: {quality}")

    momentum_rank = signal_rank(frame, momentum, signal_dates)
    quality_rank = signal_rank(frame, quality_raw, signal_dates)
    momentum_bucket = np.ceil(momentum_rank * MOMENTUM_BUCKETS)
    score = momentum_bucket.add(quality_rank / 100.0)
    score = score.where(momentum_rank.notna() & quality_rank.notna())
    metadata = {
        "momentum_definition": "CLOSE[t-21] / CLOSE[t-252] - 1",
        "formation_days": FORMATION_DAYS,
        "skip_recent_days": SKIP_RECENT_DAYS,
        "primary_sort": f"{MOMENTUM_BUCKETS} equal-sized momentum buckets",
        "secondary_sort": quality_name,
        "scalar_proxy": "momentum_bucket + quality_percentile / 100",
    }
    del close, lag_one, lag_skip, lag_start, momentum, quality_raw
    del momentum_rank, quality_rank, momentum_bucket
    gc.collect()
    return score, metadata


def build_candidate(
    frame: pd.DataFrame, candidate: str, signal_dates: list[pd.Timestamp]
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    close = pd.to_numeric(frame["close_qfq"], errors="coerce")
    spec = CANDIDATES[candidate]
    if candidate == "price_path_convexity":
        work = frame[["instrument"]].copy()
        work["_close"] = close
        mean_path = grouped_rolling(work, "_close", MONTH_DAYS, "mean")
        first_close = grouped_shift(frame, close, MONTH_DAYS - 1)
        midpoint = first_close.add(close).div(2.0)
        raw = midpoint.sub(mean_path).div(midpoint.replace(0.0, np.nan))
        evaluated = raw.mul(-1.0)
        metadata = {
            "path_window_days": MONTH_DAYS,
            "source_direction": "low convexity is long",
            "source_formula": spec["formula"],
            "evaluation_formula": spec["evaluation_formula"],
        }
        del work, mean_path, first_close, midpoint
    else:
        evaluated, metadata = build_momentum_quality_proxy(
            frame, signal_dates, candidate
        )
        raw = evaluated.copy()
        metadata.update(
            {
                "source_formula": spec["formula"],
                "evaluation_formula": spec["evaluation_formula"],
            }
        )
    signal_mask = frame["date"].isin(signal_dates)
    raw = raw.where(signal_mask)
    evaluated = evaluated.where(signal_mask)
    raw = raw.replace([np.inf, -np.inf], np.nan)
    evaluated = evaluated.replace([np.inf, -np.inf], np.nan)
    del close
    gc.collect()
    return raw, evaluated, metadata


def _assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return pd.Series(
        np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS),
        index=values.index,
    )


def _corr(left: pd.Series, right: pd.Series, method: str) -> float | None:
    value = left.corr(right, method=method)
    return None if pd.isna(value) else float(value)


def evaluate_candidate(
    frame: pd.DataFrame,
    raw_factor: pd.Series,
    evaluated_factor: pd.Series,
    close: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    source_direction: int,
) -> dict[str, Any]:
    positions = {date: index for index, date in enumerate(calendar)}
    signal_mask = frame["date"].isin(signal_dates)
    data = frame.loc[signal_mask, ["date", "instrument"]].copy()
    data["raw_factor"] = raw_factor.loc[signal_mask].to_numpy(dtype=float)
    data["evaluated_factor"] = evaluated_factor.loc[signal_mask].to_numpy(dtype=float)
    data = data.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["raw_factor", "evaluated_factor"]
    )

    source_selected_group = GROUPS if source_direction == 1 else 1
    # All evaluated factors are oriented so that higher means long.  The
    # source-direction group is retained separately for transparent reporting.
    evaluated_selected_group = GROUPS
    previous_selected: set[str] | None = None
    selected_excesses: list[float] = []
    selected_turnovers: list[float] = []
    source_rank_ics: list[float] = []
    evaluated_rank_ics: list[float] = []
    source_ics: list[float] = []
    evaluated_ics: list[float] = []
    group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    period_count = 0
    stock_counts: list[int] = []

    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        position = positions[date]
        current_position = position + ALIGNMENT_LABEL_OFFSET
        future_position = current_position + CYCLE
        if future_position >= len(calendar):
            continue
        symbols = current["instrument"].astype(str)
        current_close = close.iloc[current_position].reindex(symbols).to_numpy(dtype=float)
        future_close = close.iloc[future_position].reindex(symbols).to_numpy(dtype=float)
        current["forward_return"] = future_close / current_close - 1.0
        current = current.replace([np.inf, -np.inf], np.nan).dropna(
            subset=["raw_factor", "evaluated_factor", "forward_return"]
        )
        if len(current) < GROUPS * 10:
            continue

        source_rank_ic = _corr(
            current["raw_factor"].rank(method="average"),
            current["forward_return"].rank(method="average"),
            "pearson",
        )
        evaluated_rank_ic = _corr(
            current["evaluated_factor"].rank(method="average"),
            current["forward_return"].rank(method="average"),
            "pearson",
        )
        source_ic = _corr(current["raw_factor"], current["forward_return"], "pearson")
        evaluated_ic = _corr(
            current["evaluated_factor"], current["forward_return"], "pearson"
        )
        if source_rank_ic is not None:
            source_rank_ics.append(source_rank_ic)
        if evaluated_rank_ic is not None:
            evaluated_rank_ics.append(evaluated_rank_ic)
        if source_ic is not None:
            source_ics.append(source_ic)
        if evaluated_ic is not None:
            evaluated_ics.append(evaluated_ic)
        current["group"] = _assign_groups(current["evaluated_factor"])
        benchmark = float(current["forward_return"].mean())
        members = set(
            current.loc[
                current["group"].eq(evaluated_selected_group), "instrument"
            ].astype(str)
        )
        selected_return = float(
            current.loc[
                current["group"].eq(evaluated_selected_group), "forward_return"
            ].mean()
        )
        selected_excesses.append(selected_return - benchmark)
        if previous_selected:
            selected_turnovers.append(
                1.0 - len(members.intersection(previous_selected)) / len(members)
            )
        previous_selected = members
        for group in range(1, GROUPS + 1):
            group_returns[group].append(
                float(current.loc[current["group"].eq(group), "forward_return"].mean())
            )
        period_count += 1
        stock_counts.append(len(current))

    if not period_count:
        raise RuntimeError("No valid evaluation periods")
    years = period_count * CYCLE / 252.0
    gross_excess = float(np.sum(selected_excesses) / years)
    turnover = float(np.mean(selected_turnovers)) if selected_turnovers else None
    annual_cost = annualized_turnover_cost(turnover, CYCLE, ALIGNMENT_ROUND_TRIP_COST)
    net_excess = gross_excess - annual_cost if annual_cost is not None else None
    average_group_returns = {
        group: float(np.mean(values)) if values else None
        for group, values in group_returns.items()
    }
    group_index = pd.Series(list(average_group_returns), dtype=float)
    group_values = pd.Series(
        [average_group_returns[group] for group in average_group_returns], dtype=float
    )
    monotonicity_evaluated = _corr(group_index, group_values, "spearman")
    orientation = 1.0 if source_direction == 1 else -1.0
    monotonicity_source = (
        None
        if monotonicity_evaluated is None
        else orientation * monotonicity_evaluated
    )

    def finite_mean(values: list[float]) -> float | None:
        valid = [value for value in values if np.isfinite(value)]
        return float(np.mean(valid)) if valid else None

    return {
        "periods": period_count,
        "stock_count_mean": float(np.mean(stock_counts)),
        "source_rank_ic": finite_mean(source_rank_ics),
        "rank_ic": finite_mean(evaluated_rank_ics),
        "source_ic_mean": finite_mean(source_ics),
        "ic_mean": finite_mean(evaluated_ics),
        "monotonicity_source": monotonicity_source,
        "monotonicity": monotonicity_evaluated,
        "selected_group": source_selected_group,
        "evaluated_selected_group": evaluated_selected_group,
        "gross_excess": gross_excess,
        "turnover": turnover,
        "annual_cost": annual_cost,
        "net_excess": net_excess,
        "group_mean_returns": average_group_returns,
    }


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "periods",
        "stock_count_mean",
        "source_rank_ic",
        "rank_ic",
        "source_ic_mean",
        "ic_mean",
        "monotonicity_source",
        "monotonicity",
        "selected_group",
        "gross_excess",
        "turnover",
        "annual_cost",
        "net_excess",
        "group_mean_returns",
    )
    return {key: result.get(key) for key in keys}


def run_candidate(args: argparse.Namespace) -> int:
    spec = CANDIDATES[args.candidate]
    output_root = args.output.resolve()
    result_dir = output_root / "candidates"
    result_path = result_dir / f"{args.candidate}.json"
    if result_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing result: {result_path}")

    alignment = alignment_config_snapshot()
    validate_alignment_config(alignment)
    if not (PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT).is_file():
        raise SystemExit(f"Missing alignment rules: {ALIGNMENT_RULES_DOCUMENT}")
    data_end = (
        pd.Timestamp(pd.to_datetime(args.data_end, format="%Y%m%d"))
        if args.data_end
        else detect_cache_end(args.cap_root)
    ).normalize()
    if data_end < FORMAL_END:
        raise SystemExit(
            f"Local data end {data_end.date()} is earlier than formal end {FORMAL_END.date()}"
        )

    print(
        f"candidate={args.candidate} cycle={CYCLE} data={DATA_START.date()}..{data_end.date()}",
        flush=True,
    )
    memory_guard("start", args.max_rss_gb, args.min_available_gb)
    frame = load_full_a_data(
        args.price_root,
        args.cap_root,
        DATA_START,
        data_end,
        market_cap_field=ALIGNMENT_MARKET_CAP_FIELD,
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    frame, _categories = compact_full_a_frame(frame)
    latest_data_date = pd.Timestamp(frame["date"].max()).normalize()
    calendar = load_calendar(args.calendar_root, DATA_START, latest_data_date)
    if latest_data_date > calendar[-1]:
        latest_data_date = calendar[-1]
    all_dates = generated_signal_dates(calendar, FORMAL_START, latest_data_date)
    windows = {
        "formal_5y": [date for date in all_dates if date <= FORMAL_END],
        "recent_2026": [
            date for date in all_dates if RECENT_START <= date <= latest_data_date
        ],
        "since_2026_06_01": [
            date for date in all_dates if MID_START <= date <= latest_data_date
        ],
    }
    if any(not dates for dates in windows.values()):
        raise RuntimeError("No usable formal, recent, or 2026-06-01 signal dates")
    signal_dates = sorted(set(date for dates in windows.values() for date in dates))
    print(
        f"local_rows={len(frame)} instruments={frame['instrument'].nunique()} "
        f"signal_dates={len(signal_dates)} formal={len(windows['formal_5y'])} "
        f"recent={len(windows['recent_2026'])} mid={len(windows['since_2026_06_01'])}",
        flush=True,
    )
    memory_guard("loaded_market", args.max_rss_gb, args.min_available_gb)

    raw_factor, evaluated_factor, factor_metadata = build_candidate(
        frame, args.candidate, signal_dates
    )
    memory_guard("built_factor", args.max_rss_gb, args.min_available_gb)
    close = panel_close(frame, calendar)
    memory_guard("built_close_panel", args.max_rss_gb, args.min_available_gb)

    results: dict[str, dict[str, Any]] = {}
    for name, dates in windows.items():
        result = evaluate_candidate(
            frame,
            raw_factor,
            evaluated_factor,
            close,
            dates,
            calendar,
            int(spec["direction"]),
        )
        results[name] = compact_result(result)
        print(
            f"window={name} periods={result['periods']} "
            f"rank_ic={result['rank_ic']!s} "
            f"net_excess={pct(result['net_excess'])!s}% "
            f"turnover={pct(result['turnover'])!s}%",
            flush=True,
        )
        memory_guard(f"after_{name}", args.max_rss_gb, args.min_available_gb)

    machine = resolve_machine_profile()
    payload = {
        "candidate": args.candidate,
        "spec": spec,
        "factor_metadata": factor_metadata,
        "settings": {
            "machine_profile": machine["machine_profile"],
            "machine_label": machine["machine_label"],
            "data_provider": "Tushare",
            "network_access": "none",
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_config": alignment,
            "data_start": DATA_START,
            "formal_start": FORMAL_START,
            "formal_end": FORMAL_END,
            "recent_start": RECENT_START,
            "mid_start": MID_START,
            "local_data_end": latest_data_date,
            "universe": "full_a",
            "price_mode": ALIGNMENT_PRICE_MODE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "groups": GROUPS,
            "cycle": CYCLE,
            "label_offset": ALIGNMENT_LABEL_OFFSET,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "benchmark_mode": "factor_valid",
            "signal_schedule": "generated_calendar_10d_anchor_2021-09-07",
            "rows": len(frame),
            "instruments": int(frame["instrument"].nunique()),
            "formal_signal_periods": len(windows["formal_5y"]),
            "recent_signal_periods": len(windows["recent_2026"]),
            "mid_signal_periods": len(windows["since_2026_06_01"]),
        },
        "results": results,
    }
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    print(f"result={result_path}", flush=True)
    del raw_factor, evaluated_factor, close, frame
    gc.collect()
    return 0


def load_results(output_root: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        path = output_root / "candidates" / f"{candidate}.json"
        if path.is_file():
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def aggregate(args: argparse.Namespace) -> int:
    output_root = args.output.resolve()
    payloads = load_results(output_root)
    if len(payloads) != len(CANDIDATES):
        present = {payload["candidate"] for payload in payloads}
        missing = sorted(set(CANDIDATES).difference(present))
        raise SystemExit(f"Missing candidate results: {', '.join(missing)}")
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "quantocracy_local_reproduction.json"
    csv_path = output_root / "quantocracy_local_reproduction.csv"
    md_path = output_root / "quantocracy_local_reproduction.md"
    if not args.overwrite and any(path.exists() for path in (json_path, csv_path, md_path)):
        raise SystemExit(f"Refusing to overwrite aggregate files under {output_root}")

    rows: list[dict[str, Any]] = []
    for payload in payloads:
        for window, result in payload["results"].items():
            rows.append(
                {
                    "candidate": payload["candidate"],
                    "formula": payload["spec"]["formula"],
                    "window": window,
                    **result,
                    "source_rank_ic": result.get("source_rank_ic"),
                    "oriented_rank_ic": result.get("rank_ic"),
                    "source_ic_mean": result.get("source_ic_mean"),
                    "oriented_ic_mean": result.get("ic_mean"),
                    "gross_excess_pct": pct(result.get("gross_excess")),
                    "net_excess_pct": pct(result.get("net_excess")),
                    "turnover_pct": pct(result.get("turnover")),
                    "annual_cost_pct": pct(result.get("annual_cost")),
                }
            )
    json_path.write_text(
        json.dumps(
            {
                "alignment_rule_version": ALIGNMENT_RULE_VERSION,
                "machine_profile": payloads[0]["settings"]["machine_profile"],
                "machine_label": payloads[0]["settings"]["machine_label"],
                "data_provider": "Tushare",
                "network_access": "none",
                "candidates": payloads,
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
        + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(rows[0])
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    order = {"formal_5y": 0, "recent_2026": 1, "since_2026_06_01": 2}

    def show(value: Any, digits: int = 2) -> str:
        return "n/a" if value is None else f"{float(value):.{digits}f}%"

    def show_ic(value: Any) -> str:
        return "n/a" if value is None else f"{float(value):.4f}"

    lines = [
        "# Quantocracy candidates: local reproduction",
        "",
        f"Machine: `{payloads[0]['settings']['machine_profile']}` ({payloads[0]['settings']['machine_label']}).",
        "No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.",
        f"Alignment rule: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        "Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+cycle+1)`; 10 groups; `factor_valid`; one-way cost `0.30%`.",
        f"Formal window: `{FORMAL_START.date()}..{FORMAL_END.date()}`. Diagnostics: `{RECENT_START.date()}+` and `{MID_START.date()}+`.",
        "Signal schedule: every 10 trading days anchored at `2021-09-07`; diagnostics are not mixed into formal ranking.",
        "",
        "## Results",
        "",
        "`source RankIC/IC` use the source-sign formula. `oriented RankIC/IC` use the traded long direction. Monotonicity is a local group-return Spearman proxy, not a PandaAI byte-level field equivalent.",
        "",
        "| candidate | window | periods | source RankIC | oriented RankIC | source IC | oriented IC | source monotonicity | oriented monotonicity | gross excess | net excess | turnover | annual cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: (item["candidate"], order[item["window"]])):
        lines.append(
            f"| `{row['candidate']}` | `{row['window']}` | {row['periods']} | "
            f"{show_ic(row.get('source_rank_ic'))} | {show_ic(row.get('oriented_rank_ic'))} | "
            f"{show_ic(row.get('source_ic_mean'))} | {show_ic(row.get('oriented_ic_mean'))} | "
            f"{show_ic(row.get('monotonicity_source'))} | {show_ic(row.get('monotonicity'))} | "
            f"{show(row.get('gross_excess_pct'))} | {show(row.get('net_excess_pct'))} | "
            f"{show(row.get('turnover_pct'))} | {show(row.get('annual_cost_pct'))} |"
        )
    lines.extend(["", "## Candidate definitions", ""])
    for payload in payloads:
        spec = payload["spec"]
        lines.extend(
            [
                f"### `{payload['candidate']}`",
                "",
                f"- Source formula: `{spec['formula']}`",
                f"- Local evaluated formula: `{spec['evaluation_formula']}`",
                f"- Source: [{spec['source']}]({spec['source']})",
                f"- Fidelity note: {spec['note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation",
            "",
            "These are offline China A-share diagnostics on cached Tushare data. The source studies use different markets, universes, rebalance timing, weighting and holding rules; a positive local result is a screening signal, not platform validation.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"json={json_path}", flush=True)
    print(f"csv={csv_path}", flush=True)
    print(f"md={md_path}", flush=True)
    for payload in payloads:
        print(
            f"summary={payload['candidate']} "
            f"formal_net={pct(payload['results']['formal_5y'].get('net_excess'))}% "
            f"recent_net={pct(payload['results']['recent_2026'].get('net_excess'))}% "
            f"mid_net={pct(payload['results']['since_2026_06_01'].get('net_excess'))}%",
            flush=True,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument(
        "--price-root",
        type=Path,
        default=PROJECT_ROOT
        / ".tushare-refresh-20260918-v2"
        / "tushare_factor_recheck"
        / "qfq"
        / "daily_batches",
    )
    parser.add_argument(
        "--cap-root",
        type=Path,
        default=PROJECT_ROOT
        / ".tushare-refresh-20260918-v2"
        / "tushare_factor_recheck"
        / "daily_basic_full_a",
    )
    parser.add_argument(
        "--calendar-root",
        type=Path,
        default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "trade_calendar",
    )
    parser.add_argument("--data-end", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=MAX_RSS_GB)
    parser.add_argument("--min-available-gb", type=float, default=MIN_AVAILABLE_GB)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.aggregate:
        return aggregate(args)
    if not args.candidate:
        parser.error("choose --candidate or use --aggregate")
    return run_candidate(args)


if __name__ == "__main__":
    raise SystemExit(main())
