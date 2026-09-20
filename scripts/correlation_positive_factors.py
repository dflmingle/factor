#!/usr/bin/env python3
"""Calculate pairwise correlations among saved positive-net factors.

This is an offline local-reproduction calculation.  It reads the saved
platform/local comparison report and the aligned Tushare cache; it never
contacts PandaAI, creates factors, or starts a backtest.

The primary statistic is the arithmetic mean of daily cross-sectional
Spearman correlations.  For every pair and every date, ranks are computed on
that pair's jointly valid stock set, with average ranks for ties.  This keeps
the calculation aligned with the project contract even when two factors have
different missing-value patterns.
"""

from __future__ import annotations

import argparse
import gc
import itertools
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import financial_factor_local as financial_local  # noqa: E402
from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_CORRELATION_DESCRIPTION,
    ALIGNMENT_CORRELATION_METHOD,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE_LABEL,
)
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    saved_records,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "positive-factor-pair-correlation-20260917"
)

PLATFORM_METRIC_FIELDS = (
    "platform_rank_ic",
    "platform_ic_mean",
    "platform_ic_ir",
    "platform_ic_p_value",
    "platform_monotonicity",
    "platform_gross_excess_pct",
    "platform_turnover_pct",
    "platform_annual_cost_pct",
    "platform_net_excess_pct",
    "platform_long_sharpe",
    "platform_long_max_drawdown_pct",
    "platform_long_monthly_win_rate_pct",
)


def parse_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    return pd.Timestamp(
        pd.to_datetime(text, format="%Y%m%d" if len(text) == 8 else None)
    ).normalize()


def platform_metric_values(
    record: dict[str, Any],
    prefix: str = "",
) -> dict[str, Any]:
    return {
        f"{prefix}{field}": record.get(field) for field in PLATFORM_METRIC_FIELDS
    }


def record_direction(record: dict[str, Any]) -> Any:
    direction = record.get("platform_factor_direction")
    return record.get("direction") if direction is None else direction


def short_report_label(report: Any) -> str:
    if report is None or str(report).strip() == "":
        return "unknown-report"
    label = Path(str(report)).name
    if label.endswith(".report.csv"):
        return label[: -len(".report.csv")]
    if label.endswith(".csv"):
        return label[:-len(".csv")]
    return label


def other_factor_fields(
    row: dict[str, Any],
    current_factor_id: Any,
) -> dict[str, Any]:
    if row["factor_a_id"] == current_factor_id:
        side = "b"
    elif row["factor_b_id"] == current_factor_id:
        side = "a"
    else:
        raise ValueError(
            f"Pair row does not contain factor {current_factor_id!r}: {row!r}"
        )
    prefix = f"factor_{side}_"
    return {
        "id": row[f"{prefix}id"],
        "name": row[f"{prefix}name"],
        "report": row.get(f"{prefix}report"),
        "handler": row[f"{prefix}handler"],
        "formula": row[f"{prefix}formula"],
        "direction": row.get(f"{prefix}direction"),
        "platform_factor_direction": row.get(
            f"{prefix}platform_factor_direction"
        ),
        "platform_factor_id": row.get(f"{prefix}platform_factor_id"),
        "platform_run_id": row.get(f"{prefix}platform_run_id"),
        "configured_cycle": row.get(f"{prefix}configured_cycle"),
        "local_net_excess_pct": row.get(f"{prefix}local_net_excess_pct"),
        **{
            field: row.get(f"{prefix}{field}")
            for field in PLATFORM_METRIC_FIELDS
        },
    }


def format_neighbor_description(
    row: dict[str, Any],
    current_factor_id: Any,
    *,
    include_net: bool = False,
) -> str:
    other = other_factor_fields(row, current_factor_id)
    report = short_report_label(other["report"])
    correlation = row.get("correlation")
    correlation_text = (
        "n/a"
        if correlation is None
        else f"{float(correlation):+.6f}"
    )
    if not include_net:
        return f"{other['name']} [{report}] ({correlation_text})"
    net = other.get("platform_net_excess_pct")
    net_text = "n/a" if net is None else f"{float(net):.2f}%"
    return f"{other['name']} [{report}] (net={net_text}, rho={correlation_text})"


