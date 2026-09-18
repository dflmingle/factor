#!/usr/bin/env python3
"""Summarize platform/local turnover comparability from a saved run.

This is an offline report generator. It reads the versioned output of
``positive_factor_local_compare.py`` and never contacts PandaAI or loads the
large local market-data cache.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from platform_alignment_rules import (
    ALIGNMENT_LOCAL_TURNOVER_LOW_THRESHOLD,
    ALIGNMENT_PLATFORM_TURNOVER_HIGH_THRESHOLD,
    ALIGNMENT_PLATFORM_TURNOVER_OVER_100_THRESHOLD,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_LARGE_GROSS_DELTA_PP,
    ALIGNMENT_LARGE_NET_DELTA_PP,
    ALIGNMENT_LARGE_RANK_IC_DELTA,
    ALIGNMENT_MIN_PERIOD_COVERAGE,
    ALIGNMENT_MIN_TOP20_OVERLAP,
    ALIGNMENT_TURNOVER_GAP_ALERT_THRESHOLD,
    ALIGNMENT_TURNOVER_DOMINANT_MAX_SENSITIVITY_DELTA_PP,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/"
    "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
    "turnoverdiag1_qualitygate1/all_factor_local_compare.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/turnover_alignment_diagnosis_20260917_qualitygate1"

# These are reporting heuristics, not alignment rules. They identify cases in
# which substituting platform turnover nearly removes the net-excess gap.
TURNOVER_DOMINANT_MIN_CANONICAL_GAP_PP = 5.0
TURNOVER_DOMINANT_MAX_SENSITIVITY_GAP_PP = 2.0


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def pct_fraction(value: Any) -> float | None:
    number = finite_float(value)
    return None if number is None else 100.0 * number


def net_delta_pp(row: dict[str, Any], key: str) -> float | None:
    value = finite_float(row.get(key))
    if value is not None:
        return value
    local_net = finite_float(row.get("local_net_excess"))
    platform_net = finite_float(row.get("platform_net_excess_pct"))
    if key == "local_net_delta_pp" and local_net is not None and platform_net is not None:
        return 100.0 * local_net - platform_net
    sensitivity = finite_float(row.get("platform_turnover_cost_sensitivity"))
    if (
        key == "platform_turnover_sensitivity_delta_pp"
        and sensitivity is not None
        and platform_net is not None
    ):
        return 100.0 * sensitivity - platform_net
    return None


def normalized_row(row: dict[str, Any]) -> dict[str, Any]:
    canonical_delta = net_delta_pp(row, "local_net_delta_pp")
    sensitivity_delta = net_delta_pp(
        row, "platform_turnover_sensitivity_delta_pp"
    )
    turnover_gap = finite_float(row.get("turnover_gap_pp"))
    sensitivity_net = pct_fraction(row.get("platform_turnover_cost_sensitivity"))
    local_net = pct_fraction(row.get("local_net_excess"))
    platform_net = finite_float(row.get("platform_net_excess_pct"))
    cost_sensitivity_shift = (
        None
        if local_net is None or sensitivity_net is None
        else local_net - sensitivity_net
    )
    abs_delta_reduction = (
        None
        if canonical_delta is None or sensitivity_delta is None
        else abs(canonical_delta) - abs(sensitivity_delta)
    )
    status = str(row.get("turnover_alignment") or "unavailable")
    turnover_dominant = (
        status != "comparable"
        and canonical_delta is not None
        and sensitivity_delta is not None
        and abs(canonical_delta) >= TURNOVER_DOMINANT_MIN_CANONICAL_GAP_PP
        and abs(sensitivity_delta) <= TURNOVER_DOMINANT_MAX_SENSITIVITY_GAP_PP
    )
    flags = row.get("turnover_diagnostic_flags") or []
    if isinstance(flags, list):
        flags_text = ";".join(str(flag) for flag in flags)
    else:
        flags_text = str(flags)
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "handler": row.get("handler"),
        "formula": row.get("formula"),
        "platform_net_pct": platform_net,
        "local_net_pct": local_net,
        "local_net_delta_pp": canonical_delta,
        "local_gross_pct": pct_fraction(row.get("local_gross_excess")),
        "platform_gross_pct": pct_fraction(row.get("platform_gross_excess")),
        "platform_turnover_pct": pct_fraction(row.get("platform_turnover")),
        "local_turnover_pct": pct_fraction(row.get("local_turnover")),
        "turnover_gap_pp": turnover_gap,
        "turnover_absolute_gap_pp": finite_float(row.get("turnover_absolute_gap_pp")),
        "turnover_alignment": status,
        "turnover_comparable": bool(row.get("turnover_comparable")),
        "turnover_flags": flags_text,
        "platform_turnover_cost_pct": pct_fraction(
            row.get("platform_turnover_annual_cost")
        ),
        "platform_turnover_sensitivity_net_pct": sensitivity_net,
        "platform_turnover_sensitivity_delta_pp": sensitivity_delta,
        "turnover_cost_sensitivity_shift_pp": cost_sensitivity_shift,
        "sensitivity_abs_delta_reduction_pp": abs_delta_reduction,
        "turnover_dominant": turnover_dominant,
        "alignment_quality": row.get("alignment_quality") or "unsupported",
        "local_mining_eligible": bool(row.get("local_mining_eligible")),
        "alignment_quality_flags": ";".join(
            str(flag) for flag in (row.get("alignment_quality_flags") or [])
        ),
        "alignment_quality_reason": row.get("alignment_quality_reason"),
        "local_gross_delta_pp": finite_float(row.get("local_gross_delta_pp")),
        "rank_ic_delta": finite_float(row.get("rank_ic_delta")),
        "period_coverage": finite_float(row.get("period_coverage")),
        "top20_overlap": row.get("top20_overlap"),
        "periods": row.get("periods"),
        "date_source": row.get("date_source"),
        "fidelity": row.get("fidelity"),
    }


def summarize(payload: dict[str, Any], input_path: Path) -> dict[str, Any]:
    settings = payload.get("settings") or {}
    source_version = settings.get("alignment_rule_version")
    if source_version != ALIGNMENT_RULE_VERSION:
        raise ValueError(
            f"Input uses alignment rule {source_version!r}; "
            f"expected {ALIGNMENT_RULE_VERSION!r}"
        )
    rows = [normalized_row(row) for row in payload.get("results", [])]
    valid = [row for row in rows if row["local_net_delta_pp"] is not None]
    sensitivity_valid = [
        row
        for row in rows
        if row["platform_turnover_sensitivity_delta_pp"] is not None
    ]
    improved = [
        row
        for row in sensitivity_valid
        if row["sensitivity_abs_delta_reduction_pp"] is not None
        and row["sensitivity_abs_delta_reduction_pp"] > 0.0
    ]
    summary = {
        "alignment_rule_version": source_version,
        "alignment_rules_document": settings.get(
            "alignment_rules_document", ALIGNMENT_RULES_DOCUMENT
        ),
        "source_result": str(input_path),
        "selected_platform_records": int(
            settings.get("supported_records", len(rows))
            + settings.get("unsupported_records", len(payload.get("unsupported", [])))
        ),
        "reproduced_records": len(rows),
        "unsupported_records": len(payload.get("unsupported", [])),
        "valid_canonical_net_records": len(valid),
        "valid_sensitivity_records": len(sensitivity_valid),
        "turnover_status_counts": dict(
            Counter(row["turnover_alignment"] for row in rows)
        ),
        "quality_status_counts": dict(
            Counter(row["alignment_quality"] for row in rows)
        ),
        "local_mining_eligible_records": sum(
            row["local_mining_eligible"] for row in rows
        ),
        "turnover_comparable_records": sum(
            row["turnover_alignment"] == "comparable" for row in rows
        ),
        "sensitivity_improved_records": len(improved),
        "canonical_mae_pp": (
            mean(abs(row["local_net_delta_pp"]) for row in valid) if valid else None
        ),
        "sensitivity_mae_pp": (
            mean(abs(row["platform_turnover_sensitivity_delta_pp"]) for row in sensitivity_valid)
            if sensitivity_valid
            else None
        ),
        "canonical_gap_ge_5pp": sum(
            abs(row["local_net_delta_pp"]) >= 5.0 for row in valid
        ),
        "sensitivity_gap_ge_5pp": sum(
            abs(row["platform_turnover_sensitivity_delta_pp"]) >= 5.0
            for row in sensitivity_valid
        ),
        "turnover_dominant_records": [
            row["id"] for row in rows if row["turnover_dominant"]
        ],
        "thresholds": {
            "platform_turnover_high": ALIGNMENT_PLATFORM_TURNOVER_HIGH_THRESHOLD,
            "local_turnover_low": ALIGNMENT_LOCAL_TURNOVER_LOW_THRESHOLD,
            "turnover_gap_alert": ALIGNMENT_TURNOVER_GAP_ALERT_THRESHOLD,
            "platform_turnover_over_100": ALIGNMENT_PLATFORM_TURNOVER_OVER_100_THRESHOLD,
            "turnover_dominant_min_canonical_gap_pp": TURNOVER_DOMINANT_MIN_CANONICAL_GAP_PP,
            "turnover_dominant_max_sensitivity_gap_pp": TURNOVER_DOMINANT_MAX_SENSITIVITY_GAP_PP,
            "large_net_delta_pp": ALIGNMENT_LARGE_NET_DELTA_PP,
            "large_gross_delta_pp": ALIGNMENT_LARGE_GROSS_DELTA_PP,
            "large_rank_ic_delta": ALIGNMENT_LARGE_RANK_IC_DELTA,
            "min_top20_overlap": ALIGNMENT_MIN_TOP20_OVERLAP,
            "min_period_coverage": ALIGNMENT_MIN_PERIOD_COVERAGE,
            "turnover_dominant_max_sensitivity_delta_pp": ALIGNMENT_TURNOVER_DOMINANT_MAX_SENSITIVITY_DELTA_PP,
        },
    }
    return {"summary": summary, "rows": rows, "unsupported": payload.get("unsupported", [])}


def fmt_pct(value: Any) -> str:
    number = finite_float(value)
    return "n/a" if number is None else f"{number:.2f}%"


def fmt_pp(value: Any) -> str:
    number = finite_float(value)
    return "n/a" if number is None else f"{number:+.2f}pp"


def write_report(report: dict[str, Any], output_base: Path) -> None:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_base.with_suffix(".json")
    csv_path = output_base.with_suffix(".csv")
    md_path = output_base.with_suffix(".md")
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows = report["rows"]
    fieldnames = [
        "id",
        "name",
        "handler",
        "formula",
        "platform_net_pct",
        "local_net_pct",
        "local_net_delta_pp",
        "local_gross_pct",
        "platform_gross_pct",
        "platform_turnover_pct",
        "local_turnover_pct",
        "turnover_gap_pp",
        "turnover_absolute_gap_pp",
        "turnover_alignment",
        "turnover_comparable",
        "turnover_flags",
        "platform_turnover_cost_pct",
        "platform_turnover_sensitivity_net_pct",
        "platform_turnover_sensitivity_delta_pp",
        "turnover_cost_sensitivity_shift_pp",
        "sensitivity_abs_delta_reduction_pp",
        "turnover_dominant",
        "alignment_quality",
        "local_mining_eligible",
        "alignment_quality_flags",
        "alignment_quality_reason",
        "local_gross_delta_pp",
        "rank_ic_delta",
        "period_coverage",
        "top20_overlap",
        "periods",
        "date_source",
        "fidelity",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summary = report["summary"]
    status_counts = summary["turnover_status_counts"]
    lines = [
        "# 换手对齐诊断",
        "",
        f"规则版本：`{summary['alignment_rule_version']}`；规则文档：`{summary['alignment_rules_document']}`。",
        f"输入：`{summary['source_result']}`。完整逐条表：`{csv_path}`。",
        "",
        "## 摘要",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 已保存平台记录 | {summary['selected_platform_records']} |",
        f"| 本地已计算 | {summary['reproduced_records']} |",
        f"| 当前不支持 | {summary['unsupported_records']} |",
        f"| 本地净超额有效记录 | {summary['valid_canonical_net_records']} |",
        f"| 换手可比 | {summary['turnover_comparable_records']} |",
        f"| 质量状态 | {', '.join(f'`{key}`={value}' for key, value in sorted(summary['quality_status_counts'].items()))} |",
        f"| 可进入本地净超额挖掘 | {summary['local_mining_eligible_records']} |",
        f"| 正式净超额平均绝对差 | {fmt_pp(summary['canonical_mae_pp'])} |",
        f"| 平台换手敏感性平均绝对差 | {fmt_pp(summary['sensitivity_mae_pp'])} |",
        f"| 正式净超额绝对差 >=5pp | {summary['canonical_gap_ge_5pp']} |",
        f"| 敏感性净超额绝对差 >=5pp | {summary['sensitivity_gap_ge_5pp']} |",
        f"| 换手敏感性使绝对差变小 | {summary['sensitivity_improved_records']} |",
        "",
        "换手状态： "
        + ", ".join(f"`{key}`={value}" for key, value in sorted(status_counts.items())),
        "",
        "质量状态： "
        + ", ".join(
            f"`{key}`={value}"
            for key, value in sorted(summary["quality_status_counts"].items())
        ),
        "",
        "## 换手主导差异",
        "",
        "这里的“主导”是诊断启发式：正式净超额绝对差至少 5pp，且替换平台换手计成本后绝对差不超过 2pp。它不是对平台隐藏持仓的证明。",
        "",
        "| 记录 | 平台净超额 | 本地净超额 | 正式差 | 敏感性净超额 | 敏感性差 | 平台/本地换手 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    dominant = [row for row in rows if row["turnover_dominant"]]
    for row in dominant:
        lines.append(
            f"| {row['id']} | {fmt_pct(row['platform_net_pct'])} | {fmt_pct(row['local_net_pct'])} | {fmt_pp(row['local_net_delta_pp'])} | {fmt_pct(row['platform_turnover_sensitivity_net_pct'])} | {fmt_pp(row['platform_turnover_sensitivity_delta_pp'])} | {fmt_pct(row['platform_turnover_pct'])} / {fmt_pct(row['local_turnover_pct'])} |"
        )
    if not dominant:
        lines.append("| none | | | | | | |")

    non_comparable = [row for row in rows if row["turnover_alignment"] != "comparable"]
    lines.extend(
        [
            "",
            "## 不可直接比较的换手",
            "",
            "| 记录 | 状态 | 换手差 | 正式差 | 敏感性差 | 诊断标记 |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in sorted(non_comparable, key=lambda item: item["id"] or ""):
        lines.append(
            f"| {row['id']} | `{row['turnover_alignment']}` | {fmt_pp(row['turnover_gap_pp'])} | {fmt_pp(row['local_net_delta_pp'])} | {fmt_pp(row['platform_turnover_sensitivity_delta_pp'])} | {row['turnover_flags'] or 'n/a'} |"
        )
    if not non_comparable:
        lines.append("| none | | | | | |")

    largest = sorted(
        (row for row in rows if row["local_net_delta_pp"] is not None),
        key=lambda item: abs(item["local_net_delta_pp"]),
        reverse=True,
    )[:15]
    lines.extend(
        [
            "",
            "## 正式净超额差最大的记录",
            "",
            "| 记录 | handler | 正式差 | 敏感性差 | 平台/本地换手 | Top20 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in largest:
        overlap = "n/a" if row["top20_overlap"] is None else f"{row['top20_overlap']}/20"
        lines.append(
            f"| {row['id']} | `{row['handler']}` | {fmt_pp(row['local_net_delta_pp'])} | {fmt_pp(row['platform_turnover_sensitivity_delta_pp'])} | {fmt_pct(row['platform_turnover_pct'])} / {fmt_pct(row['local_turnover_pct'])} | {overlap} |"
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 正式本地净超额仍使用本地相邻信号期实际成员交集计算的换手；平台换手只进入敏感性结果。",
            "- 只有 `alignment_quality=aligned` 且换手可比的记录标记为 `local_mining_eligible=true`；`turnover_dominant` 和 `field_or_path_mismatch` 不进入净超额挖掘候选池。",
            "- `HT13-EXPWRET-6M` 的 RankIC 和 Top20 已接近，平台换手超过 100%，按平台换手计成本后敏感性差约为 0.71pp，主要差异可归因于平台换手摘要与本地成员换手不一致。",
            "- `F-NET-D02` 虽然也触发平台高、本地低换手，但平台换手敏感性差仍约 -16.17pp，说明它还有毛超额/因子字段差异，不能只改成本口径。",
            "- 其他记录即使敏感性变小，也不能据此声称逐期平台持仓已恢复；需要平台提供逐期持仓或逐股票换手明细才能进一步验证。",
            "",
            "## 当前不支持",
            "",
            "| 记录 | 公式 | 原因 |",
            "|---|---|---|",
        ]
    )
    for row in report["unsupported"]:
        lines.append(
            f"| {row.get('id')} | `{row.get('formula') or '?'}` | {row.get('reason') or 'n/a'} |"
        )
    if not report["unsupported"]:
        lines.append("| none | | |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output path without .json/.csv/.md suffix",
    )
    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.is_file():
        raise SystemExit(f"Input result is missing: {input_path}")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    report = summarize(payload, input_path)
    write_report(report, Path(args.output))
    print(f"json={Path(args.output).with_suffix('.json')}")
    print(f"csv={Path(args.output).with_suffix('.csv')}")
    print(f"markdown={Path(args.output).with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
