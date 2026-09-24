"""Single source of truth for the saved PandaAI/local alignment audit.

This module contains only offline comparison settings.  It does not read
credentials, contact PandaAI, or start a backtest.  Change the rule version
when a validated alignment convention changes, then regenerate the reports.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


ALIGNMENT_RULE_VERSION = "full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate4"
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

# Platform turnover is available only as a summary statistic in the saved
# result.  These thresholds classify whether it is reasonable to compare that
# summary with the local member-overlap turnover.  They do not replace the
# local turnover used by the canonical result.
ALIGNMENT_PLATFORM_TURNOVER_HIGH_THRESHOLD = 0.85
ALIGNMENT_LOCAL_TURNOVER_LOW_THRESHOLD = 0.50
ALIGNMENT_TURNOVER_GAP_ALERT_THRESHOLD = 0.25
ALIGNMENT_PLATFORM_TURNOVER_OVER_100_THRESHOLD = 1.0
ALIGNMENT_TURNOVER_SENSITIVITY_METHOD = (
    "local gross excess minus annualized cost using saved platform turnover; "
    "diagnostic only"
)

# A local result is useful for mining only when the observed platform/local
# difference is small across the return path, not merely after an accidental
# cancellation in the cost calculation.  These are screening thresholds in
# percentage points, IC units, and Top20 membership counts.
ALIGNMENT_LARGE_NET_DELTA_PP = 5.0
ALIGNMENT_LARGE_GROSS_DELTA_PP = 5.0
ALIGNMENT_LARGE_RANK_IC_DELTA = 0.02

# Local net-excess agreement tier.  A record inside ALIGNMENT_NET_CLOSE_PP can
# be ranked on its own net excess; a record between the close and the blocking
# threshold stays in the candidate space but its absolute return level carries
# a known offset, so only relative ranking and structure are trustworthy.
ALIGNMENT_NET_CLOSE_PP = 2.0

ALIGNMENT_MIN_TOP20_OVERLAP = 15
ALIGNMENT_MIN_PERIOD_COVERAGE = 0.95
ALIGNMENT_TURNOVER_DOMINANT_MAX_SENSITIVITY_DELTA_PP = 2.0

# qualitygate2 replaces the single-period Top20 membership count as a hard
# gate with the per-period RankIC agreement between the local and saved
# platform chart series.  The Top20 count is dominated by the extreme tail of
# one rebalance date, where field-definition differences (share base for
# turnover, book-equity vintage) are largest, while the IC series uses every
# saved period.  Top20 remains recorded as a diagnostic flag.
ALIGNMENT_MIN_IC_SERIES_CORR = 0.50
ALIGNMENT_MAX_IC_SERIES_MEAN_ABS_DELTA = 0.06
# qualitygate4: a saved platform run carries two RankIC amplitudes that do not
# agree with each other -- the chart series and the series implied by
# ``Rank_IC / IC_IR``.  For QFQ-known-aligned records the local series matches
# the metric-implied amplitude (F-NET01 cycle5: local std 0.1933 vs implied
# 0.1897) while the saved chart series is ~30% flatter.  A raw mean-absolute
# difference therefore fails records whose per-period *shape* agrees.  The gate
# keeps the shape requirement (Pearson and Spearman correlation against the
# chart series) and compares the amplitude-normalised difference,
# ``mean|beta * local - platform|`` with ``beta`` the OLS slope of platform on
# local.  The raw difference is still recorded and flagged as
# ``ic_chart_scale_gap`` when the amplitude ratio exceeds
# ``ALIGNMENT_IC_CHART_SCALE_GAP_RATIO``.  Records saved without the new fields
# fall back to the raw qualitygate2/3 comparison.
ALIGNMENT_MAX_IC_SERIES_SCALED_DELTA = 0.06
ALIGNMENT_IC_CHART_SCALE_GAP_RATIO = 0.20
# Some saved platform runs carry only ten to sixteen chart periods (short
# windows or partial saves).  Requiring twenty threw those records back to the
# single-period Top20 gate; ten keeps the per-period evidence usable while the
# correlation and mean-absolute-difference thresholds still have to pass.
ALIGNMENT_MIN_IC_SERIES_PERIODS = 10

# Factor families the platform has stated it does not support.  These are not
# local reproduction gaps: the local proxies can never be validated against a
# platform definition that does not exist, so they are excluded from the
# candidate space and reported under their own status.
ALIGNMENT_PLATFORM_UNSUPPORTED_HANDLERS = frozenset(
    {
        "residual_volatility",
        "residual_volatility_max_interact",
        "beta_low",
        # ``profitability`` is a Barra descriptor (see references/fields-barra.md
        # alongside beta and residual_volatility), so the local income-statement
        # proxy can never be validated against a supported platform field.
        "profitability",
    }
)
ALIGNMENT_PLATFORM_UNSUPPORTED_NOTE = (
    "platform states Barra-style risk fields are unsupported; local proxy cannot be aligned"
)

# Field leaves that have appeared in a saved platform/local comparison whose
# path metrics passed qualitygate1.  This is a search boundary, not a claim
# that every combination of these leaves is platform-equivalent: generated
# formulas still need formula-level validation.  In particular, AMOUNT,
# VOLUME, and HIGH remain individually searchable even though one saved
# AMOUNT/VOLUME/HIGH composition was rejected by the alignment audit.
ALIGNMENT_VERIFIED_SEARCH_FIELDS = frozenset(
    {
        "amount",
        "close",
        "high",
        "low",
        "market_cap",
        "open",
        "turnover",
        "volume",
        "book_to_market_ratio_lf",
        "book_to_market_ratio_lyr",
        "current_assets",
        "current_liabilities",
        "inventory",
        "gr_total_asset_lyr",
        "oper_main_profit_ttm",
        "oper_roe_lyr",
        "ratio_bm_ttm",
        "ratio_ep_ttm",
        "ratio_pcf_ocf_ttm",
        "ratio_sp_ttm",
    }
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
    # The platform field is ``ratio_cfp_ttm`` (cash-flow yield).  Rebuilding OCF
    # TTM from quarterly cash-flow statements gave a weaker per-period IC match
    # (0.837 correlation / 0.063 mean absolute difference, above the 0.06 gate);
    # the vendor's CFPS over current price proxy matches materially better
    # (0.906 / 0.049) and keeps the same economic definition.
    "reversal_bm_cfp_tsrank756": "cfps_cur_price",
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
        "platform_turnover_high_threshold": ALIGNMENT_PLATFORM_TURNOVER_HIGH_THRESHOLD,
        "local_turnover_low_threshold": ALIGNMENT_LOCAL_TURNOVER_LOW_THRESHOLD,
        "turnover_gap_alert_threshold": ALIGNMENT_TURNOVER_GAP_ALERT_THRESHOLD,
        "platform_turnover_over_100_threshold": ALIGNMENT_PLATFORM_TURNOVER_OVER_100_THRESHOLD,
        "turnover_sensitivity_method": ALIGNMENT_TURNOVER_SENSITIVITY_METHOD,
        "large_net_delta_pp": ALIGNMENT_LARGE_NET_DELTA_PP,
        "net_close_pp": ALIGNMENT_NET_CLOSE_PP,
        "large_gross_delta_pp": ALIGNMENT_LARGE_GROSS_DELTA_PP,
        "large_rank_ic_delta": ALIGNMENT_LARGE_RANK_IC_DELTA,
        "min_top20_overlap": ALIGNMENT_MIN_TOP20_OVERLAP,
        "min_period_coverage": ALIGNMENT_MIN_PERIOD_COVERAGE,
        "min_ic_series_corr": ALIGNMENT_MIN_IC_SERIES_CORR,
        "max_ic_series_mean_abs_delta": ALIGNMENT_MAX_IC_SERIES_MEAN_ABS_DELTA,
        "max_ic_series_scaled_delta": ALIGNMENT_MAX_IC_SERIES_SCALED_DELTA,
        "ic_chart_scale_gap_ratio": ALIGNMENT_IC_CHART_SCALE_GAP_RATIO,
        "min_ic_series_periods": ALIGNMENT_MIN_IC_SERIES_PERIODS,
        "platform_unsupported_handlers": sorted(ALIGNMENT_PLATFORM_UNSUPPORTED_HANDLERS),
        "top20_role": "diagnostic_flag_only",
        "turnover_dominant_max_sensitivity_delta_pp": ALIGNMENT_TURNOVER_DOMINANT_MAX_SENSITIVITY_DELTA_PP,
        "verified_search_fields": sorted(ALIGNMENT_VERIFIED_SEARCH_FIELDS),
    }


def _turnover_fraction(value: Any) -> float | None:
    """Normalize a saved turnover value to a finite fraction."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            parsed = float(text[:-1]) / 100.0 if text.endswith("%") else float(text)
        except ValueError:
            return None
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
    return parsed if math.isfinite(parsed) and parsed >= 0.0 else None


