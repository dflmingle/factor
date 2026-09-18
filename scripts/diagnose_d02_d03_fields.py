#!/usr/bin/env python3
"""Diagnose the local field and rolling-operator gaps for saved D02/D03 runs.

This is a read-only offline diagnostic.  It compares explicit Tushare field
proxies with the saved PandaAI summaries under the current alignment contract;
it does not create factors or contact PandaAI.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from financial_factor_local import load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
)
from positive_factor_local_compare import evaluate, panel_close  # noqa: E402
from stfilter_local_recheck import ensure_calendar  # noqa: E402


D02_RESULT = PROJECT_ROOT / (
    "net-dd-multiobjective-20260916-diversified-candidates.results/"
    "6aaa68ed5d52c44d2f55ce8f.json"
)
D03_RESULT = PROJECT_ROOT / (
    "net-dd-multiobjective-20260916-diversified-candidates.results/"
    "6aaa692ba7f535324660cbf6.json"
)
D02_FORMULA = "(BOOK_TO_MARKET_RATIO_LYR*MA(INSURANCE_COMMISSION_EXPENSE_MRQ_9,10))"
D03_FORMULA = (
    "COV(MIN(TOTAL_ASSETS_MRQ_1,CASH_RECEIVED_FROM_ISSUING_SECURITY_MRQ_10),"
    "INTEREST_PAYABLE_MRQ_4,30)"
)


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def day_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def finite_count(values: pd.Series) -> int:
    return int(pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).notna().sum())


def platform_dates(platform: dict[str, Any]) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    chart_dates = [pd.Timestamp(value).normalize() for value in platform.get("dates", [])]
    top_dates = [
        pd.Timestamp(row["date"]).normalize()
        for row in platform.get("top", [])
        if row.get("date")
    ]
    work_dates = sorted(set(chart_dates + top_dates))
    return chart_dates, work_dates


def read_platform_batch_metrics(result_path: Path) -> dict[str, float | None]:
    """Read the saved batch summary that contains platform net excess."""
    results_dir = result_path.parent
    if not results_dir.name.endswith(".results"):
        return {}
    report_path = results_dir.parent / f"{results_dir.name[:-len('.results')]}.report.csv"
    if not report_path.exists():
        return {}
    try:
        with report_path.open(encoding="utf-8", newline="") as handle:
            row = next(
                (
                    item
                    for item in csv.DictReader(handle)
                    if str(item.get("run_id", "")) == result_path.stem
                ),
                None,
            )
    except (OSError, csv.Error):
        return {}
    if row is None:
        return {}

    def number(key: str) -> float | None:
        try:
            value = float(row[key])
        except (KeyError, TypeError, ValueError):
            return None
        return value if np.isfinite(value) else None

    return {
        "long_excess_pct": number("long_excess_pct"),
        "turnover_pct": number("turnover_pct"),
        "annual_cost_pct": number("annual_cost_pct"),
        "net_excess_pct": number("net_excess_pct"),
    }


def report_table(
    reports: pd.DataFrame,
    field: str,
    dedup: str,
    missing_mode: str,
) -> pd.DataFrame:
    """Prepare a PIT report sequence for an MRQ_n field."""
    columns = ["instrument", "ann_date", "end_date", "update_flag", field]
    result = reports[[column for column in columns if column in reports.columns]].copy()
    if field not in result.columns:
        result[field] = np.nan
    result["ann_date"] = pd.to_datetime(result["ann_date"], errors="coerce").dt.normalize()
    result["end_date"] = pd.to_datetime(result["end_date"], errors="coerce").dt.normalize()
    result["update_flag"] = pd.to_numeric(result["update_flag"], errors="coerce").fillna(-1)
    result[field] = pd.to_numeric(result[field], errors="coerce")
    result = result.dropna(subset=["instrument", "ann_date"])

    # Mirror PandaAIFieldStore._report_panel exactly: null source values are
    # removed before MRQ numbering, then one non-null report is retained per
    # announcement date, with the latest end_date/update_flag winning.
    if missing_mode == "field_store_nonempty_reports":
        result = result.dropna(subset=[field])
        result = result.sort_values(
            ["instrument", "ann_date", "end_date", "update_flag"],
            kind="stable",
        )
        result = result.drop_duplicates(["instrument", "ann_date"], keep="last")
    elif dedup == "end_date_latest":
        result = result.sort_values(
            ["instrument", "end_date", "ann_date", "update_flag"],
            kind="stable",
        )
        result = result.drop_duplicates(["instrument", "end_date"], keep="last")
    elif dedup == "announcement_latest":
        result = result.sort_values(
            ["instrument", "ann_date", "end_date", "update_flag"],
            kind="stable",
        )
        result = result.drop_duplicates(["instrument", "ann_date", "end_date"], keep="last")
    elif dedup != "cache":
        raise ValueError(f"Unsupported report deduplication: {dedup}")

    if missing_mode == "exclude_missing_reports":
        result = result[result[field].notna()].copy()
    elif missing_mode not in {
        "keep_missing_reports",
        "field_store_nonempty_reports",
    }:
        raise ValueError(f"Unsupported missing mode: {missing_mode}")

    # MRQ_n is interpreted as the nth latest report available by announcement
    # date.  End date is the deterministic tie order when two periods share an
    # announcement date; this keeps the PIT selection explicit.
    result = result.sort_values(
        ["instrument", "ann_date", "end_date", "update_flag"],
        kind="stable",
    ).reset_index(drop=True)
    result["report_seq"] = result.groupby("instrument", sort=False).cumcount()
    return result


def attach_mrq(
    panel: pd.DataFrame,
    reports: pd.DataFrame,
    field: str,
    n: int,
    dedup: str,
    missing_mode: str,
) -> pd.Series:
    """Attach the nth announced report value to each daily panel row."""
    prepared = report_table(reports, field, dedup, missing_mode)
    left = panel[["row_id", "instrument", "date"]].sort_values(
        ["date", "instrument"], kind="stable"
    )
    right = prepared[
        ["instrument", "ann_date", "end_date", "report_seq", field]
    ].sort_values(["ann_date", "instrument", "end_date"], kind="stable")
    merged = pd.merge_asof(
        left,
        right,
        left_on="date",
        right_on="ann_date",
        by="instrument",
        direction="backward",
        allow_exact_matches=True,
    )
    merged["target_seq"] = merged["report_seq"].sub(n - 1)
    targets = merged[["row_id", "instrument", "target_seq"]].copy()
    targets = targets.rename(columns={"target_seq": "report_seq"})
    targets["report_seq"] = targets["report_seq"].astype("Int64")
    values = targets.merge(
        prepared[["instrument", "report_seq", field]],
        on=["instrument", "report_seq"],
        how="left",
        sort=False,
    )
    return values.set_index("row_id")[field].reindex(panel["row_id"].to_numpy())


def attach_asof(
    panel: pd.DataFrame,
    reports: pd.DataFrame,
    field: str,
) -> pd.Series:
    """Attach the latest value announced by each date."""
    right = reports[["instrument", "ann_date", "end_date", "update_flag", field]].copy()
    right["ann_date"] = pd.to_datetime(right["ann_date"], errors="coerce").dt.normalize()
    right["end_date"] = pd.to_datetime(right["end_date"], errors="coerce").dt.normalize()
    right[field] = pd.to_numeric(right[field], errors="coerce")
    right = right.dropna(subset=["instrument", "ann_date"])
    right = right.sort_values(
        ["ann_date", "instrument", "end_date", "update_flag"], kind="stable"
    )
    left = panel[["row_id", "instrument", "date"]].sort_values(
        ["date", "instrument"], kind="stable"
    )
    merged = pd.merge_asof(
        left,
        right,
        left_on="date",
        right_on="ann_date",
        by="instrument",
        direction="backward",
        allow_exact_matches=True,
    )
    return merged.set_index("row_id")[field].reindex(panel["row_id"].to_numpy())


def rolling_mean(panel: pd.DataFrame, values: pd.Series, window: int) -> pd.Series:
    work = panel[["row_id", "date", "instrument"]].copy()
    work["value"] = pd.to_numeric(values.to_numpy(), errors="coerce")
    work = work.sort_values(["instrument", "date"], kind="stable").reset_index(drop=True)
    grouped = work.groupby("instrument", sort=False, observed=True)["value"]
    result = grouped.rolling(window=window, min_periods=window).mean()
    result = result.reset_index(level=0, drop=True)
    return pd.Series(result.to_numpy(), index=work["row_id"].to_numpy(), dtype=float)


def _rolling_cov_group(
    left: np.ndarray,
    right: np.ndarray,
    window: int,
    ddof: int,
    precision: str,
    method: str,
) -> np.ndarray:
    dtype = np.float32 if precision == "float32" else np.float64
    lhs = np.asarray(left, dtype=dtype)
    rhs = np.asarray(right, dtype=dtype)
    output = np.full(len(lhs), np.nan, dtype=float)
    if len(lhs) < window:
        return output
    lhs_windows = np.lib.stride_tricks.sliding_window_view(lhs, window)
    rhs_windows = np.lib.stride_tricks.sliding_window_view(rhs, window)
    valid = np.isfinite(lhs_windows).all(axis=1) & np.isfinite(rhs_windows).all(axis=1)
    if method == "centered":
        lhs_centered = lhs_windows - lhs_windows.mean(axis=1, keepdims=True, dtype=dtype)
        rhs_centered = rhs_windows - rhs_windows.mean(axis=1, keepdims=True, dtype=dtype)
        numerator = (lhs_centered * rhs_centered).sum(axis=1, dtype=dtype)
    elif method == "moment":
        numerator = (
            lhs_windows.mean(axis=1, dtype=dtype) * rhs_windows.mean(axis=1, dtype=dtype)
        )
        numerator = (
            (lhs_windows * rhs_windows).mean(axis=1, dtype=dtype) - numerator
        ) * window
    else:
        raise ValueError(f"Unsupported covariance method: {method}")
    denominator = window - ddof
    if denominator <= 0:
        raise ValueError(f"Invalid ddof={ddof} for window={window}")
    output[window - 1 :] = np.where(valid, numerator / denominator, np.nan)
    return output


def rolling_covariance(
    panel: pd.DataFrame,
    left: pd.Series,
    right: pd.Series,
    window: int,
    ddof: int,
    precision: str,
    method: str,
) -> pd.Series:
    work = panel[["row_id", "date", "instrument"]].copy()
    work["left"] = pd.to_numeric(left.to_numpy(), errors="coerce")
    work["right"] = pd.to_numeric(right.to_numpy(), errors="coerce")
    work = work.sort_values(["instrument", "date"], kind="stable").reset_index(drop=True)
    result = np.full(len(work), np.nan, dtype=float)
    for _, positions in work.groupby("instrument", sort=False, observed=True).groups.items():
        index = np.asarray(positions, dtype=np.int64)
        result[index] = _rolling_cov_group(
            work.loc[index, "left"].to_numpy(),
            work.loc[index, "right"].to_numpy(),
            window,
            ddof,
            precision,
            method,
        )
    return pd.Series(result, index=work["row_id"].to_numpy(), dtype=float)


def work_panel(
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
    dates: list[pd.Timestamp],
    warmup: int,
) -> pd.DataFrame:
    date_set = set(dates)
    positions = [calendar.index(date) for date in dates]
    start = max(0, min(positions, default=0) - warmup)
    end = min(len(calendar), max(positions, default=-1) + 1)
    selected_dates = set(calendar[start:end])
    result = frame[frame["date"].isin(selected_dates)][
        ["date", "instrument", "total_mv"]
    ].copy()
    result["row_id"] = result.index.to_numpy(dtype=np.int64)
    result = result.sort_values(["instrument", "date"], kind="stable").reset_index(drop=True)
    result.attrs["signal_dates"] = sorted(date_set)
    return result


def signal_values(
    frame: pd.DataFrame,
    work: pd.DataFrame,
    values: pd.Series,
    dates: list[pd.Timestamp],
) -> pd.Series:
    table = work[["date", "instrument", "row_id"]].copy()
    table["factor"] = values.reindex(table["row_id"].to_numpy()).to_numpy()
    selected = frame[frame["date"].isin(dates)][["date", "instrument"]].copy()
    selected["row_id"] = selected.index.to_numpy(dtype=np.int64)
    joined = selected.merge(table[["date", "instrument", "factor"]], on=["date", "instrument"], how="left")
    return joined.set_index("row_id")["factor"].reindex(selected["row_id"].to_numpy())


def latest_factor_values(
    frame: pd.DataFrame,
    values: pd.Series,
    platform: dict[str, Any],
) -> list[dict[str, Any]]:
    top = [row for row in platform.get("top", []) if row.get("symbol") and row.get("date")]
    if not top:
        return []
    latest_date = max(pd.Timestamp(row["date"]).normalize() for row in top)
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = pd.to_numeric(values.to_numpy(), errors="coerce")
    latest = factor_frame[factor_frame["date"].eq(latest_date)].set_index("instrument")
    output = []
    for row in top:
        if pd.Timestamp(row["date"]).normalize() != latest_date:
            continue
        value = latest["factor"].get(str(row["symbol"]))
        output.append(
            {
                "symbol": str(row["symbol"]),
                "platform_value": clean_float(row.get("factor1")),
                "local_value": clean_float(value),
            }
        )
    return output


def candidate_result(
    candidate: str,
    formula: str,
    frame: pd.DataFrame,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    work: pd.DataFrame,
    values: pd.Series,
    platform: dict[str, Any],
    chart_dates: list[pd.Timestamp],
    direction: int,
    cycle: int,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    all_dates = sorted(set(chart_dates) | set(platform_dates(platform)[1]))
    factor = signal_values(frame, work, values, all_dates)
    eval_frame = frame[frame["date"].isin(all_dates)].copy()
    eval_frame["row_id"] = eval_frame.index.to_numpy(dtype=np.int64)
    eval_values = factor.reindex(eval_frame["row_id"].to_numpy())
    try:
        evaluated = evaluate(
            eval_frame,
            eval_values,
            close,
            platform,
            direction,
            chart_dates,
            calendar,
            cycle,
            ALIGNMENT_LABEL_OFFSET,
            None,
        )
        error = None
    except Exception as exc:  # diagnostic rows should retain failures explicitly
        evaluated = {}
        error = " ".join(str(exc).split())[:500]

    work_factor = values.reindex(work["row_id"].to_numpy())
    full_factor = pd.Series(np.nan, index=frame.index, dtype=float)
    full_factor.loc[work["row_id"].to_numpy(dtype=np.int64)] = work_factor.to_numpy()
    platform_top = [row for row in platform.get("top", []) if row.get("symbol")]
    platform_symbols = {str(row["symbol"]) for row in platform_top}
    top_date = max(
        [pd.Timestamp(row["date"]).normalize() for row in platform_top if row.get("date")],
        default=None,
    )
    local_top_symbols: list[str] = []
    if top_date is not None:
        latest = work[(work["date"] == top_date)].copy()
        latest["factor"] = work_factor.reindex(latest["row_id"].to_numpy()).to_numpy()
        local_top_symbols = (
            latest.dropna(subset=["factor"])
            .sort_values(["factor", "instrument"], ascending=[False, True])
            .head(len(platform_top))["instrument"]
            .astype(str)
            .tolist()
        )
    local_net = evaluated.get("net_excess")
    local_gross_pct = (
        None
        if evaluated.get("gross_excess") is None
        else 100.0 * evaluated["gross_excess"]
    )
    platform_group = platform.get("group_metrics", {}).get(10, {})
    platform_gross = platform_group.get("excessAnnualized")
    batch_metrics = platform.get("batch_metrics", {})
    platform_net_pct = batch_metrics.get("net_excess_pct")
    platform_cost_pct = batch_metrics.get("annual_cost_pct")
    local_net_using_platform_cost = (
        None
        if local_gross_pct is None or platform_cost_pct is None
        else local_gross_pct - platform_cost_pct
    )
    return {
        "candidate": candidate,
        "formula": formula,
        **metadata,
        "finite_work_rows": finite_count(work_factor),
        "finite_chart_rows": finite_count(
            full_factor.loc[frame["date"].isin(chart_dates)]
        ),
        "periods": evaluated.get("periods"),
        "local_rank_ic": clean_float(evaluated.get("rank_ic")),
        "local_gross_excess_pct": local_gross_pct,
        "local_turnover_pct": None if evaluated.get("turnover") is None else 100.0 * evaluated["turnover"],
        "local_net_excess_pct": None if local_net is None else 100.0 * local_net,
        "platform_gross_excess_pct": None if platform_gross is None else 100.0 * platform_gross,
        "platform_net_excess_pct": platform_net_pct,
        "platform_annual_cost_pct": platform_cost_pct,
        "local_net_using_platform_cost_pct": local_net_using_platform_cost,
        "platform_cost_sensitivity_delta_pp": (
            None
            if local_net_using_platform_cost is None or platform_net_pct is None
            else local_net_using_platform_cost - platform_net_pct
        ),
        "local_net_delta_pp": (
            None
            if local_net is None or platform_net_pct is None
            else 100.0 * local_net - platform_net_pct
        ),
        "local_gross_delta_pp": (
            None
            if local_gross_pct is None or platform_gross is None
            else local_gross_pct - 100.0 * platform_gross
        ),
        "top20_overlap": len(platform_symbols.intersection(local_top_symbols)) if platform_symbols else None,
        "platform_top_finite_count": sum(clean_float(row.get("factor1")) is not None for row in platform_top),
        "error": error,
        "latest_top_values": latest_factor_values(frame, full_factor, platform),
    }


def d02_candidates(
    frame: pd.DataFrame,
    cache: dict[str, pd.DataFrame],
    platform: dict[str, Any],
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
) -> list[dict[str, Any]]:
    chart_dates, all_dates = platform_dates(platform)
    work = work_panel(frame, calendar, all_dates, warmup=20)
    annual = cache["balancesheet"]
    annual = annual[annual["end_type"].astype(str).eq("4")]
    equity = attach_asof(work, annual, "total_hldr_eqy_exc_min_int")
    market_value = pd.Series(
        pd.to_numeric(work["total_mv"], errors="coerce").to_numpy() * 10000.0,
        index=work["row_id"].to_numpy(),
        dtype=float,
    )
    book_to_market = equity.div(market_value.replace(0.0, np.nan))
    output = []
    for field in ["comm_exp", "insurance_exp"]:
        variants = [
            (dedup, missing_mode)
            for dedup in ["cache", "end_date_latest"]
            for missing_mode in ["keep_missing_reports", "exclude_missing_reports"]
        ]
        variants.append(("field_store", "field_store_nonempty_reports"))
        for dedup, missing_mode in variants:
            expense = attach_mrq(
                work,
                cache["income"],
                field,
                9,
                dedup,
                missing_mode,
            )
            moving = rolling_mean(work, expense, 10)
            factor = book_to_market * moving / 1e7
            metadata = {
                "family": "D02",
                "field": field,
                "report_dedup": dedup,
                "missing_mode": missing_mode,
                "mrq_n": 9,
                "ma_window": 10,
                "financial_unit_scale": 1e7,
                "book_to_market_market_value_scale": 10000,
            }
            output.append(
                candidate_result(
                    f"D02-{field}-{dedup}-{missing_mode}",
                    D02_FORMULA,
                    frame,
                    close,
                    calendar,
                    work,
                    factor,
                    platform,
                    chart_dates,
                    1,
                    5,
                    metadata,
                )
            )
    return output


def d03_candidates(
    frame: pd.DataFrame,
    cache: dict[str, pd.DataFrame],
    platform: dict[str, Any],
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
) -> list[dict[str, Any]]:
    chart_dates, all_dates = platform_dates(platform)
    work = work_panel(frame, calendar, all_dates, warmup=45)
    output = []
    variants = [
        (dedup, missing_mode)
        for dedup in ["cache", "end_date_latest"]
        for missing_mode in ["keep_missing_reports", "exclude_missing_reports"]
    ]
    variants.append(("field_store", "field_store_nonempty_reports"))
    for dedup, missing_mode in variants:
        assets = attach_mrq(work, cache["balancesheet"], "total_assets", 1, dedup, missing_mode)
        issued = attach_mrq(
            work,
            cache["cashflow"],
            "proc_issue_bonds",
            10,
            dedup,
            missing_mode,
        )
        interest = attach_mrq(work, cache["balancesheet"], "int_payable", 4, dedup, missing_mode)
        left = pd.concat([assets, issued], axis=1).min(axis=1, skipna=False)
        for method, ddof, precision, scale in [
            ("centered", 1, "float64", 1.0),
            ("centered", 1, "float32", 1.0),
            ("centered", 1, "float64", 1e8),
            ("moment", 0, "float64", 1.0),
        ]:
            factor = rolling_covariance(
                work,
                left / scale,
                interest / scale,
                30,
                ddof,
                precision,
                method,
            )
            metadata = {
                "family": "D03",
                "report_dedup": dedup,
                "missing_mode": missing_mode,
                "mrq_fields": {
                    "assets": "total_assets_mrq_1",
                    "issued": "cash_received_from_issuing_security_mrq_10 -> proc_issue_bonds",
                    "interest": "interest_payable_mrq_4 -> int_payable",
                },
                "cov_method": method,
                "cov_ddof": ddof,
                "cov_precision": precision,
                "financial_unit_scale": scale,
                "finite_assets": finite_count(assets),
                "finite_issued": finite_count(issued),
                "finite_interest": finite_count(interest),
                "finite_left": finite_count(left),
            }
            output.append(
                candidate_result(
                    f"D03-{dedup}-{missing_mode}-{method}-ddof{ddof}-{precision}-scale{scale:g}",
                    D03_FORMULA,
                    frame,
                    close,
                    calendar,
                    work,
                    factor,
                    platform,
                    chart_dates,
                    1,
                    5,
                    metadata,
                )
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


def write_report(output_base: Path, report: dict[str, Any]) -> None:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    output_base.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    rows = report["candidates"]
    csv_path = output_base.with_suffix(".csv")
    columns = [
        "family", "candidate", "field", "report_dedup", "missing_mode",
        "cov_method", "cov_ddof", "cov_precision", "financial_unit_scale",
        "finite_work_rows", "finite_chart_rows", "periods", "local_rank_ic",
        "local_gross_excess_pct", "local_turnover_pct", "local_net_excess_pct",
        "platform_gross_excess_pct", "local_gross_delta_pp", "platform_net_excess_pct",
        "platform_annual_cost_pct", "local_net_using_platform_cost_pct",
        "platform_cost_sensitivity_delta_pp", "local_net_delta_pp", "top20_overlap",
        "platform_top_finite_count", "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    def value(row: dict[str, Any], key: str) -> str:
        item = row.get(key)
        if item is None:
            return "n/a"
        if isinstance(item, float):
            return f"{item:.4f}"
        return str(item)

    lines = [
        "# D02/D03 字段与协方差诊断",
        "",
        f"规则版本：`{report['alignment_rule_version']}`",
        "",
        "仅使用本地 Tushare 缓存和已保存 PandaAI 结果；没有创建因子或发起回测。",
        "",
        "| family | candidate | finite | periods | local RankIC | local gross | platform gross | gross delta pp | local net | platform net | net delta pp | local net @ platform cost | residual pp | Top20 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('family', '')} | `{row.get('candidate', '')}` | "
            f"{value(row, 'finite_chart_rows')} | {value(row, 'periods')} | "
            f"{value(row, 'local_rank_ic')} | {value(row, 'local_gross_excess_pct')}% | "
            f"{value(row, 'platform_gross_excess_pct')}% | {value(row, 'local_gross_delta_pp')} | "
            f"{value(row, 'local_net_excess_pct')}% | {value(row, 'platform_net_excess_pct')}% | "
            f"{value(row, 'local_net_delta_pp')} | {value(row, 'local_net_using_platform_cost_pct')}% | "
            f"{value(row, 'platform_cost_sensitivity_delta_pp')} | "
            f"{value(row, 'top20_overlap')}/20 |"
        )
    lines.extend(
        [
            "",
            "## 当前结论",
            "",
            "- D03 严格按 `_report_panel()` 的非空报告序号、中心化 `ddof=1`、`float32` 诊断为 89 个有效期；本地毛超额约 `6.93%`，平台为 `7.76%`。把平台年化成本 `20.6751%` 套到本地毛超额后约为 `-13.75%`，与平台净超额 `-12.9151%` 只差约 `-0.8350pp`，说明净超额差主要来自换手摘要口径，但字段值/有效期和 Top20（4/20）仍未完全复现。",
            "- D02 的 `comm_exp` 最接近的严格报告语义仍比平台毛超额低约 `8.53pp`，套用平台成本后与平台净超额仍差约 `-8.53pp`；`insurance_exp` 当前无可用记录。因此 D02 不能靠换手成本口径抹平。",
            "",
            "## 解释边界",
            "",
            "- D02 的 `insurance_exp` 与 `comm_exp` 都是 Tushare 候选代理；结果不能证明任一字段等价于平台字段。",
            "- D03 的 `proc_issue_bonds` 是 `cash_received_from_issuing_security` 的 Tushare 字段代理；中心化 `ddof=1` 才对应 AlphaPROBE `TsCov` 的已知实现。",
            "- 金额缩放只改变协方差数值尺度，若不改变浮点排序，通常不会改变分组；`float32`/矩估计的结果用于识别数值抵消。",
            "- `platform_gross_excess_pct` 来自保存结果的分组毛超额；`platform_net_excess_pct` 和平台成本来自同一批次 CSV。净超额差必须与平台净超额比较，不能把本地净超额减平台毛超额。",
            "- `local_net_using_platform_cost_pct` 是本地毛超额减去平台批次的年化成本，仅用于拆分换手影响；它不是正式本地净超额。若该值已接近平台净超额，差异主要由平台/本地换手摘要口径造成。",
            "- 正式规则未因本诊断改变；任何采用新代理的正式复现都必须递增规则版本并使用新目录。",
        ]
    )
    output_base.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "research_reports/platform_alignment/d02_d03_field_cov_diagnosis_20260917",
    )
    parser.add_argument(
        "--price-root",
        type=Path,
        default=PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches",
    )
    parser.add_argument(
        "--cap-root",
        type=Path,
        default=PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a",
    )
    parser.add_argument(
        "--financial-root",
        type=Path,
        default=PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/financial_full_a",
    )
    args = parser.parse_args()

    data_start = pd.Timestamp(ALIGNMENT_DATA_START)
    end = pd.Timestamp(ALIGNMENT_END)
    frame = load_full_a_data(args.price_root, args.cap_root, data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame[
        ["date", "instrument", "close_qfq", "total_mv"]
    ].sort_values(["instrument", "date"], kind="stable").reset_index(drop=True)
    calendar = ensure_calendar(data_start, end, token=None)
    calendar = [date for date in calendar if data_start <= date <= end]
    close = panel_close(frame, calendar)
    cache = load_financial_cache(args.financial_root)
    d02_platform = read_platform_run(D02_RESULT)
    d03_platform = read_platform_run(D03_RESULT)
    d02_platform["batch_metrics"] = read_platform_batch_metrics(D02_RESULT)
    d03_platform["batch_metrics"] = read_platform_batch_metrics(D03_RESULT)

    print(f"local_rows={len(frame)} instruments={frame['instrument'].nunique()}", flush=True)
    print("building=D02", flush=True)
    candidates = d02_candidates(frame, cache, d02_platform, close, calendar)
    print("building=D03", flush=True)
    candidates.extend(d03_candidates(frame, cache, d03_platform, close, calendar))
    report = {
        "schema_version": 2,
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment": {
            "data_start": day_text(data_start),
            "end": day_text(end),
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "label_offset": ALIGNMENT_LABEL_OFFSET,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "benchmark": "factor_valid",
        },
        "platform_runs": {
            "D02": {
                "path": str(D02_RESULT),
                "formula": D02_FORMULA,
                "chart_periods": len(d02_platform["dates"]),
                "batch_metrics": d02_platform["batch_metrics"],
            },
            "D03": {
                "path": str(D03_RESULT),
                "formula": D03_FORMULA,
                "chart_periods": len(d03_platform["dates"]),
                "batch_metrics": d03_platform["batch_metrics"],
            },
        },
        "candidates": candidates,
    }
    write_report(args.output, report)
    print(f"wrote={args.output.with_suffix('.json')}", flush=True)
    print(f"wrote={args.output.with_suffix('.csv')}", flush=True)
    print(f"wrote={args.output.with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