def factor_detail_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "factor_id": record.get("id"),
        "factor_name": record.get("name"),
        "report": record.get("report"),
        "handler": record.get("handler"),
        "formula": record.get("formula"),
        "direction": record.get("direction"),
        "platform_factor_direction": record_direction(record),
        "platform_factor_id": record.get("factor_id"),
        "platform_run_id": record.get("run_id"),
        "configured_cycle": record.get("configured_cycle"),
        **platform_metric_values(record),
    }


def format_platform_metrics(row: dict[str, Any]) -> str:
    specs = (
        ("RankIC", "platform_rank_ic", 4, ""),
        ("IC", "platform_ic_mean", 4, ""),
        ("ICIR", "platform_ic_ir", 4, ""),
        ("p", "platform_ic_p_value", 4, ""),
        ("Mono", "platform_monotonicity", 2, ""),
        ("Gross", "platform_gross_excess_pct", 2, "%"),
        ("Turnover", "platform_turnover_pct", 2, "%"),
        ("Cost", "platform_annual_cost_pct", 2, "%"),
        ("Net", "platform_net_excess_pct", 2, "%"),
        ("Sharpe", "platform_long_sharpe", 4, ""),
        ("MaxDD", "platform_long_max_drawdown_pct", 2, "%"),
        ("MonthWin", "platform_long_monthly_win_rate_pct", 2, "%"),
    )
    values: list[str] = []
    for label, field, digits, suffix in specs:
        value = row.get(field)
        if value is None or not np.isfinite(float(value)):
            text = "n/a"
        else:
            text = f"{float(value):.{digits}f}{suffix}"
        values.append(f"{label}={text}")
    local_net = row.get("local_net_excess_pct")
    local_text = "n/a" if local_net is None else f"{float(local_net):.2f}%"
    values.append(f"LocalNet={local_text}")
    return "; ".join(values)


def slim_financial_cache(
    cache: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Keep only columns consumed by the saved local financial handlers.

    ``load_financial_cache`` intentionally exposes complete statement tables
    for general research.  Attaching every one of those columns to millions
    of daily signal rows is unnecessary for this read-only correlation job and
    creates a very large temporary DataFrame.  The key columns and suffixes
    below mirror the fields read by ``build_financial_factor`` and its
    historical-rank helpers.
    """
    metadata = {
        "instrument",
        "ann_date",
        "f_ann_date",
        "end_date",
        "end_type",
        "report_type",
        "comp_type",
        "update_flag",
    }
    required = {
        "fina_indicator": {
            "roe",
            "roe_dt",
            "roa",
            "roa_yearly",
            "roic",
            "cfps",
            "ocfps",
            "debt_to_assets",
            "current_ratio",
            "grossprofit_margin",
            "assets_turn",
            "ocf_to_debt",
            "netprofit_yoy",
            "ocf_yoy",
            "op_yoy",
            "assets_yoy",
            "netprofit_margin",
        },
        "balancesheet": {
            "total_hldr_eqy_exc_min_int",
            "total_cur_assets",
            "inventories",
            "total_cur_liab",
            "total_assets",
            "total_liab",
            "money_cap",
            "cash_reser",
        },
        "income_ttm": {
            "ttm_total_revenue",
            "ttm_revenue",
            "ttm_oper_cost",
            "ttm_biz_tax_surchg",
            "ttm_n_income_attr_p",
            "ttm_n_income",
            "ttm_operate_profit",
            "ttm_ebit",
            "ttm_ebitda",
            "ttm_free_cashflow",
        },
        "cashflow_ttm": {
            "ttm_n_cashflow_act",
            "ttm_free_cashflow",
        },
    }
    slim: dict[str, pd.DataFrame] = {}
    for table_name, columns in required.items():
        table = cache.get(table_name)
        if table is None:
            continue
        keep = [
            column
            for column in table.columns
            if column in metadata or column in columns
        ]
        slim[table_name] = table.loc[:, keep].copy()
    return slim


def install_financial_snapshot_cache(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
) -> dict[str, pd.DataFrame]:
    """Cache the shared PIT snapshot for the current correlation run.

    The financial handlers all begin from the same date/instrument snapshot;
    only their final formula branch differs.  Keeping that one snapshot in
    the local module avoids rebuilding and rejoining the same rows for every
    handler.  The returned mapping is retained so the caller can release it
    after factor construction.
    """
    original = financial_local._base_signal
    snapshot: dict[str, pd.DataFrame] = {}
    expected_key = (id(frame), tuple(dates))

    def cached_base_signal(
        current_frame: pd.DataFrame,
        current_dates: list[pd.Timestamp],
    ) -> pd.DataFrame:
        key = (id(current_frame), tuple(current_dates))
        if key != expected_key:
            return original(current_frame, current_dates)
        if "selected" not in snapshot:
            snapshot["selected"] = original(current_frame, current_dates)
        return snapshot["selected"]

    financial_local._base_signal = cached_base_signal
    return snapshot


def load_platform_records(
    net_filter: str = "positive",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load supported platform records from the saved project catalog.

    This path deliberately does not use a prior local comparison report.  It
    keeps the current alignment rule version attached to the factors that are
    rebuilt below, even while a newly bumped full comparison report is being
    regenerated elsewhere.
    """
    if net_filter not in {"positive", "negative", "all"}:
        raise ValueError(f"Unsupported platform net filter: {net_filter}")
    supported, _unsupported = saved_records(formula_catalog(), net_filter)
    selected: list[dict[str, Any]] = []
    for record in supported:
        selected.append(
            {
                **record,
                "platform_net_excess_pct": float(record["platform_net_excess_pct"]),
                "local_net_excess_pct": None,
                "local_net_positive": None,
            }
        )
    selected.sort(key=lambda record: (str(record.get("name")), str(record.get("id"))))
    if len(selected) < 2:
        raise ValueError(
            f"Only {len(selected)} supported {net_filter} platform records were found"
        )
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "source_type": "saved platform report CSVs plus project formula catalog",
            "platform_net_filter": net_filter,
        }
    }
    return payload, selected