def classify_turnover_alignment(
    platform_turnover: Any,
    local_turnover: Any,
) -> dict[str, Any]:
    """Classify whether saved platform and local turnover are comparable.

    PandaAI exposes only the aggregate turnover summary for these saved runs,
    while the local evaluator has the actual selected-group member sets.  A
    large difference is therefore a diagnostic signal, not evidence that one
    side's factor values are wrong.
    """
    platform = _turnover_fraction(platform_turnover)
    local = _turnover_fraction(local_turnover)
    if platform is None or local is None:
        missing = []
        if platform is None:
            missing.append("platform_turnover")
        if local is None:
            missing.append("local_turnover")
        return {
            "status": "unavailable",
            "comparable": False,
            "platform_turnover": platform,
            "local_turnover": local,
            "gap": None,
            "gap_pp": None,
            "absolute_gap_pp": None,
            "flags": ["missing:" + ",".join(missing)],
            "reason": "turnover value unavailable or invalid",
        }

    gap = platform - local
    absolute_gap = abs(gap)
    flags: list[str] = []
    if platform > ALIGNMENT_PLATFORM_TURNOVER_OVER_100_THRESHOLD:
        flags.append("platform_turnover_over_100")
    if (
        platform >= ALIGNMENT_PLATFORM_TURNOVER_HIGH_THRESHOLD
        and local <= ALIGNMENT_LOCAL_TURNOVER_LOW_THRESHOLD
    ):
        flags.append("platform_high_local_low")
    if absolute_gap >= ALIGNMENT_TURNOVER_GAP_ALERT_THRESHOLD:
        flags.append("large_turnover_gap")

    if "platform_turnover_over_100" in flags:
        status = "platform_turnover_over_100"
    elif "platform_high_local_low" in flags:
        status = "platform_high_local_low"
    elif "large_turnover_gap" in flags:
        status = "large_turnover_gap"
    else:
        status = "comparable"

    return {
        "status": status,
        "comparable": not flags,
        "platform_turnover": platform,
        "local_turnover": local,
        "gap": gap,
        "gap_pp": gap * 100.0,
        "absolute_gap_pp": absolute_gap * 100.0,
        "flags": flags,
        "reason": "; ".join(flags) if flags else "within turnover comparison thresholds",
    }


