#!/usr/bin/env python3
"""Rebuild saved completed factors in the local catalog.

The catalog is taken from the saved ``*.report.csv`` and candidate files.  It
never calls the platform.  Factors that require financial or Barra fields not
present in the local snapshot use an explicit local proxy and are labeled in
the report; formulas with no handler remain listed as unsupported.
"""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_DESCRIPTION,
    ALIGNMENT_BENCHMARK_MODE,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_PYTHON_INDEX_HANDLERS,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_START,
    ALIGNMENT_TIE_BREAK_DESCRIPTION,
    ALIGNMENT_TIE_BREAK_HANDLERS,
    ALIGNMENT_TIE_BREAK_SEED,
    ALIGNMENT_UNIVERSE,
    alignment_config_snapshot,
    validate_alignment_config,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from financial_factor_local import (  # noqa: E402
    CFP_PROXY_BY_HANDLER,
    FINANCIAL_HANDLERS,
    MARKET_HANDLERS,
    build_market_factor,
    build_financial_factor,
    load_financial_cache,
)
from stfilter_local_recheck import (  # noqa: E402
    CACHE_ROOT,
    ensure_calendar,
    load_data as load_st_data,
    load_pool as load_st_pool,
)


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
END = pd.Timestamp(ALIGNMENT_END)
PLATFORM_START = pd.Timestamp(ALIGNMENT_START)
GROUPS = ALIGNMENT_GROUPS
ROUND_TRIP_COST = ALIGNMENT_ROUND_TRIP_COST
OUTPUT_ROOT = CACHE_ROOT / "reports" / "positive_factor_compare"
REGISTRY_PATH = PROJECT_ROOT / "pandaai-workflow-registry.json"


def normalize_formula(formula: str) -> str:
    return re.sub(r"\s+", "", formula).upper()


def cross_rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates, sort=False, observed=True).rank(method="average", pct=True)


def grouped_rolling(frame: pd.DataFrame, column: str, window: int, method: str) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)[column]
    values = getattr(grouped.rolling(window=window, min_periods=window), method)()
    return values.reset_index(level=0, drop=True).reindex(frame.index)


def rolling_stat(frame: pd.DataFrame, values: pd.Series, window: int, method: str) -> pd.Series:
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")
    return grouped_rolling(work, "_value", window, method)


def rolling_corr(
    frame: pd.DataFrame,
    left: pd.Series,
    right: pd.Series,
    window: int,
) -> pd.Series:
    work = frame[["instrument"]].copy()
    work["_left"] = pd.to_numeric(left, errors="coerce")
    work["_right"] = pd.to_numeric(right, errors="coerce")
    work["_product"] = work["_left"] * work["_right"]
    work["_left_sq"] = work["_left"] ** 2
    work["_right_sq"] = work["_right"] ** 2
    left_mean = grouped_rolling(work, "_left", window, "mean")
    right_mean = grouped_rolling(work, "_right", window, "mean")
    product_mean = grouped_rolling(work, "_product", window, "mean")
    left_sq_mean = grouped_rolling(work, "_left_sq", window, "mean")
    right_sq_mean = grouped_rolling(work, "_right_sq", window, "mean")
    covariance = product_mean - left_mean * right_mean
    left_variance = (left_sq_mean - left_mean**2).clip(lower=0.0)
    right_variance = (right_sq_mean - right_mean**2).clip(lower=0.0)
    return covariance / (left_variance * right_variance).pow(0.5).replace(0.0, np.nan)


def rolling_covariance(
    frame: pd.DataFrame,
    left: pd.Series,
    right: pd.Series,
    window: int,
) -> pd.Series:
    work = frame[["instrument"]].copy()
    work["_left"] = pd.to_numeric(left, errors="coerce")
    work["_right"] = pd.to_numeric(right, errors="coerce")
    work["_product"] = work["_left"] * work["_right"]
    return grouped_rolling(work, "_product", window, "mean") - (
        grouped_rolling(work, "_left", window, "mean")
        * grouped_rolling(work, "_right", window, "mean")
    )


def wilder_rsi(frame: pd.DataFrame, window: int) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)
    delta = frame["close_qfq"] - grouped["close_qfq"].shift(1)
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    gain_mean = gain.groupby(frame["instrument"], sort=False, observed=True).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean().reset_index(level=0, drop=True).reindex(frame.index)
    loss_mean = loss.groupby(frame["instrument"], sort=False, observed=True).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean().reset_index(level=0, drop=True).reindex(frame.index)
    denominator = gain_mean + loss_mean
    result = 100.0 * gain_mean.div(denominator)
    result = result.mask(loss_mean.eq(0.0) & gain_mean.gt(0.0), 100.0)
    result = result.mask(gain_mean.eq(0.0) & loss_mean.gt(0.0), 0.0)
    return result


def money_flow_index(frame: pd.DataFrame, window: int) -> pd.Series:
    """Build the standard daily MFI from the cached qfq OHLCV fields."""
    grouped = frame.groupby("instrument", sort=False, observed=True)
    typical_price = (
        frame["high_qfq"] + frame["low_qfq"] + frame["close_qfq"]
    ) / 3.0
    raw_flow = typical_price * pd.to_numeric(frame["volume"], errors="coerce")
    previous_typical = typical_price.groupby(
        frame["instrument"], sort=False, observed=True
    ).shift(1)
    positive_flow = raw_flow.where(typical_price.gt(previous_typical), 0.0)
    negative_flow = raw_flow.where(typical_price.lt(previous_typical), 0.0)
    work = frame[["instrument"]].copy()
    work["positive_flow"] = positive_flow
    work["negative_flow"] = negative_flow
    positive_sum = grouped_rolling(work, "positive_flow", window, "sum")
    negative_sum = grouped_rolling(work, "negative_flow", window, "sum")
    ratio = positive_sum.div(negative_sum.replace(0.0, np.nan))
    result = 100.0 - 100.0 / (1.0 + ratio)
    result = result.mask(negative_sum.eq(0.0) & positive_sum.gt(0.0), 100.0)
    result = result.mask(positive_sum.eq(0.0) & negative_sum.gt(0.0), 0.0)
    return result


def rolling_time_series_rank(
    frame: pd.DataFrame, values: pd.Series, window: int
) -> pd.Series:
    """Return each instrument's trailing percentile rank for a daily series."""
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")
    grouped = work.groupby("instrument", sort=False, observed=True)["_value"]
    ranked = grouped.rolling(window=window, min_periods=window).rank(pct=True)
    return ranked.reset_index(level=0, drop=True).reindex(frame.index)


def rolling_top_n_mean(
    frame: pd.DataFrame, values: pd.Series, window: int, n: int
) -> pd.Series:
    """Return a trailing top-n mean, retaining strict full-window semantics."""
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")

    def top_mean(window_values: np.ndarray) -> float:
        valid = window_values[~np.isnan(window_values)]
        if len(valid) < n:
            return np.nan
        return float(np.partition(valid, -n)[-n:].mean())

    grouped = work.groupby("instrument", sort=False, observed=True)["_value"]
    result = grouped.rolling(window=window, min_periods=window).apply(
        top_mean, raw=True
    )
    return result.reset_index(level=0, drop=True).reindex(frame.index)


def python_date_level_top_n_mean(
    frame: pd.DataFrame,
    values: pd.Series,
    dates: Iterable[pd.Timestamp],
    window: int,
    n: int,
) -> pd.Series:
    """Reproduce the archived Python runtime's date-level rolling semantics.

    The saved Python factor groups by MultiIndex level 0. Its runtime exposes
    rows as [date, symbol], while DELAY has already produced per-symbol
    returns. The rolling top-n operation therefore runs across symbol order
    within each date rather than down each symbol's time series.
    """
    wanted = {pd.Timestamp(value).normalize() for value in dates}
    work = frame[["date", "instrument"]].copy()
    work["_row_id"] = np.arange(len(work), dtype=np.int64)
    work["_value"] = pd.to_numeric(values, errors="coerce").to_numpy()
    work = work[work["date"].isin(wanted)].sort_values(
        ["date", "instrument"], kind="stable"
    )

    def top_mean(window_values: np.ndarray) -> float:
        valid = window_values[~np.isnan(window_values)]
        if len(valid) < n:
            return np.nan
        return float(np.partition(valid, -n)[-n:].mean())

    result = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, group in work.groupby("date", sort=False, observed=True):
        rolling = (
            group["_value"]
            .reset_index(drop=True)
            .rolling(window=window, min_periods=window)
            .apply(top_mean, raw=True)
        )
        row_ids = group["_row_id"].to_numpy(dtype=np.int64)
        result.iloc[row_ids] = rolling.to_numpy()
    return result


def rolling_weighted_mean(
    frame: pd.DataFrame, values: pd.Series, window: int
) -> pd.Series:
    """Return a linearly weighted moving average with the newest row largest."""
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")
    weights = np.arange(1.0, window + 1.0)

    def weighted_mean(window_values: np.ndarray) -> float:
        if np.isnan(window_values).any():
            return np.nan
        return float(np.dot(window_values, weights) / weights.sum())

    grouped = work.groupby("instrument", sort=False, observed=True)["_value"]
    result = grouped.rolling(window=window, min_periods=window).apply(
        weighted_mean, raw=True
    )
    return result.reset_index(level=0, drop=True).reindex(frame.index)


def rolling_mean_absolute_deviation(
    frame: pd.DataFrame, values: pd.Series, window: int
) -> pd.Series:
    """Return the rolling mean absolute deviation used by PandaAI TS_MAD."""
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")

    def mean_absolute_deviation(window_values: np.ndarray) -> float:
        if np.isnan(window_values).any():
            return np.nan
        return float(np.abs(window_values - window_values.mean()).mean())

    grouped = work.groupby("instrument", sort=False, observed=True)["_value"]
    result = grouped.rolling(window=window, min_periods=window).apply(
        mean_absolute_deviation, raw=True
    )
    return result.reset_index(level=0, drop=True).reindex(frame.index)


def rolling_beta(frame: pd.DataFrame, returns: pd.Series, window: int = 252) -> pd.Series:
    """Estimate beta against the equal-weight full-A daily return proxy."""
    market_return = returns.groupby(frame["date"], sort=False, observed=True).transform(
        "mean"
    )
    covariance = rolling_covariance(frame, returns, market_return, window)
    variance = rolling_stat(frame, market_return, window, "var")
    return covariance.div(variance.replace(0.0, np.nan))