def load_records(
    path: Path,
    selection_metric: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("results")
    if not isinstance(records, list):
        raise ValueError(f"Expected a results list in {path}")
    settings = payload.get("settings")
    if not isinstance(settings, dict):
        raise ValueError(f"Expected alignment settings in {path}")
    if settings.get("alignment_rule_version") != ALIGNMENT_RULE_VERSION:
        raise ValueError(
            "Source report uses a different alignment rule version: "
            f"{settings.get('alignment_rule_version')!r}; required {ALIGNMENT_RULE_VERSION!r}"
        )
    if settings.get("platform_net_filter") != "all":
        raise ValueError(
            "The source report must be the formal all-record report with "
            "platform_net_filter=all"
        )

    selected: list[dict[str, Any]] = []
    for record in records:
        if not record.get("formula") or not record.get("handler"):
            continue
        platform_net = record.get("platform_net_excess_pct")
        local_net = record.get("local_net_excess")
        if platform_net is None:
            continue
        platform_net = float(platform_net)
        local_net_value = None if local_net is None else float(local_net)
        if selection_metric == "platform":
            keep = platform_net > 0.0
        elif selection_metric == "local":
            keep = local_net_value is not None and local_net_value > 0.0
        else:
            raise ValueError(f"Unsupported selection metric: {selection_metric}")
        if not keep:
            continue
        selected.append(
            {
                **record,
                "platform_net_excess_pct": platform_net,
                "local_net_excess_pct": (
                    None if local_net_value is None else local_net_value * 100.0
                ),
                "local_net_positive": bool(
                    local_net_value is not None and local_net_value > 0.0
                ),
            }
        )
    selected.sort(key=lambda record: (str(record.get("name")), str(record.get("id"))))
    if len(selected) < 2:
        raise ValueError(f"Only {len(selected)} selected records in {path}; need at least two")
    return payload, selected


def pairwise_daily_spearman(
    frame: pd.DataFrame,
    values: np.ndarray,
    record_pairs: list[tuple[int, int]],
    progress_every: int = 50,
) -> list[dict[str, Any]]:
    """Aggregate exact pairwise daily Spearman correlations.

    The date loop avoids materializing one large grouped DataFrame for every
    pair.  Within a date, pairs sharing the same jointly-valid mask are ranked
    together; every pair still receives ranks computed on its own valid set.
    """
    if len(values) != len(frame):
        raise ValueError("Factor matrix and comparison frame have different row counts")
    if values.shape[1] < 2:
        raise ValueError("At least two factor columns are required")

    dates = frame["date"].to_numpy()
    if len(dates) == 0:
        raise ValueError("No comparison rows")
    boundaries = np.flatnonzero(dates[1:] != dates[:-1]) + 1
    starts = np.r_[0, boundaries]
    ends = np.r_[boundaries, len(dates)]

    pair_count = len(record_pairs)
    corr_sum = np.zeros(pair_count, dtype=np.float64)
    corr_sum_sq = np.zeros(pair_count, dtype=np.float64)
    corr_count = np.zeros(pair_count, dtype=np.int64)
    observed_date_count = np.zeros(pair_count, dtype=np.int64)
    pair_rows = np.zeros(pair_count, dtype=np.int64)
    stock_count_sum = np.zeros(pair_count, dtype=np.int64)
    stock_count_min = np.full(pair_count, np.iinfo(np.int64).max, dtype=np.int64)
    stock_count_max = np.zeros(pair_count, dtype=np.int64)

    total_dates = len(starts)
    for date_index, (start, end) in enumerate(zip(starts, ends), start=1):
        date_values = values[start:end]
        valid = np.isfinite(date_values)
        grouped_pairs: dict[bytes, tuple[np.ndarray, list[int]]] = {}
        for pair_index, (left, right) in enumerate(record_pairs):
            mask = valid[:, left] & valid[:, right]
            count = int(mask.sum())
            if count < 2:
                continue
            key = mask.tobytes()
            group = grouped_pairs.get(key)
            if group is None:
                group = (mask, [])
                grouped_pairs[key] = group
            group[1].append(pair_index)

        for mask, pair_indices in grouped_pairs.values():
            involved = sorted(
                {
                    side
                    for pair_index in pair_indices
                    for side in record_pairs[pair_index]
                }
            )
            local_values = date_values[mask][:, involved]
            ranked = rankdata(local_values, axis=0, method="average")
            if ranked.ndim == 1:
                ranked = ranked[:, None]
            centered = ranked - ranked.mean(axis=0, keepdims=True)
            sum_squares = np.einsum("ij,ij->j", centered, centered)
            column_position = {column: index for index, column in enumerate(involved)}
            count = int(mask.sum())
            for pair_index in pair_indices:
                left, right = record_pairs[pair_index]
                left_values = centered[:, column_position[left]]
                right_values = centered[:, column_position[right]]
                denominator = float(
                    np.sqrt(
                        sum_squares[column_position[left]]
                        * sum_squares[column_position[right]]
                    )
                )
                pair_rows[pair_index] += count
                observed_date_count[pair_index] += 1
                stock_count_sum[pair_index] += count
                stock_count_min[pair_index] = min(stock_count_min[pair_index], count)
                stock_count_max[pair_index] = max(stock_count_max[pair_index], count)
                if denominator == 0.0 or not np.isfinite(denominator):
                    continue
                correlation = float(np.dot(left_values, right_values) / denominator)
                if not np.isfinite(correlation):
                    continue
                corr_sum[pair_index] += correlation
                corr_sum_sq[pair_index] += correlation * correlation
                corr_count[pair_index] += 1

        if progress_every and (date_index == 1 or date_index % progress_every == 0):
            print(
                f"correlation_dates={date_index}/{total_dates} "
                f"pair_masks={len(grouped_pairs)}",
                flush=True,
            )

    output: list[dict[str, Any]] = []
    for pair_index, (left, right) in enumerate(record_pairs):
        valid_days = int(corr_count[pair_index])
        if valid_days == 0:
            correlation = None
            std = None
        else:
            correlation = float(corr_sum[pair_index] / valid_days)
            variance = max(
                corr_sum_sq[pair_index] / valid_days - correlation * correlation,
                0.0,
            )
            std = float(np.sqrt(variance))
        observed_dates = int(observed_date_count[pair_index])
        output.append(
            {
                "left_index": left,
                "right_index": right,
                "correlation": correlation,
                "abs_correlation": None if correlation is None else abs(correlation),
                "days": valid_days,
                "std": std,
                "pair_rows": int(pair_rows[pair_index]),
                "common_stocks_mean": (
                    float(stock_count_sum[pair_index] / observed_dates)
                    if observed_dates
                    else None
                ),
                "common_stocks_min": (
                    int(stock_count_min[pair_index]) if observed_dates else None
                ),
                "common_stocks_max": (
                    int(stock_count_max[pair_index]) if observed_dates else None
                ),
            }
        )
    return output


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def enrich_pairs(
    records: list[dict[str, Any]],
    pair_stats: list[dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stats in pair_stats:
        left = records[stats["left_index"]]
        right = records[stats["right_index"]]
        rows.append(
            {
                "factor_a_id": left.get("id"),
                "factor_a_name": left.get("name"),
                "factor_a_report": left.get("report"),
                "factor_a_handler": left.get("handler"),
                "factor_a_formula": left.get("formula"),
                "factor_a_direction": left.get("direction"),
                "factor_a_platform_factor_direction": record_direction(left),
                "factor_a_platform_factor_id": left.get("factor_id"),
                "factor_a_platform_run_id": left.get("run_id"),
                "factor_a_configured_cycle": left.get("configured_cycle"),
                **platform_metric_values(left, "factor_a_"),
                "factor_a_local_net_excess_pct": left.get("local_net_excess_pct"),
                "factor_b_id": right.get("id"),
                "factor_b_name": right.get("name"),
                "factor_b_report": right.get("report"),
                "factor_b_handler": right.get("handler"),
                "factor_b_formula": right.get("formula"),
                "factor_b_direction": right.get("direction"),
                "factor_b_platform_factor_direction": record_direction(right),
                "factor_b_platform_factor_id": right.get("factor_id"),
                "factor_b_platform_run_id": right.get("run_id"),
                "factor_b_configured_cycle": right.get("configured_cycle"),
                **platform_metric_values(right, "factor_b_"),
                "factor_b_local_net_excess_pct": right.get("local_net_excess_pct"),
                "correlation": stats["correlation"],
                "abs_correlation": stats["abs_correlation"],
                "high_correlation": bool(
                    stats["abs_correlation"] is not None
                    and stats["abs_correlation"] >= threshold
                ),
                "days": stats["days"],
                "std": stats["std"],
                "pair_rows": stats["pair_rows"],
                "common_stocks_mean": stats["common_stocks_mean"],
                "common_stocks_min": stats["common_stocks_min"],
                "common_stocks_max": stats["common_stocks_max"],
            }
        )
    rows.sort(
        key=lambda row: (
            -float(row["abs_correlation"])
            if row["abs_correlation"] is not None
            else float("inf"),
            str(row["factor_a_name"]),
            str(row["factor_b_name"]),
        )
    )
    return rows


def build_neighbor_rows(
    records: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    threshold: float,
    fallback_neighbors: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    related: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        candidates = [
            row
            for row in pair_rows
            if row["factor_a_id"] == record.get("id")
            or row["factor_b_id"] == record.get("id")
        ]
        candidates.sort(
            key=lambda row: (
                -float(row["abs_correlation"])
                if row["abs_correlation"] is not None
                else float("inf")
            )
        )
        high = [
            row
            for row in candidates
            if row["abs_correlation"] is not None
            and float(row["abs_correlation"]) >= threshold
        ]
        selected = high if high else candidates[:fallback_neighbors]
        for rank, row in enumerate(selected, start=1):
            other = other_factor_fields(row, record.get("id"))
            related.append(
                {
                    "factor_id": record.get("id"),
                    "factor_name": record.get("name"),
                    "factor_report": record.get("report"),
                    "factor_handler": record.get("handler"),
                    "factor_formula": record.get("formula"),
                    "factor_direction": record.get("direction"),
                    "factor_platform_factor_direction": record_direction(record),
                    "factor_platform_factor_id": record.get("factor_id"),
                    "factor_platform_run_id": record.get("run_id"),
                    "factor_configured_cycle": record.get("configured_cycle"),
                    **platform_metric_values(record, "factor_"),
                    "factor_local_net_excess_pct": record.get("local_net_excess_pct"),
                    "other_factor_id": other["id"],
                    "other_factor_name": other["name"],
                    "other_factor_report": other["report"],
                    "other_factor_handler": other["handler"],
                    "other_factor_formula": other["formula"],
                    "other_factor_direction": other["direction"],
                    "other_factor_platform_factor_direction": other["platform_factor_direction"],
                    "other_factor_platform_factor_id": other["platform_factor_id"],
                    "other_factor_platform_run_id": other["platform_run_id"],
                    "other_factor_configured_cycle": other["configured_cycle"],
                    **{
                        f"other_factor_{field}": other.get(field)
                        for field in PLATFORM_METRIC_FIELDS
                    },
                    "other_factor_local_net_excess_pct": other["local_net_excess_pct"],
                    "correlation": row["correlation"],
                    "abs_correlation": row["abs_correlation"],
                    "relation_type": "high" if high else "nearest_below_threshold",
                    "rank": rank,
                    "high_threshold": threshold,
                    "days": row["days"],
                    "common_stocks_mean": row["common_stocks_mean"],
                }
            )
        high_descriptions = [
            format_neighbor_description(row, record.get("id"), include_net=True)
            for row in high
        ]
        high_names = [
            format_neighbor_description(row, record.get("id"), include_net=False)
            for row in high
        ]
        nearest = candidates[0] if candidates else None
        if nearest is None:
            nearest_name = None
            nearest_corr = None
            nearest_abs = None
        elif nearest["factor_a_id"] == record.get("id"):
            nearest_name = format_neighbor_description(
                nearest, record.get("id"), include_net=False
            )
            nearest_corr = nearest["correlation"]
            nearest_abs = nearest["abs_correlation"]
        else:
            nearest_name = format_neighbor_description(
                nearest, record.get("id"), include_net=False
            )
            nearest_corr = nearest["correlation"]
            nearest_abs = nearest["abs_correlation"]
        summary = factor_detail_fields(record)
        summary.update(
            {
                "local_net_excess_pct": record.get("local_net_excess_pct"),
                "local_net_positive": record.get("local_net_positive"),
                "high_threshold": threshold,
                "high_neighbor_count": len(high),
                "high_neighbor_names": "; ".join(high_names),
                "high_neighbors": "; ".join(high_descriptions),
                "nearest_factor": nearest_name,
                "nearest_correlation": nearest_corr,
                "nearest_abs_correlation": nearest_abs,
                "neighbor_rows_written": len(selected),
            }
        )
        summaries.append(summary)
    summaries.sort(key=lambda row: str(row["factor_name"]))
    related.sort(key=lambda row: (str(row["factor_name"]), int(row["rank"])))
    return related, summaries


def write_outputs(
    *,
    output_prefix: Path,
    source_path: Path,
    source_payload: dict[str, Any],
    records: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    neighbor_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    settings: dict[str, Any],
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    pairs_path = output_prefix.with_suffix(".pairs.csv")
    neighbors_path = output_prefix.with_suffix(".neighbors.csv")
    summary_path = output_prefix.with_suffix(".summary.csv")
    json_path = output_prefix.with_suffix(".json")
    markdown_path = output_prefix.with_suffix(".md")
    pd.DataFrame(pair_rows).to_csv(pairs_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(neighbor_rows).to_csv(neighbors_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding="utf-8-sig")

    json_records = []
    for record in records:
        json_record = {
            "id": record.get("id"),
            "name": record.get("name"),
            "report": record.get("report"),
            "handler": record.get("handler"),
            "formula": record.get("formula"),
            "direction": record.get("direction"),
            "platform_factor_direction": record_direction(record),
            "platform_factor_id": record.get("factor_id"),
            "platform_run_id": record.get("run_id"),
            "configured_cycle": record.get("configured_cycle"),
            "local_net_excess_pct": record.get("local_net_excess_pct"),
            "local_net_positive": record.get("local_net_positive"),
        }
        json_record.update(platform_metric_values(record))
        json_records.append(json_record)
    json_payload = {
        "settings": settings,
        "source": {
            "path": str(source_path),
            "type": settings.get("source_type"),
            "alignment_rule_version": source_payload.get("settings", {}).get(
                "alignment_rule_version"
            ),
        },
        "records": json_records,
        "pairs": pair_rows,
        "artifacts": {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "pairs_csv": str(pairs_path),
            "neighbors_csv": str(neighbors_path),
            "summary_csv": str(summary_path),
        },
    }
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    high_rows = [row for row in pair_rows if row["high_correlation"]]
    selection_condition = settings.get("selection_condition", "saved records")
    lines = [
        "# Saved-platform factor pair correlations",
        "",
        "This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.",
        "",
        "## Fixed inputs",
        "",
        f"- Source: `{settings['source_type']}` under `{source_path}`; selection: `{selection_condition}`.",
        f"- Selected factors: `{settings['factor_count']}` records, `{settings['handler_count']}` unique handlers; pair count: `{settings['pair_count']}`.",
        f"- Window: `{settings['comparison_start']}..{settings['comparison_end']}`; warm-up starts `{settings['data_start']}`; trading dates: `{settings['comparison_dates']}`.",
        f"- Universe: `{ALIGNMENT_UNIVERSE_LABEL}`; prices `{ALIGNMENT_PRICE_MODE}`; market cap `{ALIGNMENT_MARKET_CAP_FIELD}`.",
        f"- Correlation: `{ALIGNMENT_CORRELATION_METHOD}`; {ALIGNMENT_CORRELATION_DESCRIPTION}.",
        f"- High-correlation threshold: `|rho| >= {settings['high_correlation_threshold']:.2f}`. Both positive and negative correlations are retained as potential duplicate exposures.",
        f"- High-correlation pairs: `{len(high_rows)}` unique pairs.",
        "",
        "## Per-factor neighbors",
        "",
        "The table lists every pair meeting the threshold for each factor. If a factor has no such pair, its nearest pair below the threshold is listed so every factor has a recorded closest neighbor.",
        "",
        "| Factor | Handler | Direction | Platform metrics | High-correlation other factors | Nearest other factor | Nearest rho |",
        "|---|---|---:|---|---|---|---:|",
    ]
    for row in summary_rows:
        high_neighbors = row["high_neighbors"] or "none"
        nearest_corr_text = (
            "n/a"
            if row["nearest_correlation"] is None
            else f"{float(row['nearest_correlation']):+.6f}"
        )
        lines.append(
            f"| {row['factor_name']} | `{row['handler']}` | {row.get('direction', 'n/a')} | "
            f"{format_platform_metrics(row)} | "
            f"{high_neighbors} | {row['nearest_factor'] or 'n/a'} | "
            f"{nearest_corr_text} |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Full pair matrix: `{pairs_path}`.",
            f"- Per-factor high-correlation/nearest neighbors: `{neighbors_path}`.",
            f"- Per-factor summary: `{summary_path}`.",
            f"- Machine-readable JSON: `{json_path}`.",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        default=None,
        help="Optional aligned local-comparison JSON; omitted means use saved platform report CSVs",
    )
    parser.add_argument(
        "--selection-metric",
        choices=["platform", "local"],
        default="platform",
        help="Select records by platform_net_excess_pct or local_net_excess",
    )
    parser.add_argument(
        "--platform-net-filter",
        choices=["positive", "negative", "all"],
        default="positive",
        help="When loading saved report CSVs, select positive, negative, or all completed records",
    )
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--start", default=ALIGNMENT_START)
    parser.add_argument("--end", default=ALIGNMENT_END)
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--financial-root", default=str(DEFAULT_FINANCIAL_ROOT))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT_PREFIX))
    parser.add_argument("--high-correlation-threshold", type=float, default=0.80)
    parser.add_argument(
        "--fallback-neighbors",
        type=int,
        default=1,
        help="Nearest below-threshold rows written for a factor with no high pair",
    )
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    if not 0.0 <= args.high_correlation_threshold <= 1.0:
        raise SystemExit("high-correlation-threshold must be between 0 and 1")
    if args.fallback_neighbors < 0:
        raise SystemExit("fallback-neighbors must be non-negative")

    data_start = parse_date(args.data_start)
    start = parse_date(args.start)
    end = parse_date(args.end)
    if data_start > start or start > end:
        raise SystemExit("dates must satisfy data-start <= start <= end")

    if args.records is None:
        if args.selection_metric != "platform":
            raise SystemExit("--records is required when --selection-metric=local")
        source_payload, records = load_platform_records(args.platform_net_filter)
        source_path = PROJECT_ROOT
        selection_condition = (
            "all completed saved platform records"
            if args.platform_net_filter == "all"
            else f"platform net excess {args.platform_net_filter} 0"
        )
    else:
        source_path = Path(args.records)
        source_payload, records = load_records(source_path, args.selection_metric)
        selection_condition = f"{args.selection_metric} net excess > 0"
    print(
        f"selected_records={len(records)} unique_handlers={len({r['handler'] for r in records})} "
        f"selection={args.selection_metric}",
        flush=True,
    )

    print("loading local full-A data...", flush=True)
    frame = load_full_a_data(Path(args.price_root), Path(args.cap_root), data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(data_start, end, token=None)
    ]
    comparison_dates = [date for date in calendar if start <= date <= end]
    if not comparison_dates:
        raise SystemExit("no comparison dates in the cached trade calendar")
    comparison_frame = frame[frame["date"].isin(comparison_dates)].sort_values(
        ["date", "instrument"], kind="stable"
    )
    if comparison_frame.empty:
        raise SystemExit("no local rows on comparison dates")
    print(
        f"frame_rows={len(frame)} comparison_rows={len(comparison_frame)} "
        f"instruments={frame['instrument'].nunique()} comparison_dates={len(comparison_dates)}",
        flush=True,
    )

    financial_handlers = {
        str(record["handler"])
        for record in records
        if str(record["handler"]) in FINANCIAL_HANDLERS
    }
    financial: dict[str, pd.DataFrame] | None = None
    if financial_handlers:
        print(f"loading financial cache for {len(financial_handlers)} handlers...", flush=True)
        raw_financial = load_financial_cache(Path(args.financial_root))
        financial = slim_financial_cache(raw_financial)
        del raw_financial
        gc.collect()
        print(
            "financial_cache_columns="
            + ", ".join(
                f"{name}:{len(table.columns)}" for name, table in financial.items()
            ),
            flush=True,
        )

    handlers = sorted({str(record["handler"]) for record in records})
    financial_snapshot: dict[str, pd.DataFrame] = {}
    if financial is not None:
        financial_snapshot = install_financial_snapshot_cache(frame, comparison_dates)
    handler_values: dict[str, np.ndarray] = {}
    comparison_index = comparison_frame.index
    for index, handler in enumerate(handlers, start=1):
        print(f"building handler={handler} ({index}/{len(handlers)})...", flush=True)
        values = build_factor(
            frame,
            handler,
            financial=financial,
            signal_dates=comparison_dates,
        )
        aligned = pd.to_numeric(values.reindex(comparison_index), errors="coerce")
        handler_values[handler] = aligned.to_numpy(dtype=np.float64)
        print(
            f"handler={handler} valid_rows={int(np.isfinite(handler_values[handler]).sum())}",
            flush=True,
        )
        del values, aligned
        gc.collect()

    financial_snapshot.clear()
    financial_local._HISTORICAL_RANK_CACHE.clear()
    gc.collect()

    record_values = np.column_stack(
        [handler_values[str(record["handler"])] for record in records]
    )
    del handler_values
    gc.collect()
    record_pairs = list(itertools.combinations(range(len(records)), 2))
    print(f"calculating_pairs={len(record_pairs)}", flush=True)
    pair_stats = pairwise_daily_spearman(
        comparison_frame,
        record_values,
        record_pairs,
        progress_every=args.progress_every,
    )
    del record_values
    gc.collect()

    pair_rows = enrich_pairs(records, pair_stats, args.high_correlation_threshold)
    neighbor_rows, summary_rows = build_neighbor_rows(
        records,
        pair_rows,
        args.high_correlation_threshold,
        args.fallback_neighbors,
    )
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "source_type": "saved project platform report CSVs and candidate formula catalog",
        "selection_metric": args.selection_metric,
        "platform_net_filter": args.platform_net_filter,
        "selection_condition": selection_condition,
        "universe": ALIGNMENT_UNIVERSE_LABEL,
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": data_start.strftime("%Y%m%d"),
        "comparison_start": start.strftime("%Y%m%d"),
        "comparison_end": end.strftime("%Y%m%d"),
        "comparison_dates": len(comparison_dates),
        "comparison_rows": len(comparison_frame),
        "comparison_instruments": int(comparison_frame["instrument"].nunique()),
        "correlation_method": ALIGNMENT_CORRELATION_METHOD,
        "correlation_description": ALIGNMENT_CORRELATION_DESCRIPTION,
        "factor_count": len(records),
        "handler_count": len(handlers),
        "pair_count": len(pair_rows),
        "high_correlation_threshold": args.high_correlation_threshold,
        "fallback_neighbors": args.fallback_neighbors,
        "high_pair_count": sum(row["high_correlation"] for row in pair_rows),
        "market_field_sources": frame.attrs.get("market_field_sources", {}),
    }
    output_prefix = Path(args.output_prefix)
    write_outputs(
        output_prefix=output_prefix,
        source_path=source_path,
        source_payload=source_payload,
        records=records,
        pair_rows=pair_rows,
        neighbor_rows=neighbor_rows,
        summary_rows=summary_rows,
        settings=settings,
    )
    print(f"report={output_prefix.with_suffix('.md')}", flush=True)
    print(f"high_pairs={settings['high_pair_count']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
