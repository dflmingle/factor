#!/usr/bin/env python3
"""Exhaustively compare every non-empty subset of 12 factor representatives.

This is an offline local proxy. It reads the canonical full-A cache and saved
platform metadata, evaluates every one of the 2**12 - 1 subsets on a common
10-day signal schedule, and never creates a PandaAI factor or calls the
platform.

The twelve inputs are the positive-net, single-mechanism representatives used
in the 2026-09-19 cluster expansion. Some saved platform records were
originally run at five days; their formula signals are still evaluated here at
the common ten-day schedule so that portfolio comparisons are well-defined.
The source cycle and alignment quality are retained as metadata and are not
treated as comparable platform performance.
"""

from __future__ import annotations

import argparse
import csv
import gc
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata

try:
    from numba import njit, prange
except ImportError:  # pragma: no cover - the project environment has numba
    njit = None
    prange = range

try:
    import torch
except Exception:  # pragma: no cover - numpy fallback remains available
    torch = None


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
    SCHEDULE_SPECS,
    START,
    build_schedules,
    cross_sectional_scores,
    daily_correlations,
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
    ALIGNMENT_ROUND_TRIP_COST,
    alignment_config_snapshot,
    validate_alignment_config,
)
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    forward_returns,
    panel_close,
    saved_records,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


TRAIN_END = pd.Timestamp("2024-09-06")
RECENT_START = pd.Timestamp("2026-01-01")
COMMON_CYCLE = 10

DEFAULT_ALIGNMENT_REPORT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports"
    / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/exhaustive-representative-combination-20260920"
)


# These are deliberately explicit. The cluster expansion has composites and
# unsupported records, so deriving this list from every positive record would
# reintroduce those records into an ostensibly independent search.
CANDIDATE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "SIZE",
        "handler": "size_only",
        "direction": 0,
        "cluster": "B01",
        "source_id": "size-only-20260911-candidates.report:SIZE-ONLY-20260911",
    },
    {
        "key": "H03",
        "handler": "impact60",
        "direction": 1,
        "cluster": "B01",
        "source_id": "h03-t10-single-20260911-candidates.report:H03-T10-SINGLE",
    },
    {
        "key": "TURN",
        "handler": "turn_bias",
        "direction": 0,
        "cluster": "B02",
        "source_id": "positive-cycle10-candidates.report:HT13-TURN-BIAS-1M",
    },
    {
        "key": "RET40",
        "handler": "reversal40",
        "direction": 1,
        "cluster": "B03",
        "source_id": "positive-cycle10-candidates.report:OSR2-RET40",
    },
    {
        "key": "DD120",
        "handler": "drawdown120",
        "direction": 1,
        "cluster": "B04",
        "source_id": "positive-cycle10-candidates.report:OSR2-DD120",
    },
    {
        "key": "CHIP250",
        "handler": "chip250",
        "direction": 1,
        "cluster": "B05",
        "source_id": "nonht-report-directions-20260909-formula.report:NONHT-CHIP-COST-250",
    },
    {
        "key": "EVEBITDA",
        "handler": "ev_ebitda_proxy",
        "direction": 1,
        "cluster": "B07",
        "source_id": "high-potential-5-20260910-candidates.report:NEW-VALUE-EVEBITDA",
    },
    {
        "key": "BM",
        "handler": "value_bm",
        "direction": 1,
        "cluster": "B08",
        "source_id": "huatai-series13-candidates.report:HT13-VALUE-BP",
    },
    {
        "key": "DD60",
        "handler": "drawdown60",
        "direction": 1,
        "cluster": "B09",
        "source_id": "oversold-rebound-recovery-candidates.report:OSR2-DD60",
    },
    {
        "key": "ASSET_GROWTH",
        "handler": "asset_growth",
        "direction": 0,
        "cluster": "B10",
        "source_id": "paper-derived-full.report:paper-derived-asset-growth",
    },
    {
        "key": "RESVOL",
        "handler": "residual_volatility",
        "direction": 1,
        "cluster": "B11",
        "source_id": "nonhuatai-factor-6-20260909.report:NONHT-RESVOL-LOW",
    },
    {
        "key": "SP",
        "handler": "value_sp",
        "direction": 1,
        "cluster": "B12",
        "source_id": "huatai-series13-candidates.report:HT13-VALUE-SP",
    },
)


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if pd.isna(value):
        return None
    return value


def _format(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(parsed):
        return "n/a"
    return f"{parsed:.2f}{suffix}" if suffix else f"{parsed:.4f}"


def _competition_cross_sectional_scores(
    signal_frame: pd.DataFrame,
    raw_values: dict[str, pd.Series],
    candidates: list[dict[str, Any]],
) -> pd.DataFrame:
    """Approximate the competition pool's per-factor Winsorize/Z-score step.

    The public rule specifies 1%-99% cross-sectional Winsorization followed by
    Z-score and equal weighting.  The platform's exact missing-value and
    standard-deviation implementation is not exposed, so this keeps finite
    rows, uses population standard deviation, and leaves missing values as NaN
    for the portfolio evaluator to exclude consistently.
    """
    grouped = signal_frame.groupby("date", sort=True, observed=True).indices
    score_columns: dict[str, pd.Series] = {}
    for candidate in candidates:
        handler = str(candidate["handler"])
        oriented = pd.to_numeric(raw_values[handler], errors="coerce").to_numpy(dtype=float)
        if int(candidate["direction"]) == 0:
            oriented = -oriented
        result = np.full(len(signal_frame), np.nan, dtype=float)
        for positions in grouped.values():
            positions = np.asarray(positions, dtype=np.int64)
            values = oriented[positions]
            finite = np.isfinite(values)
            if int(finite.sum()) < 3:
                continue
            valid_values = values[finite]
            lower, upper = np.quantile(valid_values, [0.01, 0.99])
            clipped = np.clip(valid_values, lower, upper)
            mean = float(clipped.mean())
            std = float(clipped.std(ddof=0))
            if not np.isfinite(std) or std <= 1.0e-12:
                result[positions[finite]] = 0.0
            else:
                result[positions[finite]] = (clipped - mean) / std
        score_columns[str(candidate["key"])] = pd.Series(
            result, index=signal_frame.index, dtype=float
        )
    return pd.DataFrame(score_columns, index=signal_frame.index)


def _load_candidates(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    settings = payload.get("settings") or {}
    if settings.get("alignment_rule_version") != ALIGNMENT_RULE_VERSION:
        raise ValueError("alignment report uses a different rule version")
    if settings.get("platform_net_filter") != "all":
        raise ValueError("the alignment report must be the canonical all-record report")
    records = {str(item.get("id")): item for item in payload.get("results", [])}
    candidates: list[dict[str, Any]] = []
    for spec in CANDIDATE_SPECS:
        source = records.get(str(spec["source_id"]))
        if source is None:
            raise KeyError(f"candidate source record not found: {spec['source_id']}")
        platform_net = _finite(source.get("platform_net_excess_pct"))
        if platform_net is None or platform_net <= 0.0:
            raise ValueError(f"candidate is not platform-positive: {spec['source_id']}")
        candidate = dict(spec)
        candidate.update(
            {
                "name": source.get("name"),
                "formula": source.get("formula"),
                "source_handler": source.get("handler"),
                "source_cycle": source.get("cycle"),
                "platform_configured_cycle": source.get("platform_configured_cycle"),
                "platform_direction": source.get("platform_factor_direction"),
                "platform_net_excess_pct": platform_net,
                "local_net_excess_pct": (
                    None
                    if source.get("local_net_excess") is None
                    else float(source["local_net_excess"]) * 100.0
                ),
                "alignment_quality": source.get("alignment_quality"),
                "local_mining_eligible": bool(source.get("local_mining_eligible")),
                "fidelity": source.get("fidelity"),
                "alignment_quality_reason": source.get("alignment_quality_reason"),
            }
        )
        if candidate["source_handler"] != candidate["handler"]:
            raise ValueError(
                f"handler mismatch for {candidate['key']}: "
                f"{candidate['source_handler']} != {candidate['handler']}"
            )
        candidate["candidate_key"] = str(candidate["key"])
        candidate["platform_direction_source"] = (
            "manual_cluster_record_direction"
            if candidate["platform_direction"] is None
            else "saved_platform_direction"
        )
        # The direction used by this common-cycle comparison is explicit even
        # when an older saved record omitted its direction field.
        candidate["platform_factor_direction"] = int(candidate["direction"])
        candidates.append(candidate)
    return payload, candidates


def _common_schedule(calendar: list[pd.Timestamp]) -> list[pd.Timestamp]:
    supported, _ = saved_records(formula_catalog(), "positive")
    schedules = build_schedules(supported, calendar)
    if COMMON_CYCLE not in schedules:
        raise RuntimeError("the saved ten-day schedule is unavailable")
    return schedules[COMMON_CYCLE]


def _build_blocks(
    signal_frame: pd.DataFrame,
    score_frame: pd.DataFrame,
    returns: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    keys: list[str],
) -> list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]]:
    return_index = returns.set_index(["date", "instrument"])["forward_return"]
    row_keys = pd.MultiIndex.from_frame(signal_frame[["date", "instrument"]])
    forward = pd.to_numeric(return_index.reindex(row_keys), errors="coerce").to_numpy()
    score_values = score_frame.loc[:, keys].to_numpy(dtype=float)
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


