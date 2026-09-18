#!/usr/bin/env python3
"""Build a field-level failure registry from a saved local alignment run."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from alignment_failure_registry import (
    UNACCEPTABLE_NET_DELTA_PP,
    aggregate_field_risks,
    classify_failure,
)
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, ALIGNMENT_RULES_DOCUMENT


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/"
    "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
    "turnoverdiag1_qualitygate1/all_factor_local_compare.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/factor_alignment_failure_registry"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def record_detail(row: dict[str, Any]) -> dict[str, Any]:
    attribution = classify_failure(row)
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "report": row.get("report"),
        "handler": row.get("handler"),
        "formula": row.get("formula"),
        "platform_net_excess_pct": row.get("platform_net_excess_pct"),
        "local_net_excess": row.get("local_net_excess"),
        "local_net_delta_pp": row.get("local_net_delta_pp"),
        "platform_gross_excess": row.get("platform_gross_excess"),
        "local_gross_excess": row.get("local_gross_excess"),
        "local_gross_delta_pp": row.get("local_gross_delta_pp"),
        "platform_turnover": row.get("platform_turnover"),
        "local_turnover": row.get("local_turnover"),
        "turnover_alignment": row.get("turnover_alignment"),
        "platform_turnover_sensitivity_delta_pp": row.get(
            "platform_turnover_sensitivity_delta_pp"
        ),
        "rank_ic_delta": row.get("rank_ic_delta"),
        "top20_overlap": row.get("top20_overlap"),
        "period_coverage": row.get("period_coverage"),
        "alignment_quality": row.get("alignment_quality"),
        "alignment_quality_flags": row.get("alignment_quality_flags") or [],
        "attribution": attribution,
    }


def build_payload(payload: dict[str, Any], input_path: Path) -> dict[str, Any]:
    settings = payload.get("settings") or {}
    source_version = settings.get("alignment_rule_version")
    if source_version != ALIGNMENT_RULE_VERSION:
        raise ValueError(
            f"Input uses alignment rule {source_version!r}; expected {ALIGNMENT_RULE_VERSION!r}"
        )
    rows = [dict(row) for row in payload.get("results", [])]
    details = [record_detail(row) for row in rows]
    failures = [
        item for item in details if item["attribution"]["unacceptable_by_net_excess"]
    ]
    field_risks = aggregate_field_risks(rows)
    blocked_fields = [
        item["field"] for item in field_risks if item["decision"] == "blocked"
    ]
    cause_counts = Counter(
        code
        for item in failures
        for code in item["attribution"]["cause_codes"]
    )
    valid = [
        item["attribution"]["net_delta_pp"]
        for item in details
        if item["attribution"]["net_delta_pp"] is not None
    ]
    unacceptable_count = len(failures)
    return {
        "alignment_rule_version": source_version,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "source_result": str(input_path),
        "acceptance_rule": {
            "metric": "local_net_delta_pp",
            "hard_failure": f"abs(delta) > {UNACCEPTABLE_NET_DELTA_PP:.2f}pp",
            "threshold_pp": UNACCEPTABLE_NET_DELTA_PP,
        },
        "summary": {
            "selected_platform_records": int(
                settings.get("supported_records", len(rows))
                + settings.get("unsupported_records", len(payload.get("unsupported", [])))
            ),
            "reproduced_records": len(rows),
            "valid_net_records": len(valid),
            "acceptable_net_records": len(valid) - unacceptable_count,
            "unacceptable_net_records": unacceptable_count,
            "unassessable_records": len(rows) - len(valid),
            "cause_counts": dict(cause_counts),
            "blocked_fields": blocked_fields,
        },
        "blocked_fields": blocked_fields,
        "field_risks": field_risks,
        "unacceptable_records": failures,
        "field_evidence_notes": {
            "high": "2026-09-18 单字段隔离未显示 >5pp 大偏差；不要因组合失败全局拉黑 HIGH。",
            "amount": "2026-09-18 AMOUNT/VOLUME 单独组合净超额差约 0.67pp；不要因 T10 组合失败全局拉黑 AMOUNT。",
            "volume": "2026-09-18 AMOUNT/VOLUME 单独组合净超额差约 0.67pp；不要因组合失败全局拉黑 VOLUME。",
            "turnover": "平台只保存汇总换手，换手差异优先标记为成本摘要风险，不等于 TURNOVER 叶子错误。",
        },
        "policy": {
            "default_search_uses_blocked_fields": False,
            "diagnostic_override": "--allow-blocked-fields",
            "block_rule": "至少 2 条 >5pp 记录且该字段没有任何 <=5pp 的已评估记录",
        },
    }


def markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# 因子对齐失败登记表",
        "",
        f"规则版本：`{payload['alignment_rule_version']}`",
        f"硬失败标准：`{payload['acceptance_rule']['hard_failure']}`",
        f"来源：`{payload['source_result']}`",
        "",
        "## 摘要",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 平台记录 | {summary['selected_platform_records']} |",
        f"| 本地复现记录 | {summary['reproduced_records']} |",
        f"| 有效净超额 | {summary['valid_net_records']} |",
        f"| 净超额可接受（<=5pp） | {summary['acceptable_net_records']} |",
        f"| 净超额不可接受（>5pp） | {summary['unacceptable_net_records']} |",
        f"| 暂无法判断 | {summary['unassessable_records']} |",
        f"| 默认拉黑字段 | {', '.join(payload['blocked_fields']) or '无；当前证据不足以全局拉黑已验证字段'} |",
        "",
        "## 不可接受记录",
        "",
        "| 记录 | handler | 净超额差(pp) | 毛超额差(pp) | 原因 | 公式字段 | 字段归因 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for item in payload["unacceptable_records"]:
        attribution = item["attribution"]
        field_notes = "; ".join(
            f"{entry['field']}({entry['confidence']})"
            for entry in attribution["field_attribution"]
        ) or "n/a"
        formula = str(item.get("formula") or "")
        if len(formula) > 180:
            formula = formula[:177] + "..."
        lines.append(
            f"| {item.get('id')} | {item.get('handler')} | {item.get('local_net_delta_pp')} | "
            f"{item.get('local_gross_delta_pp')} | {', '.join(attribution['cause_codes'])} | "
            f"{', '.join(attribution['formula_fields'])} | {field_notes} |"
        )
        lines.append(f"|  |  |  |  | 说明 | `{formula}` | {' '.join(attribution['cause_details'])} |")
    lines.extend(
        [
            "",
            "## 字段风险",
            "",
            "决策只依据净超额 >5pp 的重复证据；字段出现在失败公式中不等于字段已经被证明错误。",
            "",
            "| 字段 | 公式数 | >5pp | <=5pp | 换手主导 | 平均绝对差(pp) | 最大绝对差(pp) | 决策 |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in payload["field_risks"]:
        mean_delta = item["mean_abs_net_delta_pp"]
        max_delta = item["max_abs_net_delta_pp"]
        lines.append(
            f"| `{item['field']}` | {item['formula_count']} | {item['unacceptable_net_count']} | "
            f"{item['acceptable_net_count']} | {item['turnover_dominant_count']} | "
            f"{'n/a' if mean_delta is None else f'{mean_delta:.2f}'} | "
            f"{'n/a' if max_delta is None else f'{max_delta:.2f}'} | {item['decision']} |"
        )
    lines.extend(
        [
            "",
            "## 使用规则",
            "",
            "- 默认 GP/GFN 不使用登记表中 `blocked` 字段。",
            "- `suspect` 字段只记录风险，不自动排除，避免把 HIGH、AMOUNT、VOLUME 等已通过单字段隔离的字段误拉黑。",
            "- 需要复查被拉黑字段时，显式使用 `--allow-blocked-fields`，结果仍标记为诊断模式。",
            "- 每次正式全量复现后重新运行 `python scripts/build_alignment_failure_registry.py`，再开始下一轮本地挖掘。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    registry = build_payload(payload, args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.output.with_suffix(".md").write_text(markdown(registry), encoding="utf-8")
    print(f"wrote={args.output.with_suffix('.json')}")
    print(f"wrote={args.output.with_suffix('.md')}")
    print(f"unacceptable={registry['summary']['unacceptable_net_records']}")
    print(f"blocked_fields={','.join(registry['blocked_fields']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