def annualized_turnover_cost(
    turnover: Any,
    cycle: Any,
    round_trip_cost: float = ALIGNMENT_ROUND_TRIP_COST,
) -> float | None:
    """Calculate annualized cost for a turnover fraction and rebalance cycle."""
    normalized_turnover = _turnover_fraction(turnover)
    try:
        normalized_cycle = float(cycle)
    except (TypeError, ValueError):
        return None
    if normalized_turnover is None or not math.isfinite(normalized_cycle) or normalized_cycle <= 0:
        return None
    return normalized_turnover * (252.0 / normalized_cycle) * float(round_trip_cost)


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def classify_alignment_quality(
    *,
    net_delta_pp: Any,
    gross_delta_pp: Any,
    platform_rank_ic: Any,
    local_rank_ic: Any,
    top20_overlap: Any,
    local_periods: Any,
    platform_periods: Any,
    turnover_status: str | None,
    sensitivity_delta_pp: Any,
    ic_series_corr: Any = None,
    ic_series_mean_abs_delta: Any = None,
    ic_series_periods: Any = None,
    ic_series_rank_corr: Any = None,
    ic_series_std_local: Any = None,
    ic_series_std_platform: Any = None,
    ic_series_beta: Any = None,
    ic_series_mean_abs_delta_scaled: Any = None,
    handler: str | None = None,
) -> dict[str, Any]:
    """Classify whether a local row is safe to use for platform-like mining.

    ``turnover_dominant`` is deliberately narrower than a generic small net
    difference: it requires the gross return path, IC, Top20 and period
    coverage to agree, with the remaining difference explained by the saved
    platform turnover summary.  A local row with a large field/path mismatch
    is never promoted by the cost sensitivity calculation.
    """
    net_delta = _finite_number(net_delta_pp)
    gross_delta = _finite_number(gross_delta_pp)
    platform_rank = _finite_number(platform_rank_ic)
    local_rank = _finite_number(local_rank_ic)
    overlap = _finite_number(top20_overlap)
    local_count = _finite_number(local_periods)
    platform_count = _finite_number(platform_periods)
    sensitivity_delta = _finite_number(sensitivity_delta_pp)
    series_corr = _finite_number(ic_series_corr)
    series_delta = _finite_number(ic_series_mean_abs_delta)
    series_periods = _finite_number(ic_series_periods)
    series_rank_corr = _finite_number(ic_series_rank_corr)
    series_std_local = _finite_number(ic_series_std_local)
    series_std_platform = _finite_number(ic_series_std_platform)
    series_beta = _finite_number(ic_series_beta)
    series_delta_scaled = _finite_number(ic_series_mean_abs_delta_scaled)

    flags: list[str] = []
    if net_delta is None:
        flags.append("missing_net_delta")
        net_tier = "net_unavailable"
    elif abs(net_delta) >= ALIGNMENT_LARGE_NET_DELTA_PP:
        flags.append("large_net_delta")
        net_tier = "net_blocked"
    elif abs(net_delta) <= ALIGNMENT_NET_CLOSE_PP:
        net_tier = "net_close"
    else:
        net_tier = "net_proxy"
        flags.append("net_proxy_offset")

    if gross_delta is None:
        flags.append("missing_gross_delta")
    elif abs(gross_delta) >= ALIGNMENT_LARGE_GROSS_DELTA_PP:
        flags.append("large_gross_delta")

    rank_delta = None
    if platform_rank is None or local_rank is None:
        flags.append("missing_rank_ic")
    else:
        rank_delta = local_rank - platform_rank
        if abs(rank_delta) >= ALIGNMENT_LARGE_RANK_IC_DELTA:
            flags.append("large_rank_ic_delta")

    if overlap is not None and overlap < ALIGNMENT_MIN_TOP20_OVERLAP:
        flags.append("low_top20_overlap")
    elif overlap is None:
        flags.append("missing_top20_overlap")

    # The per-period series needs enough saved chart points to be meaningful.
    # When the platform saved too few, fall back to the historical Top20
    # membership gate instead of failing a record that has no evidence either
    # way, so short-chart runs keep the qualitygate1 behaviour.
    ic_series_usable = (
        series_periods is not None and series_periods >= ALIGNMENT_MIN_IC_SERIES_PERIODS
    )
    if not ic_series_usable:
        flags.append("ic_series_unavailable_top20_fallback")
        if overlap is not None and overlap < ALIGNMENT_MIN_TOP20_OVERLAP:
            flags.append("low_top20_overlap_fallback")
        elif overlap is None:
            flags.append("missing_top20_overlap_fallback")
    else:
        if series_corr is None or series_corr < ALIGNMENT_MIN_IC_SERIES_CORR:
            flags.append("low_ic_series_corr")
        if (
            series_rank_corr is not None
            and series_rank_corr < ALIGNMENT_MIN_IC_SERIES_CORR
            and "low_ic_series_corr" not in flags
        ):
            flags.append("low_ic_series_corr")
        if series_delta_scaled is not None:
            # qualitygate4: compare amplitude-normalised series; the raw
            # difference stays visible as a diagnostic flag.
            if series_delta_scaled > ALIGNMENT_MAX_IC_SERIES_SCALED_DELTA:
                flags.append("large_ic_series_delta")
            elif (
                series_delta is not None
                and series_delta > ALIGNMENT_MAX_IC_SERIES_MEAN_ABS_DELTA
            ):
                flags.append("ic_chart_scale_gap")
        elif (
            series_delta is None
            or series_delta > ALIGNMENT_MAX_IC_SERIES_MEAN_ABS_DELTA
        ):
            flags.append("large_ic_series_delta")
        if (
            series_std_local is not None
            and series_std_platform is not None
            and series_std_platform > 0
            and abs(series_std_local / series_std_platform - 1.0)
            > ALIGNMENT_IC_CHART_SCALE_GAP_RATIO
            and "ic_chart_scale_gap" not in flags
        ):
            flags.append("ic_chart_scale_gap")

    period_coverage = None
    if local_count is None or platform_count is None or platform_count <= 0:
        flags.append("missing_period_coverage")
    else:
        period_coverage = local_count / platform_count
        if period_coverage < ALIGNMENT_MIN_PERIOD_COVERAGE:
            flags.append("low_period_coverage")

    turnover_not_comparable = turnover_status not in {None, "comparable"}
    if turnover_not_comparable:
        flags.append("turnover_not_comparable")

    large_net = net_delta is not None and abs(net_delta) >= ALIGNMENT_LARGE_NET_DELTA_PP
    path_flags = {
        "missing_gross_delta",
        "large_gross_delta",
        "missing_rank_ic",
        "large_rank_ic_delta",
        "low_ic_series_corr",
        "large_ic_series_delta",
        "low_top20_overlap_fallback",
        "missing_top20_overlap_fallback",
        "missing_period_coverage",
        "low_period_coverage",
    }
    diagnostic_flags = [
        flag
        for flag in flags
        if flag
        in {
            "low_top20_overlap",
            "missing_top20_overlap",
            "ic_series_unavailable_top20_fallback",
            "ic_chart_scale_gap",
        }
    ]
    field_or_path_flags = [flag for flag in flags if flag in path_flags]
    turnover_dominant = (
        large_net
        and turnover_not_comparable
        and not field_or_path_flags
        and sensitivity_delta is not None
        and abs(sensitivity_delta) <= ALIGNMENT_TURNOVER_DOMINANT_MAX_SENSITIVITY_DELTA_PP
    )

    if large_net and not turnover_dominant:
        flags.append("unexplained_net_delta")
        field_or_path_flags.append("unexplained_net_delta")

    if handler in ALIGNMENT_PLATFORM_UNSUPPORTED_HANDLERS:
        status = "platform_unsupported"
        reason = ALIGNMENT_PLATFORM_UNSUPPORTED_NOTE
        flags.append("platform_unsupported_family")
    elif net_delta is None:
        status = "unsupported"
        reason = "local net excess is unavailable"
    elif turnover_dominant:
        status = "turnover_dominant"
        reason = "large net difference remains after path metrics align; saved platform turnover explains it"
    elif field_or_path_flags:
        status = "field_or_path_mismatch"
        reason = "field/path diagnostics exceed alignment thresholds"
    else:
        status = "aligned"
        reason = (
            "net, gross, RankIC, per-period IC agreement and period coverage are within thresholds"
        )

    mining_eligible = status == "aligned" and not turnover_not_comparable
    return {
        "status": status,
        "mining_eligible": mining_eligible,
        "flags": flags,
        "diagnostic_flags": diagnostic_flags,
        "ic_series_corr": series_corr,
        "ic_series_mean_abs_delta": series_delta,
        "ic_series_periods": series_periods,
        "ic_series_rank_corr": series_rank_corr,
        "ic_series_std_local": series_std_local,
        "ic_series_std_platform": series_std_platform,
        "ic_series_beta": series_beta,
        "ic_series_mean_abs_delta_scaled": series_delta_scaled,
        "net_tier": net_tier,
        "reason": reason,
        "net_delta_pp": net_delta,
        "gross_delta_pp": gross_delta,
        "rank_ic_delta": rank_delta,
        "period_coverage": period_coverage,
        "turnover_status": turnover_status,
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
