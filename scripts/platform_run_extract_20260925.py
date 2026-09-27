"""Extract platform metrics from either factor_run or factor_result payload shapes."""
from __future__ import annotations


def load_analysis(payload: dict) -> dict:
    analysis = payload.get("factor_analysis") or (payload.get("results") or {}).get("factor_analysis") or {}
    if isinstance(analysis, dict) and analysis.get("query_group_return_analysis"):
        return analysis
    nodes = (payload.get("results") or {}).get("nodes") or payload.get("nodes") or {}
    if isinstance(nodes, list):
        nodes = {str(i): node for i, node in enumerate(nodes)}
    from json import JSONDecodeError, loads
    for node in nodes.values():
        raw = node.get("result_json") if isinstance(node, dict) else None
        if not isinstance(raw, str):
            continue
        try:
            nested = loads(raw)
        except (TypeError, ValueError, JSONDecodeError):
            continue
        if isinstance(nested, dict) and nested.get("factor_data_analysis") and nested.get("group_return_analysis"):
            return {"query_factor_analysis_data": nested["factor_data_analysis"],
                    "query_group_return_analysis": nested["group_return_analysis"]}
    return analysis if isinstance(analysis, dict) else {}


def _percent(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def metrics(payload: dict, direction: str = "1", group_number: int = 10) -> dict:
    """Return platform long-side metrics; the side follows the direction flag."""
    analysis = load_analysis(payload)
    groups = {str(row["group"]): row for row in (analysis.get("query_group_return_analysis") or [])}
    if len(groups) < 2:
        raise ValueError(f"fewer than two group rows returned (status={payload.get('status')})")
    held = "分组10" if str(direction) == "1" else "分组1"
    row = groups.get(held, {})
    indicators = {item["indicator"]: item.get("factor1", item.get("factor_value"))
                  for item in analysis.get("query_factor_analysis_data", [])}
    out = {
        "long_excess": _percent(row.get("excessAnnualized")),
        "annualized_return": _percent(row.get("annualizedReturn")),
        "turnover": _percent(row.get("turnoverRate")),
        "max_drawdown": _percent(row.get("maxDrawdown")),
        "excess_max_drawdown": _percent(row.get("excessMaxDrawdown")),
        "monthly_win_rate": _percent(row.get("monthlyWinRate")),
        "ic_mean": indicators.get("IC_mean"),
        "rank_ic": indicators.get("Rank_IC"),
        "ic_ir": indicators.get("IC_IR"),
        "ic_p_value": indicators.get("p-value"),
        "monotonicity": indicators.get("单调性"),
    }
    spreads = {name: _percent(groups.get(name, {}).get("excessAnnualized"))
               for name in ("分组1", "分组10", "多空组合")}
    out["group_excess"] = spreads
    return out