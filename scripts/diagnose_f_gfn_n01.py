#!/usr/bin/env python3
"""Deep offline diagnosis for the saved F-GFN-N01 platform run.

The script reads the archived PandaAI response and the local Tushare cache. It
does not create factors, call the platform, or change the canonical alignment
rules.  Raw daily data is intentionally limited to the available 2024 file
and is reported as a separate sensitivity rather than mixed into the formal
qfq/full-A result.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_MODE,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_ROUND_TRIP_COST,
)
from tushare_factor_recheck import load_trade_dates  # noqa: E402


GROUPS = ALIGNMENT_GROUPS
CYCLE = 5
PLATFORM_GROUP = 10
DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
END = pd.Timestamp(ALIGNMENT_END)
PLATFORM_RESULT = (
    PROJECT_ROOT
    / "alphaprobe-gfn-new-20260916-candidates.results"
    / "6aaa71e56df2a192a47e8de1.json"
)
DEFAULT_PRICE_ROOT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
)
DEFAULT_CAP_ROOT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
)
DEFAULT_RAW_ROOT = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/daily"
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/f_gfn_n01_20260917"


def parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(
        pd.to_datetime(value, format="%Y%m%d" if len(str(value)) == 8 else None)
    ).normalize()


def day_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (pd.Series, pd.Index)):
        return value.tolist()
    if pd.isna(value):
        return None
    return value


def arithmetic_periods(cumulative: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(cumulative), dtype=float)
    if not len(values):
        return np.asarray([], dtype=float)
    return np.diff(np.concatenate(([0.0], values)))


def platform_period_frame(platform: dict[str, Any]) -> pd.DataFrame:
    dates = pd.DatetimeIndex(platform["dates"]).normalize()
    rank = np.asarray(platform.get("rank_ic_values", []), dtype=float)
    if len(dates) != len(rank):
        raise RuntimeError("Platform chart dates and RankIC series lengths do not match")

    result: dict[str, Any] = {"date": dates, "platform_rank_ic": rank}
    for group in range(1, GROUPS + 1):
        if len(platform.get("return_cumulative", [])) < group:
            raise RuntimeError(f"Platform return chart has no group {group}")
        if len(platform.get("excess_cumulative", [])) < group:
            raise RuntimeError(f"Platform excess chart has no group {group}")
        returns = arithmetic_periods(platform["return_cumulative"][group - 1])
        excess = arithmetic_periods(platform["excess_cumulative"][group - 1])
        if not (len(dates) == len(returns) == len(excess)):
            raise RuntimeError(f"Platform chart series lengths do not match for group {group}")
        result[f"platform_group_return_{group}"] = returns
        result[f"platform_excess_{group}"] = excess
        result[f"platform_benchmark_{group}"] = returns - excess
        result[f"platform_group_cumulative_{group}"] = np.cumsum(returns)
        result[f"platform_excess_cumulative_{group}"] = np.cumsum(excess)

    # Keep the original selected-group aliases for the headline diagnostics.
    result["platform_group_return"] = result[f"platform_group_return_{PLATFORM_GROUP}"]
    result["platform_excess"] = result[f"platform_excess_{PLATFORM_GROUP}"]
    result["platform_benchmark"] = result[f"platform_benchmark_{PLATFORM_GROUP}"]
    result["platform_group_cumulative"] = result[
        f"platform_group_cumulative_{PLATFORM_GROUP}"
    ]
    result["platform_excess_cumulative"] = result[
        f"platform_excess_cumulative_{PLATFORM_GROUP}"
    ]
    return pd.DataFrame(result)


def correlation_summary(
    left: pd.Series, right: pd.Series, *, scale: float = 1.0
) -> dict[str, Any]:
    joined = pd.concat(
        [pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")],
        axis=1,
    )
    joined.columns = ["local", "platform"]
    joined = joined.replace([np.inf, -np.inf], np.nan).dropna()
    if joined.empty:
        return {"n": 0, "corr": None, "rmse": None, "mean_delta": None, "sign_agreement": None}
    delta = joined["local"] - joined["platform"]
    return {
        "n": int(len(joined)),
        "corr": finite(joined["local"].corr(joined["platform"]))
        if len(joined) > 1
        else None,
        "rmse": finite(np.sqrt(np.mean(delta**2)) * scale),
        "mean_delta": finite(delta.mean() * scale),
        "sign_agreement": finite(
            np.mean(np.sign(joined["local"]) == np.sign(joined["platform"]))
        ),
    }


def load_raw_2024(raw_root: Path) -> pd.DataFrame:
    paths = sorted(raw_root.glob("2024*.parquet"))
    if not paths:
        paths = sorted(raw_root.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No raw daily parquet found under {raw_root}")
    frames: list[pd.DataFrame] = []
    for path in paths:
        available = set(pq.ParquetFile(path).schema_arrow.names)
        wanted = [
            column
            for column in [
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "vol",
                "amount",
            ]
            if column in available
        ]
        part = pd.read_parquet(path, columns=wanted)
        if part.empty:
            continue
        part = part.rename(
            columns={
                "ts_code": "instrument",
                "trade_date": "date",
                "vol": "volume",
            }
        )
        part["date"] = pd.to_datetime(part["date"], format="mixed", errors="coerce").dt.normalize()
        part["instrument"] = part["instrument"].astype(str)
        part = part[
            part["instrument"].str.endswith((".SH", ".SZ"))
            & part["date"].between(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"))
        ]
        frames.append(part)
    if not frames:
        raise RuntimeError("The raw daily cache has no 2024 .SH/.SZ rows")
    result = pd.concat(frames, ignore_index=True)
    for column in ["open", "high", "low", "close", "volume", "amount"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.drop_duplicates(["date", "instrument"], keep="last")
    return result.sort_values(["instrument", "date"], ignore_index=True)


def signal_source_rows(
    price_root: Path, wanted_dates: set[pd.Timestamp]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read only platform signal dates to audit overlapping qfq source files."""
    paths = sorted(price_root.glob("batch_*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No qfq parquet batches found under {price_root}")
    schema_counts: Counter[str] = Counter()
    total_rows = 0
    parts: list[pd.DataFrame] = []
    wanted_columns = [
        "date",
        "instrument",
        "open",
        "close",
        "volume",
        "high_qfq",
        "low_qfq",
        "amount",
    ]
    wanted_array = np.array(sorted(wanted_dates), dtype="datetime64[ns]")
    for path in paths:
        schema = tuple(pq.ParquetFile(path).schema_arrow.names)
        schema_counts["|".join(schema)] += 1
        total_rows += int(pq.ParquetFile(path).metadata.num_rows)
        columns = [column for column in wanted_columns if column in schema]
        part = pd.read_parquet(path, columns=columns)
        if part.empty:
            continue
        part["date"] = pd.to_datetime(part["date"], errors="coerce").dt.normalize()
        part = part[part["date"].isin(wanted_array)].copy()
        if part.empty:
            continue
        part["instrument"] = part["instrument"].astype(str)
        part = part[part["instrument"].str.endswith((".SH", ".SZ"))]
        parts.append(part)
    if not parts:
        raise RuntimeError("No qfq source rows found on the platform signal dates")
    source = pd.concat(parts, ignore_index=True)
    for column in ["open", "close", "volume", "high_qfq", "low_qfq", "amount"]:
        if column in source.columns:
            source[column] = pd.to_numeric(source[column], errors="coerce")
    source["_rich_field_count"] = source[
        [column for column in ["high_qfq", "low_qfq", "amount"] if column in source.columns]
    ].notna().sum(axis=1)
    duplicate_rows = int(source.duplicated(["date", "instrument"], keep=False).sum())
    duplicate_extra = int(len(source) - source.drop_duplicates(["date", "instrument"]).shape[0])
    source = source.sort_values(
        ["date", "instrument", "_rich_field_count"], kind="stable"
    ).drop_duplicates(["date", "instrument"], keep="last")
    source = source.drop(columns=["_rich_field_count"])
    field_stats = {}
    for column in ["high_qfq", "low_qfq", "amount"]:
        if column in source.columns:
            values = pd.to_numeric(source[column], errors="coerce")
            field_stats[column] = {
                "non_null": int(values.notna().sum()),
                "positive": int(values.gt(0).sum()),
                "rows": int(len(values)),
            }
    audit = {
        "file_count": len(paths),
        "schema_counts": dict(schema_counts),
        "all_file_rows": total_rows,
        "signal_source_rows_before_dedup": int(len(parts and pd.concat(parts, ignore_index=True))),
        "signal_source_rows_after_dedup": int(len(source)),
        "duplicate_key_rows": duplicate_rows,
        "duplicate_key_extra_rows": duplicate_extra,
        "signal_dates_requested": len(wanted_dates),
        "signal_dates_present": int(source["date"].nunique()),
        "field_stats_after_dedup": field_stats,
    }
    return source, audit


def daily_basic_source_audit(cap_root: Path, wanted_dates: set[pd.Timestamp]) -> dict[str, Any]:
    paths = sorted(cap_root.glob("daily_basic_*.parquet"))
    matched: list[Path] = []
    date_pattern = re.compile(r"daily_basic_(\d{8})$")
    for path in paths:
        match = date_pattern.match(path.stem)
        if match and parse_date(match.group(1)) in wanted_dates:
            matched.append(path)
    rows: list[pd.DataFrame] = []
    for path in matched:
        part = pd.read_parquet(path, columns=["date", "instrument", "total_mv"])
        part["date"] = pd.to_datetime(part["date"], errors="coerce").dt.normalize()
        part["instrument"] = part["instrument"].astype(str)
        part = part[part["instrument"].str.endswith((".SH", ".SZ"))]
        rows.append(part)
    if rows:
        frame = pd.concat(rows, ignore_index=True)
        duplicate_extra = int(len(frame) - frame.drop_duplicates(["date", "instrument"]).shape[0])
        present_dates = int(frame["date"].nunique())
        positive_mv = int(pd.to_numeric(frame["total_mv"], errors="coerce").gt(0).sum())
        total_rows = int(len(frame))
    else:
        duplicate_extra = present_dates = positive_mv = total_rows = 0
    return {
        "file_count": len(paths),
        "signal_date_files": len(matched),
        "signal_dates_requested": len(wanted_dates),
        "signal_dates_present": present_dates,
        "rows": total_rows,
        "duplicate_key_extra_rows": duplicate_extra,
        "positive_total_mv_rows": positive_mv,
    }


def source_reconciliation(
    qfq_source: pd.DataFrame, raw: pd.DataFrame, frame: pd.DataFrame
) -> dict[str, Any]:
    qfq = qfq_source[qfq_source["date"].between("2024-01-01", "2024-12-31")].copy()
    # Compare source-selected qfq fields directly with raw fields. The
    # separately reported loaded-frame audit covers the values after the
    # daily_basic join used by the canonical evaluator.
    joined = qfq.merge(raw, on=["date", "instrument"], how="inner", suffixes=("_qfq", "_raw"))

    def compare(left: str, right: str) -> dict[str, Any]:
        if left not in joined or right not in joined:
            return {"n": 0, "exact_fraction": None, "median_relative_error": None}
        a = pd.to_numeric(joined[left], errors="coerce")
        b = pd.to_numeric(joined[right], errors="coerce")
        valid = a.notna() & b.notna() & b.ne(0)
        if not valid.any():
            return {"n": 0, "exact_fraction": None, "median_relative_error": None}
        a = a[valid]
        b = b[valid]
        relative = a.sub(b).div(b.abs().clip(lower=1e-12))
        return {
            "n": int(len(a)),
            "exact_fraction": float(np.mean(np.isclose(a, b, rtol=1e-10, atol=1e-8))),
            "median_relative_error": finite(relative.median()),
            "p95_absolute_relative_error": finite(relative.abs().quantile(0.95)),
        }

    def ratio_stats(left: str, right: str) -> dict[str, Any]:
        if left not in joined or right not in joined:
            return {"n": 0, "median": None, "p05": None, "p95": None}
        a = pd.to_numeric(joined[left], errors="coerce")
        b = pd.to_numeric(joined[right], errors="coerce")
        valid = a.notna() & b.notna() & b.ne(0)
        if not valid.any():
            return {"n": 0, "median": None, "p05": None, "p95": None}
        ratio = a[valid].div(b[valid]).replace([np.inf, -np.inf], np.nan).dropna()
        if ratio.empty:
            return {"n": 0, "median": None, "p05": None, "p95": None}
        return {
            "n": int(len(ratio)),
            "median": finite(ratio.median()),
            "p05": finite(ratio.quantile(0.05)),
            "p95": finite(ratio.quantile(0.95)),
        }

    result: dict[str, Any] = {
        "raw_rows_2024": int(len(raw)),
        "qfq_signal_rows_2024": int(len(qfq)),
        "joined_rows_2024": int(len(joined)),
        "coverage_vs_raw": float(len(joined) / len(raw)) if len(raw) else None,
        "field_comparisons": {
            "volume_qfq_vs_volume_raw": compare("volume_qfq", "volume_raw"),
            "amount_qfq_vs_amount_raw": compare("amount_qfq", "amount_raw"),
            # qfq source already uses the distinct name ``high_qfq``; raw
            # daily data therefore remains ``high`` after the merge.
            "high_qfq_vs_high_raw": compare("high_qfq", "high"),
            "close_qfq_vs_close_raw": compare("close_qfq", "close_raw"),
        },
        "field_ratios_qfq_over_raw": {
            "volume": ratio_stats("volume_qfq", "volume_raw"),
            "amount": ratio_stats("amount_qfq", "amount_raw"),
            "high": ratio_stats("high_qfq", "high"),
            "close": ratio_stats("close_qfq", "close_raw"),
        },
    }
    high_ratio = pd.to_numeric(joined.get("high_qfq"), errors="coerce").div(
        pd.to_numeric(joined.get("high"), errors="coerce")
    )
    close_ratio = pd.to_numeric(joined.get("close_qfq"), errors="coerce").div(
        pd.to_numeric(joined.get("close_raw"), errors="coerce")
    )
    ratio = pd.DataFrame({"high_adjustment_ratio": high_ratio, "close_adjustment_ratio": close_ratio}).replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    ratio_delta = ratio["high_adjustment_ratio"] - ratio["close_adjustment_ratio"]
    result["adjustment_ratio_consistency"] = {
        "n": int(len(ratio)),
        "high_ratio_median": finite(ratio["high_adjustment_ratio"].median()),
        "close_ratio_median": finite(ratio["close_adjustment_ratio"].median()),
        "ratio_delta_median": finite(ratio_delta.median()),
        "ratio_delta_p95_abs": finite(ratio_delta.abs().quantile(0.95))
        if len(ratio)
        else None,
    }
    return result


def make_close_panel(
    frame: pd.DataFrame, calendar: list[pd.Timestamp]
) -> pd.DataFrame:
    observed = frame.pivot(index="date", columns="instrument", values="close_qfq")
    return observed.reindex(calendar).sort_index(axis=1).ffill()


def panel_long(panel: pd.DataFrame, dates: list[pd.Timestamp], name: str) -> pd.DataFrame:
    work = panel.copy()
    work.index = pd.DatetimeIndex(dates)
    result = work.stack(dropna=False).rename(name).reset_index()
    return result.rename(columns={"level_0": "date", "level_1": "instrument"})


def build_returns(
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    label_offset: int,
) -> pd.DataFrame:
    positions = {date: index for index, date in enumerate(calendar)}
    current_positions = [positions[date] + label_offset for date in signal_dates]
    future_positions = [position + cycle for position in current_positions]
    if min(current_positions, default=0) < 0 or max(future_positions, default=-1) >= len(calendar):
        raise RuntimeError("Local data does not cover the requested forward label")
    current = panel_long(close.iloc[current_positions], signal_dates, "current_close")
    future = panel_long(close.iloc[future_positions], signal_dates, "future_close")
    result = current.merge(future, on=["date", "instrument"], how="left")
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    return result[["date", "instrument", "forward_return"]]


def factor_from_denominator(frame: pd.DataFrame, column: str) -> pd.Series:
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    denominator = pd.to_numeric(frame[column], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        result = amount.div(volume.replace(0.0, np.nan)).div(
            denominator.replace(0.0, np.nan)
        )
    return result.replace([np.inf, -np.inf], np.nan)


def raw_factor_values(frame: pd.DataFrame, raw: pd.DataFrame, column: str) -> pd.Series:
    keys = frame.loc[
        frame["date"].between("2024-01-01", "2024-12-31"),
        ["date", "instrument"],
    ].copy()
    keys["_row_id"] = keys.index.to_numpy(dtype=np.int64)
    fields = ["date", "instrument", "amount", "volume", column]
    source = raw[[field for field in fields if field in raw.columns]].copy()
    joined = keys.merge(source, on=["date", "instrument"], how="left")
    amount = pd.to_numeric(joined["amount"], errors="coerce")
    volume = pd.to_numeric(joined["volume"], errors="coerce")
    denominator = pd.to_numeric(joined[column], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        values = amount.div(volume.replace(0.0, np.nan)).div(
            denominator.replace(0.0, np.nan)
        )
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    result.loc[joined["_row_id"].to_numpy(dtype=np.int64)] = values.replace(
        [np.inf, -np.inf], np.nan
    ).to_numpy()
    return result


def evaluate_variant(
    frame: pd.DataFrame,
    factor_values: pd.Series,
    returns: pd.DataFrame,
    platform_periods: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    label_offset: int,
    variant: str,
    scope: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = pd.to_numeric(factor_values.to_numpy(), errors="coerce")
    factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]
    data = factor_frame.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    previous_members: dict[int, set[str]] = {}
    rows: list[dict[str, Any]] = []
    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = np.ceil(
            current["factor"].rank(method="first") * GROUPS / len(current)
        ).astype(int).clip(1, GROUPS)
        factor_rank = current["factor"].rank(method="average")
        return_rank = current["forward_return"].rank(method="average")
        rank_ic = factor_rank.corr(return_rank)
        ic = current["factor"].corr(current["forward_return"])
        benchmark = float(current["forward_return"].mean())
        row: dict[str, Any] = {
            "variant": variant,
            "scope": scope,
            "label_offset": label_offset,
            "date": date,
            "stock_count": int(len(current)),
            "rank_ic": finite(rank_ic),
            "ic": finite(ic),
            "benchmark": benchmark,
        }
        for group in range(1, GROUPS + 1):
            selected = current[current["group"].eq(group)]
            members = set(selected["instrument"].astype(str))
            previous = previous_members.get(group)
            turnover = (
                float(1.0 - len(members.intersection(previous)) / len(members))
                if previous
                else np.nan
            )
            previous_members[group] = members
            group_return = float(selected["forward_return"].mean())
            row[f"group_{group}_return"] = group_return
            row[f"group_{group}_excess"] = group_return - benchmark
            row[f"turnover_{group}"] = finite(turnover)
            row[f"group_{group}_count"] = int(len(selected))

        # Preserve the selected-group aliases used by the existing headline
        # report and by the previously generated period CSVs.
        row["group_return"] = row[f"group_{PLATFORM_GROUP}_return"]
        row["excess"] = row[f"group_{PLATFORM_GROUP}_excess"]
        row["turnover"] = row[f"turnover_{PLATFORM_GROUP}"]
        row["selected_count"] = row[f"group_{PLATFORM_GROUP}_count"]
        rows.append(row)
    local_periods = pd.DataFrame(rows)
    if local_periods.empty:
        raise RuntimeError(f"No valid local periods for {variant}, label_offset={label_offset}")
    local_periods["date"] = pd.to_datetime(local_periods["date"]).dt.normalize()
    joined = local_periods.merge(platform_periods, on="date", how="inner")
    periods_per_year = 252.0 / CYCLE
    years = len(local_periods) / periods_per_year
    local_gross = float(local_periods["excess"].sum() / years)
    turnover_values = local_periods["turnover"].dropna()
    local_turnover = float(turnover_values.mean()) if not turnover_values.empty else None
    local_cost = (
        local_turnover * periods_per_year * ALIGNMENT_ROUND_TRIP_COST
        if local_turnover is not None
        else None
    )
    local_net = local_gross - local_cost if local_cost is not None else None
    platform_metric = {
        key: platform_periods.attrs.get("platform_group_metrics", {})
        .get(PLATFORM_GROUP, {})
        .get(key)
        for key in ["annualizedReturn", "excessAnnualized", "turnoverRate", "sharpeRatio"]
    }
    platform_net = (
        platform_metric["excessAnnualized"]
        - platform_metric["turnoverRate"] * periods_per_year * ALIGNMENT_ROUND_TRIP_COST
        if platform_metric["excessAnnualized"] is not None
        and platform_metric["turnoverRate"] is not None
        else None
    )
    platform_turnover_cost = (
        platform_metric["turnoverRate"] * periods_per_year * ALIGNMENT_ROUND_TRIP_COST
        if platform_metric["turnoverRate"] is not None
        else None
    )
    sensitivity_net = (
        local_gross - platform_turnover_cost
        if platform_turnover_cost is not None
        else None
    )
    # Cumulative comparisons are built on the joined date sequence.  This is
    # important for the 2024 raw sensitivity, whose platform series starts
    # before the sensitivity window.
    joined["local_cumulative_excess"] = joined["excess"].cumsum()
    joined["local_cumulative_return"] = joined["group_return"].cumsum()
    joined["platform_subset_cumulative_excess"] = joined["platform_excess"].cumsum()
    joined["platform_subset_cumulative_return"] = joined["platform_group_return"].cumsum()
    if joined.empty:
        largest = None
    else:
        joined["delta_excess"] = joined["excess"] - joined["platform_excess"]
        largest = joined.loc[joined["delta_excess"].abs().idxmax()]

    group_comparisons: list[dict[str, Any]] = []
    for group in range(1, GROUPS + 1):
        local_return = local_periods[f"group_{group}_return"].to_numpy(dtype=float)
        local_excess = local_periods[f"group_{group}_excess"].to_numpy(dtype=float)
        local_turnover_values = local_periods[f"turnover_{group}"].dropna()
        platform_return = platform_periods[f"platform_group_return_{group}"].to_numpy(
            dtype=float
        )
        platform_excess = platform_periods[f"platform_excess_{group}"].to_numpy(
            dtype=float
        )
        group_joined = local_periods[
            ["date", f"group_{group}_return", f"group_{group}_excess"]
        ].merge(
            platform_periods[
                [
                    "date",
                    f"platform_group_return_{group}",
                    f"platform_excess_{group}",
                ]
            ],
            on="date",
            how="inner",
        )
        return_sequence = correlation_summary(
            group_joined[f"group_{group}_return"],
            group_joined[f"platform_group_return_{group}"],
            scale=100.0,
        )
        excess_sequence = correlation_summary(
            group_joined[f"group_{group}_excess"],
            group_joined[f"platform_excess_{group}"],
            scale=100.0,
        )

        best_return_match: tuple[int, dict[str, Any]] | None = None
        best_excess_match: tuple[int, dict[str, Any]] | None = None
        for platform_group in range(1, GROUPS + 1):
            candidate = local_periods[["date", f"group_{group}_return", f"group_{group}_excess"]].merge(
                platform_periods[
                    [
                        "date",
                        f"platform_group_return_{platform_group}",
                        f"platform_excess_{platform_group}",
                    ]
                ],
                on="date",
                how="inner",
            )
            return_match = correlation_summary(
                candidate[f"group_{group}_return"],
                candidate[f"platform_group_return_{platform_group}"],
            )
            excess_match = correlation_summary(
                candidate[f"group_{group}_excess"],
                candidate[f"platform_excess_{platform_group}"],
            )
            if return_match.get("corr") is not None and (
                best_return_match is None
                or return_match["corr"] > best_return_match[1]["corr"]
            ):
                best_return_match = (platform_group, return_match)
            if excess_match.get("corr") is not None and (
                best_excess_match is None
                or excess_match["corr"] > best_excess_match[1]["corr"]
            ):
                best_excess_match = (platform_group, excess_match)

        metric = platform_periods.attrs.get("platform_group_metrics", {}).get(group, {})
        local_years = len(local_return) / periods_per_year
        platform_years = len(platform_return) / periods_per_year
        group_comparisons.append(
            {
                "variant": variant,
                "scope": scope,
                "label_offset": label_offset,
                "group": group,
                "periods": int(len(local_return)),
                "platform_periods": int(len(platform_return)),
                "local_cumulative_return": finite(np.nansum(local_return)),
                "platform_cumulative_return_window": finite(np.nansum(platform_return)),
                "local_cumulative_excess": finite(np.nansum(local_excess)),
                "platform_cumulative_excess_window": finite(np.nansum(platform_excess)),
                "local_annualized_return": finite(
                    np.nansum(local_return) / local_years if local_years else None
                ),
                "platform_window_annualized_return": finite(
                    np.nansum(platform_return) / platform_years
                    if platform_years
                    else None
                ),
                "platform_reported_annualized_return": finite(
                    metric.get("annualizedReturn")
                ),
                "local_annualized_excess": finite(
                    np.nansum(local_excess) / local_years if local_years else None
                ),
                "platform_window_annualized_excess": finite(
                    np.nansum(platform_excess) / platform_years
                    if platform_years
                    else None
                ),
                "platform_reported_annualized_excess": finite(
                    metric.get("excessAnnualized")
                ),
                "local_turnover": finite(local_turnover_values.mean())
                if not local_turnover_values.empty
                else None,
                "platform_reported_turnover": finite(metric.get("turnoverRate")),
                "platform_reported_sharpe": finite(metric.get("sharpeRatio")),
                "same_group_return_sequence": return_sequence,
                "same_group_excess_sequence": excess_sequence,
                "best_platform_group_by_return_corr": (
                    best_return_match[0] if best_return_match else None
                ),
                "best_platform_return_corr": (
                    best_return_match[1].get("corr") if best_return_match else None
                ),
                "best_platform_group_by_excess_corr": (
                    best_excess_match[0] if best_excess_match else None
                ),
                "best_platform_excess_corr": (
                    best_excess_match[1].get("corr") if best_excess_match else None
                ),
            }
        )

    result = {
        "variant": variant,
        "scope": scope,
        "label_offset": label_offset,
        "periods": int(len(local_periods)),
        "platform_periods": int(len(platform_periods)),
        "period_coverage": float(len(joined) / len(platform_periods))
        if len(platform_periods)
        else None,
        "local_stock_count_mean": finite(local_periods["stock_count"].mean()),
        "local_stock_count_min": int(local_periods["stock_count"].min()),
        "local_stock_count_max": int(local_periods["stock_count"].max()),
        "local_rank_ic": finite(local_periods["rank_ic"].mean()),
        "local_ic_mean": finite(local_periods["ic"].mean()),
        "platform_rank_ic_chart_mean": finite(platform_periods["platform_rank_ic"].mean()),
        "platform_rank_ic_metric": None,
        "rank_ic_delta": finite(
            local_periods["rank_ic"].mean() - platform_periods["platform_rank_ic"].mean()
        ),
        "local_gross_excess": local_gross,
        "local_turnover": local_turnover,
        "local_annual_cost": local_cost,
        "local_net_excess": local_net,
        "platform_gross_excess": finite(platform_metric["excessAnnualized"]),
        "platform_turnover": finite(platform_metric["turnoverRate"]),
        "platform_turnover_cost": platform_turnover_cost,
        "platform_net_excess": platform_net,
        "platform_turnover_sensitivity_net": sensitivity_net,
        "net_delta_pp": finite(
            (local_net - platform_net) * 100.0
            if local_net is not None and platform_net is not None
            else None
        ),
        "gross_delta_pp": finite(
            (local_gross - platform_metric["excessAnnualized"]) * 100.0
            if platform_metric["excessAnnualized"] is not None
            else None
        ),
        "sensitivity_delta_pp": finite(
            (sensitivity_net - platform_net) * 100.0
            if sensitivity_net is not None and platform_net is not None
            else None
        ),
        "turnover_gap_pp": finite(
            (local_turnover - platform_metric["turnoverRate"]) * 100.0
            if local_turnover is not None and platform_metric["turnoverRate"] is not None
            else None
        ),
        "rank_ic_sequence": correlation_summary(
            joined["rank_ic"], joined["platform_rank_ic"]
        )
        if not joined.empty
        else None,
        "group_return_sequence": correlation_summary(
            joined["group_return"], joined["platform_group_return"], scale=100.0
        )
        if not joined.empty
        else None,
        "excess_sequence": correlation_summary(
            joined["excess"], joined["platform_excess"], scale=100.0
        )
        if not joined.empty
        else None,
        "benchmark_sequence": correlation_summary(
            joined["benchmark"], joined["platform_benchmark"], scale=100.0
        )
        if not joined.empty
        else None,
        "cumulative_excess_sequence": correlation_summary(
            joined["local_cumulative_excess"],
            joined["platform_subset_cumulative_excess"],
            scale=100.0,
        )
        if not joined.empty
        else None,
        "largest_abs_excess_delta": None
        if largest is None
        else {
            "date": day_text(largest["date"]),
            "delta_pp": finite(largest["delta_excess"] * 100.0),
        },
        "last_cumulative_excess_delta_pp": finite(
            (joined["local_cumulative_excess"].iloc[-1]
             - joined["platform_subset_cumulative_excess"].iloc[-1])
            * 100.0
        )
        if not joined.empty
        else None,
        "group_comparisons": group_comparisons,
    }
    return result, local_periods


def top20_diagnostic(
    frame: pd.DataFrame,
    platform: dict[str, Any],
    factor_map: dict[str, pd.Series],
) -> tuple[dict[str, Any], pd.DataFrame]:
    rows = [row for row in platform.get("top", []) if row.get("symbol") and row.get("date")]
    if not rows:
        return {"available": False}, pd.DataFrame()
    dates = [pd.Timestamp(row["date"]).normalize() for row in rows]
    latest_date = max(dates)
    platform_rows = [row for row in rows if pd.Timestamp(row["date"]).normalize() == latest_date]
    current = frame[frame["date"].eq(latest_date)][["instrument"]].copy()
    platform_symbols = [str(row["symbol"]) for row in platform_rows]
    output_rows: list[dict[str, Any]] = []
    local_top_by_variant: dict[str, list[str]] = {}
    overlap_by_variant: dict[str, int] = {}
    for variant, values in factor_map.items():
        work = current.copy()
        work["factor"] = pd.to_numeric(
            values.reindex(work.index), errors="coerce"
        ).to_numpy()
        work = work.dropna().sort_values(["factor", "instrument"], ascending=[False, True])
        local_top = work.head(len(platform_symbols))["instrument"].astype(str).tolist()
        local_top_by_variant[variant] = local_top
        overlap_by_variant[variant] = len(set(local_top).intersection(platform_symbols))
        ranks = work.reset_index(drop=True)
        rank_map = {
            str(symbol): int(index + 1)
            for index, symbol in enumerate(ranks["instrument"].astype(str))
        }
        value_map = dict(zip(work["instrument"].astype(str), work["factor"]))
        for row in platform_rows:
            symbol = str(row["symbol"])
            output_rows.append(
                {
                    "variant": variant,
                    "date": day_text(latest_date),
                    "symbol": symbol,
                    "platform_display_factor1": finite(row.get("factor1")),
                    "local_factor": finite(value_map.get(symbol)),
                    "local_desc_rank": rank_map.get(symbol),
                    "local_in_top20": symbol in local_top,
                }
            )
    display_values = [row.get("factor1") for row in platform_rows]
    display_unique = sorted({str(value) for value in display_values})
    summary = {
        "available": True,
        "platform_top_count": len(platform_rows),
        "platform_top_date": day_text(latest_date),
        "platform_top_dates": sorted({day_text(value) for value in dates}),
        "platform_display_factor1_unique_count": len(display_unique),
        "platform_display_factor1_unique_values": display_unique,
        "chart_last_date": day_text(max(platform["dates"])) if platform.get("dates") else None,
        "top_date_equals_chart_last": bool(platform.get("dates") and latest_date == max(platform["dates"])),
        "local_top20_by_variant": local_top_by_variant,
        "overlap_by_variant": overlap_by_variant,
        "warning": (
            "platform Top20 factor1 is constant or uses a non-chart date; treat member overlap as display diagnostics only"
            if len(display_unique) <= 1 or (platform.get("dates") and latest_date != max(platform["dates"]))
            else None
        ),
    }
    return summary, pd.DataFrame(output_rows)


def calendar_audit(calendar: list[pd.Timestamp], platform_dates: list[pd.Timestamp]) -> dict[str, Any]:
    positions = {date: index for index, date in enumerate(calendar)}
    indexes = [positions[date] for date in platform_dates if date in positions]
    differences = [right - left for left, right in zip(indexes, indexes[1:]) if right > left]
    return {
        "calendar_start": day_text(calendar[0]),
        "calendar_end": day_text(calendar[-1]),
        "calendar_days": len(calendar),
        "platform_dates_present_in_calendar": len(indexes),
        "platform_signal_trading_day_gap_counts": dict(Counter(differences)),
        "platform_configured_cycle": CYCLE,
        "platform_chart_start": day_text(platform_dates[0]),
        "platform_chart_end": day_text(platform_dates[-1]),
    }


def year_table(periods: pd.DataFrame) -> pd.DataFrame:
    if periods.empty:
        return periods
    work = periods.copy()
    work["year"] = pd.to_datetime(work["date"]).dt.year
    grouped = work.groupby(["variant", "scope", "label_offset", "year"], as_index=False).agg(
        periods=("date", "size"),
        stock_count_mean=("stock_count", "mean"),
        rank_ic=("rank_ic", "mean"),
        group_return_sum=("group_return", "sum"),
        excess_sum=("excess", "sum"),
        turnover_mean=("turnover", "mean"),
    )
    return grouped


def format_number(value: Any, digits: int = 3) -> str:
    number = finite(value)
    return "n/a" if number is None else f"{number:.{digits}f}"


def format_pct(value: Any, digits: int = 2) -> str:
    number = finite(value)
    return "n/a" if number is None else f"{number * 100.0:.{digits}f}%"


def write_markdown(
    path: Path,
    payload: dict[str, Any],
    variant_frame: pd.DataFrame,
    group_frame: pd.DataFrame,
    top_summary: dict[str, Any],
    reconciliation: dict[str, Any],
) -> None:
    platform = payload["platform"]
    lines = [
        "# F-GFN-N01 深度诊断",
        "",
        "本报告只读取已保存的平台结果和本地缓存，不创建因子、不发起平台回测。",
        "",
        f"- 规则版本：`{ALIGNMENT_RULE_VERSION}`；规则文档：`{ALIGNMENT_RULES_DOCUMENT}`",
        f"- 正式口径：全 A、qfq、`{ALIGNMENT_MARKET_CAP_FIELD}`、平台信号日、`close(t+1)->close(t+6)`、10 组、`{ALIGNMENT_BENCHMARK_MODE}`、{ALIGNMENT_ONE_WAY_COST:.2%} 单边成本",
        f"- 平台结果：`{platform['path']}`；图表期数：`{platform['chart_periods']}`；图表日期：`{platform['chart_start']}..{platform['chart_end']}`",
        "- `qfq_*` 是正式口径敏感性；`raw_*_2024` 仅使用本地已有的 2024 raw 文件，不能替代正式结果。",
        "",
        "## 结论",
        "",
        "1. N01 的差异不是单纯换手成本差：qfq HIGH 基线的逐期 RankIC、毛超额和 Top20 排名都没有与平台对上。",
        "2. 切换 qfq 的 CLOSE/OPEN/LOW 仍不能把平台 RankIC 变成接近本地；raw 2024 也只能改变局部结果，不能证明字段语义等价。",
        "3. 平台 Top20 的展示字段存在独立异常：Top20 日期晚于图表最后日期，且 20 个 `factor1` 相同。它不能作为逐股票因子值或 Top20 重合的可靠证据。",
        "4. 10 组收益逐组核对后，即使某个组的相关性较高，也只能说明可能存在分组错位，不能修复 RankIC 与因子值语义差异。",
        "5. 在拿到平台逐股票因子值、逐期持仓或明确的 HIGH/AMOUNT/VOLUME 语义前，N01 应继续标为 `unsupported`，不能进入本地因子挖掘池。",
        "",
        "## 结果对比",
        "",
        "| variant | label | periods | RankIC local/platform | sequence corr | excess corr | gross excess local/platform | net local/platform | sensitivity net | turnover local/platform |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in variant_frame.iterrows():
        rank_seq = row.get("rank_ic_sequence") or {}
        excess_seq = row.get("excess_sequence") or {}
        lines.append(
            f"| {row['variant']} | {row['label_offset']} | {int(row['periods'])}/{int(row['platform_periods'])} | "
            f"{format_number(row['local_rank_ic'], 4)}/{format_number(row['platform_rank_ic_chart_mean'], 4)} | "
            f"{format_number(rank_seq.get('corr'), 3)} | {format_number(excess_seq.get('corr'), 3)} | "
            f"{format_pct(row['local_gross_excess'])}/{format_pct(row['platform_gross_excess'])} | "
            f"{format_pct(row['local_net_excess'])}/{format_pct(row['platform_net_excess'])} | "
            f"{format_pct(row['platform_turnover_sensitivity_net'])} | "
            f"{format_pct(row['local_turnover'])}/{format_pct(row['platform_turnover'])} |"
        )
    lines.extend(
        [
            "",
            "`sequence corr` 是逐期序列相关；`excess corr` 是第10组逐期超额收益相关。平台和本地的换手定义可能不是同一语义，因此平台换手代入的 `sensitivity net` 只用于诊断。",
            "",
            "## 10 组逐组诊断（qfq HIGH，label=1）",
            "",
            "下表中的 `platform window` 是从平台累计曲线还原后、按当前窗口的算术年化；`platform reported` 是平台保存的分组汇总值。`best group` 用于检查是否存在分组编号错位，不是替换正式分组口径。",
            "",
            "| group | local ann return | platform window | platform reported | local ann excess | platform window excess | platform reported excess | same return corr | same excess corr | best platform group/return corr | best platform group/excess corr |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    formal_groups = group_frame[
        group_frame["variant"].eq("qfq_high") & group_frame["label_offset"].eq(1)
    ].sort_values("group")
    for _, row in formal_groups.iterrows():
        lines.append(
            f"| {int(row['group'])} | {format_pct(row['local_annualized_return'])} | "
            f"{format_pct(row['platform_window_annualized_return'])} | "
            f"{format_pct(row['platform_reported_annualized_return'])} | "
            f"{format_pct(row['local_annualized_excess'])} | "
            f"{format_pct(row['platform_window_annualized_excess'])} | "
            f"{format_pct(row['platform_reported_annualized_excess'])} | "
            f"{format_number((row.get('same_group_return_sequence') or {}).get('corr'), 3)} | "
            f"{format_number((row.get('same_group_excess_sequence') or {}).get('corr'), 3)} | "
            f"{row.get('best_platform_group_by_return_corr', 'n/a')}/"
            f"{format_number(row.get('best_platform_return_corr'), 3)} | "
            f"{row.get('best_platform_group_by_excess_corr', 'n/a')}/"
            f"{format_number(row.get('best_platform_excess_corr'), 3)} |"
        )
    lines.extend(
        [
            "",
            "## 平台结果完整性",
            "",
            f"- RankIC 图表：{platform['rank_chart_periods']} 期，均值 `{format_number(platform['rank_ic_mean'], 4)}`；最后日期 `{platform['chart_end']}`。",
            f"- 平台配置结束日为 `{platform['configured_end']}`，Top20 日期为 `{top_summary.get('platform_top_date', 'n/a')}`。Top20 日期与图表最后日期相同：`{top_summary.get('top_date_equals_chart_last')}`。",
            f"- Top20 返回 `{top_summary.get('platform_top_count', 0)}` 条，展示 `factor1` 去重后 `{top_summary.get('platform_display_factor1_unique_count', 0)}` 个值：`{', '.join(top_summary.get('platform_display_factor1_unique_values', []))}`。",
            f"- 诊断标记：`{top_summary.get('warning') or 'none'}`。",
            "",
            "## 数据审计",
            "",
            f"- qfq 源文件 `{payload['data_audit']['qfq']['file_count']}` 个，文件行数合计 `{payload['data_audit']['qfq']['all_file_rows']:,}`；信号日源记录去重前后为 `{payload['data_audit']['qfq']['signal_source_rows_before_dedup']:,}/{payload['data_audit']['qfq']['signal_source_rows_after_dedup']:,}`，重复键额外行 `{payload['data_audit']['qfq']['duplicate_key_extra_rows']:,}`。",
            f"- daily_basic 信号日文件 `{payload['data_audit']['daily_basic']['signal_date_files']}` 个，覆盖 `{payload['data_audit']['daily_basic']['signal_dates_present']}/{payload['data_audit']['daily_basic']['signal_dates_requested']}` 个信号日。",
            f"- 正式加载后的本地 frame 为 `{payload['data_audit']['loaded_frame']['rows']:,}` 行、`{payload['data_audit']['loaded_frame']['instruments']}` 只股票；信号日覆盖 `{payload['data_audit']['loaded_frame']['signal_dates_present']}/{payload['data_audit']['loaded_frame']['signal_dates_requested']}`。",
            f"- 2024 raw 与 qfq 信号日交集 `{reconciliation['joined_rows_2024']:,}` 行，raw 覆盖率 `{format_pct(reconciliation['coverage_vs_raw'])}`；volume 精确比例 `{format_number(reconciliation['field_comparisons']['volume_qfq_vs_volume_raw'].get('exact_fraction'), 4)}`，amount 精确比例 `{format_number(reconciliation['field_comparisons']['amount_qfq_vs_amount_raw'].get('exact_fraction'), 4)}`。",
            f"- qfq/raw 中位数比例：volume `{format_number(reconciliation['field_ratios_qfq_over_raw']['volume'].get('median'), 4)}`，amount `{format_number(reconciliation['field_ratios_qfq_over_raw']['amount'].get('median'), 4)}`；amount 的 P95 相对误差为 `{format_number(reconciliation['field_comparisons']['amount_qfq_vs_amount_raw'].get('p95_absolute_relative_error'), 8)}`，未见约 0.1 的单位缩放。",
            f"- 2024 的 qfq HIGH/raw HIGH 调整比例与 qfq CLOSE/raw CLOSE 的差值 P95 为 `{format_number(reconciliation['adjustment_ratio_consistency'].get('ratio_delta_p95_abs'), 6)}`，这只是复权一致性检查，不等于平台 HIGH 语义已确认。",
            "",
            "## 文件",
            "",
            "- `variant_summary.csv`：各字段/标签变体汇总。",
            "- `group_summary.csv`：所有变体、所有分组的逐组年化和序列相关诊断。",
            "- `periods_all.csv`：逐期 RankIC、基准、第10组收益、超额和换手。",
            "- `periods_<variant>_label<offset>.csv`：单变体逐期结果。",
            "- `year_summary.csv`：按年份拆解。",
            "- `top20_diagnostic.csv`：平台 Top20 展示值与各本地变体值对照。",
            "- `data_audit.json`：源文件、覆盖率、重复键和 2024 raw/qfq 字段对照。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    platform_path = Path(args.platform_result)
    if not platform_path.is_file():
        raise SystemExit(f"Missing saved platform result: {platform_path}")
    platform = read_platform_run(platform_path)
    platform_periods = platform_period_frame(platform)
    # Keep every platform group metric available for the group-level audit;
    # evaluate_variant still selects PLATFORM_GROUP from this mapping.
    platform_periods.attrs["platform_group_metrics"] = platform["group_metrics"]
    chart_dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
    top_dates = [
        pd.Timestamp(row["date"]).normalize()
        for row in platform.get("top", [])
        if row.get("date")
    ]
    wanted_dates = set(chart_dates + top_dates)
    print(f"platform_chart_periods={len(chart_dates)} chart={day_text(chart_dates[0])}..{day_text(chart_dates[-1])}", flush=True)
    print("loading=qfq_full_a", flush=True)
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        parse_date(args.data_start),
        parse_date(args.end),
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(
        f"local_rows={len(frame)} instruments={frame['instrument'].nunique()} dates={frame['date'].nunique()}",
        flush=True,
    )
    calendar = [
        pd.Timestamp(value).normalize()
        for value in load_trade_dates(parse_date(args.data_start), parse_date(args.end))
    ]
    close = make_close_panel(frame, calendar)
    qfq_source, qfq_audit = signal_source_rows(Path(args.price_root), wanted_dates)
    raw = load_raw_2024(Path(args.raw_root))
    cap_audit = daily_basic_source_audit(Path(args.cap_root), wanted_dates)
    reconciliation = source_reconciliation(qfq_source, raw, frame)
    print("building=forward_returns", flush=True)

    variant_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    period_frames: list[pd.DataFrame] = []
    factor_map: dict[str, pd.Series] = {}
    variant_specs = [
        ("qfq_high", "qfq", "high_qfq"),
        ("qfq_close", "qfq", "close_qfq"),
        ("qfq_open", "qfq", "open_qfq"),
        ("qfq_low", "qfq", "low_qfq"),
    ]
    raw_specs = [
        ("raw_high_2024", "raw_2024", "high"),
        ("raw_close_2024", "raw_2024", "close"),
        ("raw_open_2024", "raw_2024", "open"),
        ("raw_low_2024", "raw_2024", "low"),
    ]
    for variant, scope, denominator in variant_specs:
        factor_map[variant] = factor_from_denominator(frame, denominator)
    for variant, scope, denominator in raw_specs:
        factor_map[variant] = raw_factor_values(frame, raw, denominator)

    for variant, scope, _ in variant_specs + raw_specs:
        if scope == "qfq":
            dates = chart_dates
        else:
            dates = [date for date in chart_dates if date.year == 2024]
        for label_offset in [1, 0]:
            print(f"evaluating={variant} label_offset={label_offset} periods={len(dates)}", flush=True)
            returns = build_returns(close, calendar, dates, CYCLE, label_offset)
            platform_subset = platform_periods[platform_periods["date"].isin(dates)].copy()
            result, periods = evaluate_variant(
                frame,
                factor_map[variant],
                returns,
                platform_subset,
                dates,
                label_offset,
                variant,
                scope,
            )
            variant_rows.append(result)
            group_rows.extend(result["group_comparisons"])
            period_frames.append(periods)
            periods.to_csv(
                output / f"periods_{variant}_label{label_offset}.csv",
                index=False,
                encoding="utf-8-sig",
            )

    variant_frame = pd.DataFrame(variant_rows)
    variant_frame.to_csv(output / "variant_summary.csv", index=False, encoding="utf-8-sig")
    group_frame = pd.DataFrame(group_rows)
    group_frame.to_csv(output / "group_summary.csv", index=False, encoding="utf-8-sig")
    all_periods = pd.concat(period_frames, ignore_index=True)
    all_periods.to_csv(output / "periods_all.csv", index=False, encoding="utf-8-sig")
    years = year_table(all_periods)
    years.to_csv(output / "year_summary.csv", index=False, encoding="utf-8-sig")

    top_summary, top_frame = top20_diagnostic(
        frame,
        platform,
        {variant: factor_map[variant] for variant, _, _ in variant_specs},
    )
    top_frame.to_csv(output / "top20_diagnostic.csv", index=False, encoding="utf-8-sig")

    platform_raw = json.loads(platform_path.read_text(encoding="utf-8-sig"))
    analysis = platform_raw.get("results", {}).get("factor_analysis", {})
    platform_chart_periods = len(platform_periods)
    group_metrics = platform["group_metrics"].get(PLATFORM_GROUP, {})
    platform_payload = {
        "path": str(platform_path),
        "configured_start": day_text(pd.Timestamp("2021-09-07")),
        "configured_end": day_text(END),
        "chart_periods": platform_chart_periods,
        "rank_chart_periods": len(platform.get("rank_ic_values", [])),
        "chart_start": day_text(platform["dates"][0]),
        "chart_end": day_text(platform["dates"][-1]),
        "rank_ic_mean": finite(np.mean(platform["rank_ic_values"])),
        "metrics": platform["metrics"],
        "group10": group_metrics,
        "top_count": len(platform.get("top", [])),
        "top_dates": sorted({day_text(value) for value in top_dates}),
        "chart_series_lengths": {
            "rank_ic": len(platform.get("rank_ic_values", [])),
            "group_return_series": [len(values) for values in platform.get("return_cumulative", [])],
            "group_excess_series": [len(values) for values in platform.get("excess_cumulative", [])],
        },
        "raw_analysis_keys": sorted(analysis.keys()),
    }
    data_audit = {
        "qfq": qfq_audit,
        "daily_basic": cap_audit,
        "loaded_frame": {
            "rows": int(len(frame)),
            "instruments": int(frame["instrument"].nunique()),
            "dates": int(frame["date"].nunique()),
            "signal_dates_requested": len(wanted_dates),
            "signal_dates_present": int(frame[frame["date"].isin(wanted_dates)]["date"].nunique()),
            "market_field_sources": frame.attrs.get("market_field_sources", {}),
        },
        "source_reconciliation_2024": reconciliation,
        "calendar": calendar_audit(calendar, chart_dates),
    }
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "data_start": day_text(parse_date(args.data_start)),
            "end": day_text(parse_date(args.end)),
            "cycle": CYCLE,
            "groups": GROUPS,
            "label_offsets": [1, 0],
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "formal_scope": "full-A Tushare qfq joined with daily_basic .SH/.SZ",
            "raw_scope": "2024 raw daily cache only; sensitivity, not formal result",
        },
        "platform": platform_payload,
        "data_audit": data_audit,
        "top20": top_summary,
        "source_reconciliation_2024": reconciliation,
        "variants": variant_rows,
        "group_comparisons": group_rows,
    }
    (output / "diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    (output / "data_audit.json").write_text(
        json.dumps(data_audit, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    write_markdown(
        output / "diagnosis.md",
        payload,
        variant_frame,
        group_frame,
        top_summary,
        reconciliation,
    )
    print(f"report={output / 'diagnosis.md'}", flush=True)
    for row in variant_rows:
        rank_seq = row.get("rank_ic_sequence") or {}
        print(
            f"{row['variant']} label={row['label_offset']} rank_ic={row['local_rank_ic']:.4f} "
            f"platform={row['platform_rank_ic_chart_mean']:.4f} corr={rank_seq.get('corr')!s} "
            f"gross={row['local_gross_excess']:.4f} net={row['local_net_excess']!s}",
            flush=True,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-result", default=str(PLATFORM_RESULT))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--data-start", default=day_text(DATA_START))
    parser.add_argument("--end", default=day_text(END))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
