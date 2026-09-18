from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_VERIFIED_SEARCH_FIELDS,
    alignment_config_snapshot,
    annualized_turnover_cost,
    classify_alignment_quality,
    classify_turnover_alignment,
)
from search_field_policy import (  # noqa: E402
    load_field_exclusion_policy,
    resolve_named_search_fields,
    resolve_terminal_fields,
)
from alignment_failure_registry import (  # noqa: E402
    aggregate_field_risks,
    classify_failure,
    extract_formula_components,
)
from positive_factor_local_compare import handler_for, unsupported_reason  # noqa: E402
from diagnose_d02_d03_fields import report_table  # noqa: E402


class _FakeFieldStore:
    def __init__(self, fields: set[str]) -> None:
        self.fields = fields

    def active_search_fields(self, include_period_variants: bool = True) -> list[str]:
        return sorted(self.fields)

    def status(self, field: str) -> dict[str, str]:
        return {"field": field, "status": "local_direct", "note": ""}


class _FakePanel:
    def __init__(self, fields: set[str]) -> None:
        self.pandaai_field_store = _FakeFieldStore(fields)


def test_alignment_snapshot_freezes_verified_search_boundary() -> None:
    snapshot = alignment_config_snapshot()

    assert snapshot["verified_search_fields"] == sorted(ALIGNMENT_VERIFIED_SEARCH_FIELDS)
    assert "amount" in ALIGNMENT_VERIFIED_SEARCH_FIELDS
    assert "ratio_ep_ttm" in ALIGNMENT_VERIFIED_SEARCH_FIELDS
    assert ALIGNMENT_RULE_VERSION.endswith("qualitygate1")


def test_gp_verified_terminals_have_no_unverified_fallback() -> None:
    data = _FakePanel(set(ALIGNMENT_VERIFIED_SEARCH_FIELDS))

    terminals = resolve_terminal_fields(
        active_fields=data.pandaai_field_store.active_search_fields(),
        mode="verified",
        field_file=None,
        price_volume_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
        formula_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
        allow_unverified_fields=False,
    )

    assert set(terminals) == set(ALIGNMENT_VERIFIED_SEARCH_FIELDS)


def test_gp_broad_terminal_range_requires_explicit_diagnostic_flag() -> None:
    data = _FakePanel(set(ALIGNMENT_VERIFIED_SEARCH_FIELDS) | {"unverified_field"})

    with pytest.raises(ValueError, match="unverified fields"):
        resolve_terminal_fields(
            active_fields=data.pandaai_field_store.active_search_fields(),
            mode="all",
            field_file=None,
            price_volume_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
            formula_fields=data.pandaai_field_store.active_search_fields(),
            allow_unverified_fields=False,
        )

    terminals = resolve_terminal_fields(
        active_fields=data.pandaai_field_store.active_search_fields(),
        mode="all",
        field_file=None,
        price_volume_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
        formula_fields=data.pandaai_field_store.active_search_fields(),
        allow_unverified_fields=True,
    )
    assert "unverified_field" in terminals


def test_gp_empty_field_file_is_not_silently_replaced() -> None:
    data = _FakePanel(set(ALIGNMENT_VERIFIED_SEARCH_FIELDS))

    with pytest.raises(ValueError, match="does not contain any field names"):
        resolve_terminal_fields(
            active_fields=data.pandaai_field_store.active_search_fields(),
            mode="verified",
            field_file="",
            price_volume_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
            formula_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
            allow_unverified_fields=False,
        )


def test_gfn_verified_feature_set_preserves_named_market_fields() -> None:
    data = _FakePanel(set(ALIGNMENT_VERIFIED_SEARCH_FIELDS))

    result = resolve_named_search_fields(
        data,
        feature_set="verified",
        extra_fields=None,
        max_extra_fields=64,
        allow_unverified_fields=False,
        base_feature_names=(),
        fundamental_core_fields=(),
    )

    assert result["feature_set"] == "verified"
    assert "amount" in result["search_fields"]
    assert "market_cap" in result["search_fields"]
    assert "turnover" in result["search_fields"]
    assert result["unverified_fields"] == []