def _flatten_blocks(
    blocks: list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]],
    candidate_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    dates = np.asarray([block[0].to_datetime64() for block in blocks], dtype="datetime64[ns]")
    offsets = np.zeros(len(blocks) + 1, dtype=np.int64)
    for index, block in enumerate(blocks, start=1):
        offsets[index] = offsets[index - 1] + len(block[1])
    scores = np.concatenate([block[3] for block in blocks], axis=0).astype(np.float64)
    forward = np.concatenate([block[2] for block in blocks], axis=0).astype(np.float64)
    instruments_text = np.concatenate([block[1] for block in blocks], axis=0).astype(str)
    instruments, _ = pd.factorize(instruments_text, sort=True)
    instruments = instruments.astype(np.int32)
    if scores.shape[1] != candidate_count:
        raise RuntimeError("flattened score matrix has an unexpected column count")
    return dates, offsets, scores, forward, instruments, instruments_text


def _combination_catalog(keys: list[str]) -> tuple[list[int], np.ndarray, np.ndarray, list[str]]:
    total = (1 << len(keys)) - 1
    bitmasks = list(range(1, total + 1))
    masks = np.zeros((total, len(keys)), dtype=np.int8)
    sizes = np.zeros(total, dtype=np.int16)
    labels: list[str] = []
    for row, bitmask in enumerate(bitmasks):
        selected = [index for index in range(len(keys)) if bitmask & (1 << index)]
        masks[row, selected] = 1
        sizes[row] = len(selected)
        labels.append("+".join(keys[index] for index in selected))
    return bitmasks, masks, sizes, labels