def grouped_ewm(frame: pd.DataFrame, values: pd.Series, alpha: float, min_periods: int) -> pd.Series:
    work = frame[["instrument"]].copy()
    work["_value"] = pd.to_numeric(values, errors="coerce")
    result = work.groupby("instrument", sort=False, observed=True)["_value"].ewm(
        alpha=alpha, adjust=False, min_periods=min_periods
    ).mean()
    return result.reset_index(level=0, drop=True).reindex(frame.index)


def grouped_finite_exp_weighted_sum(
    frame: pd.DataFrame,
    values: pd.Series,
    window: int,
    tau: float,
) -> pd.Series:
    """Match a finite, explicitly expanded exponential-weighted sum.

    The platform formulas use weights ``exp(-k / tau)`` for exactly ``window``
    observations. A recursive infinite-history EWM is not equivalent. The
    finite sum is recovered from the recursive state by removing the state
    from ``window`` rows ago; the common EWM scale cancels in the ratio.
    """
    work = frame[["instrument"]].copy()
    raw = pd.to_numeric(values, errors="coerce")
    work["_value"] = raw.fillna(0.0)
    decay = float(np.exp(-1.0 / tau))
    state = work.groupby("instrument", sort=False, observed=True)["_value"].ewm(
        alpha=1.0 - decay,
        adjust=False,
        min_periods=0,
    ).mean()
    state = state.reset_index(level=0, drop=True).reindex(frame.index)
    position = work.groupby("instrument", sort=False, observed=True).cumcount()
    initial = work.groupby("instrument", sort=False, observed=True)["_value"].transform("first")
    # Pandas initializes adjust=False at the first observation rather than at
    # alpha * first_observation. Remove that one-time transient before using
    # the recurrence as an unnormalised weighted sum.
    transient = initial.mul(decay ** (position + 1))
    state = state.sub(transient).div(1.0 - decay)
    lagged = state.groupby(frame["instrument"], sort=False, observed=True).shift(window)
    finite_sum = state.sub(lagged.fillna(0.0).mul(decay**window))

    validity = frame[["instrument"]].copy()
    validity["_valid"] = raw.notna().astype(float)
    valid_count = grouped_rolling(validity, "_valid", window, "sum")
    return finite_sum.where(valid_count.eq(float(window)))


def formula_catalog() -> dict[str, set[str]]:
    catalog: dict[str, set[str]] = {}
    for path in PROJECT_ROOT.glob("*.txt"):
        for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or " ~ " not in line:
                continue
            parts = line.split(" ~ ")
            if len(parts) < 3:
                continue
            catalog.setdefault(parts[0].strip(), set()).add(parts[1].strip())
    return catalog


def platform_configs() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for workflow in registry.get("workflows", []):
        factor_id = workflow.get("_id")
        if not factor_id:
            continue
        info = workflow.get("factor_info") or {}
        result[str(factor_id)] = {
            "factor_id": factor_id,
            "workflow_name": workflow.get("name"),
            "run_id": workflow.get("last_run_id"),
            "market": info.get("market"),
            "stock_pool": info.get("stock_pool"),
            "start_date": info.get("start_date"),
            "end_date": info.get("end_date"),
            "adjustment_cycle": info.get("adjustment_cycle"),
            "group_number": info.get("group_number"),
            "factor_direction": info.get("factor_direction"),
        }
    return result