def test_gfn_custom_unverified_fields_require_diagnostic_flag() -> None:
    data = _FakePanel(set(ALIGNMENT_VERIFIED_SEARCH_FIELDS) | {"unverified_field"})

    with pytest.raises(ValueError, match="unverified fields"):
        resolve_named_search_fields(
            data,
            feature_set="verified",
            extra_fields="unverified_field",
            max_extra_fields=64,
            allow_unverified_fields=False,
            base_feature_names=(),
            fundamental_core_fields=(),
        )

    result = resolve_named_search_fields(
        data,
        feature_set="verified",
        extra_fields="unverified_field",
        max_extra_fields=64,
        allow_unverified_fields=True,
        base_feature_names=(),
        fundamental_core_fields=(),
    )
    assert result["search_fields"] == ["unverified_field"]
    assert result["unverified_fields"] == ["unverified_field"]


def test_failure_registry_extracts_leaf_fields_and_operators() -> None:
    result = extract_formula_components("RANK(CLOSE) + TS_MAX(MARKET_CAP,20)")

    assert result["fields"] == ["close", "market_cap"]
    assert result["operators"] == ["rank", "ts_max"]


def test_failure_registry_marks_turnover_summary_as_non_field_causal() -> None:
    result = classify_failure(
        {
            "formula": "-(TURNOVER * RETURNS(CLOSE,1))",
            "local_net_delta_pp": 26.6,
            "local_gross_delta_pp": 0.1,
            "platform_turnover_sensitivity_delta_pp": 0.7,
            "turnover_alignment": "platform_turnover_over_100",
            "rank_ic_delta": 0.001,
            "top20_overlap": 19,
            "period_coverage": 1.0,
            "alignment_quality_flags": ["large_net_delta"],
        }
    )

    assert result["turnover_dominant"] is True
    assert "platform_turnover_summary_mismatch" in result["cause_codes"]
    turnover = next(item for item in result["field_attribution"] if item["field"] == "turnover")
    assert turnover["confidence"] == "high"
    assert turnover["avoid_by_default"] is False


def test_failure_registry_blocks_only_repeated_unacceptable_field() -> None:
    rows = [
        {"id": "bad-1", "formula": "CLOSE", "local_net_delta_pp": 6.0, "alignment_quality": "field_or_path_mismatch"},
        {"id": "bad-2", "formula": "CLOSE", "local_net_delta_pp": -7.0, "alignment_quality": "field_or_path_mismatch"},
    ]

    risks = aggregate_field_risks(rows)

    close = next(item for item in risks if item["field"] == "close")
    assert close["decision"] == "blocked"
    assert close["unacceptable_net_count"] == 2


def test_search_policy_excludes_registry_blocked_fields(tmp_path: Path) -> None:
    registry = tmp_path / "failure.json"
    registry.write_text(
        '{"blocked_fields":["close"],"field_risks":[{"field":"close","decision":"blocked","decision_reason":"test"}]}',
        encoding="utf-8",
    )
    data = _FakePanel(set(ALIGNMENT_VERIFIED_SEARCH_FIELDS))

    terminals = resolve_terminal_fields(
        active_fields=data.pandaai_field_store.active_search_fields(),
        mode="verified",
        field_file=None,
        price_volume_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
        formula_fields=ALIGNMENT_VERIFIED_SEARCH_FIELDS,
        allow_unverified_fields=False,
        failure_registry=registry,
    )

    assert "close" not in terminals
    assert load_field_exclusion_policy(registry)["blocked_fields"] == ["close"]


def test_gfn_formulas_have_local_handlers() -> None:
    assert handler_for("AMOUNT / VOLUME / HIGH") is None
    assert handler_for(
        "BOOK_TO_MARKET_RATIO_LF / OPER_MAIN_PROFIT_TTM"
    ) == "book_to_market_lf_div_oper_main_profit_ttm"


def test_unverified_insurance_mrq_formula_is_not_broadly_mapped() -> None:
    formula = "(BOOK_TO_MARKET_RATIO_LYR*MA(INSURANCE_COMMISSION_EXPENSE_MRQ_9,10))"

    assert handler_for(formula) is None
    assert "verified MRQ field mapping" in unsupported_reason(formula)


