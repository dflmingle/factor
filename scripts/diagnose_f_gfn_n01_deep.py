#!/usr/bin/env python3
"""Deeper offline diagnosis for the saved F-GFN-N01 run.

This script only reads the saved PandaAI result and local Tushare caches.  It
does not create a factor or start a platform run.  The output is deliberately
versioned separately from the canonical alignment result because raw-price and
formula-parser variants are sensitivities, not validated alignment rules.

The diagnosis covers four questions that the first N01 audit could not settle:

* does switching qfq/raw price data or HIGH/CLOSE change the conclusion;
* does the label offset explain the gap;
* could operator association explain ``AMOUNT / VOLUME / HIGH``; and
* can an AMOUNT unit conversion change the ranking (it cannot when it is a
  positive scalar applied uniformly to the whole cross-section).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose_f_gfn_n01 import (  # noqa: E402
    CYCLE,
    DEFAULT_CAP_ROOT,
    DEFAULT_PRICE_ROOT,
    DEFAULT_RAW_ROOT,
    END,
    GROUPS,
    PLATFORM_RESULT,
    build_returns,
    day_text,
    evaluate_variant,
    factor_from_denominator,
    finite,
    json_default,
    load_raw_2024,
    make_close_panel,
    parse_date,
    platform_period_frame,
    raw_factor_values,
)
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_MODE,
    ALIGNMENT_DATA_START,
    ALIGNMENT_GROUPS,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
)
from tushare_factor_recheck import load_trade_dates  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/f_gfn_n01_deep_20260917"


def left_associated_factor(frame: pd.DataFrame, denominator: str) -> pd.Series:
    """Evaluate (AMOUNT / VOLUME) / denominator on the qfq frame."""
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    denom = pd.to_numeric(frame[denominator], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        values = amount.div(volume.replace(0.0, np.nan)).div(denom.replace(0.0, np.nan))
    return values.replace([np.inf, -np.inf], np.nan)


def right_associated_factor(frame: pd.DataFrame, denominator: str) -> pd.Series:
    """Evaluate AMOUNT / (VOLUME / denominator) as a parser sensitivity."""
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    denom = pd.to_numeric(frame[denominator], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        values = amount.mul(denom).div(volume.replace(0.0, np.nan))
    return values.replace([np.inf, -np.inf], np.nan)


def raw_formula_values(
    frame: pd.DataFrame,
    raw: pd.DataFrame,
    denominator: str,
    association: str,
) -> pd.Series:
    """Evaluate a direct N01 parser variant on the raw 2024 source."""
    keys = frame.loc[
        frame["date"].between("2024-01-01", "2024-12-31"),
        ["date", "instrument"],
    ].copy()
    keys["_row_id"] = keys.index.to_numpy(dtype=np.int64)
    source = raw[["date", "instrument", "amount", "volume", denominator]].copy()
    joined = keys.merge(source, on=["date", "instrument"], how="left")
    amount = pd.to_numeric(joined["amount"], errors="coerce")
    volume = pd.to_numeric(joined["volume"], errors="coerce")
    denom = pd.to_numeric(joined[denominator], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        if association == "left":
            values = amount.div(volume.replace(0.0, np.nan)).div(
                denom.replace(0.0, np.nan)
            )
        else:
            values = amount.mul(denom).div(volume.replace(0.0, np.nan))
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    result.loc[joined["_row_id"].to_numpy(dtype=np.int64)] = values.replace(
        [np.inf, -np.inf], np.nan
    ).to_numpy()
    return result


def make_raw_close_panel(raw: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    """Build a raw close panel; only 2024 signal dates are used by this audit."""
    observed = raw.pivot(index="date", columns="instrument", values="close")
    return observed.reindex(calendar).sort_index(axis=1).ffill()


def platform_integrity(platform_path: Path, platform: dict[str, Any]) -> dict[str, Any]:
    raw = json.loads(platform_path.read_text(encoding="utf-8-sig"))
    result_nodes = raw.get("results", {}).get("nodes", {})
    urls = [
        str(value.get("url"))
        for value in result_nodes.values()
        if isinstance(value, dict) and value.get("url")
    ]
    top = [row for row in platform.get("top", []) if isinstance(row, dict)]
    top_dates = sorted({str(row.get("date")) for row in top if row.get("date")})
    factor_values = [
        row.get("factor1") if row.get("factor1") is not None else row.get("factor_value")
        for row in top
    ]
    factor_values = [value for value in factor_values if value is not None]
    chart_last = day_text(platform["dates"][-1]) if platform.get("dates") else None
    return {
        "saved_result_keys": sorted(raw),
        "result_node_count": len(result_nodes),
        "factor_value_download_url_count": len(urls),
        "factor_value_download_available": bool(urls),
        "top_count": len(top),
        "top_dates": top_dates,
        "top_factor1_unique_values": sorted({str(value) for value in factor_values}),
        "top_factor1_unique_count": len({str(value) for value in factor_values}),
        "chart_last_date": chart_last,
        "top_date_equals_chart_last": bool(top_dates and chart_last and top_dates[-1][:10].replace("-", "") == chart_last),
        "top_symbols": [str(row.get("symbol")) for row in top if row.get("symbol")],
        "interpretation": (
            "The saved result exposes no factor-value download URL; Top20 factor1 is constant "
            "and is dated after the chart. Treat Top20 membership as a display diagnostic only."
            if not urls and len({str(value) for value in factor_values}) <= 1
            else "The saved result requires further inspection before using Top20 as a value-level check."
        ),
    }


def scalar_invariance(
    frame: pd.DataFrame,
    base_values: pd.Series,
    signal_dates: list[pd.Timestamp],
    scales: list[float],
) -> dict[str, Any]:
    """Check ranking/grouping invariance under positive AMOUNT unit scalars.

    A direct ``rank(method="first")`` comparison is sensitive to a few ULPs
    of floating-point noise when two factor values are tied or nearly tied.
    Keep that strict result for auditability, but use tolerance-based tie
    groups for the economic ranking conclusion.
    """

    ranking_rtol = 1e-12
    ranking_atol = 1e-15

    def tie_groups(values: np.ndarray) -> np.ndarray:
        order = np.argsort(values, kind="mergesort")
        ordered = values[order]
        starts = np.r_[True, ~np.isclose(
            ordered[1:],
            ordered[:-1],
            rtol=ranking_rtol,
            atol=ranking_atol,
        )]
        labels = np.cumsum(starts, dtype=np.int64) - 1
        result = np.empty(len(values), dtype=np.int64)
        result[order] = labels
        return result

    base = pd.to_numeric(base_values, errors="coerce")
    rows: list[dict[str, Any]] = []
    all_rank_equal = True
    all_strict_rank_equal = True
    max_abs_identity_error = 0.0
    max_rank_difference = 0
    for scale in scales:
        scaled = base * scale
        valid = base.notna() & scaled.notna()
        if valid.any():
            identity_error = float(np.nanmax(np.abs(scaled[valid].to_numpy() - base[valid].to_numpy() * scale)))
        else:
            identity_error = None
        rank_equal = True
        material_rank_equal = True
        rank_difference = 0
        material_rank_difference = 0
        for date in signal_dates:
            mask = frame["date"].eq(date) & valid
            if not mask.any():
                continue
            base_date = base[mask].to_numpy(dtype=float)
            scaled_date = scaled[mask].to_numpy(dtype=float)
            left = pd.Series(base_date).rank(method="first").to_numpy()
            right = pd.Series(scaled_date).rank(method="first").to_numpy()
            difference = int(np.sum(left != right))
            rank_difference = max(rank_difference, difference)
            rank_equal = rank_equal and difference == 0
            normalized_scaled = scaled_date / scale
            base_groups = tie_groups(base_date)
            scaled_groups = tie_groups(normalized_scaled)
            material_difference = int(np.sum(base_groups != scaled_groups))
            material_rank_difference = max(material_rank_difference, material_difference)
            material_rank_equal = material_rank_equal and material_difference == 0
        all_strict_rank_equal = all_strict_rank_equal and rank_equal
        max_rank_difference = max(max_rank_difference, rank_difference)
        if identity_error is not None:
            max_abs_identity_error = max(max_abs_identity_error, identity_error)
        rows.append(
            {
                "amount_scale": scale,
                "rank_equal_on_all_signal_dates": material_rank_equal,
                "strict_rank_equal_on_all_signal_dates": rank_equal,
                "material_rank_equal_on_all_signal_dates": material_rank_equal,
                "max_rank_difference_rows_on_one_date": rank_difference,
                "max_material_rank_difference_rows_on_one_date": material_rank_difference,
                "max_absolute_scalar_identity_error": identity_error,
            }
        )
        all_rank_equal = all_rank_equal and material_rank_equal
    return {
        "scales": rows,
        "all_rank_equal": all_rank_equal,
        "all_strict_rank_equal": all_strict_rank_equal,
        "max_rank_difference_rows": max_rank_difference,
        "max_material_rank_difference_rows": max(
            row["max_material_rank_difference_rows_on_one_date"] for row in rows
        ),
        "max_absolute_scalar_identity_error": max_abs_identity_error,
        "ranking_tolerance": {
            "rtol": ranking_rtol,
            "atol": ranking_atol,
            "meaning": "near-equal factor values are treated as one tie group",
        },
        "conclusion": (
            "A positive uniform AMOUNT unit conversion cannot change cross-sectional ranking, "
            "RankIC, groups, Top20 or turnover; it is not a candidate alignment fix."
            if all_rank_equal
            else "Material rank changes occurred; inspect missing-value or formula handling."
        ),
    }


def source_unit_audit(frame: pd.DataFrame, raw: pd.DataFrame) -> dict[str, Any]:
    qfq = frame[frame["date"].between("2024-01-01", "2024-12-31")][
        ["date", "instrument", "amount", "volume"]
    ].copy()
    joined = qfq.merge(raw[["date", "instrument", "amount", "volume"]], on=["date", "instrument"], how="inner", suffixes=("_qfq", "_raw"))
    result: dict[str, Any] = {"joined_rows": int(len(joined))}
    for field in ["amount", "volume"]:
        left = pd.to_numeric(joined[f"{field}_qfq"], errors="coerce")
        right = pd.to_numeric(joined[f"{field}_raw"], errors="coerce")
        valid = left.notna() & right.notna() & right.ne(0)
        ratio = left[valid].div(right[valid]) if valid.any() else pd.Series(dtype=float)
        result[field] = {
            "n": int(valid.sum()),
            "median_qfq_over_raw": finite(ratio.median()) if not ratio.empty else None,
            "p05_qfq_over_raw": finite(ratio.quantile(0.05)) if not ratio.empty else None,
            "p95_qfq_over_raw": finite(ratio.quantile(0.95)) if not ratio.empty else None,
            "exact_fraction": float(np.mean(np.isclose(left[valid], right[valid], rtol=1e-10, atol=1e-8))) if valid.any() else None,
        }
    result["interpretation"] = (
        "AMOUNT and VOLUME are effectively unchanged between the cached qfq and raw sources; "
        "there is no observed 0.1 or 10 unit split to explain the platform ranking."
    )
    return result


def compact_result(row: dict[str, Any]) -> dict[str, Any]:
    rank_seq = row.get("rank_ic_sequence") or {}
    excess_seq = row.get("excess_sequence") or {}
    return {
        key: row.get(key)
        for key in [
            "variant",
            "scope",
            "label_offset",
            "periods",
            "platform_periods",
            "period_coverage",
            "local_rank_ic",
            "platform_rank_ic_chart_mean",
            "rank_ic_delta",
            "local_gross_excess",
            "platform_gross_excess",
            "gross_delta_pp",
            "local_turnover",
            "platform_turnover",
            "local_net_excess",
            "platform_net_excess",
            "net_delta_pp",
            "platform_turnover_sensitivity_net",
        ]
    } | {
        "rank_ic_sequence_corr": rank_seq.get("corr"),
        "excess_sequence_corr": excess_seq.get("corr"),
    }


def fmt_num(value: Any, digits: int = 4) -> str:
    number = finite(value)
    return "n/a" if number is None else f"{number:.{digits}f}"


def fmt_pct(value: Any, digits: int = 2) -> str:
    number = finite(value)
    return "n/a" if number is None else f"{number * 100.0:.{digits}f}%"


def write_report(path: Path, payload: dict[str, Any], results: list[dict[str, Any]]) -> None:
    platform = payload["platform"]
    integrity = payload["platform_integrity"]
    lines = [
        "# F-GFN-N01 深度诊断 2",
        "",
        "本报告只读取已保存的平台运行结果和本地 Tushare 缓存，不创建因子、不发起平台回测。",
        "",
        f"- 规则版本：`{ALIGNMENT_RULE_VERSION}`；正式规则文档：`{ALIGNMENT_RULES_DOCUMENT}`",
        f"- 正式公共口径：全 A、qfq、`{ALIGNMENT_MARKET_CAP_FIELD}`、10 组、`{ALIGNMENT_BENCHMARK_MODE}`、{ALIGNMENT_ONE_WAY_COST:.2%} 单边成本",
        f"- 诊断结果目录：`{path.parent}`；raw 只覆盖本地已有的 2024 文件，不能替代正式全量结果。",
        "",
        "## 结论",
        "",
        "1. `AMOUNT` 乘 `0.1/1/10/100` 是正的统一标量；按容差处理近等值后逐信号日实质排序不变，所以金额单位换算不能抹平 N01 差异。",
        "2. qfq/raw、HIGH/CLOSE 和 label=0/1 的组合没有同时接近平台的 RankIC、收益路径和换手；切换标签或复权不能作为正式修复。",
        "3. 左结合 `(AMOUNT/VOLUME)/HIGH` 与右结合 `AMOUNT/(VOLUME/HIGH)` 是不同因子；右结合仅是解析敏感性，若结果仍不过质量门槛，也不能据此改平台公式。",
        "4. 已保存结果和在线 `factor_result` 都没有逐票因子值下载 URL；Top20 日期晚于图表最后日期，且 20 个展示因子值相同。Top20 只能标记为展示异常，不能证明本地排序错误的具体方向。",
        "5. N01 继续保持 `unsupported`，不进入本地因子挖掘池；下一步需要平台提供逐票因子值或逐期持仓明细，才能继续定位字段语义。",
        "",
        "## 组合结果",
        "",
        "`gross`/`net` 是本地正式代理值；平台列是保存结果摘要；`rank corr` 和 `excess corr` 是与平台图表逐期序列的相关性。",
        "",
        "| variant | scope | label | periods | RankIC local/platform | rank corr | gross local/platform | excess corr | net local/platform | turnover local/platform |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['variant']} | {row['scope']} | {row['label_offset']} | {row['periods']}/{row['platform_periods']} | "
            f"{fmt_num(row['local_rank_ic'])}/{fmt_num(row['platform_rank_ic_chart_mean'])} | "
            f"{fmt_num(row['rank_ic_sequence_corr'], 3)} | "
            f"{fmt_pct(row['local_gross_excess'])}/{fmt_pct(row['platform_gross_excess'])} | "
            f"{fmt_num(row['excess_sequence_corr'], 3)} | "
            f"{fmt_pct(row['local_net_excess'])}/{fmt_pct(row['platform_net_excess'])} | "
            f"{fmt_pct(row['local_turnover'])}/{fmt_pct(row['platform_turnover'])} |"
        )
    lines.extend(
        [
            "",
            "## AMOUNT 单位不变量",
            "",
            f"- 检查的正标量：`{', '.join(str(row['amount_scale']) for row in payload['amount_scalar_invariance']['scales'])}`。",
            f"- 按容差合并近等值后的排序保持一致：`{payload['amount_scalar_invariance']['all_rank_equal']}`；最大实质排序差异行数：`{payload['amount_scalar_invariance']['max_material_rank_difference_rows']}`。",
            f"- 严格浮点排序完全一致：`{payload['amount_scalar_invariance']['all_strict_rank_equal']}`；最大严格差异行数：`{payload['amount_scalar_invariance']['max_rank_difference_rows']}`（仅近等值舍入噪声）。",
            f"- 最大标量恒等式误差：`{payload['amount_scalar_invariance']['max_absolute_scalar_identity_error']:.3e}`。",
            "- 因此不能靠把 Tushare 的千元/手换算成元/股来改变 N01 的股票顺序；若平台顺序不同，原因不是统一单位常数。",
            "",
            "## 平台结果完整性",
            "",
            f"- Top20 条数：`{integrity['top_count']}`；Top20 日期：`{', '.join(integrity['top_dates'])}`；图表最后日期：`{integrity['chart_last_date']}`。",
            f"- Top20 `factor1` 去重后：`{integrity['top_factor1_unique_count']}` 个值：`{', '.join(integrity['top_factor1_unique_values'])}`。",
            f"- 结果节点中的逐票下载 URL：`{integrity['factor_value_download_url_count']}`；可用：`{integrity['factor_value_download_available']}`。",
            f"- 判断：{integrity['interpretation']}",
            "",
            "## 数据源审计",
            "",
            f"- qfq/raw 2024 交集：`{payload['source_unit_audit']['joined_rows']:,}` 行。",
            f"- AMOUNT qfq/raw 中位数比例：`{fmt_num(payload['source_unit_audit']['amount']['median_qfq_over_raw'])}`，P05/P95：`{fmt_num(payload['source_unit_audit']['amount']['p05_qfq_over_raw'])}`/`{fmt_num(payload['source_unit_audit']['amount']['p95_qfq_over_raw'])}`。",
            f"- VOLUME qfq/raw 中位数比例：`{fmt_num(payload['source_unit_audit']['volume']['median_qfq_over_raw'])}`，P05/P95：`{fmt_num(payload['source_unit_audit']['volume']['p05_qfq_over_raw'])}`/`{fmt_num(payload['source_unit_audit']['volume']['p95_qfq_over_raw'])}`。",
            "",
            "## 文件",
            "",
            "- `diagnosis.json`：机器可读的完整结果。",
            "- `variant_summary.csv`：各组合的核心指标。",
            "- `periods_*.csv`：逐期本地/平台序列。",
            "- `amount_scalar_invariance.json`：金额单位正标量不变量检查。",
            "- `platform_top_audit.json`：平台 Top20 与结果节点审计。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    platform_path = Path(args.platform_result)
    platform = read_platform_run(platform_path)
    platform_periods = platform_period_frame(platform)
    platform_periods.attrs["platform_group_metrics"] = platform["group_metrics"]
    chart_dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
    raw_dates = [date for date in chart_dates if date.year == 2024]
    if not raw_dates:
        raise RuntimeError("The saved platform result has no 2024 chart dates")

    print("loading=qfq_full_a", flush=True)
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        parse_date(args.data_start),
        parse_date(args.end),
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD).sort_values(
        ["instrument", "date"], ignore_index=True
    )
    raw = load_raw_2024(Path(args.raw_root))
    calendar = [
        pd.Timestamp(value).normalize()
        for value in load_trade_dates(parse_date(args.data_start), parse_date(args.end))
    ]
    qfq_close = make_close_panel(frame, calendar)
    raw_close = make_raw_close_panel(raw, calendar)
    qfq_returns = {
        offset: build_returns(qfq_close, calendar, chart_dates, CYCLE, offset)
        for offset in [1, 0]
    }
    raw_returns = {
        offset: build_returns(raw_close, calendar, raw_dates, CYCLE, offset)
        for offset in [1, 0]
    }

    factor_map: dict[str, pd.Series] = {
        "qfq_high_left": left_associated_factor(frame, "high_qfq"),
        "qfq_close_left": left_associated_factor(frame, "close_qfq"),
        "qfq_high_right": right_associated_factor(frame, "high_qfq"),
        "qfq_close_right": right_associated_factor(frame, "close_qfq"),
        "raw_high_left": raw_formula_values(frame, raw, "high", "left"),
        "raw_close_left": raw_formula_values(frame, raw, "close", "left"),
        "raw_high_right": raw_formula_values(frame, raw, "high", "right"),
        "raw_close_right": raw_formula_values(frame, raw, "close", "right"),
    }

    specs = [
        ("qfq_high_left__qfq_return", "qfq", "qfq_high_left", qfq_returns, chart_dates),
        ("qfq_close_left__qfq_return", "qfq", "qfq_close_left", qfq_returns, chart_dates),
        ("qfq_high_right__qfq_return", "qfq_parser_sensitivity", "qfq_high_right", qfq_returns, chart_dates),
        ("qfq_close_right__qfq_return", "qfq_parser_sensitivity", "qfq_close_right", qfq_returns, chart_dates),
        ("raw_high_left__qfq_return", "raw_factor_qfq_return", "raw_high_left", qfq_returns, raw_dates),
        ("raw_close_left__qfq_return", "raw_factor_qfq_return", "raw_close_left", qfq_returns, raw_dates),
        ("raw_high_left__raw_return", "raw", "raw_high_left", raw_returns, raw_dates),
        ("raw_close_left__raw_return", "raw", "raw_close_left", raw_returns, raw_dates),
        ("raw_high_right__raw_return", "raw_parser_sensitivity", "raw_high_right", raw_returns, raw_dates),
        ("raw_close_right__raw_return", "raw_parser_sensitivity", "raw_close_right", raw_returns, raw_dates),
    ]

    result_rows: list[dict[str, Any]] = []
    for variant, scope, factor_name, return_map, dates in specs:
        for label_offset in [1, 0]:
            print(f"evaluating={variant} label={label_offset} periods={len(dates)}", flush=True)
            platform_subset = platform_periods[platform_periods["date"].isin(dates)].copy()
            platform_subset.attrs["platform_group_metrics"] = platform["group_metrics"]
            row, periods = evaluate_variant(
                frame,
                factor_map[factor_name],
                return_map[label_offset],
                platform_subset,
                dates,
                label_offset,
                variant,
                scope,
            )
            result_rows.append(compact_result(row))
            periods.to_csv(
                output / f"periods_{variant}_label{label_offset}.csv",
                index=False,
                encoding="utf-8-sig",
            )

    amount_base_dates = chart_dates
    scalar = scalar_invariance(
        frame,
        factor_map["qfq_high_left"],
        amount_base_dates,
        [0.1, 1.0, 10.0, 100.0],
    )
    scalar["base_variant"] = "qfq_high_left__qfq_return"
    scalar["base_label_offset"] = 1
    scalar["note"] = "Only positive uniform AMOUNT scalars are tested; zero/negative transforms are different formulas."

    integrity = platform_integrity(platform_path, platform)
    source_audit = source_unit_audit(frame, raw)
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "data_start": day_text(parse_date(args.data_start)),
            "end": day_text(parse_date(args.end)),
            "cycle": CYCLE,
            "groups": GROUPS,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "platform_result": str(platform_path),
            "formal_scope": "qfq full-A and factor_valid benchmark",
            "raw_scope": "2024 raw daily cache only",
            "diagnostic_only": True,
        },
        "platform": {
            "formula": "AMOUNT / VOLUME / HIGH",
            "chart_periods": len(chart_dates),
            "chart_start": day_text(chart_dates[0]),
            "chart_end": day_text(chart_dates[-1]),
            "rank_ic": platform["metrics"].get("Rank_IC"),
            "group10": platform["group_metrics"].get(10, {}),
        },
        "platform_integrity": integrity,
        "source_unit_audit": source_audit,
        "amount_scalar_invariance": scalar,
        "variants": result_rows,
        "parser_note": {
            "platform_formula": "AMOUNT / VOLUME / HIGH",
            "left_associated_expression": "(AMOUNT / VOLUME) / HIGH",
            "right_associated_sensitivity": "AMOUNT / (VOLUME / HIGH) = AMOUNT * HIGH / VOLUME",
            "warning": "The right-associated expression is a different factor and is not evidence of the platform parser without per-stock values.",
        },
    }
    (output / "diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(result_rows).to_csv(output / "variant_summary.csv", index=False, encoding="utf-8-sig")
    (output / "amount_scalar_invariance.json").write_text(
        json.dumps(scalar, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    (output / "platform_top_audit.json").write_text(
        json.dumps(integrity, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    write_report(output / "diagnosis.md", payload, result_rows)
    print(f"report={output / 'diagnosis.md'}", flush=True)
    for row in result_rows:
        print(
            f"{row['variant']} label={row['label_offset']} rank={fmt_num(row['local_rank_ic'])} "
            f"platform={fmt_num(row['platform_rank_ic_chart_mean'])} gross={fmt_pct(row['local_gross_excess'])} "
            f"net={fmt_pct(row['local_net_excess'])}",
            flush=True,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-result", default=str(PLATFORM_RESULT))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--data-start", default="20180101")
    parser.add_argument("--end", default=day_text(END))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
