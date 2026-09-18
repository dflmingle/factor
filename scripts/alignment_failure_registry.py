"""Field-level diagnostics for local/PandaAI alignment failures.

The registry is deliberately conservative.  A field appearing in a failed
formula is a suspect, not proof that the field is wrong.  A field is blocked
from default local search only after multiple unacceptable records use it and
none of its assessed records is within the net-excess tolerance.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import math
import re
from typing import Any, Iterable


UNACCEPTABLE_NET_DELTA_PP = 5.0
FIELD_BLOCK_MIN_UNACCEPTABLE_RECORDS = 2

MARKET_FIELDS = frozenset(
    {"amount", "close", "high", "low", "market_cap", "open", "turnover", "volume"}
)

_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*\b")
_FUNCTION_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]*)\s*\(")


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def extract_formula_components(formula: str | None) -> dict[str, list[str]]:
    """Extract leaf fields and callable operators without a full formula parser."""
    text = str(formula or "").upper()
    # Saved Python/report-backed workflows store a filename in ``formula``;
    # those names are identifiers for a handler, not PandaAI leaf fields.
    if text.endswith((".PY", ".REPORT")):
        return {"fields": [], "operators": []}
    function_names = set(_FUNCTION_PATTERN.findall(text))
    fields = sorted(
        {
            token.lower()
            for token in _TOKEN_PATTERN.findall(text)
            if token not in function_names
        }
    )
    return {
        "fields": fields,
        "operators": sorted(name.lower() for name in function_names),
    }


def is_unacceptable_net_delta(value: Any) -> bool:
    number = finite_number(value)
    return number is not None and abs(number) > UNACCEPTABLE_NET_DELTA_PP


def _field_role(field: str) -> str:
    if field in MARKET_FIELDS:
        return "market_data_leaf"
    if field.endswith(("_lyr", "_ttm")) or "_mrq_" in field:
        return "financial_period_leaf"
    if field.startswith(("cal_", "barra_")):
        return "platform_internal_or_intraday_leaf"
    return "declared_formula_leaf"


def _turnover_dominant(row: dict[str, Any], unacceptable: bool) -> bool:
    sensitivity = finite_number(row.get("platform_turnover_sensitivity_delta_pp"))
    status = str(row.get("turnover_alignment") or "")
    return bool(
        unacceptable
        and status != "comparable"
        and sensitivity is not None
        and abs(sensitivity) <= 2.0
    )


def classify_failure(row: dict[str, Any]) -> dict[str, Any]:
    """Return an auditable, non-causal attribution for one comparison row."""
    delta = finite_number(row.get("local_net_delta_pp"))
    gross_delta = finite_number(row.get("local_gross_delta_pp"))
    rank_delta = finite_number(row.get("rank_ic_delta"))
    top20 = finite_number(row.get("top20_overlap"))
    coverage = finite_number(row.get("period_coverage"))
    components = extract_formula_components(row.get("formula"))
    unacceptable = is_unacceptable_net_delta(delta)
    turnover_dominant = _turnover_dominant(row, unacceptable)
    flags = set(row.get("alignment_quality_flags") or [])
    causes: list[str] = []
    details: list[str] = []

    if delta is None:
        causes.append("net_excess_unavailable")
        details.append("没有有效的本地净超额，无法判断误差是否超过 5pp。")
    if turnover_dominant:
        causes.append("platform_turnover_summary_mismatch")
        details.append(
            "正式净超额差异在替换平台汇总换手成本后降至 2pp 以内；"
            "平台没有逐期持仓，不能把该差异归因到因子字段。"
        )
    if gross_delta is not None and abs(gross_delta) > 5.0:
        causes.append("gross_return_path_mismatch")
        details.append(
            f"毛超额差异为 {gross_delta:+.2f}pp，优先检查字段值、复权、停牌处理、标签和算子路径。"
        )
    if top20 is None:
        causes.append("top20_unavailable")
        details.append("没有可比较的 Top20，无法确认最新横截面排序。")
    elif top20 < 15:
        causes.append("factor_ranking_path_mismatch")
        details.append(f"Top20 仅重合 {int(top20)}/20，说明因子值或排序路径仍不一致。")
    if rank_delta is None:
        causes.append("rank_ic_unavailable")
    elif abs(rank_delta) >= 0.02:
        causes.append("rank_ic_path_mismatch")
        details.append(f"RankIC 差异为 {rank_delta:+.4f}，超过 0.02 门槛。")
    if coverage is None:
        causes.append("period_coverage_unavailable")
        details.append("没有有效期覆盖率。")
    elif coverage < 0.95:
        causes.append("period_coverage_mismatch")
        details.append(f"有效期覆盖率为 {coverage:.1%}，低于 95%。")
    if unacceptable and not turnover_dominant:
        causes.append("unexplained_net_excess_gap")
        details.append(
            f"净超额绝对差为 {abs(delta):.2f}pp，超过不可接受阈值 {UNACCEPTABLE_NET_DELTA_PP:.2f}pp。"
        )

    field_attribution: list[dict[str, Any]] = []
    for field in components["fields"]:
        if field in MARKET_FIELDS and "gross_return_path_mismatch" in causes:
            note = "该行情叶子出现在失败公式中，但现有结果不足以单独证明它是根因。"
            confidence = "low"
        elif field.endswith(("_lyr", "_ttm")) or "_mrq_" in field:
            note = "需要核对公告日 PIT、合并口径、TTM 还原和平台字段定义。"
            confidence = "medium"
        else:
            note = "仅根据公式出现位置登记为嫌疑字段，未完成单字段反事实验证。"
            confidence = "low"
        field_attribution.append(
            {
                "field": field,
                "role": _field_role(field),
                "confidence": confidence,
                "avoid_by_default": False,
                "reason": note,
            }
        )

    if "platform_turnover_summary_mismatch" in causes and "turnover" in components["fields"]:
        for item in field_attribution:
            if item["field"] == "turnover":
                item.update(
                    {
                        "confidence": "high",
                        "avoid_by_default": False,
                        "reason": (
                            "问题是平台汇总换手与本地成员交集换手的语义差异；"
                            "不能据此拉黑本地 TURNOVER 叶子。"
                        ),
                    }
                )

    return {
        "acceptable_by_net_excess": delta is not None and not unacceptable,
        "unacceptable_by_net_excess": unacceptable,
        "net_delta_pp": delta,
        "gross_delta_pp": gross_delta,
        "turnover_dominant": turnover_dominant,
        "cause_codes": list(dict.fromkeys(causes)),
        "cause_details": details,
        "formula_fields": components["fields"],
        "formula_operators": components["operators"],
        "field_attribution": field_attribution,
        "alignment_flags": sorted(flags),
    }


def aggregate_field_risks(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate field evidence and decide whether a field can be blocked."""
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "formula_count": 0,
            "assessed_net_count": 0,
            "acceptable_net_count": 0,
            "unacceptable_net_count": 0,
            "unassessable_count": 0,
            "turnover_dominant_count": 0,
            "alignment_mismatch_count": 0,
            "max_abs_net_delta_pp": None,
            "sum_abs_net_delta_pp": 0.0,
            "record_ids": [],
        }
    )
    for row in rows:
        detail = classify_failure(row)
        row_id = str(row.get("id") or "")
        fields = detail["formula_fields"]
        for field in fields:
            item = stats[field]
            item["formula_count"] += 1
            if row_id:
                item["record_ids"].append(row_id)
            delta = detail["net_delta_pp"]
            if detail["turnover_dominant"]:
                item["turnover_dominant_count"] += 1
                continue
            if delta is None:
                item["unassessable_count"] += 1
                continue
            absolute = abs(delta)
            item["assessed_net_count"] += 1
            item["sum_abs_net_delta_pp"] += absolute
            item["max_abs_net_delta_pp"] = max(
                absolute, item["max_abs_net_delta_pp"] or 0.0
            )
            if detail["unacceptable_by_net_excess"]:
                item["unacceptable_net_count"] += 1
            else:
                item["acceptable_net_count"] += 1
            if row.get("alignment_quality") not in {None, "aligned"}:
                item["alignment_mismatch_count"] += 1

    result: list[dict[str, Any]] = []
    for field, item in stats.items():
        assessed = item["assessed_net_count"]
        unacceptable = item["unacceptable_net_count"]
        acceptable = item["acceptable_net_count"]
        should_block = (
            unacceptable >= FIELD_BLOCK_MIN_UNACCEPTABLE_RECORDS
            and acceptable == 0
        )
        if should_block:
            decision = "blocked"
            decision_reason = (
                f"{unacceptable} 条超过 5pp，且没有一条已评估记录在 5pp 内"
            )
        elif unacceptable:
            decision = "suspect"
            decision_reason = (
                f"存在 {unacceptable} 条超过 5pp，但也有 {acceptable} 条在 5pp 内；"
                "不能单独归因并全局拉黑"
            )
        else:
            decision = "retain"
            decision_reason = "当前没有超过 5pp 的净超额记录"
        result.append(
            {
                "field": field,
                "role": _field_role(field),
                "formula_count": item["formula_count"],
                "assessed_net_count": assessed,
                "acceptable_net_count": acceptable,
                "unacceptable_net_count": unacceptable,
                "unassessable_count": item["unassessable_count"],
                "turnover_dominant_count": item["turnover_dominant_count"],
                "alignment_mismatch_count": item["alignment_mismatch_count"],
                "unacceptable_rate": (
                    unacceptable / assessed if assessed else None
                ),
                "mean_abs_net_delta_pp": (
                    item["sum_abs_net_delta_pp"] / assessed if assessed else None
                ),
                "max_abs_net_delta_pp": item["max_abs_net_delta_pp"],
                "decision": decision,
                "decision_reason": decision_reason,
                "record_ids": sorted(set(item["record_ids"])),
            }
        )
    return sorted(result, key=lambda item: (-item["unacceptable_net_count"], item["field"]))


def blocked_search_fields(registry: dict[str, Any]) -> set[str]:
    return {
        str(field).strip().lower()
        for field in registry.get("blocked_fields", [])
        if str(field).strip()
    }