def test_unverified_amount_volume_high_formula_is_not_promoted_to_qfq_proxy() -> None:
    formula = "AMOUNT / VOLUME / HIGH"

    assert handler_for(formula) is None
    assert "field semantics" in unsupported_reason(formula)


def test_field_store_report_sequence_drops_nulls_before_mrq_numbering() -> None:
    reports = pd.DataFrame(
        {
            "instrument": ["000001.SZ"] * 4,
            "ann_date": ["2020-01-15", "2020-01-15", "2020-04-15", "2020-07-15"],
            "end_date": ["2019-09-30", "2019-12-31", "2020-03-31", "2020-06-30"],
            "update_flag": [0, 0, 0, 0],
            "value": [10.0, np.nan, np.nan, 30.0],
        }
    )

    prepared = report_table(
        reports,
        "value",
        "field_store",
        "field_store_nonempty_reports",
    )

    assert prepared["value"].tolist() == [10.0, 30.0]
    assert prepared["report_seq"].tolist() == [0, 1]


def test_turnover_alignment_marks_close_values_comparable() -> None:
    result = classify_turnover_alignment(0.5206, 0.5111)

    assert result["status"] == "comparable"
    assert result["comparable"] is True
    assert np.isclose(result["gap_pp"], 0.95)
    assert result["flags"] == []


def test_turnover_alignment_flags_platform_high_local_low() -> None:
    result = classify_turnover_alignment("89.85%", 0.0338)

    assert result["status"] == "platform_high_local_low"
    assert result["comparable"] is False
    assert "platform_high_local_low" in result["flags"]
    assert result["gap_pp"] > 85.0


def test_turnover_alignment_flags_over_100_percent() -> None:
    result = classify_turnover_alignment(2.1673, 0.4550)

    assert result["status"] == "platform_turnover_over_100"
    assert "platform_turnover_over_100" in result["flags"]
    assert "large_turnover_gap" in result["flags"]


def test_turnover_cost_uses_fraction_and_rebalance_cycle() -> None:
    cost = annualized_turnover_cost(0.8985, 5)

    assert np.isclose(cost, 0.8985 * 252.0 / 5.0 * ALIGNMENT_ROUND_TRIP_COST)
    assert annualized_turnover_cost(None, 5) is None


def test_alignment_quality_accepts_small_consistent_difference() -> None:
    result = classify_alignment_quality(
        net_delta_pp=1.2,
        gross_delta_pp=-1.0,
        platform_rank_ic=0.10,
        local_rank_ic=0.095,
        top20_overlap=19,
        local_periods=120,
        platform_periods=120,
        turnover_status="comparable",
        sensitivity_delta_pp=1.2,
    )

    assert result["status"] == "aligned"
    assert result["mining_eligible"] is True
    assert result["flags"] == []


def test_alignment_quality_does_not_hide_field_mismatch_with_cost_sensitivity() -> None:
    result = classify_alignment_quality(
        net_delta_pp=18.2,
        gross_delta_pp=9.7,
        platform_rank_ic=-0.0045,
        local_rank_ic=0.0342,
        top20_overlap=0,
        local_periods=241,
        platform_periods=241,
        turnover_status="large_turnover_gap",
        sensitivity_delta_pp=9.7,
    )

    assert result["status"] == "field_or_path_mismatch"
    assert result["mining_eligible"] is False
    assert "large_gross_delta" in result["flags"]
    assert "low_top20_overlap" in result["flags"]


def test_alignment_quality_identifies_turnover_dominant_difference() -> None:
    result = classify_alignment_quality(
        net_delta_pp=26.6,
        gross_delta_pp=0.7,
        platform_rank_ic=0.0991,
        local_rank_ic=0.1004,
        top20_overlap=19,
        local_periods=120,
        platform_periods=120,
        turnover_status="platform_turnover_over_100",
        sensitivity_delta_pp=0.71,
    )

    assert result["status"] == "turnover_dominant"
    assert result["mining_eligible"] is False
