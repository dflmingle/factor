"""Single source of truth for the saved PandaAI/local alignment audit.

This module contains only offline comparison settings.  It does not read
credentials, contact PandaAI, or start a backtest.  Change the rule version
when a validated alignment convention changes, then regenerate the reports.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


ALIGNMENT_RULE_VERSION = "full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1"
ALIGNMENT_RULES_DOCUMENT = "research_reports/platform_alignment/ALIGNMENT_RULES.md"

# The local panel starts before the five-year platform window so time-series
# factors have their required trading-day warm-up.
ALIGNMENT_DATA_START = "20180101"
ALIGNMENT_START = "20210907"
ALIGNMENT_END = "20260907"

ALIGNMENT_UNIVERSE = "full_a"
ALIGNMENT_UNIVERSE_LABEL = "沪深全A"
ALIGNMENT_PRICE_MODE = "qfq"
ALIGNMENT_MARKET_CAP_FIELD = "total_mv"
ALIGNMENT_GROUPS = 10

# The platform-equivalent label uses the next trading day's close as both the
# entry reference and the start of the forward holding interval.
ALIGNMENT_LABEL_OFFSET = 1

# The evaluator stores the round-trip cost.  Reports display the corresponding
# 0.30% one-way cost.
ALIGNMENT_ONE_WAY_COST = 0.003
ALIGNMENT_ROUND_TRIP_COST = ALIGNMENT_ONE_WAY_COST * 2.0

# Excess is measured against the same factor-valid cross-section used for the
# group calculation.  A full-A benchmark is a separate sensitivity only.
ALIGNMENT_BENCHMARK_MODE = "factor_valid"
ALIGNMENT_BENCHMARK_DESCRIPTION = (
    "mean forward return of rows with valid factor and return values"
)

# PandaAI's factor-correlation workflow is reproduced as a daily
# cross-sectional Spearman correlation followed by an arithmetic mean over
# valid dates.  Pooled stock-day correlation is retained only as a diagnostic.
ALIGNMENT_CORRELATION_METHOD = "daily_cross_sectional_spearman_mean"
ALIGNMENT_CORRELATION_DESCRIPTION = (
    "average of daily cross-sectional Spearman correlations using average ranks"
)

# Some saved platform factors deliberately produce large exact-value ties
# (binary cross signals and the saved Python OBV). The platform result does
# not expose its per-date tie order, but its turnover shows that ties are not
# kept in a stable symbol order. Use a deterministic per-date permutation as
# an explicit comparison proxy for only the verified handlers below.
ALIGNMENT_TIE_BREAK_SEED = 918273
ALIGNMENT_TIE_BREAK_HANDLERS = frozenset(
    {
        "rsi_cross30",
        "ma20_cross5",
        "python_obv",
    }
)
ALIGNMENT_TIE_BREAK_DESCRIPTION = (
    "deterministic per-date pseudo-random order within exact factor ties; "
    "comparison proxy for platform's unavailable tie order"
)

# The archived MAX(5) Python result reveals that the runtime's MultiIndex is
# ordered as [date, symbol] while DELAY still operates per instrument. Its
# explicit groupby(level=0) therefore rolls across symbols within each date.
# Keep this compatibility rule scoped to the saved Python handler.
ALIGNMENT_PYTHON_INDEX_HANDLERS = frozenset({"max5_low21"})
ALIGNMENT_PYTHON_INDEX_DESCRIPTION = (
    "reproduce the archived Python runtime's [date, symbol] level-0 rolling "
    "semantics for max5_low21"
)


# Formula-specific cash-flow proxies selected by the offline diagnosis under
# the evaluator above.  These are explicit proxies, not claims of byte-level
# equivalence to PandaAI's internal fields.
CFP_PROXY_BY_HANDLER = {
    "reversal_bm_cfp": "cfps_lyr_price",
    "reversal_bm_cfp_rev2": "ocfps_cur_price",
    "reversal_bm_cfp_rev3": "ocfps_cur_price",
    "reversal_bm_cfp_val2": "cfps_lyr_price",
    "reversal_bm_cfp_val3": "cfps_cur_price",
    "reversal_bm_cfp_sp": "cfps_lyr_price",
    "reversal_bm_cfp_pcf": "cfps_lyr_price",
    "reversal_bm_cfp_ma63": "cfps_cur_price",
    "reversal_bm_cfp_tsrank756": "ocf_ttm_mv",
}


def alignment_config_snapshot() -> dict[str, Any]:
    """Return the canonical settings that define a comparable local run.

    Rebalance cycle and factor direction are read from each saved platform
    result, so they are intentionally not part of this fixed configuration.
    """
    return {
        "universe": ALIGNMENT_UNIVERSE,
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": ALIGNMENT_DATA_START,
        "start": ALIGNMENT_START,
        "end": ALIGNMENT_END,
        "groups": ALIGNMENT_GROUPS,
        "label_offset": ALIGNMENT_LABEL_OFFSET,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
        "correlation_method": ALIGNMENT_CORRELATION_METHOD,
    }


def _date_key(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    return str(value).strip().replace("-", "").replace("/", "")


def validate_alignment_config(config: Mapping[str, Any]) -> None:
    """Reject a local run whose core settings differ from this rule version.

    The check is deliberately independent of pandas and the data cache so it
    can run on a new computer before expensive data loading starts.
    """
    expected = alignment_config_snapshot()
    date_fields = {"data_start", "start", "end"}
    errors: list[str] = []
    for key, expected_value in expected.items():
        actual_value = config.get(key)
        if key in date_fields:
            matches = _date_key(actual_value) == _date_key(expected_value)
        elif key in {"round_trip_cost", "one_way_cost"}:
            try:
                matches = math.isclose(
                    float(actual_value), float(expected_value), rel_tol=0.0, abs_tol=1e-12
                )
            except (TypeError, ValueError):
                matches = False
        else:
            matches = actual_value == expected_value
        if not matches:
            errors.append(f"{key}={actual_value!r} (required {expected_value!r})")
    if errors:
        raise ValueError(
            "Alignment configuration does not match rule "
            f"{ALIGNMENT_RULE_VERSION}: " + "; ".join(errors)
        )


def return_label(offset: int = ALIGNMENT_LABEL_OFFSET) -> str:
    """Return the human-readable close-to-close label for a rule version."""
    return f"close(t+{offset}) -> close(t+{offset}+cycle)"