def report_cycle(report_name: str) -> int | None:
    report_path = PROJECT_ROOT / report_name.replace(".csv", ".md")
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8-sig", errors="ignore")
    match = re.search(r"Settings:\s*(\d+)-day rebalance", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def handler_for(formula: str) -> str | None:
    normalized = normalize_formula(formula)
    exact = {
        "RETURNS(CLOSE,120)": "momentum120",
        "MA(TURNOVER,21)/MA(TURNOVER,504)-1": "turn_bias",
        "1-MA(TURNOVER,21)/MA(TURNOVER,504)": "turn_signal",
        "RANK(1-RETURNS(CLOSE,40))": "reversal40",
        "RANK(1-CLOSE/TS_MAX(CLOSE,120))": "drawdown120",
        "RANK(1-CLOSE/TS_MAX(CLOSE,60))": "drawdown60",
        "RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)": "chip250",
        "(RANK(-SUM(TURNOVER*RETURNS(CLOSE,1),21)/SUM(TURNOVER,21))+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/2": "weighted_reversal_lowturn",
        "(RANK(1-RETURNS(CLOSE,40))+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/2": "reversal_turn_eq",
        "(RANK(1-RETURNS(CLOSE,40))+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1))/2": "reversal_chip_eq",
        "(RANK(1-RETURNS(CLOSE,40))+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/3": "reversal_chip_turn_eq",
        "(RANK(1-RETURNS(CLOSE,40))+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504))+RANK(-ZSCORE(RANK(MARKET_CAP))))/4": "reversal_chip_turn_size_eq",
    }
    if normalized in exact:
        return exact[normalized]

    simple_technical = {
        "1-RETURNS(CLOSE,5)": "reversal5",
        "RANK(1-RETURNS(CLOSE,5))": "reversal5",
        "1-RETURNS(CLOSE,10)": "reversal10",
        "RANK(1-RETURNS(CLOSE,10))": "reversal10",
        "1-RETURNS(CLOSE,20)": "reversal20",
        "RANK(1-RETURNS(CLOSE,20))": "reversal20",
        "0-CLOSE/MA(CLOSE,40)": "ma_reversion40",
        "RANK((CLOSE/DELAY(CLOSE,20))-1)": "momentum20",
        "RANK((OPEN/DELAY(CLOSE,20))-1)": "momentum20_open",
        "RANK(1-CLOSE/TS_MAX(CLOSE,20))": "drawdown20",
        "RANK(1-CLOSE/MA(CLOSE,20))": "ma_drawdown20",
        "RANK(1-RSI(CLOSE,14)/100)": "rsi14",
        "RANK(-TS_MAX(RETURNS(CLOSE,1),21))": "max_return21_low",
        "RANK(-TS_SKEW(RETURNS(CLOSE,1),60))": "skew60_low",
        "RANK(-SUM(TURNOVER*RETURNS(CLOSE,1),21)/SUM(TURNOVER,21))": "weighted_reversal",
        "-SUM(TURNOVER*RETURNS(CLOSE,1),21)/SUM(TURNOVER,21)": "weighted_reversal",
        "STDDEV(TURNOVER,21)": "turnover_std21",
        "STDDEV(RETURNS(CLOSE,1),21)": "volatility21",
        "RANK(1-TS_ZSCORE(CLOSE,20))": "zscore20_low",
        "RANK(-ABS(MIN(BIAS(CLOSE,20),0)+5))": "moderate_bias5",
        "RANK(-ABS((1-CLOSE/TS_MAX(CLOSE,60))-0.10))": "moderate_drawdown60",
        "RANK(IF(RSI(CLOSE,14)<50,-ABS(RSI(CLOSE,14)-35),-99999))": "rsi35",
        "RANK(1-RSI(CLOSE,14)/100)*AS_FLOAT(CROSS(RSI(CLOSE,14),30))": "rsi_cross30",
        "RANK(MA(1-RSI(CLOSE,28)/100,10))": "smooth_rsi28",
        "RANK((1-RETURNS(CLOSE,5))/(STDDEV(RETURNS(CLOSE,1),20)+0.0001))": "scaled_reversal5",
        "RANK(1-RETURNS(CLOSE,5))+RANK(MA(TURNOVER,5)/MA(TURNOVER,20))": "capitulation20",
        "(RANK(1-RETURNS(CLOSE,5))+RANK(1-CLOSE/TS_MAX(CLOSE,20)))/2": "reversal5_drawdown20",
        "(RANK(1-RETURNS(CLOSE,5))+RANK(1-RSI(CLOSE,14)/100)/2": "reversal5_rsi14",
        "(RANK(1-RETURNS(CLOSE,5))+RANK(1-RSI(CLOSE,14)/100))/2": "reversal5_rsi14",
        "(RANK(1-CLOSE/TS_MAX(CLOSE,60))+RANK(RETURNS(CLOSE,5)))/2": "drawdown60_recovery5",
        "(RANK(1-CLOSE/MA(CLOSE,20))+RANK(CLOSE/MA(CLOSE,5)-1))/2": "ma20_recovery5",
        "(RANK(1-RETURNS(CLOSE,20))+RANK(RETURNS(CLOSE,5)))/2": "reversal20_recovery5",
        "RANK(1-CLOSE/MA(CLOSE,20))*AS_FLOAT(CROSS(CLOSE,MA(CLOSE,5)))": "ma20_cross5",
    }
    if normalized in simple_technical:
        return simple_technical[normalized]

    if (
        "RANK(IF(RSI(CLOSE,14)<50,-ABS(RSI(CLOSE,14)-35),-99999))" in normalized
        and "RANK(RETURNS(CLOSE,3))" in normalized
    ):
        return "rsi35_recovery3"
    if (
        "RANK(IF(RSI(CLOSE,14)<50,-ABS(RSI(CLOSE,14)-35),-99999))" in normalized
        and "RANK(RETURNS(CLOSE,5))" in normalized
    ):
        return "rsi35_recovery5"
    if normalized == "RANK(1-MFI(CLOSE,HIGH,LOW,VOLUME,14)/100)":
        return "mfi14"
    if normalized == "RANK(-BETA)":
        return "beta_low"
    if normalized == "WMA((((1/LOW)/LOW)/VOLUME),40)":
        return "wma_low_volume40"
    if normalized == "WMA(((-5)*TS_MAD(AMOUNT,10)),50)":
        return "wma_amount_mad10_50"
    if normalized == "RANK(SUM(IF(TS_RANK(ABS(RETURNS(CLOSE,1)),252)<=0.80,RETURNS(CLOSE,1),0),252)-SUM(IF(TS_RANK(ABS(RETURNS(CLOSE,1)),252)<=0.80,RETURNS(CLOSE,1),0),21))":
        return "ltmom_exhigh252_21"
    if normalized.endswith("LITERATURE-RANKIC-OPTIMIZATION-20260909-MAX5.PY"):
        return "max5_low21"
    if normalized.endswith("WORKFLOW-6AA40282-PYTHON.PY"):
        return "python_obv"

    if normalized == "((MA(AMOUNT/VOLUME,10)/CLOSE)-1)*(VOLUME/MA(VOLUME,20))*(BIAS(CLOSE,20)/100)":
        return "vwap10_volume20_momentum20"
    if normalized == "-1*CORR(RANK(OPEN),RANK(VOLUME),10)":
        return "alpha3"
    if normalized == "-1*RANK(COV(RANK(CLOSE),RANK(VOLUME),5))":
        return "alpha13"
    if normalized == "-1*SUM(RANK(CORR(RANK(HIGH),RANK(VOLUME),3)),3)":
        return "alpha15"
    if normalized == "-1*RANK(COV(RANK(HIGH),RANK(VOLUME),5))":
        return "alpha16"
    if normalized == "-1*RANK(STDDEV(HIGH,10))*CORR(HIGH,VOLUME,10)":
        return "alpha40"
    if normalized == "-1*CORR(HIGH,RANK(VOLUME),5)":
        return "alpha44"
    if normalized == "-1*TS_MAX(RANK(CORR(RANK(VOLUME),RANK((HIGH+LOW+CLOSE)/3),5)),5)":
        return "alpha50"
    if normalized == "-1*CORR(RANK((CLOSE-TS_MIN(LOW,12))/(TS_MAX(HIGH,12)-TS_MIN(LOW,12))),RANK(VOLUME),6)":
        return "alpha55"
    if normalized == "RANK(-RESIDUAL_VOLATILITY)*RANK(-TS_MAX(RETURNS(CLOSE,1),21))":
        return "residual_volatility_max_interact"

    if "RANK(1-RETURNS(CLOSE,20))+RANK(GR_NET_PROFIT_TTM)" in normalized:
        return "reversal20_growth_net"
    if all(
        token in normalized
        for token in (
            "RANK(GR_REVENUE_TTM)",
            "RANK(GR_OPER_PROFIT_TTM)",
            "RANK(GR_NET_PROFIT_TTM)",
            "RANK(GR_OCF_TTM)",
        )
    ):
        return "growth_broad_reversal20"
    if "RANK(GR_OPER_PROFIT_TTM)" in normalized and "RANK(GR_OCF_TTM)" in normalized:
        return "growth_operating_cashflow_reversal20"
    if normalized == "RANK(GR_REVENUE_TTM)":
        return "growth_revenue"
    if normalized == "RANK(GR_ROE_TTM)":
        return "growth_roe"
    if normalized == "GR_NET_PROFIT_TTM":
        return "growth_net_profit"
    if normalized == "GR_OCF_TTM":
        return "growth_ocf"
    if normalized == "OPER_ROE_TTM":
        return "quality_roe"
    if normalized == "CFD_OCF_TO_DEBT_TTM":
        return "quality_cash_debt"
    if normalized == "RATIO_EP_TTM":
        return "value_ep"
    if normalized == "RATIO_PCF_OCF_TTM":
        return "value_pcf"
    if normalized == "RANK(RATIO_EP_TTM)":
        return "value_ep"
    if normalized == "RANK(RATIO_PCF_OCF_TTM)":
        return "value_pcf"
    if normalized == "TS_RANK(RATIO_EP_TTM,126)":
        return "value_ep_tsrank126"
    if normalized == "TS_RANK(OPER_ROA_NET_TTM,756)":
        return "quality_roa_tsrank756"
    if normalized == "TS_RANK(OPER_ROE_TTM,756)":
        return "quality_roe_tsrank756"
    if normalized == "TS_RANK(OPER_GROSS_MARGIN_TTM,756)":
        return "quality_gross_margin_tsrank756"
    if normalized == "TS_RANK(OPER_OPER_PROFIT_TO_TP_TTM,756)":
        return "quality_oper_profit_tsrank756"
    if normalized == "TS_RANK(OPER_NET_MARGIN_TTM,378)":
        return "quality_net_margin_tsrank378"
    if normalized == "TS_RANK(OPER_TOTAL_ASSET_TURNOVER_TTM,378)":
        return "quality_asset_turnover_tsrank378"
    if normalized == "RANK(OPER_ROIC_TTM)":
        return "quality_roic"
    if normalized == "RANK(CFD_SURPLUS_CASH_MULTI_TTM)":
        return "cash_conversion"
    if normalized == "RANK(OPER_ROE_LYR)":
        return "quality_roe_lyr"
    if normalized == "RANK(PROFITABILITY)":
        return "profitability"

    if (
        "RANK(1-RETURNS(CLOSE,40))" in normalized
        and "RANK(RATIO_BM_TTM)" in normalized
        and "RANK(RATIO_EP_TTM)" in normalized
        and "RANK(RATIO_CFP_TTM)" in normalized
    ):
        return "reversal_bm_ep_cfp"
    if (
        "RANK(1-RETURNS(CLOSE,40))" in normalized
        and "RANK(RATIO_BM_TTM)" in normalized
        and "RANK(RATIO_EP_TTM)" in normalized
        and "RANK(OPER_ROE_TTM)" in normalized
    ):
        return "reversal_bm_ep_roe"
    if (
        "RANK(1-RETURNS(CLOSE,40))" in normalized
        and "RANK(RATIO_BM_TTM)" in normalized
        and "RANK(RATIO_EP_TTM)" in normalized
    ):
        return "reversal_bm_ep"
    if (
        "RANK(RATIO_BM_TTM)" in normalized
        and "RANK(RATIO_EP_TTM)" in normalized
        and "RANK(RATIO_SP_TTM)" in normalized
        and "RANK(RATIO_PCF_OCF_TTM)" in normalized
    ):
        return "value_eq"
    if (
        "RANK(1-RETURNS(CLOSE,40))" in normalized
        and "RANK(RATIO_EP_TTM)" in normalized
        and "RANK(RATIO_BM_TTM)" not in normalized
    ):
        return "reversal_ep_eq"
    if (
        "RANK(1-RETURNS(CLOSE,40))" in normalized
        and "RANK(RATIO_BM_TTM)" in normalized
        and "RANK(OPER_ROE_TTM)" in normalized
        and "RANK(RATIO_EP_TTM)" not in normalized
        and "RANK(RATIO_CFP_TTM)" not in normalized
    ):
        return "reversal_bm_roe_eq"
    if (
        "RANK(RATIO_BM_TTM)" in normalized
        and "RANK(GR_NET_PROFIT_TTM)" in normalized
        and "RANK(OPER_ROE_TTM)" in normalized
        and "RANK(1-RETURNS(CLOSE,20))" in normalized
    ):
        return "style_eq"

    if "EMA(TURNOVER*RETURNS(CLOSE,1),63)" in normalized:
        return "ema_weighted_reversal63"
    if "DELAY(TURNOVER*RETURNS(CLOSE,1)" in normalized:
        if "0.959189457109" in normalized:
            return "exp_weighted_reversal126"
        if "0.920044414629" in normalized:
            return "exp_weighted_reversal63"

    impact_h03 = "RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))"
    impact_abs_return = "RANK(SUM(ABS(CLOSE/DELAY(CLOSE,1)-1)/(AMOUNT+1),60)/60)"
    impact_downside = "RANK(SUM((ABS(CLOSE/DELAY(CLOSE,1)-1)-(CLOSE/DELAY(CLOSE,1)-1))/2,60)/(SUM(AMOUNT,60)+1))"
    impact_aggregate = "RANK(SUM(ABS(CLOSE/DELAY(CLOSE,1)-1),60)/(SUM(AMOUNT,60)+1))"

    if normalized == impact_h03:
        return "impact60"
    if normalized == impact_abs_return:
        return "impact_abs_return60"
    if normalized == impact_downside:
        return "impact_downside60"
    if normalized == impact_aggregate:
        return "impact_aggregate60"
    if normalized == "RANK(MARKET_CAP)":
        return "size_only"
    if normalized == "RANK(-RATIO_EV_EBITDA_TTM)":
        return "ev_ebitda_proxy"
    if normalized == "RANK(BOOK_TO_MARKET_RATIO_LF)-RANK(MARKET_CAP)":
        return "book_to_market_lf_minus_size"
    if normalized == f"RANK(BOOK_TO_MARKET_RATIO_LF)+{impact_abs_return}":
        return "book_to_market_lf_plus_impact"

    has_t10_base = all(
        token in normalized
        for token in (
            "RANK(1-RETURNS(CLOSE,40))",
            "RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)",
            "RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504))",
        )
    )
    has_size_component = "RANK(-ZSCORE(RANK(MARKET_CAP)))" in normalized
    has_working_capital = "RANK((CURRENT_ASSETS-INVENTORY-CURRENT_LIABILITIES)/(ABS(MARKET_CAP)+1))" in normalized
    has_fscore_component = "OPER_ROA_NET_TTM" in normalized or "CFD_OCF_TO_DEBT_TTM" in normalized
    if has_t10_base and impact_h03 in normalized and has_fscore_component:
        return "t10_size_plus_impact_fscore"
    if has_t10_base and impact_h03 in normalized and not has_fscore_component:
        if has_working_capital:
            return "t10_size_plus_impact_wc"
        if "RANK(BOOK_TO_MARKET_RATIO_LF)" in normalized:
            return "t10_size_plus_impact_bm"
        if impact_abs_return in normalized:
            return "t10_size_plus_impact_g13"
        if "RANK(1-CLOSE/TS_MAX(CLOSE,120))" in normalized:
            return "t10_size_plus_impact_dd120"
        if impact_downside in normalized:
            return "t10_size_plus_impact_downside"
        if impact_aggregate in normalized:
            return "t10_size_plus_impact_aggregate"
        if has_size_component:
            return "t10_size_plus_impact"
        return "t10_nomcap_plus_impact"
    if has_t10_base and has_working_capital:
        return "t10_size_plus_wc_mcap"

    if normalized == "RATIO_BM_TTM":
        return "value_bm"
    if normalized == "RATIO_SP_TTM":
        return "value_sp"
    if normalized == "RANK(GR_TOTAL_ASSET_LYR)":
        return "asset_growth"
    if "RESIDUAL_VOLATILITY" in normalized:
        return "residual_volatility"
    if "BOOK_TO_MARKET_RATIO_LYR" in normalized:
        if "RANK(1-RETURNS(CLOSE,40))" not in normalized:
            return (
                "paper_composite"
                if "MARKET_CAP" in normalized
                else "paper_composite_nomcap"
            )
        if "RANK((SUM(VOLUME" in normalized:
            return "reversal_chip_turn_paper"
        if "MARKET_CAP" in normalized:
            return "reversal_turn_paper"
        return "reversal_turn_paper_nomcap"
    if "OPER_ROA_NET_TTM" in normalized:
        return "fscore_interact" if ")*RANK((IF(" in normalized else "fscore_eq"
    if "RANK(RATIO_BM_TTM)" in normalized:
        if "RATIO_PCF_OCF_TTM" in normalized:
            return "reversal_bm_cfp_pcf"
        if "RATIO_EP_TTM" in normalized:
            return "reversal_bm_ep_cfp"
        if "RATIO_SP_TTM" in normalized:
            return "reversal_bm_cfp_sp"
        if "RATIO_CFP_TTM" in normalized and "3*RANK(1-RETURNS(CLOSE,40))" in normalized:
            return "reversal_bm_cfp_rev3"
        if "RATIO_CFP_TTM" in normalized and "2*RANK(1-RETURNS(CLOSE,40))" in normalized:
            return "reversal_bm_cfp_rev2"
        if "RATIO_CFP_TTM" in normalized and "3*RANK(RATIO_BM_TTM)" in normalized:
            return "reversal_bm_cfp_val3"
        if "2*RANK(RATIO_BM_TTM)" in normalized and "RATIO_CFP_TTM" in normalized:
            return "reversal_bm_cfp_val2"
        if "RATIO_CFP_TTM" in normalized:
            return "reversal_bm_cfp"
        if "2*RANK(1-RETURNS(CLOSE,40))" in normalized:
            return "reversal_bm_rev2"
        if "2*RANK(RATIO_BM_TTM)" in normalized:
            return "reversal_bm_val2"
        if "*" in normalized and "0.5+0.5*RANK(RATIO_BM_TTM)" in normalized:
            return "reversal_bm_interact"
        return "reversal_bm_eq"
    if "MA(RATIO_BM_TTM,63)" in normalized:
        if "MA(RATIO_CFP_TTM,63)" in normalized:
            return "reversal_bm_cfp_ma63"
        return "reversal_bm_ma63"
    if "TS_RANK(RATIO_BM_TTM,756)" in normalized:
        if "TS_RANK(RATIO_CFP_TTM,756)" in normalized:
            return "reversal_bm_cfp_tsrank756"
        return "reversal_bm_tsrank756"
    if "MA(RATIO_BM_TTM" in normalized and "RATIO_CFP_TTM" in normalized:
        return "reversal_bm_cfp_ma63"
    if "TS_RANK(RATIO_BM_TTM" in normalized and "RATIO_CFP_TTM" in normalized:
        return "reversal_bm_cfp_tsrank756"
    return None


def saved_records(
    catalog: dict[str, set[str]],
    net_filter: str = "positive",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if net_filter not in {"positive", "negative", "all"}:
        raise ValueError(f"Unsupported platform net filter: {net_filter}")
    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for report_path in sorted(PROJECT_ROOT.glob("*.report.csv")):
        with report_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            for row in rows:
                if row.get("status") != "completed":
                    continue
                net_text = row.get("net_excess_pct")
                if net_text is None or str(net_text).strip() == "":
                    continue
                platform_net = float(net_text)
                if net_filter == "positive" and platform_net <= 0:
                    continue
                if net_filter == "negative" and platform_net >= 0:
                    continue
                name = row["name"]
                formulas = sorted(catalog.get(name, set()))
                formula = formulas[0] if formulas else None
                handler = handler_for(formula or "")
                record = {
                    "id": f"{report_path.stem}:{name}",
                    "name": name,
                    "report": report_path.name,
                    "direction": int(row["direction"]),
                    "factor_id": row.get("factor_id"),
                    "run_id": row.get("run_id"),
                    "platform_net_excess_pct": platform_net,
                    "platform_rank_ic": float(row["rank_ic"]) if row.get("rank_ic") else None,
                    "platform_ic_mean": float(row["ic_mean"]) if row.get("ic_mean") else None,
                    "platform_turnover_pct": float(row["turnover_pct"]) if row.get("turnover_pct") else None,
                    "platform_gross_excess_pct": float(row["long_excess_pct"]) if row.get("long_excess_pct") else None,
                    "platform_annual_cost_pct": float(row["annual_cost_pct"]) if row.get("annual_cost_pct") else None,
                    "raw_result": str(row.get("raw_result", "")).replace("\\", "/"),
                    "formula": formula,
                    "handler": handler,
                    "configured_cycle": report_cycle(report_path.name),
                }
                if handler is None:
                    record["reason"] = unsupported_reason(formula)
                    unsupported.append(record)
                else:
                    supported.append(record)
    return supported, unsupported


def positive_records(catalog: dict[str, set[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep the original positive-only API used by offline diagnostics."""
    return saved_records(catalog, "positive")


def build_factor(
    frame: pd.DataFrame,
    handler: str,
    financial: dict[str, pd.DataFrame] | None = None,
    signal_dates: list[pd.Timestamp] | None = None,
) -> pd.Series:
    if handler in FINANCIAL_HANDLERS:
        if financial is None or signal_dates is None:
            raise RuntimeError(f"Financial cache is required for handler {handler}")
        return build_financial_factor(frame, handler, signal_dates, financial)
    if handler in MARKET_HANDLERS:
        if signal_dates is None:
            raise RuntimeError(f"Signal dates are required for handler {handler}")
        return build_market_factor(frame, handler, signal_dates)

    grouped = frame.groupby("instrument", sort=False, observed=True)
    close = frame["close_qfq"]
    open_price = frame["open_qfq"]
    turnover = frame["turnover"]
    dates = frame["date"]
    ret1 = close.div(grouped["close_qfq"].shift(1)).sub(1.0)
    ret3 = close.div(grouped["close_qfq"].shift(3)).sub(1.0)
    ret5 = close.div(grouped["close_qfq"].shift(5)).sub(1.0)
    ret10 = close.div(grouped["close_qfq"].shift(10)).sub(1.0)
    ret20 = close.div(grouped["close_qfq"].shift(20)).sub(1.0)
    ret40 = close.div(grouped["close_qfq"].shift(40)).sub(1.0)

    if handler == "momentum120":
        return close.div(grouped["close_qfq"].shift(120)).sub(1.0)
    if handler == "momentum20":
        return close.div(grouped["close_qfq"].shift(20)).sub(1.0)
    if handler == "momentum20_open":
        return open_price.div(grouped["close_qfq"].shift(20)).sub(1.0)
    if handler == "ma_reversion40":
        return close.div(rolling_stat(frame, close, 40, "mean")).mul(-1.0)

    reversal_windows = {
        "reversal5": (5, ret5),
        "reversal10": (10, ret10),
        "reversal20": (20, ret20),
    }
    if handler in reversal_windows:
        return cross_rank(1.0 - reversal_windows[handler][1], dates)

    if handler in {"drawdown20", "ma_drawdown20"}:
        if handler == "drawdown20":
            denominator = rolling_stat(frame, close, 20, "max")
        else:
            denominator = rolling_stat(frame, close, 20, "mean")
        return cross_rank(1.0 - close.div(denominator), dates)

    if handler in {
        "rsi14",
        "rsi_cross30",
        "rsi35",
        "smooth_rsi28",
        "rsi35_recovery3",
        "rsi35_recovery5",
    }:
        window = 28 if handler == "smooth_rsi28" else 14
        rsi = wilder_rsi(frame, window)
        rsi_signal = 1.0 - rsi / 100.0
        if handler == "rsi14":
            return cross_rank(rsi_signal, dates)
        if handler == "rsi_cross30":
            previous_rsi = rsi.groupby(frame["instrument"], sort=False, observed=True).shift(1)
            crossed = rsi.ge(30.0) & previous_rsi.lt(30.0)
            score_rank = cross_rank(rsi_signal, dates)
            return score_rank.where(crossed, 0.0)
        if handler == "rsi35":
            raw = rsi.sub(35.0).abs().mul(-1.0).where(rsi.lt(50.0), -99999.0)
            return cross_rank(raw, dates)
        if handler in {"rsi35_recovery3", "rsi35_recovery5"}:
            raw = rsi.sub(35.0).abs().mul(-1.0).where(rsi.lt(50.0), -99999.0)
            recovery = ret3 if handler.endswith("3") else ret5
            return (cross_rank(raw, dates) + cross_rank(recovery, dates)) / 2.0
        smoothed = rolling_stat(frame.assign(_rsi_signal=rsi_signal), rsi_signal, 10, "mean")
        return cross_rank(smoothed, dates)

    if handler == "mfi14":
        mfi = money_flow_index(frame, 14)
        return cross_rank(1.0 - mfi / 100.0, dates)

    if handler == "beta_low":
        return cross_rank(-rolling_beta(frame, ret1, 252), dates)

    if handler == "ltmom_exhigh252_21":
        absolute_return_rank = rolling_time_series_rank(frame, ret1.abs(), 252)
        filtered_return = ret1.where(absolute_return_rank.le(0.80), 0.0)
        work = frame[["instrument"]].copy()
        work["_filtered_return"] = filtered_return
        trailing_252 = grouped_rolling(work, "_filtered_return", 252, "sum")
        trailing_21 = grouped_rolling(work, "_filtered_return", 21, "sum")
        return cross_rank(trailing_252 - trailing_21, dates)

    if handler == "max5_low21":
        if handler in ALIGNMENT_PYTHON_INDEX_HANDLERS and signal_dates is not None:
            max5 = python_date_level_top_n_mean(frame, ret1, signal_dates, 21, 5)
        else:
            max5 = rolling_top_n_mean(frame, ret1, 21, 5)
        return cross_rank(-max5, dates)

    if handler == "wma_low_volume40":
        raw = 1.0 / frame["low_qfq"].pow(2) / frame["volume"]
        return rolling_weighted_mean(frame, raw, 40)

    if handler == "wma_amount_mad10_50":
        amount = pd.to_numeric(frame["amount"], errors="coerce")
        mad = rolling_mean_absolute_deviation(frame, amount, 10)
        return rolling_weighted_mean(frame, -5.0 * mad, 50)

    if handler == "python_obv":
        # The platform Python component is interpreted as a per-symbol daily
        # series here; the raw cumulative OBV remains unranked as in the code.
        obv_increment = frame["volume"] * ret1
        obv = obv_increment.groupby(
            frame["instrument"], sort=False, observed=True
        ).cumsum()
        obv_90_high = rolling_stat(frame, obv, 90, "max")
        obv_30_ma = rolling_stat(frame, obv, 30, "mean")
        large_order_volume = rolling_stat(frame, frame["volume"], 20, "max")
        large_order_ratio = large_order_volume.div(frame["volume"].replace(0.0, np.nan))
        buy_signal = large_order_ratio.gt(0.01).astype(float)
        sell_signal = large_order_ratio.lt(0.0).astype(float).mul(-1.0)
        obv_signal = obv.eq(obv_90_high) & obv.gt(obv_30_ma)
        return buy_signal + sell_signal + obv_signal.astype(float)

    if handler in {"max_return21_low", "skew60_low", "turnover_std21", "volatility21"}:
        if handler == "max_return21_low":
            return cross_rank(-rolling_stat(frame, ret1, 21, "max"), dates)
        if handler == "skew60_low":
            return cross_rank(-rolling_stat(frame, ret1, 60, "skew"), dates)
        if handler == "turnover_std21":
            return rolling_stat(frame, turnover, 21, "std")
        return rolling_stat(frame, ret1, 21, "std")

    if handler in {"zscore20_low", "moderate_bias5", "moderate_drawdown60"}:
        if handler == "zscore20_low":
            mean = rolling_stat(frame, close, 20, "mean")
            std = rolling_stat(frame, close, 20, "std")
            return cross_rank(-close.sub(mean).div(std.replace(0.0, np.nan)), dates)
        if handler == "moderate_bias5":
            mean = rolling_stat(frame, close, 20, "mean")
            bias = close.div(mean).sub(1.0).mul(100.0)
            return cross_rank(-bias.clip(upper=0.0).add(5.0).abs(), dates)
        rolling_max = rolling_stat(frame, close, 60, "max")
        drawdown = 1.0 - close.div(rolling_max)
        return cross_rank(-drawdown.sub(0.10).abs(), dates)

    if handler in {
        "weighted_reversal",
        "exp_weighted_reversal63",
        "exp_weighted_reversal126",
        "ema_weighted_reversal63",
    }:
        weighted_return = turnover * ret1
        if handler == "weighted_reversal":
            numerator = rolling_stat(frame.assign(_weighted_return=weighted_return), weighted_return, 21, "sum")
            denominator = rolling_stat(frame, turnover, 21, "sum")
        elif handler == "ema_weighted_reversal63":
            # EMA(X, N) uses the standard alpha=2/(N+1) recurrence.  This is
            # distinct from the finite, manually expanded exp(-k/tau)
            # formulas used by the HT13 candidates.
            alpha = 2.0 / 64.0
            numerator = grouped_ewm(frame, weighted_return, alpha, 63)
            denominator = grouped_ewm(frame, turnover, alpha, 63)
        else:
            window = 63 if handler.endswith("63") else 126
            tau = 12.0 if window == 63 else 24.0
            numerator = grouped_finite_exp_weighted_sum(
                frame, weighted_return, window, tau
            )
            denominator = grouped_finite_exp_weighted_sum(frame, turnover, window, tau)
        return cross_rank(-numerator.div(denominator.replace(0.0, np.nan)), dates)

    if handler in {
        "scaled_reversal5",
        "capitulation20",
        "reversal5_drawdown20",
        "reversal5_rsi14",
        "drawdown60_recovery5",
        "ma20_recovery5",
        "reversal20_recovery5",
        "ma20_cross5",
    }:
        reversal5_rank = cross_rank(1.0 - ret5, dates)
        if handler == "scaled_reversal5":
            volatility = rolling_stat(frame, ret1, 20, "std")
            return cross_rank((1.0 - ret5).div(volatility.add(0.0001)), dates)
        if handler == "capitulation20":
            turn5 = rolling_stat(frame, turnover, 5, "mean")
            turn20 = rolling_stat(frame, turnover, 20, "mean")
            return reversal5_rank + cross_rank(turn5.div(turn20), dates)
        if handler == "reversal5_drawdown20":
            denominator = rolling_stat(frame, close, 20, "max")
            return reversal5_rank + cross_rank(1.0 - close.div(denominator), dates)
        if handler == "reversal5_rsi14":
            rsi = wilder_rsi(frame, 14)
            return reversal5_rank + cross_rank(1.0 - rsi / 100.0, dates)
        if handler == "drawdown60_recovery5":
            denominator = rolling_stat(frame, close, 60, "max")
            return cross_rank(1.0 - close.div(denominator), dates) + cross_rank(ret5, dates)
        if handler == "ma20_recovery5":
            ma20 = rolling_stat(frame, close, 20, "mean")
            ma5 = rolling_stat(frame, close, 5, "mean")
            return cross_rank(1.0 - close.div(ma20), dates) + cross_rank(close.div(ma5).sub(1.0), dates)
        if handler == "reversal20_recovery5":
            return cross_rank(1.0 - ret20, dates) + cross_rank(ret5, dates)
        ma20 = rolling_stat(frame, close, 20, "mean")
        ma5 = rolling_stat(frame, close, 5, "mean")
        previous_close = close.groupby(
            frame["instrument"], sort=False, observed=True
        ).shift(1)
        previous_ma5 = ma5.groupby(
            frame["instrument"], sort=False, observed=True
        ).shift(1)
        crossed = close.gt(ma5) & previous_close.le(previous_ma5)
        score_rank = cross_rank(1.0 - close.div(ma20), dates)
        return score_rank.where(crossed, 0.0)

    if handler == "vwap10_volume20_momentum20":
        amount = pd.to_numeric(frame.get("amount"), errors="coerce")
        if amount is None or amount.isna().all():
            amount = frame["volume"] * (open_price + close) / 2.0
        amount_per_volume = amount.div(frame["volume"].replace(0.0, np.nan))
        vwap10 = rolling_stat(frame, amount_per_volume, 10, "mean")
        volume20 = rolling_stat(frame, frame["volume"], 20, "mean")
        bias = close.div(rolling_stat(frame, close, 20, "mean")).sub(1.0)
        return vwap10.div(close).sub(1.0) * frame["volume"].div(volume20) * bias

    if handler.startswith("alpha"):
        open_rank = cross_rank(open_price, dates)
        high_rank = cross_rank(frame["high_qfq"], dates)
        low_rank = cross_rank(frame["low_qfq"], dates)
        volume_rank = cross_rank(frame["volume"], dates)
        close_rank = cross_rank(close, dates)
        if handler == "alpha3":
            return -rolling_corr(frame, open_rank, volume_rank, 10)
        if handler == "alpha13":
            return -cross_rank(rolling_covariance(frame, close_rank, volume_rank, 5), dates)
        if handler == "alpha15":
            corr = rolling_corr(frame, high_rank, volume_rank, 3)
            return -rolling_stat(frame, cross_rank(corr, dates), 3, "sum")
        if handler == "alpha16":
            return -cross_rank(rolling_covariance(frame, high_rank, volume_rank, 5), dates)
        if handler == "alpha40":
            high_std = rolling_stat(frame, frame["high_qfq"], 10, "std")
            corr = rolling_corr(frame, frame["high_qfq"], frame["volume"], 10)
            return -cross_rank(high_std, dates) * corr
        if handler == "alpha44":
            return -rolling_corr(frame, frame["high_qfq"], volume_rank, 5)
        if handler == "alpha50":
            typical_rank = cross_rank((frame["high_qfq"] + frame["low_qfq"] + close) / 3.0, dates)
            corr = rolling_corr(frame, volume_rank, typical_rank, 5)
            return -rolling_stat(frame, cross_rank(corr, dates), 5, "max")
        ratio = close.sub(rolling_stat(frame, frame["low_qfq"], 12, "min")).div(
            rolling_stat(frame, frame["high_qfq"], 12, "max")
            .sub(rolling_stat(frame, frame["low_qfq"], 12, "min"))
        )
        return -rolling_corr(frame, ratio.rank(method="average"), volume_rank, 6)

    if handler in {"turn_bias", "turn_signal", "weighted_reversal_lowturn", "reversal_turn_eq", "reversal_chip_turn_eq", "reversal_chip_turn_size_eq"}:
        turn21 = grouped_rolling(frame, "turnover", 21, "mean")
        turn504 = grouped_rolling(frame, "turnover", 504, "mean")
        turn_signal = 1.0 - turn21.div(turn504)
    else:
        turn_signal = None

    if handler == "turn_bias":
        return turn21.div(turn504).sub(1.0)
    if handler == "turn_signal":
        return turn_signal

    if handler in {"drawdown120", "drawdown60"}:
        window = 120 if handler == "drawdown120" else 60
        rolling_max = grouped["close_qfq"].rolling(window=window, min_periods=window).max()
        rolling_max = rolling_max.reset_index(level=0, drop=True).reindex(frame.index)
        return cross_rank(1.0 - close.div(rolling_max), dates)

    if handler in {"reversal40", "reversal_turn_eq", "reversal_chip_eq", "reversal_chip_turn_eq", "reversal_chip_turn_size_eq"}:
        reversal_rank = cross_rank(1.0 - ret40, dates)
    else:
        reversal_rank = None

    if handler == "reversal40":
        return reversal_rank

    if handler in {"weighted_reversal_lowturn"}:
        turnover_return = frame.assign(_turnover_return=turnover * ret1)
        weighted_reversal = -grouped_rolling(turnover_return, "_turnover_return", 21, "sum").div(
            grouped_rolling(frame, "turnover", 21, "sum")
        )
        return (
            cross_rank(weighted_reversal, dates)
            + cross_rank(turn_signal, dates)
        ) / 2.0

    if handler in {"reversal_chip_eq", "reversal_chip_turn_eq", "reversal_chip_turn_size_eq", "chip250"}:
        weighted_price = frame["volume"] * (open_price + close) / 2.0
        weighted_frame = frame.assign(_weighted_price=weighted_price)
        vwap = grouped_rolling(weighted_frame, "_weighted_price", 250, "sum").div(
            grouped_rolling(frame, "volume", 250, "sum")
        )
        chip_rank = cross_rank(vwap.div(close).sub(1.0), dates)
    else:
        chip_rank = None

    if handler == "chip250":
        return chip_rank
    if handler == "reversal_chip_eq":
        return (reversal_rank + chip_rank) / 2.0
    if handler == "reversal_turn_eq":
        return (reversal_rank + cross_rank(turn_signal, dates)) / 2.0
    if handler == "reversal_chip_turn_eq":
        return (reversal_rank + chip_rank + cross_rank(turn_signal, dates)) / 3.0
    if handler == "reversal_chip_turn_size_eq":
        cap_rank = cross_rank(frame["total_mv"], dates)
        cap_mean = cap_rank.groupby(dates, sort=False, observed=True).transform("mean")
        cap_std = cap_rank.groupby(dates, sort=False, observed=True).transform("std")
        size_rank = cross_rank(cap_rank.sub(cap_mean).div(cap_std.replace(0.0, np.nan)).mul(-1.0), dates)
        return (reversal_rank + chip_rank + cross_rank(turn_signal, dates) + size_rank) / 4.0
    raise KeyError(f"Unsupported handler: {handler}")


def fidelity_note(handler: str) -> str:
    if handler == "growth_roe":
        return (
            "Tushare PIT proxy: YoY growth of TTM attributable net income / "
            "average announced equity, ranked cross-sectionally"
        )
    if handler == "quality_roa_tsrank756":
        return (
            "Tushare PIT proxy: strict 756-day TS_RANK of TTM net income / "
            "announced total assets"
        )
    if handler == "quality_oper_profit_tsrank756":
        return (
            "Tushare PIT proxy: strict 756-day TS_RANK of TTM operating profit / "
            "TTM net income; platform total-profit denominator is absent locally"
        )
    if handler in {
        "mfi14",
        "beta_low",
        "max5_low21",
        "ltmom_exhigh252_21",
        "python_obv",
        "rsi35_recovery3",
        "rsi35_recovery5",
        "wma_low_volume40",
        "ema_weighted_reversal63",
    }:
        return {
            "mfi14": "direct local proxy: standard MFI from cached qfq high/low/close and volume",
            "beta_low": "proxy: 252-day beta to the equal-weight full-A daily return",
            "max5_low21": "compatibility reconstruction of the saved Python top-five factor: per-symbol DELAY followed by [date, symbol] level-0 rolling",
            "ltmom_exhigh252_21": "direct local reconstruction with per-symbol 252-day absolute-return rank filtering",
            "python_obv": "local per-symbol interpretation of the saved Python OBV component; raw output is left unranked",
            "rsi35_recovery3": "direct local RSI35 proxy plus 3-day recovery rank",
            "rsi35_recovery5": "direct local RSI35 proxy plus 5-day recovery rank",
            "wma_low_volume40": "direct local reconstruction of WMA((((1/LOW)/LOW)/VOLUME),40) using qfq low and volume",
            "ema_weighted_reversal63": "direct local reconstruction of EMA(X,63) with alpha=2/(63+1)",
        }[handler]
    if handler in {
        "impact60",
        "impact_abs_return60",
        "impact_downside60",
        "impact_aggregate60",
        "t10_size_plus_impact",
        "t10_size_plus_impact_g13",
        "t10_size_plus_impact_dd120",
        "t10_size_plus_impact_downside",
        "t10_size_plus_impact_aggregate",
        "t10_nomcap_plus_impact",
        "t10_size_plus_impact_bm",
        "t10_size_plus_impact_wc",
        "book_to_market_lf_plus_impact",
    }:
        return "market proxy: cached high/low/amount when present; otherwise open/close range and volume*average-price proxies"
    if handler == "size_only":
        return "direct local market-cap rank from Tushare daily_basic total_mv"
    if handler == "book_to_market_lf_minus_size":
        return "PIT proxy: book_to_market_ratio_lf mapped to latest announced equity / market cap"
    if handler == "t10_size_plus_wc_mcap":
        return "PIT proxy: working-capital term uses current balance fields when present, otherwise total assets - total liabilities"
    if handler == "ev_ebitda_proxy":
        return "PIT proxy: EV uses market cap plus liabilities less cash when present; EBITDA falls back to TTM operating profit"
    if handler == "residual_volatility":
        return "proxy: market-model residual volatility, not the platform Barra field"
    if handler in CFP_PROXY_BY_HANDLER:
        return f"Tushare PIT financial proxy; CFP component uses {CFP_PROXY_BY_HANDLER[handler]} selected by the offline proxy diagnosis"
    if handler in {"reversal_bm_tsrank756", "reversal_bm_cfp_tsrank756"}:
        return "Tushare PIT ratio with strict 756-day rolling rank; local history warmup may shorten periods"
    if handler in {"reversal_bm_ma63", "reversal_bm_cfp_ma63"}:
        return "Tushare PIT ratio with strict 63-day daily moving average"
    if handler in FINANCIAL_HANDLERS:
        return "Tushare PIT financial proxy; consolidated statements and reconstructed TTM"
    return "direct local market-data reconstruction"


def unsupported_reason(formula: str | None) -> str:
    normalized = normalize_formula(formula or "")
    if "CAL_" in normalized:
        return "platform intraday cal_* fields are not present in the local daily cache"
    if "DIVIDEND_YIELD_TTM" in normalized:
        return "local snapshot has no complete point-in-time dividend history for dividend_yield_ttm"
    if "OPER_ADJ_PROFIT_RATIO_TTM" in normalized:
        return "local financial cache has no adjusted-profit/non-recurring-income fields"
    if "HIGH" in normalized or "LOW" in normalized or "AMOUNT" in normalized:
        return "market formula needs high/low/amount; use the rich market cache or the explicit local proxy"
    if "CURRENT_ASSETS" in normalized or "INVENTORY" in normalized or "CURRENT_LIABILITIES" in normalized:
        return "working-capital formula needs balance-sheet fields not present in the current cache"
    if "BOOK_TO_MARKET_RATIO_LF" in normalized:
        return "book_to_market_ratio_lf is not mapped in the local financial cache"
    if "EV" in normalized or "EBITDA" in normalized:
        return "EV/EBITDA fields are not mapped in the local financial cache"
    return "no local handler for this formula"


def infer_cycle(calendar: list[pd.Timestamp], signal_dates: list[pd.Timestamp]) -> int:
    positions = [calendar.index(date) for date in signal_dates]
    differences = [right - left for left, right in zip(positions, positions[1:]) if right > left]
    if not differences:
        raise RuntimeError("Cannot infer rebalance cycle from one platform signal date")
    return Counter(differences).most_common(1)[0][0]


def fallback_signal_dates(
    calendar: list[pd.Timestamp],
    cycle: int,
    templates: dict[int, list[pd.Timestamp]],
) -> tuple[list[pd.Timestamp], str]:
    template = templates.get(cycle)
    if template:
        return list(template), f"reference_chart_{cycle}d"

    start_position = calendar.index(PLATFORM_START)
    dates = [
        date
        for position, date in enumerate(calendar[start_position::cycle], start=start_position)
        if position + cycle < len(calendar)
    ]
    return dates, "generated_calendar"


def panel_close(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    panel = frame.pivot(index="date", columns="instrument", values="close_qfq")
    return panel.reindex(calendar).sort_index(axis=1).ffill()


def forward_returns(
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    label_offset: int = 0,
) -> pd.DataFrame:
    current_positions = [calendar.index(date) + label_offset for date in signal_dates]
    future_positions = [position + cycle for position in current_positions]
    if min(current_positions, default=0) < 0 or max(future_positions, default=-1) >= len(calendar):
        raise RuntimeError("Local data does not cover the platform forward target")
    current = close.iloc[current_positions].copy()
    current.index = signal_dates
    current = current.stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    future = close.iloc[future_positions].copy()
    future.index = signal_dates
    future = future.stack(dropna=False).rename("future_close").reset_index()
    future = future.rename(columns={"level_0": "date", "level_1": "instrument"})
    result = current.merge(future, on=["date", "instrument"], how="left")
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    return result[["date", "instrument", "forward_return"]]


def assign_groups(values: pd.Series, tie_break: pd.Series | None = None) -> pd.Series:
    """Assign equal-sized groups, optionally using a proxy tie order."""
    if tie_break is None or not values.duplicated(keep=False).any():
        ranks = values.rank(method="first")
        return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)

    order = np.lexsort((tie_break.to_numpy(dtype=float), values.to_numpy(dtype=float)))
    labels = np.ceil(
        np.arange(1, len(values) + 1, dtype=float) * GROUPS / len(values)
    ).astype(int).clip(1, GROUPS)
    groups = np.empty(len(values), dtype=int)
    groups[order] = labels
    return pd.Series(groups, index=values.index)


def deterministic_tie_break(current: pd.DataFrame, handler: str | None) -> pd.Series | None:
    """Return a reproducible per-date order for handlers with platform ties."""
    if handler not in ALIGNMENT_TIE_BREAK_HANDLERS or current.empty:
        return None
    date = pd.Timestamp(current["date"].iloc[0]).strftime("%Y-%m-%d")
    symbols = sorted(current["instrument"].astype(str).unique())
    seed_bytes = f"{ALIGNMENT_TIE_BREAK_SEED}|{handler}|{date}".encode("utf-8")
    seed = int.from_bytes(hashlib.blake2b(seed_bytes, digest_size=8).digest(), "little")
    generator = np.random.default_rng(seed)
    order = pd.Series(generator.random(len(symbols)), index=symbols)
    return current["instrument"].astype(str).map(order).reset_index(drop=True)


def evaluate(
    frame: pd.DataFrame,
    factor_values: pd.Series,
    close: pd.DataFrame,
    platform: dict[str, Any],
    direction: int,
    signal_dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    cycle: int,
    label_offset: int = 0,
    handler: str | None = None,
) -> dict[str, Any]:
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = factor_values.to_numpy(dtype=float)
    signal_factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]
    returns = forward_returns(close, calendar, signal_dates, cycle, label_offset)
    data = signal_factor_frame.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    selected_group = GROUPS if direction == 1 else 1
    previous: dict[int, set[str]] = {}
    rank_ics: list[float] = []
    ics: list[float] = []
    group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    group_turnovers: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    period_rows: list[dict[str, Any]] = []

    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        tie_break = deterministic_tie_break(current, handler)
        current["group"] = assign_groups(current["factor"], tie_break)
        rank_ic = current["factor"].rank(method="average").corr(current["forward_return"].rank(method="average"))
        ic = current["factor"].corr(current["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))
        benchmark = float(current["forward_return"].mean())
        row: dict[str, Any] = {"date": date, "stock_count": int(len(current)), "benchmark": benchmark}
        for group in range(1, GROUPS + 1):
            members = set(current.loc[current["group"].eq(group), "instrument"])
            group_return = float(current.loc[current["group"].eq(group), "forward_return"].mean())
            old_members = previous.get(group)
            turnover = (
                1.0 - len(members.intersection(old_members)) / len(members)
                if old_members
                else np.nan
            )
            previous[group] = members
            group_returns[group].append(group_return)
            if np.isfinite(turnover):
                group_turnovers[group].append(float(turnover))
            row[f"excess_{group}"] = group_return - benchmark
            row[f"turnover_{group}"] = turnover
        period_rows.append(row)

    periods = pd.DataFrame(period_rows)
    years = len(periods) * cycle / 252.0
    selected_excess = None
    selected_turnover = None
    if years and len(periods):
        selected_excess = float(periods[f"excess_{selected_group}"].sum() / years)
    if group_turnovers[selected_group]:
        selected_turnover = float(np.mean(group_turnovers[selected_group]))
    selected_cost = selected_turnover * (252.0 / cycle) * ROUND_TRIP_COST if selected_turnover is not None else None
    selected_net = selected_excess - selected_cost if selected_excess is not None and selected_cost is not None else None

    platform_top_rows = [
        row
        for row in platform.get("top", [])
        if row.get("symbol") and row.get("date")
    ]
    top_dates = [pd.Timestamp(row["date"]).normalize() for row in platform_top_rows]
    latest_date = max(top_dates) if top_dates else signal_dates[-1]
    latest = factor_frame[factor_frame["date"].eq(latest_date)].dropna()
    # The saved platform `top` payload is the highest raw factor values even
    # when direction=0 holds the bottom group.  Keep this ranking separate
    # from the direction-selected return calculation.
    latest = latest.sort_values(["factor", "instrument"], ascending=[False, True])
    local_top = latest.head(20)["instrument"].tolist()
    platform_top = [
        str(row["symbol"])
        for row in platform_top_rows
        if pd.Timestamp(row["date"]).normalize() == latest_date
    ]
    platform_group = platform.get("group_metrics", {}).get(selected_group, {})
    platform_rank = platform.get("metrics", {}).get("Rank_IC")
    platform_ic = platform.get("metrics", {}).get("IC_mean")
    platform_net = None

    return {
        "periods": len(periods),
        "cycle": cycle,
        "stock_count_mean": float(periods["stock_count"].mean()) if not periods.empty else None,
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.mean(ics)) if ics else None,
        "selected_group": selected_group,
        "gross_excess": selected_excess,
        "turnover": selected_turnover,
        "annual_cost": selected_cost,
        "net_excess": selected_net,
        "platform_rank_ic": platform_rank,
        "platform_ic_mean": platform_ic,
        "platform_gross_excess": platform_group.get("excessAnnualized"),
        "platform_turnover": platform_group.get("turnoverRate"),
        "top20_overlap": len(set(local_top).intersection(platform_top)) if platform_top else None,
        "local_top20": local_top,
        "platform_top20": platform_top,
        "tie_break_proxy": handler if handler in ALIGNMENT_TIE_BREAK_HANDLERS else None,
    }


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


def validate_existing_output(
    output_root: Path,
    output_name: str,
    alignment_config: dict[str, Any],
) -> None:
    """Keep an output directory from silently mixing alignment versions."""
    if not output_root.exists():
        return
    if not output_root.is_dir():
        raise RuntimeError(f"Output path is not a directory; choose a new path: {output_root}")
    metadata_path = output_root / f"{output_name}.json"
    if metadata_path.is_file():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Existing output metadata is unreadable; choose a new output directory: {metadata_path}"
            ) from exc
        settings = payload.get("settings", {})
        existing_version = settings.get("alignment_rule_version")
        if existing_version != ALIGNMENT_RULE_VERSION:
            raise RuntimeError(
                f"Refusing to overwrite output from alignment rule {existing_version!r}; "
                f"use a new directory for {ALIGNMENT_RULE_VERSION}: {output_root}"
            )
        existing_config = settings.get("alignment_config")
        # Reports written before the metadata field was added may still carry
        # the same rule version. They are upgraded in place only when the
        # version already matches; a different version is always isolated.
        if existing_config is not None and existing_config != alignment_config:
            raise RuntimeError(
                "Existing output has different alignment settings; choose a new output directory: "
                f"{output_root}"
            )
        return
    if any(output_root.iterdir()):
        raise RuntimeError(
            "Existing output directory has no compatible alignment metadata; "
            f"choose a new versioned directory: {output_root}"
        )


def write_outputs(
    supported: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    output_root: Path,
    universe: str,
    pool_count: int,
    data_start: pd.Timestamp,
    label_offset: int,
    market_cap_field: str,
    net_filter: str,
    market_field_sources: dict[str, str] | None = None,
) -> None:
    alignment_config = alignment_config_snapshot()
    alignment_config.update(
        {
            "universe": universe,
            "market_cap_field": market_cap_field,
            "data_start": data_start.strftime("%Y%m%d"),
            "label_offset": label_offset,
        }
    )
    validate_alignment_config(alignment_config)
    output_name = f"{net_filter}_factor_local_compare"
    validate_existing_output(output_root, output_name, alignment_config)
    output_root.mkdir(parents=True, exist_ok=True)
    local_universe = (
        "full-A Tushare qfq rows joined with daily_basic and filtered to .SH/.SZ"
        if universe == "full_a"
        else "fixed ST-filter workflow pool"
    )
    net_description = {
        "positive": "greater than zero",
        "negative": "less than zero",
        "all": "present in the saved completed report",
    }[net_filter]
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_config": alignment_config,
            "alignment_status": "canonical",
            "data_start": data_start.strftime("%Y%m%d"),
            "end": END.strftime("%Y%m%d"),
            "groups": GROUPS,
            "round_trip_cost": ROUND_TRIP_COST,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "price_mode": ALIGNMENT_PRICE_MODE,
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
            "label_offset": label_offset,
            "return_label": f"close(t+{label_offset}) -> close(t+{label_offset}+cycle)",
            "pool_count": pool_count,
            "market_cap_field": market_cap_field,
            "platform_net_filter": net_filter,
            "local_universe": local_universe,
            "supported_records": len(supported),
            "unsupported_records": len(unsupported),
            "market_field_sources": market_field_sources or {},
            "tie_break_handlers": sorted(ALIGNMENT_TIE_BREAK_HANDLERS),
            "tie_break_seed": ALIGNMENT_TIE_BREAK_SEED,
            "tie_break_description": ALIGNMENT_TIE_BREAK_DESCRIPTION,
        },
        "results": rows,
        "unsupported": unsupported,
    }
    (output_root / f"{output_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    lines = [
        f"# {net_filter.title()} platform-net-excess factors: local reproduction",
        "",
        f"The catalog contains every completed saved run whose platform `net_excess_pct` is {net_description}.",
        f"Alignment rules: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        f"The local side uses `{local_universe}` and `{ALIGNMENT_PRICE_MODE}` Tushare daily data.",
        f"The platform pool is shown per row from the saved workflow registry; local membership follows the selected `{universe}` mode.",
        f"Local forward return label: `close(t+{label_offset}) -> close(t+{label_offset}+cycle)`.",
        f"Local benchmark mode: `{ALIGNMENT_BENCHMARK_MODE}` ({ALIGNMENT_BENCHMARK_DESCRIPTION}).",
        f"Local net excess = arithmetic gross excess - annualized turnover cost using {100 * ALIGNMENT_ONE_WAY_COST:.2f}% one-way cost.",
        "",
        f"- selected platform records: `{len(supported) + len(unsupported)}`",
        f"- locally reproduced: `{len(rows)}`",
        f"- data-unavailable: `{len(unsupported)}`",
        "",
        "## Locally reproduced",
        "",
        "| run | handler | platform pool | cycle | dates | platform net | local net | delta net (pp) | platform RankIC | local RankIC | platform gross excess | local gross excess | platform turnover | local turnover | Top20 |",
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        def pct(value: Any) -> str:
            return "n/a" if value is None else f"{100 * float(value):.2f}%"

        def num(value: Any) -> str:
            return "n/a" if value is None else f"{float(value):.4f}"

        platform_net = row["platform_net_excess_pct"]
        local_net = row["local_net_excess"]
        delta = None if local_net is None else 100 * local_net - platform_net
        lines.append(
            f"| {row['id']} | {row['handler']} | {row.get('platform_stock_pool', 'unknown')} | {row['cycle']} | {row['date_source']} ({row['platform_chart_periods']}) | {platform_net:.2f}% | {pct(local_net)} | {'n/a' if delta is None else f'{delta:.2f}'} | {num(row['platform_rank_ic'])} | {num(row['local_rank_ic'])} | {pct(row['platform_gross_excess'])} | {pct(row['local_gross_excess'])} | {pct(row['platform_turnover'])} | {pct(row['local_turnover'])} | {row['top20_overlap'] if row['top20_overlap'] is not None else 'n/a'}/20 |"
        )
    lines.extend(
        [
            "",
            "## Fidelity notes",
            "",
            "- Financial records use announcement-date point-in-time joins. Tushare consolidated statements (`comp_type=1`) are selected, and quarterly cumulative statements are converted to TTM.",
            f"- `{ALIGNMENT_RULE_VERSION}` uses a local data warm-up from `{data_start.strftime('%Y-%m-%d')}`; `MA(...,63)` and `TS_RANK(...,756)` use daily point-in-time ratios.",
            "- `residual_volatility` is a market-model residual-volatility proxy, not the platform's internal Barra field.",
            f"- Market-cap formulas use Tushare daily_basic `{market_cap_field}`; impact formulas use cached high/low/amount when available, with explicit open/close and volume*average-price proxies only where needed.",
            "- `book_to_market_ratio_lf` uses the latest point-in-time balance-sheet equity; the working-capital and EV/EBITDA formulas use documented fallbacks when their raw fields are absent.",
            "- Close net-excess differences do not prove exact field equivalence; local membership follows the selected universe mode.",
            "",
            "## Not reproducible from current local cache",
            "",
            "| run | platform net | formula | reason |",
            "|---|---:|---|---|",
        ]
    )
    for row in unsupported:
        lines.append(
            f"| {row['id']} | {row['platform_net_excess_pct']:.2f}% | `{row.get('formula') or '?'}` | {row['reason']} |"
        )
    (output_root / f"{output_name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", choices=["st_pool", "full_a"], default=ALIGNMENT_UNIVERSE)
    parser.add_argument(
        "--price-root",
        default=str(CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"),
    )
    parser.add_argument(
        "--cap-root",
        default=str(CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"),
    )
    parser.add_argument("--financial-root", default=str(CACHE_ROOT / "financial_full_a"))
    parser.add_argument("--output", default=str(OUTPUT_ROOT))
    parser.add_argument(
        "--platform-net-filter",
        choices=["positive", "negative", "all"],
        default="all",
        help="Select saved completed runs by platform net excess; all is the canonical full catalog.",
    )
    parser.add_argument("--data-start", default=DATA_START.strftime("%Y%m%d"))
    parser.add_argument(
        "--market-cap-field",
        choices=["total_mv", "circ_mv"],
        default=ALIGNMENT_MARKET_CAP_FIELD,
        help="daily_basic market-cap field used wherever the formula references MARKET_CAP",
    )
    parser.add_argument(
        "--label-offset",
        type=int,
        default=ALIGNMENT_LABEL_OFFSET,
        help="Trading-day offset applied to both the current and future close in the forward label.",
    )
    args = parser.parse_args()

    data_start = pd.Timestamp(
        pd.to_datetime(args.data_start, format="%Y%m%d" if len(args.data_start) == 8 else None)
    ).normalize()
    if data_start > PLATFORM_START:
        raise SystemExit("--data-start cannot be later than the platform comparison start")
    alignment_config = alignment_config_snapshot()
    alignment_config.update(
        {
            "universe": args.universe,
            "market_cap_field": args.market_cap_field,
            "data_start": data_start.strftime("%Y%m%d"),
            "label_offset": args.label_offset,
        }
    )
    try:
        validate_alignment_config(alignment_config)
    except ValueError as exc:
        raise SystemExit(
            f"{exc}. Read {ALIGNMENT_RULES_DOCUMENT}; use the dedicated diagnostic script "
            "for non-canonical sensitivity tests."
        ) from exc
    rules_path = PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT
    if not rules_path.is_file():
        raise SystemExit(f"Alignment rules document is missing: {rules_path}")
    validate_existing_output(
        Path(args.output),
        f"{args.platform_net_filter}_factor_local_compare",
        alignment_config,
    )
    calendar = [pd.Timestamp(value).normalize() for value in ensure_calendar(data_start, END, token=None)]
    catalog = formula_catalog()
    supported, unsupported = saved_records(catalog, args.platform_net_filter)
    configs = platform_configs()
    for record in supported + unsupported:
        record["platform_config"] = configs.get(str(record.get("factor_id")))
    if not supported and not unsupported:
        raise SystemExit(f"No {args.platform_net_filter} platform-net-excess records found")

    for record in supported + unsupported:
        if record["raw_result"] and not (PROJECT_ROOT / record["raw_result"]).exists():
            record["reason"] = f"saved platform result is missing: {record['raw_result']}"
            if record in supported:
                supported.remove(record)
                unsupported.append(record)
    supported = [record for record in supported if (PROJECT_ROOT / record["raw_result"]).exists()]

    print(
        f"{args.platform_net_filter}_records={len(supported) + len(unsupported)} "
        f"supported={len(supported)} unsupported={len(unsupported)}",
        flush=True,
    )
    if args.universe == "full_a":
        frame = load_full_a_data(
            Path(args.price_root),
            Path(args.cap_root),
            data_start,
            END,
        )
        frame = select_market_cap(frame, args.market_cap_field)
        pool = set(frame["instrument"].astype(str).unique())
    else:
        frame = load_st_data(DATA_START, END)
        pool = load_st_pool()
        frame = frame[frame["instrument"].isin(pool)].copy()
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(f"local_rows={len(frame)} pool={len(pool)}", flush=True)
    close = panel_close(frame, calendar)

    financial: dict[str, pd.DataFrame] | None = None
    financial_records = [record for record in supported if record["handler"] in FINANCIAL_HANDLERS]
    if financial_records:
        try:
            financial = load_financial_cache(Path(args.financial_root))
            print(
                f"financial_cache=loaded records={len(financial_records)} "
                f"fina_rows={len(financial['fina_indicator'])}",
                flush=True,
            )
        except FileNotFoundError as exc:
            for record in list(financial_records):
                supported.remove(record)
                record["reason"] = str(exc)
                unsupported.append(record)
            financial_records = []

    chart_templates: dict[int, list[pd.Timestamp]] = {}
    chart_records: list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int]] = []
    for record in supported:
        platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
        signal_dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
        signal_dates = [date for date in signal_dates if DATA_START <= date <= END]
        configured_cycle = record.get("configured_cycle")
        if len(signal_dates) >= 2:
            inferred_cycle = infer_cycle(calendar, signal_dates)
            cycle = configured_cycle or inferred_cycle
            if configured_cycle and inferred_cycle != configured_cycle:
                print(
                    f"warning={record['id']}: report_cycle={configured_cycle} chart_cycle={inferred_cycle}; using report cycle",
                    flush=True,
                )
            if cycle not in chart_templates or len(signal_dates) > len(chart_templates[cycle]):
                chart_templates[cycle] = signal_dates
            chart_records.append((record, platform, signal_dates, cycle))
        else:
            chart_records.append((record, platform, [], configured_cycle or 0))

    prepared: list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int, str]] = []
    for record, platform, signal_dates, cycle in chart_records:
        if signal_dates:
            date_source = "platform_chart"
        elif cycle:
            signal_dates, date_source = fallback_signal_dates(calendar, cycle, chart_templates)
        else:
            raise RuntimeError(f"Cannot determine rebalance cycle for {record['id']}")
        if not signal_dates:
            raise RuntimeError(f"No signal dates available for {record['id']}")
        prepared.append((record, platform, signal_dates, cycle, date_source))

    by_handler: dict[str, list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int, str]]] = {}
    for item in prepared:
        by_handler.setdefault(item[0]["handler"], []).append(item)

    rows: list[dict[str, Any]] = []
    for handler, items in by_handler.items():
        print(f"building={handler} records={len(items)}", flush=True)
        handler_dates = sorted(
            {
                date
                for record, platform, dates, _, _ in items
                for date in dates
            }
            | {
                pd.Timestamp(row["date"]).normalize()
                for _, platform, _, _, _ in items
                for row in platform.get("top", [])
                if row.get("date")
            }
        )
        values = build_factor(frame, handler, financial=financial, signal_dates=handler_dates)
        for record, platform, signal_dates, cycle, date_source in items:
            result = evaluate(
                frame,
                values,
                close,
                platform,
                record["direction"],
                signal_dates,
                calendar,
                cycle,
                args.label_offset,
                handler,
            )
            output = {
                "id": record["id"],
                "name": record["name"],
                "report": record["report"],
                "formula": record["formula"],
                "handler": handler,
                "platform_factor_id": record.get("factor_id"),
                "platform_run_id": record.get("run_id"),
                "platform_stock_pool": (record.get("platform_config") or {}).get("stock_pool", "unknown"),
                "platform_market": (record.get("platform_config") or {}).get("market"),
                "platform_start_date": (record.get("platform_config") or {}).get("start_date"),
                "platform_end_date": (record.get("platform_config") or {}).get("end_date"),
                "platform_configured_cycle": (record.get("platform_config") or {}).get("adjustment_cycle"),
                "platform_group_number": (record.get("platform_config") or {}).get("group_number"),
                "platform_factor_direction": (record.get("platform_config") or {}).get("factor_direction"),
                "cycle": cycle,
                "platform_net_excess_pct": record["platform_net_excess_pct"],
                "local_net_excess": result["net_excess"],
                "local_gross_excess": result["gross_excess"],
                "local_turnover": result["turnover"],
                "local_rank_ic": result["rank_ic"],
                "local_ic_mean": result["ic_mean"],
                "local_stock_count_mean": result["stock_count_mean"],
                "platform_rank_ic": result["platform_rank_ic"],
                "platform_ic_mean": result["platform_ic_mean"],
                "platform_gross_excess": result["platform_gross_excess"],
                "platform_turnover": result["platform_turnover"],
                "top20_overlap": result["top20_overlap"],
                "periods": result["periods"],
                "date_source": date_source,
                "platform_chart_periods": len(platform["dates"]),
                "fidelity": fidelity_note(handler),
                "tie_break_proxy": result["tie_break_proxy"],
            }
            rows.append(output)
            print(
                f"{record['id']}: local_net={result['net_excess']!s} platform_net={record['platform_net_excess_pct'] / 100:.6f} "
                f"rank_ic={result['rank_ic']!s} top20={result['top20_overlap']!s}/20",
                flush=True,
            )
        del values

    rows.sort(key=lambda row: row["id"])
    output_root = Path(args.output)
    write_outputs(
        supported,
        unsupported,
        rows,
        output_root,
        args.universe,
        len(pool),
        data_start,
        args.label_offset,
        args.market_cap_field,
        args.platform_net_filter,
        frame.attrs.get("market_field_sources"),
    )
    print(
        f"report={output_root / f'{args.platform_net_filter}_factor_local_compare.md'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