if njit is not None:

    @njit(parallel=True, cache=False)
    def _evaluate_combinations_numba(
        scores: np.ndarray,
        forward: np.ndarray,
        instruments: np.ndarray,
        offsets: np.ndarray,
        masks: np.ndarray,
        sizes: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        combination_count = masks.shape[0]
        period_count = len(offsets) - 1
        held_returns = np.full((combination_count, period_count), np.nan)
        gross_excess = np.full((combination_count, period_count), np.nan)
        turnover = np.full((combination_count, period_count), np.nan)
        stock_counts = np.zeros((combination_count, period_count), dtype=np.int32)
        valid_period = np.zeros((combination_count, period_count), dtype=np.uint8)
        instrument_count = 0
        for value in instruments:
            if value + 1 > instrument_count:
                instrument_count = value + 1

        for combination in prange(combination_count):
            previous_marker = 0
            previous_seen = np.full(instrument_count, -1, dtype=np.int32)
            max_rows = 0
            for period in range(period_count):
                count = offsets[period + 1] - offsets[period]
                if count > max_rows:
                    max_rows = count
            work = np.empty(max_rows, dtype=np.float64)
            row_indices = np.empty(max_rows, dtype=np.int64)

            for period in range(period_count):
                start = offsets[period]
                end = offsets[period + 1]
                valid_count = 0
                benchmark_sum = 0.0
                for row in range(start, end):
                    return_value = forward[row]
                    if not np.isfinite(return_value):
                        continue
                    valid = True
                    score_sum = 0.0
                    for factor in range(masks.shape[1]):
                        if masks[combination, factor] == 1:
                            score_value = scores[row, factor]
                            if not np.isfinite(score_value):
                                valid = False
                                break
                            score_sum += score_value
                    if valid:
                        row_indices[valid_count] = row
                        # The tiny row-order term reproduces the stable sort
                        # used by the canonical Python evaluator when exact
                        # combination scores tie.
                        work[valid_count] = (
                            score_sum / sizes[combination]
                            + (row - start) * 1.0e-12
                        )
                        valid_count += 1
                        benchmark_sum += return_value

                if valid_count < GROUPS * 10:
                    continue
                cutoff = (valid_count * (GROUPS - 1)) // GROUPS
                partition = np.argpartition(work[:valid_count], cutoff)
                held_count = valid_count - cutoff
                held_sum = 0.0
                overlap = 0
                marker = period + 1
                for position in range(cutoff, valid_count):
                    local_index = partition[position]
                    row = row_indices[local_index]
                    held_sum += forward[row]
                    if previous_marker != 0 and previous_seen[instruments[row]] == previous_marker:
                        overlap += 1
                for position in range(cutoff, valid_count):
                    local_index = partition[position]
                    row = row_indices[local_index]
                    previous_seen[instruments[row]] = marker
                held = held_sum / held_count
                benchmark = benchmark_sum / valid_count
                held_returns[combination, period] = held
                gross_excess[combination, period] = held - benchmark
                if previous_marker != 0:
                    turnover[combination, period] = 1.0 - overlap / held_count
                stock_counts[combination, period] = valid_count
                valid_period[combination, period] = 1
                previous_marker = marker
        return held_returns, gross_excess, turnover, stock_counts, valid_period


def _evaluate_combinations_python(
    scores: np.ndarray,
    forward: np.ndarray,
    instruments: np.ndarray,
    offsets: np.ndarray,
    masks: np.ndarray,
    sizes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Small fallback for environments without numba."""
    combination_count = len(masks)
    period_count = len(offsets) - 1
    held_returns = np.full((combination_count, period_count), np.nan)
    gross_excess = np.full((combination_count, period_count), np.nan)
    turnover = np.full((combination_count, period_count), np.nan)
    stock_counts = np.zeros((combination_count, period_count), dtype=np.int32)
    valid_period = np.zeros((combination_count, period_count), dtype=np.uint8)
    for combination, mask in enumerate(masks):
        previous: set[int] | None = None
        for period in range(period_count):
            start, end = int(offsets[period]), int(offsets[period + 1])
            score_block = scores[start:end, mask.astype(bool)]
            return_block = forward[start:end]
            valid = np.isfinite(return_block) & np.isfinite(score_block).all(axis=1)
            if int(valid.sum()) < GROUPS * 10:
                continue
            valid_scores = score_block[valid].mean(axis=1)
            valid_scores += np.arange(len(valid_scores), dtype=float) * 1.0e-12
            valid_returns = return_block[valid]
            valid_instruments = instruments[start:end][valid]
            order = np.argsort(valid_scores, kind="stable")
            cutoff = (len(order) * (GROUPS - 1)) // GROUPS
            selected = order[cutoff:]
            members = set(valid_instruments[selected].tolist())
            if previous is not None:
                turnover[combination, period] = 1.0 - len(members & previous) / len(members)
            previous = members
            held_returns[combination, period] = float(valid_returns[selected].mean())
            gross_excess[combination, period] = float(
                valid_returns[selected].mean() - valid_returns.mean()
            )
            stock_counts[combination, period] = int(valid.sum())
            valid_period[combination, period] = 1
    return held_returns, gross_excess, turnover, stock_counts, valid_period


def _evaluate_combinations_torch(
    scores: np.ndarray,
    forward: np.ndarray,
    instruments: np.ndarray,
    offsets: np.ndarray,
    masks: np.ndarray,
    sizes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """CPU-vectorized evaluator used when the local Numba is incompatible.

    Torch computes all combination scores in chunks and ``topk`` extracts only
    the held decile. Previous held sets stay in a NumPy marker matrix so
    turnover uses the same membership-overlap definition as the canonical
    evaluator without materializing a 4095 x date x stock cube.
    """
    if torch is None:
        return _evaluate_combinations_python(scores, forward, instruments, offsets, masks, sizes)
    thread_count = os.cpu_count() or 4
    torch.set_num_threads(max(1, min(int(thread_count), 8)))
    score_tensor = torch.from_numpy(scores)
    forward_tensor = torch.from_numpy(forward)
    weight_tensor = torch.from_numpy(
        masks.astype(np.float64) / sizes.astype(np.float64)[:, None]
    ).T.contiguous()
    combination_count = len(masks)
    period_count = len(offsets) - 1
    held_returns = np.full((combination_count, period_count), np.nan)
    gross_excess = np.full((combination_count, period_count), np.nan)
    turnover = np.full((combination_count, period_count), np.nan)
    stock_counts = np.zeros((combination_count, period_count), dtype=np.int32)
    valid_period = np.zeros((combination_count, period_count), dtype=np.uint8)
    instrument_count = int(instruments.max()) + 1 if len(instruments) else 0
    previous_seen = np.full((combination_count, instrument_count), -1, dtype=np.int32)
    previous_marker = np.zeros(combination_count, dtype=np.int32)
    row_epsilon_cache: dict[int, Any] = {}
    chunk_size = 256

    for period in range(period_count):
        start, end = int(offsets[period]), int(offsets[period + 1])
        score_block = score_tensor[start:end]
        return_block = forward_tensor[start:end]
        row_count = end - start
        row_epsilon = row_epsilon_cache.get(row_count)
        if row_epsilon is None:
            row_epsilon = torch.arange(row_count, dtype=torch.float64) * 1.0e-12
            row_epsilon_cache[row_count] = row_epsilon
        finite_scores = torch.isfinite(score_block)
        finite_returns = torch.isfinite(return_block)
        safe_scores = torch.nan_to_num(score_block, nan=0.0, posinf=0.0, neginf=0.0)
        safe_returns = torch.nan_to_num(return_block, nan=0.0, posinf=0.0, neginf=0.0)
        instrument_block = instruments[start:end]

        for left in range(0, combination_count, chunk_size):
            right = min(left + chunk_size, combination_count)
            weights = weight_tensor[:, left:right]
            mask_chunk = torch.from_numpy(masks[left:right].astype(np.float64).T)
            size_chunk = sizes[left:right]
            selected_score_counts = torch.matmul(finite_scores.to(torch.float64), mask_chunk)
            size_tensor = torch.from_numpy(size_chunk.astype(np.float64))
            valid = finite_returns[:, None] & (
                selected_score_counts == size_tensor[None, :]
            )
            valid_counts = valid.sum(dim=0)
            count_np = valid_counts.cpu().numpy().astype(np.int32)
            usable = count_np >= GROUPS * 10
            if not bool(usable.any()):
                continue

            combination_scores = torch.matmul(safe_scores, weights) + row_epsilon[:, None]
            combination_scores = combination_scores.masked_fill(~valid, -torch.inf)
            top_counts = count_np - (count_np * (GROUPS - 1) // GROUPS)
            max_top = int(top_counts[usable].max())
            top_values, top_indices = torch.topk(
                combination_scores, k=max_top, dim=0, largest=True, sorted=False
            )
            position_mask_np = (
                np.arange(max_top, dtype=np.int32)[:, None] < top_counts[None, :]
            )
            position_mask = torch.from_numpy(position_mask_np)
            returns_matrix = safe_returns[:, None].expand(row_count, right - left)
            held_sum = (torch.gather(returns_matrix, 0, top_indices) * position_mask).sum(dim=0)
            benchmark_sum = (safe_returns[:, None] * valid).sum(dim=0)
            held_np = held_sum.cpu().numpy() / top_counts
            benchmark_np = benchmark_sum.cpu().numpy() / np.maximum(count_np, 1)
            top_indices_np = top_indices.cpu().numpy()

            marker = period + 1
            for local in range(right - left):
                combination = left + local
                if not usable[local]:
                    continue
                selected_positions = np.flatnonzero(position_mask_np[:, local])
                selected_instruments = instrument_block[top_indices_np[selected_positions, local]]
                if previous_marker[combination] != 0:
                    overlap = int(
                        np.count_nonzero(
                            previous_seen[combination, selected_instruments]
                            == previous_marker[combination]
                        )
                    )
                    turnover[combination, period] = 1.0 - overlap / len(selected_instruments)
                previous_seen[combination, selected_instruments] = marker
                previous_marker[combination] = marker
                held_returns[combination, period] = held_np[local]
                gross_excess[combination, period] = held_np[local] - benchmark_np[local]
                stock_counts[combination, period] = count_np[local]
                valid_period[combination, period] = 1
    return held_returns, gross_excess, turnover, stock_counts, valid_period


def _evaluate_combinations_numpy(
    scores: np.ndarray,
    forward: np.ndarray,
    instruments: np.ndarray,
    offsets: np.ndarray,
    masks: np.ndarray,
    sizes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized CPU evaluator for the normal NumPy-only environment."""
    combination_count = len(masks)
    period_count = len(offsets) - 1
    held_returns = np.full((combination_count, period_count), np.nan)
    gross_excess = np.full((combination_count, period_count), np.nan)
    turnover = np.full((combination_count, period_count), np.nan)
    stock_counts = np.zeros((combination_count, period_count), dtype=np.int32)
    valid_period = np.zeros((combination_count, period_count), dtype=np.uint8)
    instrument_count = int(instruments.max()) + 1 if len(instruments) else 0
    previous_seen = np.full((combination_count, instrument_count), -1, dtype=np.int32)
    previous_marker = np.zeros(combination_count, dtype=np.int32)
    chunk_size = 256

    for period in range(period_count):
        start, end = int(offsets[period]), int(offsets[period + 1])
        score_block = scores[start:end]
        return_block = forward[start:end]
        row_count = end - start
        finite_scores = np.isfinite(score_block)
        finite_returns = np.isfinite(return_block)
        safe_scores = np.nan_to_num(score_block, nan=0.0, posinf=0.0, neginf=0.0)
        safe_returns = np.nan_to_num(return_block, nan=0.0, posinf=0.0, neginf=0.0)
        row_epsilon = np.arange(row_count, dtype=np.float64)[:, None] * 1.0e-12
        instrument_block = instruments[start:end]

        for left in range(0, combination_count, chunk_size):
            right = min(left + chunk_size, combination_count)
            mask_chunk = masks[left:right].astype(np.float64).T
            size_chunk = sizes[left:right].astype(np.float64)
            selected_score_counts = finite_scores.astype(np.float64) @ mask_chunk
            valid = finite_returns[:, None] & (selected_score_counts == size_chunk[None, :])
            count_np = valid.sum(axis=0).astype(np.int32)
            usable = count_np >= GROUPS * 10
            if not bool(usable.any()):
                continue
            weights = mask_chunk / size_chunk[None, :]
            combination_scores = safe_scores @ weights + row_epsilon
            combination_scores[~valid] = -np.inf
            top_counts = count_np - (count_np * (GROUPS - 1) // GROUPS)
            max_top = int(top_counts[usable].max())
            top_indices = np.argpartition(
                -combination_scores, max_top - 1, axis=0
            )[:max_top]
            position_mask = np.arange(max_top, dtype=np.int32)[:, None] < top_counts[None, :]
            top_returns = safe_returns[top_indices]
            held_sum = np.where(position_mask, top_returns, 0.0).sum(axis=0)
            benchmark_sum = (safe_returns[:, None] * valid).sum(axis=0)
            held_np = held_sum / np.maximum(top_counts, 1)
            benchmark_np = benchmark_sum / np.maximum(count_np, 1)
            current_instruments = instrument_block[top_indices]
            marker = period + 1
            for local in range(right - left):
                combination = left + local
                if not usable[local]:
                    continue
                selected_positions = np.flatnonzero(position_mask[:, local])
                selected_instruments = current_instruments[selected_positions, local]
                if previous_marker[combination] != 0:
                    overlap = int(
                        np.count_nonzero(
                            previous_seen[combination, selected_instruments]
                            == previous_marker[combination]
                        )
                    )
                    turnover[combination, period] = 1.0 - overlap / len(selected_instruments)
                previous_seen[combination, selected_instruments] = marker
                previous_marker[combination] = marker
                held_returns[combination, period] = held_np[local]
                gross_excess[combination, period] = held_np[local] - benchmark_np[local]
                stock_counts[combination, period] = count_np[local]
                valid_period[combination, period] = 1
    return held_returns, gross_excess, turnover, stock_counts, valid_period


def _annual_cost(turnover: float | None, cycle: int) -> float | None:
    if turnover is None:
        return None
    return turnover * (252.0 / cycle) * ROUND_TRIP_COST


def _summary(
    held: np.ndarray,
    gross: np.ndarray,
    turnover: np.ndarray,
    stock_counts: np.ndarray,
    valid: np.ndarray,
    dates: np.ndarray,
    cycle: int,
    period_label: str,
    date_mask: np.ndarray,
    rank_ic: np.ndarray | None = None,
    ic: np.ndarray | None = None,
) -> dict[str, Any]:
    selected = np.flatnonzero(valid & date_mask)
    if len(selected) == 0:
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
    selected_dates = pd.to_datetime(dates[selected])
    selected_held = held[selected]
    selected_gross = gross[selected]
    selected_turnover = turnover[selected]
    years = len(selected) * cycle / 252.0
    finite_turnover = selected_turnover[np.isfinite(selected_turnover)]
    turnover_mean = float(finite_turnover.mean()) if len(finite_turnover) else None
    gross_annual = float(np.nansum(selected_gross) / years)
    cost = _annual_cost(turnover_mean, cycle)
    net = gross_annual - cost if cost is not None else None
    after_cost = selected_held - np.where(
        np.isfinite(selected_turnover), selected_turnover * ROUND_TRIP_COST, 0.0
    )
    std = float(np.std(after_cost, ddof=1)) if len(after_cost) > 1 else None
    mean = float(np.mean(after_cost)) if len(after_cost) else None
    sharpe = (
        mean / std * np.sqrt(252.0 / cycle)
        if mean is not None and std is not None and std > 0.0
        else None
    )
    curve = np.cumprod(1.0 + after_cost)
    running_max = np.maximum.accumulate(curve)
    drawdown = float(-(curve / running_max - 1.0).min() * 100.0)
    monthly = pd.Series(selected_gross, index=selected_dates).groupby(
        selected_dates.to_period("M")
    ).sum()
    result = {
        "period_label": period_label,
        "periods": len(selected),
        "first_signal_date": selected_dates.min(),
        "last_signal_date": selected_dates.max(),
        "mean_stock_count": float(stock_counts[selected].mean()),
        "rank_ic": None,
        "ic_mean": None,
        "gross_excess_pct": gross_annual * 100.0,
        "turnover_pct": None if turnover_mean is None else turnover_mean * 100.0,
        "annual_cost_pct": None if cost is None else cost * 100.0,
        "net_excess_pct": None if net is None else net * 100.0,
        "sharpe_after_cost": None if sharpe is None else float(sharpe),
        "max_drawdown_pct": drawdown,
        "monthly_win_rate_pct": float((monthly > 0.0).mean() * 100.0)
        if len(monthly)
        else None,
    }
    if rank_ic is not None:
        rank_values = rank_ic[selected][np.isfinite(rank_ic[selected])]
        result["rank_ic"] = float(rank_values.mean()) if len(rank_values) else None
    if ic is not None:
        ic_values = ic[selected][np.isfinite(ic[selected])]
        result["ic_mean"] = float(ic_values.mean()) if len(ic_values) else None
    return result


def _exact_period_ics(
    selected_indices: tuple[int, ...],
    blocks: list[tuple[pd.Timestamp, np.ndarray, np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray]:
    rank_ics = np.full(len(blocks), np.nan, dtype=float)
    ics = np.full(len(blocks), np.nan, dtype=float)
    for period, block in enumerate(blocks):
        forward = block[2]
        values = block[3][:, list(selected_indices)].mean(axis=1)
        valid = np.isfinite(forward) & np.isfinite(values)
        if int(valid.sum()) < GROUPS * 10:
            continue
        current = values[valid]
        returns = forward[valid]
        if np.nanstd(current) == 0.0 or np.nanstd(returns) == 0.0:
            continue
        rank_ics[period] = float(np.corrcoef(rankdata(current, method="average"), rankdata(returns, method="average"))[0, 1])
        ics[period] = float(np.corrcoef(current, returns)[0, 1])
    return rank_ics, ics


def _union_find_clusters(
    keys: list[str], correlation_rows: list[dict[str, Any]], threshold: float
) -> dict[str, str]:
    parent = list(range(len(keys)))

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    positions = {key: index for index, key in enumerate(keys)}
    for row in correlation_rows:
        value = _finite(row.get("abs_correlation"))
        if value is not None and value >= threshold:
            union(positions[str(row["candidate_a"])], positions[str(row["candidate_b"])])
    roots = sorted({find(index) for index in range(len(keys))})
    labels = {root: f"C{position + 1:02d}" for position, root in enumerate(roots)}
    return {key: labels[find(index)] for index, key in enumerate(keys)}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _summary_fields(prefix: str, summary: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in summary.items():
        if key == "period_label":
            continue
        fields[f"{prefix}_{key}"] = value
    return fields


def _sort_rows(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row[field]) if _finite(row.get(field)) is not None else np.inf,
            int(row["factor_count"]),
            str(row["components"]),
        ),
    )


def _build_report(
    output_dir: Path,
    settings: dict[str, Any],
    candidates: list[dict[str, Any]],
    correlations: list[dict[str, Any]],
    cluster_map: dict[str, str],
    combination_rows: list[dict[str, Any]],
    count_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Exhaustive representative combination search",
        "",
        f"Alignment rule: `{settings['alignment_rule_version']}`.",
        "",
        "This is an offline local proxy. It did not create factors, spend PandaAI compute, or claim an official pool score.",
        "",
        "## Scope and method",
        "",
        f"- Candidates: `{settings['candidate_count']}` explicit single-mechanism representatives.",
        f"- Non-empty subsets evaluated: `{settings['combination_count']}` (`2^{settings['candidate_count']}-1`); "
        f"reported pool size is `>= {settings.get('min_factor_count', 1)}` with `{settings.get('eligible_combination_count', settings['combination_count'])}` combinations.",
        f"- Common local cycle: `{settings['common_cycle']}` trading days; signal dates: `{settings['period_count']}`.",
        f"- Formal window: `{settings['formal_start']}` to `{settings['formal_end']}`; recent diagnostic: `{settings['recent_start']}` onward.",
        f"- Warm-up: `{settings['data_start']}`; universe: full A `.SH/.SZ`; price: qfq; cap: `{ALIGNMENT_MARKET_CAP_FIELD}`.",
        f"- Label: `{settings['label']}`; groups: `{GROUPS}`; one-way cost: `{ALIGNMENT_ONE_WAY_COST:.2%}`.",
        settings.get("portfolio_score_description", "- Each input is direction-aligned, converted to a daily cross-sectional percentile rank, and combined with equal weights."),
        "- Net excess is arithmetic annualized gross excess minus annualized cost from the combination's actual held-group turnover.",
        "- Training ends at `2024-09-06`; validation is the later formal period and is diagnostic only.",
        "",
        "The saved platform source cycle is shown below. A few representatives only have a saved five-day source record; their formula signal is evaluated at the common ten-day schedule for this comparison. That makes the local portfolios comparable, but it does not turn their saved five-day platform result into a ten-day platform result.",
        "",
        "## Candidate inputs",
        "",
        "| key | cluster | handler | dir | source cycle | platform net | alignment | source name |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for item in candidates:
        lines.append(
            f"| `{item['key']}` | {item['cluster']} | `{item['handler']}` | {item['direction']} | "
            f"{item.get('source_cycle') or 'n/a'} | {_format(item.get('platform_net_excess_pct'), '%')} | "
            f"{item.get('alignment_quality') or 'n/a'} | {item.get('name') or 'n/a'} |"
        )

    lines.extend(["", "## Correlation and clusters", ""])
    high_rows = [row for row in correlations if (_finite(row.get("abs_correlation")) or 0.0) >= 0.60]
    lines.append("Direction-aligned daily cross-sectional Spearman correlations at or above 0.60:")
    lines.extend(["", "| factor A | factor B | rho | days |", "|---|---|---:|---:|"])
    for row in sorted(high_rows, key=lambda item: -float(item["abs_correlation"])):
        lines.append(
            f"| `{row['candidate_a']}` | `{row['candidate_b']}` | {float(row['correlation']):.4f} | {row['days']} |"
        )
    if not high_rows:
        lines.append("| n/a | n/a | n/a | n/a |")
    lines.extend(["", "Connected components at abs(rho) >= 0.80:", "", "| local cluster | members |", "|---|---|"])
    for cluster in sorted(set(cluster_map.values())):
        members = [key for key, value in cluster_map.items() if value == cluster]
        lines.append(f"| {cluster} | {', '.join(f'`{key}`' for key in members)} |")

    lines.extend(
        [
            "",
            "## Best result by factor count",
            "",
            "The `all` columns include highly correlated additions. The `<0.80` columns require every pair in the subset to have abs(rho) below 0.80.",
            "",
            "| count | all train | all valid | all full | all recent | <0.80 train | <0.80 valid |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    minimum_count = int(settings.get("min_factor_count", 1))
    for row in count_rows:
        if int(row["factor_count"]) < minimum_count:
            continue
        lines.append(
            f"| {row['factor_count']} | {row['best_all_train_components']} ({_format(row['best_all_train_net_excess_pct'], '%')}) | "
            f"{row['best_all_test_components']} ({_format(row['best_all_test_net_excess_pct'], '%')}) | "
            f"{row['best_all_full_components']} ({_format(row['best_all_full_net_excess_pct'], '%')}) | "
            f"{row['best_all_recent_components']} ({_format(row['best_all_recent_net_excess_pct'], '%')}) | "
            f"{row['best_low_corr_train_components']} ({_format(row['best_low_corr_train_net_excess_pct'], '%')}) | "
            f"{row['best_low_corr_test_components']} ({_format(row['best_low_corr_test_net_excess_pct'], '%')}) |"
        )

    lines.extend(["", "## Top combinations selected on training", "", "| rank | count | components | max abs rho | train net | validation net | full net | recent net | full turnover | full max DD | full RankIC |", "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    report_combinations = [
        row for row in combination_rows if int(row["factor_count"]) >= minimum_count
    ]
    for rank, row in enumerate(_sort_rows(report_combinations, "train_net_excess_pct")[:25], start=1):
        lines.append(
            f"| {rank} | {row['factor_count']} | `{row['components']}` | {float(row['max_abs_correlation']):.4f} | "
            f"{_format(row['train_net_excess_pct'], '%')} | {_format(row['test_net_excess_pct'], '%')} | "
            f"{_format(row['full_net_excess_pct'], '%')} | {_format(row['recent_net_excess_pct'], '%')} | "
            f"{_format(row['full_turnover_pct'], '%')} | {_format(row['full_max_drawdown_pct'], '%')} | "
            f"{_format(row.get('full_rank_ic'))} |"
        )

    lines.extend(["", "## Key diagnostics", ""])
    for title, field in (
        ("Best training-period combination", "train_net_excess_pct"),
        ("Best validation-period combination (diagnostic ranking)", "test_net_excess_pct"),
        ("Best full-period combination (descriptive ranking)", "full_net_excess_pct"),
        ("Best recent-period combination (diagnostic ranking)", "recent_net_excess_pct"),
    ):
        row = _sort_rows(report_combinations, field)[0]
        lines.append(
            f"- {title}: `{row['components']}`; count `{row['factor_count']}`; "
            f"train/validation/full/recent net = `{_format(row['train_net_excess_pct'], '%')}` / "
            f"`{_format(row['test_net_excess_pct'], '%')}` / `{_format(row['full_net_excess_pct'], '%')}` / "
            f"`{_format(row['recent_net_excess_pct'], '%')}`; max abs rho `{float(row['max_abs_correlation']):.4f}`."
        )
    c1 = next(
        (row for row in combination_rows if row["components"] == "SIZE+TURN+RET40+DD120+CHIP250"),
        None,
    )
    size_h03 = next((row for row in combination_rows if row["components"] == "SIZE+H03"), None)
    if c1 is not None:
        lines.append(
            f"- Exact requested C1-style subset `SIZE+TURN+RET40+DD120+CHIP250`: train/validation/full/recent net = "
            f"`{_format(c1['train_net_excess_pct'], '%')}` / `{_format(c1['test_net_excess_pct'], '%')}` / "
            f"`{_format(c1['full_net_excess_pct'], '%')}` / `{_format(c1['recent_net_excess_pct'], '%')}`; "
            f"full turnover `{_format(c1['full_turnover_pct'], '%')}`, full max drawdown `{_format(c1['full_max_drawdown_pct'], '%')}`."
        )
    if size_h03 is not None:
        lines.append(
            f"- Same-cluster check `SIZE+H03`: train/validation/full/recent net = `{_format(size_h03['train_net_excess_pct'], '%')}` / "
            f"`{_format(size_h03['test_net_excess_pct'], '%')}` / `{_format(size_h03['full_net_excess_pct'], '%')}` / "
            f"`{_format(size_h03['recent_net_excess_pct'], '%')}`; max abs rho `{float(size_h03['max_abs_correlation']):.4f}`."
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- Training ranking is the only ranking used for a prospective selection. Validation and recent winners were selected after seeing those periods and are diagnostics, not unbiased out-of-sample choices.",
            "- A low correlation only means different signal exposure. It does not prove independent alpha or remove the common small-cap/market-regime exposure.",
            "- The combination is an equal-weight local portfolio proxy. PandaAI's official pool treatment and C score are not reproduced by averaging single-factor platform headlines.",
            "- EV/EBITDA and residual-volatility inputs are retained because they were in the requested representative set, but their saved alignment quality is marked as a field/path proxy issue. Results involving them need separate confirmation before platform submission.",
            "",
            "## Artifacts",
            "",
            f"- All 4095 combinations: `{output_dir / 'all_combinations.csv'}`",
            f"- Selected combinations with exact RankIC/IC: `{output_dir / 'selected_combinations.csv'}`",
            f"- Per-period holdings diagnostics for selected combinations: `{output_dir / 'selected_periods.csv'}`",
            f"- Machine-readable payload: `{output_dir / 'report.json'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-report", type=Path, default=DEFAULT_ALIGNMENT_REPORT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument(
        "--score-mode",
        choices=["rank", "winsor_z"],
        default="rank",
        help="portfolio component normalization; winsor_z matches the public pool rule proxy",
    )
    parser.add_argument(
        "--min-factor-count",
        type=int,
        default=1,
        help="minimum pool size included in the report and exact IC audit",
    )
    parser.add_argument(
        "--audit-components",
        action="append",
        default=[],
        help=(
            "comma-separated component lists to include in the exact RankIC audit, "
            "for example SIZE+RET40+CHIP250"
        ),
    )
    args = parser.parse_args()
    if args.top_k < 1 or args.min_factor_count < 1:
        raise SystemExit("top-k and min-factor-count must be positive")

    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)
    alignment_payload, candidates = _load_candidates(args.alignment_report)
    keys = [str(item["key"]) for item in candidates]
    handlers = sorted({str(item["handler"]) for item in candidates})
    print(f"candidates={len(candidates)} handlers={handlers}", flush=True)

    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    signal_dates = _common_schedule(calendar)
    print(f"schedule_cycle={COMMON_CYCLE} signal_dates={len(signal_dates)}", flush=True)

    frame = load_full_a_data(args.price_root, args.cap_root, DATA_START, END)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(f"panel_rows={len(frame)}", flush=True)

    close = panel_close(frame, calendar)
    returns = forward_returns(close, calendar, signal_dates, COMMON_CYCLE, LABEL_OFFSET)
    signal_mask = frame["date"].isin(signal_dates)
    signal_frame = frame.loc[signal_mask, ["date", "instrument"]].copy().reset_index(drop=True)
    if signal_frame.duplicated(["date", "instrument"]).any():
        raise RuntimeError("duplicate date/instrument rows in signal panel")

    financial = None
    if any(handler in FINANCIAL_HANDLERS for handler in handlers):
        financial = load_financial_cache(args.financial_root)
        print(f"financial_cache=loaded tables={len(financial)}", flush=True)
    raw_values: dict[str, pd.Series] = {}
    for number, handler in enumerate(handlers, start=1):
        print(f"building={handler} ({number}/{len(handlers)})", flush=True)
        values = build_factor(frame, handler, financial=financial, signal_dates=signal_dates)
        raw_values[handler] = pd.to_numeric(
            values.loc[signal_mask].reset_index(drop=True), errors="coerce"
        )
        del values
        gc.collect()
    correlation_scores = cross_sectional_scores(signal_frame, raw_values, candidates)
    if args.score_mode == "winsor_z":
        scores = _competition_cross_sectional_scores(signal_frame, raw_values, candidates)
    else:
        scores = correlation_scores
    del raw_values, financial, close
    gc.collect()
    blocks = _build_blocks(signal_frame, scores, returns, signal_dates, keys)
    if len(blocks) != len(signal_dates):
        raise RuntimeError(f"signal block count {len(blocks)} != schedule count {len(signal_dates)}")
    dates, offsets, flat_scores, flat_forward, flat_instruments, flat_instrument_text = _flatten_blocks(
        blocks, len(candidates)
    )
    print(
        f"blocks={len(blocks)} flattened_rows={len(flat_forward)} "
        f"mean_rows={len(flat_forward) / len(blocks):.1f}",
        flush=True,
    )

    bitmasks, masks, sizes, labels = _combination_catalog(keys)
    start_time = time.perf_counter()
    print(f"evaluating_combinations={len(bitmasks)}", flush=True)
    if njit is not None:
        held, gross, turnover, stock_counts, valid_period = _evaluate_combinations_numba(
            flat_scores, flat_forward, flat_instruments, offsets, masks, sizes
        )
        evaluator = "numba_parallel_argpartition_stable_tie_proxy"
    elif torch is not None:
        held, gross, turnover, stock_counts, valid_period = _evaluate_combinations_torch(
            flat_scores, flat_forward, flat_instruments, offsets, masks, sizes
        )
        evaluator = "torch_cpu_chunked_topk_stable_tie_proxy"
    else:
        held, gross, turnover, stock_counts, valid_period = _evaluate_combinations_numpy(
            flat_scores, flat_forward, flat_instruments, offsets, masks, sizes
        )
        evaluator = "numpy_chunked_argpartition_stable_tie_proxy"
    elapsed = time.perf_counter() - start_time
    print(f"combination_evaluation_seconds={elapsed:.1f}", flush=True)

    date_index = pd.to_datetime(dates)
    full_mask = np.ones(len(dates), dtype=bool)
    train_mask = date_index.to_numpy() <= TRAIN_END.to_datetime64()
    test_mask = date_index.to_numpy() > TRAIN_END.to_datetime64()
    recent_mask = date_index.to_numpy() >= RECENT_START.to_datetime64()
    summaries: dict[tuple[int, str], dict[str, Any]] = {}
    for combination in range(len(bitmasks)):
        for period_label, mask in (
            ("full", full_mask),
            ("train", train_mask),
            ("test", test_mask),
            ("recent", recent_mask),
        ):
            summaries[(combination, period_label)] = _summary(
                held[combination],
                gross[combination],
                turnover[combination],
                stock_counts[combination],
                valid_period[combination].astype(bool),
                dates,
                COMMON_CYCLE,
                period_label,
                mask,
            )

    # Correlations are cross-sectional: every score row needs the signal date
    # for that stock.  ``dates`` above is intentionally one entry per block,
    # so it cannot be paired with the flattened stock-level score matrix.
    correlation_frame = correlation_scores.loc[:, keys].reset_index(drop=True)
    date_series = signal_frame["date"].reset_index(drop=True)
    correlation_rows = daily_correlations(date_series, correlation_frame, keys)
    for row in correlation_rows:
        row["candidate_a"] = str(row["candidate_a"])
        row["candidate_b"] = str(row["candidate_b"])
        row["correlation"] = _finite(row.get("correlation"))
        row["abs_correlation"] = _finite(row.get("abs_correlation"))
    if not correlation_rows or all(row.get("days", 0) == 0 for row in correlation_rows):
        raise RuntimeError("correlation calculation produced no valid signal days")
    size_h03 = next(
        (
            row
            for row in correlation_rows
            if {row["candidate_a"], row["candidate_b"]} == {"SIZE", "H03"}
        ),
        None,
    )
    if size_h03 is None or size_h03.get("correlation") is None or size_h03.get("days", 0) == 0:
        raise RuntimeError("SIZE-H03 correlation regression check did not produce a value")
    print(
        f"correlation_regression_SIZE_H03={size_h03['correlation']:.6f} "
        f"days={size_h03['days']}",
        flush=True,
    )
    cluster_map = _union_find_clusters(keys, correlation_rows, 0.80)

    single_by_key: dict[str, int] = {}
    for index, key in enumerate(keys):
        single_by_key[key] = 1 << index
    bitmask_to_row = {bitmask: index for index, bitmask in enumerate(bitmasks)}
    candidate_meta = {str(item["key"]): item for item in candidates}
    corr_values: dict[frozenset[str], float] = {}
    for row in correlation_rows:
        value = _finite(row.get("correlation"))
        if value is not None:
            corr_values[frozenset((str(row["candidate_a"]), str(row["candidate_b"])))] = value

    combination_rows: list[dict[str, Any]] = []
    for combination, bitmask in enumerate(bitmasks):
        selected_keys = [keys[index] for index in range(len(keys)) if masks[combination, index]]
        pair_values = [
            abs(corr_values[frozenset(pair)])
            for pair in itertools.combinations(selected_keys, 2)
            if frozenset(pair) in corr_values
        ]
        factor_clusters = sorted({candidate_meta[key]["cluster"] for key in selected_keys})
        train_summary = summaries[(combination, "train")]
        test_summary = summaries[(combination, "test")]
        full_summary = summaries[(combination, "full")]
        recent_summary = summaries[(combination, "recent")]
        component_train = [
            _finite(summaries[(bitmask_to_row[single_by_key[key]], "train")].get("net_excess_pct"))
            for key in selected_keys
        ]
        component_test = [
            _finite(summaries[(bitmask_to_row[single_by_key[key]], "test")].get("net_excess_pct"))
            for key in selected_keys
        ]
        component_full = [
            _finite(summaries[(bitmask_to_row[single_by_key[key]], "full")].get("net_excess_pct"))
            for key in selected_keys
        ]
        best_train = max((value for value in component_train if value is not None), default=None)
        best_test = max((value for value in component_test if value is not None), default=None)
        best_full = max((value for value in component_full if value is not None), default=None)
        row: dict[str, Any] = {
            "combination_id": f"M{bitmask:04d}",
            "bitmask": bitmask,
            "factor_count": int(sizes[combination]),
            "components": "+".join(selected_keys),
            "component_clusters": "+".join(factor_clusters),
            "unique_base_cluster_count": len(factor_clusters),
            "max_abs_correlation": max(pair_values) if pair_values else 0.0,
            "mean_abs_correlation": float(np.mean(pair_values)) if pair_values else 0.0,
            "eligible_corr_lt_0_60": bool(max(pair_values, default=0.0) < 0.60),
            "eligible_corr_lt_0_80": bool(max(pair_values, default=0.0) < 0.80),
            "best_component_train_net_excess_pct": best_train,
            "best_component_test_net_excess_pct": best_test,
            "best_component_full_net_excess_pct": best_full,
            "train_delta_vs_best_component_pct": (
                None
                if best_train is None or train_summary.get("net_excess_pct") is None
                else train_summary["net_excess_pct"] - best_train
            ),
            "test_delta_vs_best_component_pct": (
                None
                if best_test is None or test_summary.get("net_excess_pct") is None
                else test_summary["net_excess_pct"] - best_test
            ),
            "full_delta_vs_best_component_pct": (
                None
                if best_full is None or full_summary.get("net_excess_pct") is None
                else full_summary["net_excess_pct"] - best_full
            ),
        }
        row.update(_summary_fields("full", full_summary))
        row.update(_summary_fields("train", train_summary))
        row.update(_summary_fields("test", test_summary))
        row.update(_summary_fields("recent", recent_summary))
        combination_rows.append(row)

    # Pick a finite audit set for exact RankIC/IC. All combinations still have
    # complete return/risk metrics above; exact IC is more expensive because it
    # needs a new cross-sectional ranking for every selected combination.
    eligible_rows = [
        row for row in combination_rows if int(row["factor_count"]) >= args.min_factor_count
    ]
    eligible_bitmasks = {int(row["bitmask"]) for row in eligible_rows}
    selected_bitmasks: set[int] = set()
    for index in range(len(keys)):
        bitmask = 1 << index
        if bitmask in eligible_bitmasks:
            selected_bitmasks.add(bitmask)
    size_h03_mask = sum(1 << keys.index(key) for key in ("SIZE", "H03"))
    if size_h03_mask in eligible_bitmasks:
        selected_bitmasks.add(size_h03_mask)
    c1_mask = sum(
        1 << keys.index(key) for key in ("SIZE", "TURN", "RET40", "DD120", "CHIP250")
    )
    if c1_mask in eligible_bitmasks:
        selected_bitmasks.add(c1_mask)
    for requested in args.audit_components:
        for component_text in str(requested).split(","):
            component_text = component_text.strip()
            if not component_text:
                continue
            requested_keys = component_text.split("+")
            unknown = [key for key in requested_keys if key not in keys]
            if unknown or len(set(requested_keys)) != len(requested_keys):
                raise SystemExit(
                    f"invalid --audit-components value {component_text!r}; "
                    f"unknown or duplicate keys: {unknown or requested_keys}"
                )
            requested_mask = sum(1 << keys.index(key) for key in requested_keys)
            if requested_mask not in eligible_bitmasks:
                raise SystemExit(
                    f"--audit-components value {component_text!r} does not meet "
                    f"--min-factor-count={args.min_factor_count}"
                )
            selected_bitmasks.add(requested_mask)
    for field in (
        "train_net_excess_pct",
        "test_net_excess_pct",
        "full_net_excess_pct",
        "recent_net_excess_pct",
    ):
        for row in _sort_rows(eligible_rows, field)[: args.top_k]:
            selected_bitmasks.add(int(row["bitmask"]))
    for factor_count in range(1, len(keys) + 1):
        ranked = [row for row in eligible_rows if row["factor_count"] == factor_count]
        for row in _sort_rows(ranked, "train_net_excess_pct")[:3]:
            selected_bitmasks.add(int(row["bitmask"]))
    print(f"exact_ic_combinations={len(selected_bitmasks)}", flush=True)

    exact_by_bitmask: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    exact_period_rows: list[dict[str, Any]] = []
    for number, bitmask in enumerate(sorted(selected_bitmasks), start=1):
        indices = tuple(index for index in range(len(keys)) if bitmask & (1 << index))
        rank_values, ic_values = _exact_period_ics(indices, blocks)
        exact_by_bitmask[bitmask] = (rank_values, ic_values)
        combination_index = bitmask_to_row[bitmask]
        valid = valid_period[combination_index].astype(bool)
        for period, date in enumerate(dates):
            if not valid[period]:
                continue
            exact_period_rows.append(
                {
                    "combination_id": f"M{bitmask:04d}",
                    "components": labels[combination_index],
                    "date": pd.Timestamp(date),
                    "stock_count": int(stock_counts[combination_index, period]),
                    "held_return": held[combination_index, period],
                    "gross_excess": gross[combination_index, period],
                    "turnover": turnover[combination_index, period],
                    "rank_ic": rank_values[period],
                    "ic": ic_values[period],
                }
            )
        if number % 50 == 0 or number == len(selected_bitmasks):
            print(f"exact_ic_done={number}/{len(selected_bitmasks)}", flush=True)

    for row in combination_rows:
        bitmask = int(row["bitmask"])
        exact = exact_by_bitmask.get(bitmask)
        if exact is None:
            row["full_rank_ic"] = None
            row["full_ic_mean"] = None
            row["train_rank_ic"] = None
            row["train_ic_mean"] = None
            row["test_rank_ic"] = None
            row["test_ic_mean"] = None
            row["recent_rank_ic"] = None
            row["recent_ic_mean"] = None
            row["exact_ic_audit"] = False
            continue
        rank_values, ic_values = exact
        index = bitmask_to_row[bitmask]
        valid = valid_period[index].astype(bool)
        row["full_rank_ic"] = _summary(
            held[index], gross[index], turnover[index], stock_counts[index], valid, dates,
            COMMON_CYCLE, "full", full_mask, rank_values, ic_values
        )["rank_ic"]
        row["full_ic_mean"] = _summary(
            held[index], gross[index], turnover[index], stock_counts[index], valid, dates,
            COMMON_CYCLE, "full", full_mask, rank_values, ic_values
        )["ic_mean"]
        for label, mask in (("train", train_mask), ("test", test_mask), ("recent", recent_mask)):
            exact_summary = _summary(
                held[index], gross[index], turnover[index], stock_counts[index], valid, dates,
                COMMON_CYCLE, label, mask, rank_values, ic_values
            )
            row[f"{label}_rank_ic"] = exact_summary["rank_ic"]
            row[f"{label}_ic_mean"] = exact_summary["ic_mean"]
        row["exact_ic_audit"] = True

    combination_rows.sort(key=lambda row: int(row["bitmask"]))
    selected_rows = [
        row for row in combination_rows if int(row["bitmask"]) in selected_bitmasks
    ]
    selected_rows.sort(key=lambda row: (-float(row["train_net_excess_pct"]), int(row["bitmask"])))

    count_rows: list[dict[str, Any]] = []
    for factor_count in range(1, len(keys) + 1):
        all_rows = [row for row in combination_rows if row["factor_count"] == factor_count]
        low_rows = [row for row in all_rows if row["eligible_corr_lt_0_80"]]
        def best(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
            return _sort_rows(rows, field)[0] if rows else None
        record: dict[str, Any] = {"factor_count": factor_count, "all_total": len(all_rows), "low_corr_total": len(low_rows)}
        for label, field in (
            ("all_train", "train_net_excess_pct"),
            ("all_test", "test_net_excess_pct"),
            ("all_full", "full_net_excess_pct"),
            ("all_recent", "recent_net_excess_pct"),
            ("low_corr_train", "train_net_excess_pct"),
            ("low_corr_test", "test_net_excess_pct"),
        ):
            source_rows = low_rows if label.startswith("low_corr") else all_rows
            winner = best(source_rows, field)
            record[f"best_{label}_components"] = None if winner is None else winner["components"]
            record[f"best_{label}_net_excess_pct"] = None if winner is None else winner[field]
            record[f"best_{label}_full_net_excess_pct"] = None if winner is None else winner["full_net_excess_pct"]
            record[f"best_{label}_test_net_excess_pct"] = None if winner is None else winner["test_net_excess_pct"]
        count_rows.append(record)

    # Compact source metadata and a correlation matrix are part of the JSON
    # audit payload; CSVs carry the flat tables for filtering.
    candidate_rows: list[dict[str, Any]] = []
    for item in candidates:
        candidate_rows.append(
            {
                "key": item["key"],
                "cluster": item["cluster"],
                "handler": item["handler"],
                "direction": item["direction"],
                "formula": item["formula"],
                "name": item["name"],
                "source_id": item["source_id"],
                "source_cycle": item.get("source_cycle"),
                "platform_configured_cycle": item.get("platform_configured_cycle"),
                "platform_net_excess_pct": item.get("platform_net_excess_pct"),
                "alignment_quality": item.get("alignment_quality"),
                "local_mining_eligible": item.get("local_mining_eligible"),
                "fidelity": item.get("fidelity"),
            }
        )

    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment_config": alignment_config,
        "candidate_count": len(candidates),
        "combination_count": len(combination_rows),
        "eligible_combination_count": len(eligible_rows),
        "min_factor_count": args.min_factor_count,
        "candidate_selection": "explicit positive-net single-mechanism representatives from canonical all-record alignment report",
        "common_cycle": COMMON_CYCLE,
        "formal_start": START.strftime("%Y-%m-%d"),
        "formal_end": END.strftime("%Y-%m-%d"),
        "recent_start": RECENT_START.strftime("%Y-%m-%d"),
        "data_start": DATA_START.strftime("%Y-%m-%d"),
        "period_count": len(blocks),
        "label": "close(t+1) -> close(t+1+cycle)",
        "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
        "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
        "correlation_method": "daily_cross_sectional_spearman_mean",
        "portfolio_rule": (
            "equal weight of direction-aligned 1%-99% Winsorized cross-sectional Z-scores; held group 10"
            if args.score_mode == "winsor_z"
            else "equal weight of direction-aligned cross-sectional percentile ranks; held group 10"
        ),
        "score_mode": args.score_mode,
        "portfolio_score_description": (
            "- Each component is direction-aligned, Winsorized at the daily 1st/99th percentiles, Z-scored, and then equal-weighted. "
            "The implementation uses population standard deviation and excludes stocks missing a selected component as a local proxy."
            if args.score_mode == "winsor_z"
            else "- Each input is direction-aligned, converted to a daily cross-sectional percentile rank, and combined with equal weights."
        ),
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "train_end": TRAIN_END.strftime("%Y-%m-%d"),
        "evaluator": evaluator,
        "numba_available": njit is not None,
        "source_alignment_records": len(alignment_payload.get("results", [])),
        "source_platform_net_filter": alignment_payload.get("settings", {}).get("platform_net_filter"),
        "source_schedule": "saved platform signal dates from VERIFY10-F260910-12",
        "correlation_thresholds": [0.60, 0.80],
    }
    payload = {
        "settings": settings,
        "candidates": candidate_rows,
        "correlations": correlation_rows,
        "clusters_at_0_80": cluster_map,
        "factor_count_summary": count_rows,
        "selected_combinations": selected_rows,
    }

    output_dir = args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_dir / "candidates.csv", candidate_rows)
    _write_csv(output_dir / "correlations.csv", correlation_rows)
    _write_csv(output_dir / "all_combinations.csv", combination_rows)
    _write_csv(output_dir / "selected_combinations.csv", selected_rows)
    _write_csv(output_dir / "factor_count_summary.csv", count_rows)
    _write_csv(output_dir / "selected_periods.csv", exact_period_rows)
    (output_dir / "report.md").write_text(
        _build_report(
            output_dir,
            settings,
            candidates,
            correlation_rows,
            cluster_map,
            combination_rows,
            count_rows,
            selected_rows,
        ),
        encoding="utf-8",
    )
    print(f"output_dir={output_dir}", flush=True)
    print(f"report={output_dir / 'report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
