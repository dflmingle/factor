#!/usr/bin/env python3
"""Point-in-time financial factor construction from the local Tushare cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from platform_alignment_rules import CFP_PROXY_BY_HANDLER


MARKET_HANDLERS = {
    "size_only",
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
}


FINANCIAL_HANDLERS = {
    "value_bm",
    "value_sp",
    "reversal_bm_eq",
    "reversal_bm_rev2",
    "reversal_bm_val2",
    "reversal_bm_cfp",
    "reversal_bm_cfp_rev2",
    "reversal_bm_cfp_rev3",
    "reversal_bm_cfp_val2",
    "reversal_bm_cfp_val3",
    "reversal_bm_cfp_sp",
    "reversal_bm_ep_cfp",
    "reversal_bm_ma63",
    "reversal_bm_tsrank756",
    "reversal_bm_cfp_ma63",
    "reversal_bm_cfp_tsrank756",
    "reversal_bm_interact",
    "reversal_bm_cfp_pcf",
    "asset_growth",
    "paper_composite",
    "paper_composite_nomcap",
    "reversal_turn_paper",
    "reversal_turn_paper_nomcap",
    "reversal_chip_turn_paper",
    "fscore_interact",
    "fscore_eq",
    "residual_volatility",
    "book_to_market_lf_minus_size",
    "t10_size_plus_wc_mcap",
    "t10_size_plus_impact_bm",
    "t10_size_plus_impact_wc",
    "t10_size_plus_impact_fscore",
    "book_to_market_lf_plus_impact",
    "ev_ebitda_proxy",
    "reversal20_growth_net",
    "growth_operating_cashflow_reversal20",
    "growth_broad_reversal20",
    "growth_revenue",
    "growth_roe",
    "growth_net_profit",
    "growth_ocf",
    "quality_roe",
    "quality_roe_lyr",
    "quality_cash_debt",
    "quality_roic",
    "quality_roa_tsrank756",
    "quality_roe_tsrank756",
    "quality_gross_margin_tsrank756",
    "quality_oper_profit_tsrank756",
    "quality_net_margin_tsrank378",
    "quality_asset_turnover_tsrank378",
    "value_ep",
    "value_pcf",
    "value_ep_tsrank126",
    "cash_conversion",
    "profitability",
    "reversal_bm_ep",
    "reversal_bm_ep_cfp",
    "reversal_bm_ep_roe",
    "reversal_bm_roe_eq",
    "reversal_ep_eq",
    "value_eq",
    "style_eq",
    "residual_volatility_max_interact",
}


CFP_PROXIES = {
    "ocf_ttm_mv",
    "fcf_ttm_mv",
    "cfps_cur_price",
    "ocfps_cur_price",
    "cfps_lyr_price",
    "ocfps_lyr_price",
}


def _as_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _normalise_table(frame: pd.DataFrame, endpoint: str) -> pd.DataFrame:
    result = frame.copy()
    result["instrument"] = result["ts_code"].astype(str)
    for column in ["ann_date", "f_ann_date", "end_date"]:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce").dt.normalize()
    if "update_flag" in result.columns:
        result["update_flag"] = pd.to_numeric(result["update_flag"], errors="coerce").fillna(-1)
    else:
        result["update_flag"] = -1

    if endpoint == "fina_indicator" and "end_type" not in result.columns:
        month = result["end_date"].dt.month
        result["end_type"] = month.map({3: "1", 6: "2", 9: "3", 12: "4"})

    keys = ["instrument", "ann_date", "end_date"]
    for column in ["report_type", "comp_type"]:
        if column in result.columns:
            keys.append(column)
    result = result.sort_values(keys + ["update_flag"])
    result = result.drop_duplicates(keys, keep="last")
    numeric = [
        column
        for column in result.columns
        if column not in {"ts_code", "instrument", "ann_date", "f_ann_date", "end_date", "end_type", "report_type", "comp_type"}
    ]
    return _as_numeric(result, numeric).reset_index(drop=True)


def _prefer_consolidated(frame: pd.DataFrame) -> pd.DataFrame:
    """Prefer consolidated statements per instrument, with a per-name fallback."""
    if "comp_type" not in frame.columns:
        return frame
    is_consolidated = frame["comp_type"].astype(str).eq("1")
    has_consolidated = is_consolidated.groupby(frame["instrument"]).transform("any")
    keep = is_consolidated | ~has_consolidated
    return frame.loc[keep].copy()


def _quarter_number(value: pd.Timestamp) -> int | None:
    if pd.isna(value):
        return None
    month = int(value.month)
    return {3: 1, 6: 2, 9: 3, 12: 4}.get(month)


def _quarter_end(year: int, quarter: int) -> pd.Timestamp:
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[quarter]
    return pd.Timestamp(year=year, month=month_day[0], day=month_day[1])


def _make_ttm(frame: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    """Convert cumulative quarterly statements into point-in-time TTM rows."""
    available_columns = [column for column in value_columns if column in frame.columns]
    output: list[dict[str, Any]] = []
    if not available_columns:
        return pd.DataFrame(columns=["instrument", "ann_date", "end_date"])

    # The old implementation rebuilt every discrete quarter for every report
    # row.  That is quadratic in the number of filings and became very slow
    # once the full Tushare statement field set was enabled.  A quarter's
    # discrete value depends only on itself and the immediately preceding
    # cumulative quarter, so update those two entries incrementally.
    for instrument, group in frame.groupby("instrument", sort=False, observed=True):
        group = group.sort_values(["ann_date", "end_date", "update_flag"])
        end_dates = pd.to_datetime(group["end_date"]).tolist()
        ann_dates = pd.to_datetime(group["ann_date"]).tolist()
        values = group[available_columns].to_numpy(dtype=float, na_value=np.nan)
        period_values: dict[pd.Timestamp, np.ndarray] = {}
        discrete_values: dict[pd.Timestamp, np.ndarray] = {}

        for ann_date, end_date, raw_values in zip(ann_dates, end_dates, values):
            quarter = _quarter_number(end_date)
            if pd.isna(end_date) or pd.isna(ann_date) or quarter is None:
                continue

            period_values[end_date] = raw_values.copy()
            if quarter == 1:
                discrete_values[end_date] = raw_values.copy()
            else:
                previous_period = _quarter_end(end_date.year, quarter - 1)
                previous = period_values.get(previous_period)
                if previous is None:
                    discrete_values[end_date] = np.full(raw_values.shape, np.nan)
                else:
                    discrete_values[end_date] = raw_values - previous

            # A revised quarter also changes the discrete value of the next
            # quarter if that quarter has already been observed.
            next_quarter = quarter + 1
            next_year = end_date.year
            if next_quarter == 5:
                next_quarter = 1
                next_year += 1
            next_period = _quarter_end(next_year, next_quarter)
            next_values = period_values.get(next_period)
            if next_values is not None:
                discrete_values[next_period] = next_values - raw_values

            periods = sorted(
                period
                for period, period_values_for_row in discrete_values.items()
                if period <= end_date and np.isfinite(period_values_for_row).any()
            )
            if len(periods) < 4:
                continue
            last_four = periods[-4:]
            stacked = np.stack([discrete_values[period] for period in last_four])
            valid = np.isfinite(stacked).all(axis=0)
            ttm_values = stacked.sum(axis=0, where=np.isfinite(stacked), initial=0.0)
            result: dict[str, Any] = {
                "instrument": instrument,
                "ann_date": ann_date,
                "end_date": end_date,
            }
            for column, value, is_valid in zip(available_columns, ttm_values, valid):
                if is_valid:
                    result[f"ttm_{column}"] = float(value)
            if len(result) > 3:
                output.append(result)
    return pd.DataFrame(output)


def _ttm_value_columns(frame: pd.DataFrame) -> list[str]:
    """Select cumulative statement columns for generic TTM reconstruction."""
    metadata = {
        "ts_code",
        "instrument",
        "ann_date",
        "f_ann_date",
        "end_date",
        "end_type",
        "report_type",
        "comp_type",
        "update_flag",
    }
    # Per-share values are point-in-period indicators, not additive flows.
    return [
        column
        for column in frame.columns
        if column not in metadata
        and not column.lower().endswith(("_eps", "eps"))
    ]


def load_financial_cache(root: Path) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for endpoint in ["fina_indicator", "income", "balancesheet", "cashflow"]:
        paths = sorted((root / endpoint).glob("batch_*.parquet"))
        if not paths:
            raise FileNotFoundError(f"Missing financial cache: {root / endpoint}")
        frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
        normalized = _normalise_table(frame, endpoint)
        if endpoint in {"income", "balancesheet", "cashflow"}:
            normalized = _prefer_consolidated(normalized)
        result[endpoint] = normalized

    result["income_ttm"] = _make_ttm(
        result["income"],
        _ttm_value_columns(result["income"]),
    )
    result["cashflow_ttm"] = _make_ttm(
        result["cashflow"],
        _ttm_value_columns(result["cashflow"]),
    )
    return result


def _asof(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    if right.empty:
        return pd.DataFrame(index=left.index)
    right = right.dropna(subset=["ann_date"])
    if right.empty:
        return pd.DataFrame(index=left.index)
    left_sorted = left.sort_values(["date", "instrument"])
    right_sorted = right.sort_values(["ann_date", "instrument"])
    return pd.merge_asof(
        left_sorted,
        right_sorted,
        left_on="date",
        right_on="ann_date",
        by="instrument",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("row_id")


def _attach(
    signal: pd.DataFrame,
    right: pd.DataFrame,
    suffix: str,
    keep_columns: list[str] | None = None,
) -> pd.DataFrame:
    if right.empty:
        return signal
    keys = {"instrument", "ann_date", "f_ann_date", "end_date", "end_type", "report_type", "comp_type", "update_flag"}
    columns = keep_columns or [column for column in right.columns if column not in keys and column != "ts_code"]
    columns = [column for column in columns if column in right.columns]
    if not columns:
        return signal
    joined = _asof(signal[["row_id", "instrument", "date"]], right[["instrument", "ann_date"] + columns])
    joined = joined.set_index("row_id")[columns]
    if suffix:
        joined = joined.add_suffix(suffix)
    return signal.join(joined, on="row_id")


def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return an aligned numeric column even when a cache field is absent."""
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _coalesce_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Use the first available PIT field, retaining row-level fallbacks."""
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    for column in columns:
        result = result.combine_first(_numeric_series(frame, column))
    return result


def _annual(frame: pd.DataFrame) -> pd.DataFrame:
    if "end_type" not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame[frame["end_type"].astype(str).eq("4")].copy()


def _rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates, sort=False, observed=True).rank(method="average", pct=True)


def _zscore(values: pd.Series, dates: pd.Series) -> pd.Series:
    grouped = values.groupby(dates, sort=False, observed=True)
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return values.sub(mean).div(std)


def _rolling(frame: pd.DataFrame, column: str, window: int, method: str) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)[column]
    values = getattr(grouped.rolling(window=window, min_periods=window), method)()
    return values.reset_index(level=0, drop=True).reindex(frame.index)


def _market_raw(frame: pd.DataFrame, variant: str) -> pd.Series:
    """Build the raw 60-day impact statistic used by the new formulas.

    The full-A snapshot historically kept only open/close/volume.  The loader
    supplies high/low/amount from a rich cache when available and otherwise
    supplies explicit open/close proxies, so the calculation remains usable
    without silently claiming exact OHLCV equivalence.
    """
    grouped = frame.groupby("instrument", sort=False, observed=True)
    close = _numeric_series(frame, "close_qfq")
    previous_close = grouped["close_qfq"].shift(1)
    one_day_return = close.div(previous_close).sub(1.0).replace([np.inf, -np.inf], np.nan)
    amount = _numeric_series(frame, "amount")
    if amount.isna().all():
        amount = _numeric_series(frame, "volume").mul(
            _numeric_series(frame, "open_qfq").add(close).div(2.0)
        )
    amount = amount.where(amount.gt(0.0))

    if variant == "h03":
        high = _numeric_series(frame, "high_qfq")
        low = _numeric_series(frame, "low_qfq")
        component = high.sub(low).div(previous_close.add(0.000001))
        work = frame[["instrument"]].copy()
        work["component"] = component
        work["amount"] = amount
        return _rolling(work, "component", 60, "sum").div(
            _rolling(work, "amount", 60, "sum").add(1.0)
        )

    if variant == "abs_return":
        component = one_day_return.abs().div(amount.add(1.0)).div(1.0)
        work = frame[["instrument"]].copy()
        work["component"] = component
        return _rolling(work, "component", 60, "sum").div(60.0)

    if variant == "downside":
        component = one_day_return.abs().sub(one_day_return).div(2.0)
        work = frame[["instrument"]].copy()
        work["component"] = component
        work["amount"] = amount
        return _rolling(work, "component", 60, "sum").div(
            _rolling(work, "amount", 60, "sum").add(1.0)
        )

    if variant == "aggregate":
        work = frame[["instrument"]].copy()
        work["component"] = one_day_return.abs()
        work["amount"] = amount
        return _rolling(work, "component", 60, "sum").div(
            _rolling(work, "amount", 60, "sum").add(1.0)
        )

    raise KeyError(f"Unsupported impact variant: {variant}")


def _residual_volatility(frame: pd.DataFrame, window: int = 252) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)
    ret = frame["close_qfq"].div(grouped["close_qfq"].shift(1)).sub(1.0)
    market = ret.groupby(frame["date"], sort=False, observed=True).transform("mean")
    work = frame[["instrument"]].copy()
    work["ret"] = ret
    work["market"] = market
    work["ret_market"] = ret * market
    work["ret_sq"] = ret * ret
    work["market_sq"] = market * market
    ret_mean = _rolling(work, "ret", window, "mean")
    market_mean = _rolling(work, "market", window, "mean")
    cross_mean = _rolling(work, "ret_market", window, "mean")
    market_sq_mean = _rolling(work, "market_sq", window, "mean")
    beta = cross_mean.sub(ret_mean.mul(market_mean)).div(
        market_sq_mean.sub(market_mean.mul(market_mean)).replace(0.0, np.nan)
    )
    residual = ret.sub(beta.mul(market))
    residual_mean = _rolling(work.assign(residual=residual), "residual", window, "mean")
    residual_sq_mean = _rolling(work.assign(residual=residual * residual), "residual", window, "mean")
    return residual_sq_mean.sub(residual_mean.mul(residual_mean)).clip(lower=0.0).pow(0.5)


def _comparison(left: pd.Series, right: pd.Series, op: str) -> pd.Series:
    valid = left.notna() & right.notna()
    if op == ">":
        result = left.gt(right)
    else:
        result = left.lt(right)
    return result.astype(float).where(valid)


def _positive(left: pd.Series) -> pd.Series:
    return left.gt(0.0).astype(float).where(left.notna())


def _financial_snapshot(signal: pd.DataFrame, cache: dict[str, pd.DataFrame]) -> pd.DataFrame:
    fina = cache["fina_indicator"]
    fina_lyr = _annual(fina)
    balance = cache["balancesheet"]
    balance_lyr = _annual(balance)
    signal = _attach(signal, fina, "_cur")
    signal = _attach(signal, fina_lyr, "_lyr")
    signal = _attach(signal, balance, "_bs_cur")
    signal = _attach(signal, balance_lyr, "_bs_lyr")
    signal = _attach(signal, cache["income_ttm"], "")
    signal = _attach(signal, cache["cashflow_ttm"], "")
    return signal


def _value_columns(signal: pd.DataFrame) -> pd.DataFrame:
    mv = _numeric_series(signal, "total_mv").replace(0.0, np.nan)
    equity_cur = _numeric_series(signal, "total_hldr_eqy_exc_min_int_bs_cur")
    equity_lyr = _numeric_series(signal, "total_hldr_eqy_exc_min_int_bs_lyr")
    revenue = _numeric_series(signal, "ttm_total_revenue")
    if revenue.isna().all():
        revenue = _numeric_series(signal, "ttm_revenue")
    net_income = _numeric_series(signal, "ttm_n_income_attr_p")
    ocf = _numeric_series(signal, "ttm_n_cashflow_act")
    signal["ratio_bm_ttm"] = equity_cur.div(mv)
    # PandaAI's *_lf field is the latest reported (MRQ) balance-sheet value.
    signal["book_to_market_ratio_lf"] = equity_cur.div(mv)
    signal["book_to_market_ratio_lyr"] = equity_lyr.div(mv)
    signal["ratio_sp_ttm"] = revenue.div(mv)
    signal["ratio_ep_ttm"] = net_income.div(mv)
    signal["ratio_cfp_ttm"] = ocf.div(mv)
    signal["ratio_pcf_ocf_ttm"] = mv.div(ocf.where(ocf.abs() > 1e-12))
    signal["cfd_surplus_cash_multi_ttm"] = ocf.div(net_income.where(net_income.abs() > 1e-12))
    return signal


def _market_snapshot(frame: pd.DataFrame, dates: list[pd.Timestamp]) -> pd.DataFrame:
    work = frame.copy()
    work["row_id"] = np.arange(len(work), dtype=np.int64)
    grouped = work.groupby("instrument", sort=False, observed=True)
    work["ret40"] = work["close_qfq"].div(grouped["close_qfq"].shift(40)).sub(1.0)
    turn21 = _rolling(work, "turnover", 21, "mean")
    turn504 = _rolling(work, "turnover", 504, "mean")
    work["turn_signal"] = 1.0 - turn21.div(turn504.replace(0.0, np.nan))
    weighted_price = work["volume"] * (work["open_qfq"] + work["close_qfq"]) / 2.0
    weighted = work.assign(_weighted_price=weighted_price)
    vwap = _rolling(weighted, "_weighted_price", 250, "sum").div(_rolling(work, "volume", 250, "sum"))
    work["chip"] = vwap.div(work["close_qfq"]).sub(1.0)
    return work[work["date"].isin(dates)].copy()


def _base_signal(frame: pd.DataFrame, dates: list[pd.Timestamp]) -> pd.DataFrame:
    selected = _market_snapshot(frame, dates)
    selected = _financial_snapshot(selected, _FINANCIAL_CACHE)
    selected = _value_columns(selected)
    return selected


def _add_market_ranks(selected: pd.DataFrame) -> pd.DataFrame:
    dates_series = selected["date"]
    selected["rev_rank"] = _rank(1.0 - selected["ret40"], dates_series)
    selected["turn_rank"] = _rank(selected["turn_signal"], dates_series)
    selected["chip_rank"] = _rank(selected["chip"], dates_series)
    selected["cap_rank"] = _rank(selected["total_mv"], dates_series)
    selected["size_rank"] = _rank(-selected["cap_rank"], dates_series)
    return selected


def _selected_full_series(selected: pd.DataFrame, values: pd.Series) -> pd.Series:
    result = values.reindex(selected["row_id"].to_numpy())
    result.index = selected.index
    return result


def _materialize_factor(
    frame: pd.DataFrame,
    selected: pd.DataFrame,
    factor: pd.Series,
) -> pd.Series:
    values = pd.Series(np.nan, index=frame.index, dtype=float)
    values.loc[selected["row_id"].to_numpy(dtype=np.int64)] = pd.to_numeric(
        factor, errors="coerce"
    ).to_numpy()
    return values


def _direct_cfp_ratio(selected: pd.DataFrame, proxy: str) -> pd.Series:
    """Build one of the cash-flow proxies on the point-in-time snapshot."""
    if proxy == "ocf_ttm_mv":
        return selected["ratio_cfp_ttm"]
    if proxy == "fcf_ttm_mv":
        numerator = _numeric_series(selected, "ttm_free_cashflow")
        denominator = _numeric_series(selected, "total_mv")
        return numerator.div(denominator.replace(0.0, np.nan))
    if proxy not in CFP_PROXIES:
        raise KeyError(f"Unsupported CFP proxy: {proxy}")
    field, suffix = proxy.split("_", 1)
    if suffix not in {"cur_price", "lyr_price"}:
        raise KeyError(f"Unsupported CFP proxy: {proxy}")
    period_suffix = "_cur" if suffix == "cur_price" else "_lyr"
    numerator = _numeric_series(selected, f"{field}{period_suffix}")
    denominator = _numeric_series(selected, "close_qfq")
    return numerator.div(denominator.replace(0.0, np.nan))


def _historical_ratio_rank(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    ratio: str,
    window: int,
    operation: str,
) -> pd.Series:
    """Rank a daily point-in-time ratio after applying a time-series mean.

    Financial values are forward-filled from their announcement dates.  Only
    the fields needed for the requested ratio are attached to the daily price
    panel so the historical window does not duplicate the full finance cache.
    """
    if not dates:
        return pd.Series(dtype=float)
    cache_key = (id(frame), tuple(dates), ratio, window, operation)
    cached = _HISTORICAL_RANK_CACHE.get(cache_key)
    if cached is not None:
        return cached
    first_date = min(dates)
    last_date = max(dates)
    history = frame[
        frame["date"].between(first_date - pd.Timedelta(days=1400), last_date)
    ][["date", "instrument", "total_mv", "close_qfq"]].copy()
    history["row_id"] = history.index.to_numpy(dtype=np.int64)

    if ratio == "bm":
        history = _attach(
            history,
            cache["balancesheet"],
            "_bs_cur",
            ["total_hldr_eqy_exc_min_int"],
        )
        history = _value_columns(history)
        ratio_values = history["ratio_bm_ttm"]
    elif ratio == "cfp":
        history = _attach(
            history,
            cache["cashflow_ttm"],
            "",
            ["ttm_n_cashflow_act"],
        )
        history = _value_columns(history)
        ratio_values = history["ratio_cfp_ttm"]
    elif ratio in CFP_PROXIES:
        if ratio == "ocf_ttm_mv":
            history = _attach(
                history,
                cache["cashflow_ttm"],
                "",
                ["ttm_n_cashflow_act"],
            )
            numerator = _numeric_series(history, "ttm_n_cashflow_act")
            denominator = _numeric_series(history, "total_mv")
        elif ratio == "fcf_ttm_mv":
            history = _attach(
                history,
                cache["cashflow_ttm"],
                "",
                ["ttm_free_cashflow"],
            )
            numerator = _numeric_series(history, "ttm_free_cashflow")
            denominator = _numeric_series(history, "total_mv")
        else:
            field, suffix = ratio.split("_", 1)
            if suffix == "cur_price":
                table = cache["fina_indicator"]
                table_suffix = "_cur"
            elif suffix == "lyr_price":
                table = _annual(cache["fina_indicator"])
                table_suffix = "_lyr"
            else:
                raise KeyError(f"Unsupported CFP proxy: {ratio}")
            history = _attach(history, table, table_suffix, [field])
            numerator = _numeric_series(history, f"{field}{table_suffix}")
            denominator = _numeric_series(history, "close_qfq")
        ratio_values = numerator.div(denominator.replace(0.0, np.nan))
    elif ratio == "ep":
        history = _attach(
            history,
            cache["income_ttm"],
            "",
            ["ttm_n_income_attr_p", "ttm_n_income"],
        )
        numerator = _coalesce_numeric(history, ["ttm_n_income_attr_p", "ttm_n_income"])
        denominator = _numeric_series(history, "total_mv")
        ratio_values = numerator.div(denominator.replace(0.0, np.nan))
    elif ratio == "pcf":
        history = _attach(
            history,
            cache["cashflow_ttm"],
            "",
            ["ttm_n_cashflow_act"],
        )
        numerator = _numeric_series(history, "total_mv")
        denominator = _numeric_series(history, "ttm_n_cashflow_act")
        ratio_values = numerator.div(denominator.replace(0.0, np.nan))
    else:
        raise KeyError(f"Unsupported historical ratio: {ratio}")

    history["ratio"] = ratio_values
    history = history.sort_values(["instrument", "date"])
    if operation == "ma":
        history["ratio_transformed"] = _rolling(history, "ratio", window, "mean")
    elif operation == "ts_rank":
        grouped = history.groupby("instrument", sort=False, observed=True)["ratio"]
        values = grouped.rolling(window=window, min_periods=window).rank(pct=True)
        history["ratio_transformed"] = values.reset_index(level=0, drop=True).reindex(history.index)
    else:
        raise KeyError(f"Unsupported historical ratio operation: {operation}")
    selected = history[history["date"].isin(dates)]
    ranks = _rank(selected["ratio_transformed"], selected["date"])
    result = pd.Series(ranks.to_numpy(), index=selected["row_id"].to_numpy(), dtype=float)
    _HISTORICAL_RANK_CACHE[cache_key] = result
    return result


def _historical_indicator_rank(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    field: str,
    window: int,
) -> pd.Series:
    """Rank a point-in-time financial indicator after its daily time-series rank."""
    if not dates:
        return pd.Series(dtype=float)
    cache_key = (id(frame), tuple(dates), "indicator", field, window)
    cached = _HISTORICAL_RANK_CACHE.get(cache_key)
    if cached is not None:
        return cached
    first_date = min(dates)
    last_date = max(dates)
    history = frame[
        frame["date"].between(first_date - pd.Timedelta(days=1400), last_date)
    ][["date", "instrument"]].copy()
    history["row_id"] = history.index.to_numpy(dtype=np.int64)
    history = _attach(history, cache["fina_indicator"], "_cur", [field])
    value = _numeric_series(history, f"{field}_cur")
    history["value"] = value
    history = history.sort_values(["instrument", "date"]).reset_index(drop=True)
    grouped = history.groupby("instrument", sort=False, observed=True)["value"]
    ts_rank = grouped.rolling(window=window, min_periods=window).rank(pct=True)
    history["ts_rank"] = ts_rank.reset_index(level=0, drop=True).reindex(history.index)
    selected = history[history["date"].isin(dates)]
    ranks = _rank(selected["ts_rank"], selected["date"])
    result = pd.Series(ranks.to_numpy(), index=selected["row_id"].to_numpy(), dtype=float)
    _HISTORICAL_RANK_CACHE[cache_key] = result
    return result


def _ttm_ratio_history(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    numerator_columns: list[str],
    denominator_columns: list[str],
    average_denominator: bool = False,
    lag: int = 252,
) -> pd.DataFrame:
    """Build a daily PIT TTM ratio from announced income and balance data."""
    if not dates:
        return pd.DataFrame()
    first_date = min(dates)
    last_date = max(dates)
    history = frame[
        frame["date"].between(first_date - pd.Timedelta(days=1500), last_date)
    ][["date", "instrument"]].copy()
    history["row_id"] = history.index.to_numpy(dtype=np.int64)
    history = _attach(history, cache["income_ttm"], "", numerator_columns)
    history = _attach(
        history,
        cache["balancesheet"],
        "_bs",
        denominator_columns,
    )
    history["_numerator"] = _coalesce_numeric(history, numerator_columns)
    history["_denominator"] = _coalesce_numeric(
        history,
        [f"{column}_bs" for column in denominator_columns],
    )
    history = history.sort_values(["instrument", "date"]).reset_index(drop=True)
    if average_denominator:
        previous = history.groupby(
            "instrument", sort=False, observed=True
        )["_denominator"].shift(lag)
        history["_denominator"] = history["_denominator"].add(previous).div(2.0)
    history["ratio"] = history["_numerator"].div(
        history["_denominator"].replace(0.0, np.nan)
    )
    return history


def _historical_ttm_ratio_rank(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    numerator_columns: list[str],
    denominator_columns: list[str],
    window: int,
) -> pd.Series:
    """Cross-sectionally rank a strict time-series rank of a PIT TTM ratio."""
    cache_key = (
        id(frame),
        tuple(dates),
        "ttm_ratio",
        tuple(numerator_columns),
        tuple(denominator_columns),
        window,
    )
    cached = _HISTORICAL_RANK_CACHE.get(cache_key)
    if cached is not None:
        return cached
    history = _ttm_ratio_history(
        frame,
        dates,
        cache,
        numerator_columns,
        denominator_columns,
    )
    if history.empty:
        return pd.Series(dtype=float)
    grouped = history.groupby("instrument", sort=False, observed=True)["ratio"]
    ts_rank = grouped.rolling(window=window, min_periods=window).rank(pct=True)
    history["ts_rank"] = ts_rank.reset_index(level=0, drop=True).reindex(
        history.index
    )
    selected = history[history["date"].isin(dates)]
    ranks = _rank(selected["ts_rank"], selected["date"])
    result = pd.Series(ranks.to_numpy(), index=selected["row_id"].to_numpy(), dtype=float)
    _HISTORICAL_RANK_CACHE[cache_key] = result
    return result


def _historical_ttm_growth_rank(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    numerator_columns: list[str],
    denominator_columns: list[str],
    lag: int = 252,
) -> pd.Series:
    """Rank year-over-year growth of a daily PIT TTM ratio."""
    cache_key = (
        id(frame),
        tuple(dates),
        "ttm_growth",
        tuple(numerator_columns),
        tuple(denominator_columns),
        lag,
    )
    cached = _HISTORICAL_RANK_CACHE.get(cache_key)
    if cached is not None:
        return cached
    history = _ttm_ratio_history(
        frame,
        dates,
        cache,
        numerator_columns,
        denominator_columns,
        average_denominator=True,
        lag=lag,
    )
    if history.empty:
        return pd.Series(dtype=float)
    previous = history.groupby(
        "instrument", sort=False, observed=True
    )["ratio"].shift(lag)
    history["growth"] = history["ratio"].div(
        previous.replace(0.0, np.nan)
    ).sub(1.0)
    selected = history[history["date"].isin(dates)]
    ranks = _rank(selected["growth"], selected["date"])
    result = pd.Series(ranks.to_numpy(), index=selected["row_id"].to_numpy(), dtype=float)
    _HISTORICAL_RANK_CACHE[cache_key] = result
    return result


_FINANCIAL_CACHE: dict[str, pd.DataFrame] = {}
_HISTORICAL_RANK_CACHE: dict[tuple[Any, ...], pd.Series] = {}


def _working_capital_to_market(selected: pd.DataFrame) -> pd.Series:
    """Rebuild (current assets - inventory - current liabilities) / market cap."""
    mv = _numeric_series(selected, "total_mv").abs()
    current_assets = _coalesce_numeric(
        selected,
        [
            "total_cur_assets_bs_cur",
            "total_cur_assets_bs_lyr",
            "total_assets_bs_cur",
            "total_assets_bs_lyr",
        ],
    )
    inventory = _coalesce_numeric(
        selected,
        ["inventories_bs_cur", "inventories_bs_lyr", "inventory_bs_cur", "inventory_bs_lyr"],
    ).fillna(0.0)
    current_liabilities = _coalesce_numeric(
        selected,
        [
            "total_cur_liab_bs_cur",
            "total_cur_liab_bs_lyr",
            "current_liabilities_bs_cur",
            "current_liabilities_bs_lyr",
            "total_liab_bs_cur",
            "total_liab_bs_lyr",
        ],
    )
    return current_assets.sub(inventory).sub(current_liabilities).div(mv.add(1.0))


def _ev_to_ebitda_proxy(selected: pd.DataFrame) -> pd.Series:
    """Use the closest available PIT enterprise-value / EBITDA inputs."""
    mv = _numeric_series(selected, "total_mv").abs()
    liabilities = _coalesce_numeric(
        selected,
        ["total_liab_bs_cur", "total_liab_bs_lyr"],
    ).fillna(0.0)
    cash = _coalesce_numeric(
        selected,
        [
            "money_cap_bs_cur",
            "money_cap_bs_lyr",
            "cash_reser_bs_cur",
            "cash_reser_bs_lyr",
            "cash_equivalent_bs_cur",
            "cash_equivalent_bs_lyr",
        ],
    ).fillna(0.0)
    enterprise_value = mv.add(liabilities).sub(cash)
    ebitda = _coalesce_numeric(
        selected,
        ["ttm_ebitda", "ttm_ebit", "ttm_operate_profit"],
    )
    return enterprise_value.div(ebitda.where(ebitda.abs().gt(1e-12)))


def build_market_factor(
    frame: pd.DataFrame,
    handler: str,
    dates: list[pd.Timestamp],
) -> pd.Series:
    """Build the newly supported market-only formulas without finance joins."""
    selected = _market_snapshot(frame, dates)
    _add_market_ranks(selected)
    dates_series = selected["date"]

    impact_rank_cache: dict[str, pd.Series] = {}

    def impact_rank(variant: str) -> pd.Series:
        if variant not in impact_rank_cache:
            impact_rank_cache[variant] = _rank(
                _selected_full_series(selected, _market_raw(frame, variant)),
                dates_series,
            )
        return impact_rank_cache[variant]

    if handler == "size_only":
        factor = selected["cap_rank"]
    elif handler == "impact60":
        factor = impact_rank("h03")
    elif handler == "impact_abs_return60":
        factor = impact_rank("abs_return")
    elif handler == "impact_downside60":
        factor = impact_rank("downside")
    elif handler == "impact_aggregate60":
        factor = impact_rank("aggregate")
    elif handler == "t10_size_plus_impact":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
        ) / 5.0
    elif handler == "t10_size_plus_impact_g13":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + impact_rank("abs_return")
        ) / 6.0
    elif handler == "t10_size_plus_impact_dd120":
        grouped = frame.groupby("instrument", sort=False, observed=True)
        rolling_max = grouped["close_qfq"].rolling(window=120, min_periods=120).max()
        rolling_max = rolling_max.reset_index(level=0, drop=True).reindex(frame.index)
        drawdown = _rank(
            1.0
            - _selected_full_series(
                selected,
                frame["close_qfq"].div(rolling_max),
            ),
            dates_series,
        )
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + drawdown
        ) / 6.0
    elif handler == "t10_size_plus_impact_downside":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + impact_rank("downside")
        ) / 6.0
    elif handler == "t10_size_plus_impact_aggregate":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + impact_rank("aggregate")
        ) / 6.0
    elif handler == "t10_nomcap_plus_impact":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + impact_rank("h03")
        ) / 4.0
    else:
        raise KeyError(f"Unsupported market handler: {handler}")

    return _materialize_factor(frame, selected, factor)


def build_financial_factor(
    frame: pd.DataFrame,
    handler: str,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
) -> pd.Series:
    global _FINANCIAL_CACHE
    _FINANCIAL_CACHE = cache
    selected = _base_signal(frame, dates)
    _add_market_ranks(selected)
    dates_series = selected["date"]
    selected["bm_rank"] = _rank(selected["ratio_bm_ttm"], dates_series)
    selected["bm_lf_rank"] = _rank(selected["book_to_market_ratio_lf"], dates_series)
    selected["bm_lyr_rank"] = _rank(selected["book_to_market_ratio_lyr"], dates_series)
    selected["sp_rank"] = _rank(selected["ratio_sp_ttm"], dates_series)
    cfp_proxy = CFP_PROXY_BY_HANDLER.get(handler, "ocf_ttm_mv")
    if handler in {"reversal_bm_cfp_ma63", "reversal_bm_cfp_tsrank756"}:
        operation = "ma" if handler.endswith("ma63") else "ts_rank"
        window = 63 if operation == "ma" else 756
        historical_cfp = _historical_ratio_rank(
            frame, dates, cache, cfp_proxy, window, operation
        )
        selected["cfp_rank"] = selected["row_id"].map(historical_cfp)
    else:
        selected["cfp_rank"] = _rank(
            _direct_cfp_ratio(selected, cfp_proxy), dates_series
        )
    selected["ep_rank"] = _rank(selected["ratio_ep_ttm"], dates_series)
    selected["pcf_rank"] = _rank(selected["ratio_pcf_ocf_ttm"], dates_series)

    selected["oper_roe_lyr_rank"] = _rank(_numeric_series(selected, "roe_lyr"), dates_series)
    growth = _numeric_series(selected, "assets_yoy_lyr")
    selected["growth"] = growth
    selected["growth_rank"] = _rank(growth, dates_series)
    selected["paper_score"] = (
        _zscore(selected["bm_lyr_rank"], dates_series)
        + _zscore(selected["oper_roe_lyr_rank"], dates_series)
        - _zscore(selected["growth_rank"], dates_series)
        - _zscore(selected["cap_rank"], dates_series)
    )
    selected["paper_rank"] = _rank(selected["paper_score"], dates_series)
    selected["paper_nomcap_score"] = (
        _zscore(selected["bm_lyr_rank"], dates_series)
        + _zscore(selected["oper_roe_lyr_rank"], dates_series)
        - _zscore(selected["growth_rank"], dates_series)
    )
    selected["paper_nomcap_rank"] = _rank(selected["paper_nomcap_score"], dates_series)

    impact_rank_cache: dict[str, pd.Series] = {}

    def impact_rank(variant: str) -> pd.Series:
        if variant not in impact_rank_cache:
            impact_rank_cache[variant] = _rank(
                _selected_full_series(selected, _market_raw(frame, variant)),
                dates_series,
            )
        return impact_rank_cache[variant]

    def drawdown_rank(window: int) -> pd.Series:
        grouped = frame.groupby("instrument", sort=False, observed=True)
        rolling_max = grouped["close_qfq"].rolling(window=window, min_periods=window).max()
        rolling_max = rolling_max.reset_index(level=0, drop=True).reindex(frame.index)
        raw = 1.0 - _selected_full_series(
            selected,
            frame["close_qfq"].div(rolling_max),
        )
        return _rank(raw, dates_series)

    selected["wc_rank"] = _rank(_working_capital_to_market(selected), dates_series)

    roe_cur = _numeric_series(selected, "roe_cur")
    roe_lyr = _numeric_series(selected, "roe_lyr")
    if roe_lyr.isna().all():
        roe_lyr = _numeric_series(selected, "roe_dt_lyr")
    roa_cur = _numeric_series(selected, "roa_yearly_cur")
    roa_lyr = _numeric_series(selected, "roa_yearly_lyr")
    if roa_cur.isna().all():
        roa_cur = _numeric_series(selected, "roa_cur")
    if roa_lyr.isna().all():
        roa_lyr = _numeric_series(selected, "roa_lyr")
    debt_cur = _numeric_series(selected, "debt_to_assets_cur")
    debt_lyr = _numeric_series(selected, "debt_to_assets_lyr")
    current_cur = _numeric_series(selected, "current_ratio_cur")
    current_lyr = _numeric_series(selected, "current_ratio_lyr")
    gross_cur = _numeric_series(selected, "grossprofit_margin_cur")
    gross_lyr = _numeric_series(selected, "grossprofit_margin_lyr")
    turn_cur = _numeric_series(selected, "assets_turn_cur")
    turn_lyr = _numeric_series(selected, "assets_turn_lyr")
    ocf_debt = _numeric_series(selected, "ocf_to_debt_cur")
    cash_multi = _numeric_series(selected, "cfd_surplus_cash_multi_ttm")
    score = sum(
        [
            _positive(roa_cur),
            _positive(ocf_debt),
            _comparison(roa_cur, roa_lyr, ">"),
            _positive(cash_multi.sub(1.0)),
            _comparison(debt_lyr, debt_cur, ">"),
            _comparison(current_cur, current_lyr, ">"),
            _comparison(gross_cur, gross_lyr, ">"),
            _comparison(turn_cur, turn_lyr, ">"),
        ]
    )
    selected["fscore_rank"] = _rank(score, dates_series)

    growth_net = _coalesce_numeric(selected, ["netprofit_yoy_cur", "netprofit_yoy_lyr"])
    growth_ocf = _coalesce_numeric(selected, ["ocf_yoy_cur", "ocf_yoy_lyr"])
    growth_operating = _coalesce_numeric(selected, ["op_yoy_cur", "op_yoy_lyr"])
    growth_revenue = _coalesce_numeric(selected, ["op_yoy_cur", "op_yoy_lyr"])
    quality_roe = _coalesce_numeric(selected, ["roe_cur", "roe_lyr"])
    quality_roic = _coalesce_numeric(selected, ["roic_cur", "roic_lyr"])
    quality_cash_debt = _coalesce_numeric(selected, ["ocf_to_debt_cur", "ocf_to_debt_lyr"])
    profitability_numerator = _coalesce_numeric(selected, ["ttm_operate_profit", "ttm_ebit"])
    profitability_denominator = _coalesce_numeric(selected, ["ttm_total_revenue", "ttm_revenue"])
    profitability = profitability_numerator.div(profitability_denominator.replace(0.0, np.nan))

    if handler == "value_bm":
        factor = selected["ratio_bm_ttm"]
    elif handler == "value_sp":
        factor = selected["ratio_sp_ttm"]
    elif handler == "asset_growth":
        factor = selected["growth_rank"]
    elif handler == "paper_composite":
        factor = selected["paper_score"]
    elif handler == "paper_composite_nomcap":
        factor = selected["paper_nomcap_score"]
    elif handler == "reversal_turn_paper":
        factor = (selected["rev_rank"] + selected["turn_rank"] + selected["paper_rank"]) / 3.0
    elif handler == "reversal_turn_paper_nomcap":
        factor = (selected["rev_rank"] + selected["turn_rank"] + selected["paper_nomcap_rank"]) / 3.0
    elif handler == "reversal_chip_turn_paper":
        factor = (
            selected["rev_rank"] + selected["chip_rank"] + selected["turn_rank"] + selected["paper_rank"]
        ) / 4.0
    elif handler == "fscore_interact":
        factor = selected["rev_rank"] * selected["fscore_rank"]
    elif handler == "fscore_eq":
        factor = (selected["rev_rank"] + selected["fscore_rank"]) / 2.0
    elif handler == "reversal_bm_eq":
        factor = (selected["rev_rank"] + selected["bm_rank"]) / 2.0
    elif handler == "reversal_bm_rev2":
        factor = (2.0 * selected["rev_rank"] + selected["bm_rank"]) / 3.0
    elif handler == "reversal_bm_val2":
        factor = (selected["rev_rank"] + 2.0 * selected["bm_rank"]) / 3.0
    elif handler == "reversal_bm_cfp":
        factor = (selected["rev_rank"] + selected["bm_rank"] + selected["cfp_rank"]) / 3.0
    elif handler == "reversal_bm_cfp_rev2":
        factor = (2.0 * selected["rev_rank"] + selected["bm_rank"] + selected["cfp_rank"]) / 4.0
    elif handler == "reversal_bm_cfp_rev3":
        factor = (3.0 * selected["rev_rank"] + selected["bm_rank"] + selected["cfp_rank"]) / 5.0
    elif handler == "reversal_bm_cfp_val2":
        factor = (selected["rev_rank"] + 2.0 * selected["bm_rank"] + 2.0 * selected["cfp_rank"]) / 5.0
    elif handler == "reversal_bm_cfp_val3":
        factor = (selected["rev_rank"] + 3.0 * selected["bm_rank"] + 3.0 * selected["cfp_rank"]) / 7.0
    elif handler == "reversal_bm_cfp_sp":
        factor = (
            selected["rev_rank"] + selected["bm_rank"] + selected["cfp_rank"] + selected["sp_rank"]
        ) / 4.0
    elif handler == "reversal_bm_ep_cfp":
        factor = (
            selected["rev_rank"] + selected["bm_rank"] + selected["ep_rank"] + selected["cfp_rank"]
        ) / 4.0
    elif handler == "reversal_bm_ma63":
        bm_ma_rank = _historical_ratio_rank(frame, dates, cache, "bm", 63, "ma")
        selected["bm_ma_rank"] = selected["row_id"].map(bm_ma_rank)
        factor = (selected["rev_rank"] + selected["bm_ma_rank"]) / 2.0
    elif handler == "reversal_bm_tsrank756":
        bm_ts_rank = _historical_ratio_rank(frame, dates, cache, "bm", 756, "ts_rank")
        selected["bm_ts_rank"] = selected["row_id"].map(bm_ts_rank)
        factor = (selected["rev_rank"] + selected["bm_ts_rank"]) / 2.0
    elif handler == "reversal_bm_cfp_ma63":
        bm_ma_rank = _historical_ratio_rank(frame, dates, cache, "bm", 63, "ma")
        cfp_ma_rank = _historical_ratio_rank(frame, dates, cache, cfp_proxy, 63, "ma")
        selected["bm_ma_rank"] = selected["row_id"].map(bm_ma_rank)
        selected["cfp_ma_rank"] = selected["row_id"].map(cfp_ma_rank)
        factor = (
            selected["rev_rank"] + selected["bm_ma_rank"] + selected["cfp_ma_rank"]
        ) / 3.0
    elif handler == "reversal_bm_cfp_tsrank756":
        bm_ts_rank = _historical_ratio_rank(frame, dates, cache, "bm", 756, "ts_rank")
        cfp_ts_rank = _historical_ratio_rank(
            frame, dates, cache, cfp_proxy, 756, "ts_rank"
        )
        selected["bm_ts_rank"] = selected["row_id"].map(bm_ts_rank)
        selected["cfp_ts_rank"] = selected["row_id"].map(cfp_ts_rank)
        factor = (
            selected["rev_rank"] + selected["bm_ts_rank"] + selected["cfp_ts_rank"]
        ) / 3.0
    elif handler == "reversal_bm_interact":
        factor = selected["rev_rank"] * (0.5 + 0.5 * selected["bm_rank"])
    elif handler == "reversal_bm_cfp_pcf":
        factor = (
            selected["rev_rank"]
            + selected["bm_rank"]
            + selected["cfp_rank"]
            + 1.0
            - selected["pcf_rank"]
        ) / 4.0
    elif handler == "book_to_market_lf_minus_size":
        factor = selected["bm_lf_rank"] - selected["cap_rank"]
    elif handler == "t10_size_plus_wc_mcap":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + selected["wc_rank"]
        ) / 5.0
    elif handler == "t10_size_plus_impact_bm":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + selected["bm_lf_rank"]
        ) / 6.0
    elif handler == "t10_size_plus_impact_wc":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + selected["wc_rank"]
        ) / 6.0
    elif handler == "t10_size_plus_impact_fscore":
        factor = (
            selected["rev_rank"]
            + selected["chip_rank"]
            + selected["turn_rank"]
            + selected["size_rank"]
            + impact_rank("h03")
            + selected["fscore_rank"]
        ) / 6.0
    elif handler == "book_to_market_lf_plus_impact":
        factor = selected["bm_lf_rank"] + impact_rank("abs_return")
    elif handler == "ev_ebitda_proxy":
        factor = _rank(-_ev_to_ebitda_proxy(selected), dates_series)
    elif handler == "residual_volatility":
        residual = _residual_volatility(frame)
        selected["residual"] = residual.reindex(selected["row_id"]).to_numpy()
        factor = _rank(-selected["residual"], dates_series)
    elif handler == "residual_volatility_max_interact":
        residual = _residual_volatility(frame)
        selected["residual"] = residual.reindex(selected["row_id"]).to_numpy()
        grouped = frame.groupby("instrument", sort=False, observed=True)
        ret1 = frame["close_qfq"].div(grouped["close_qfq"].shift(1)).sub(1.0)
        max_return = _rolling(
            frame.assign(_ret1=ret1),
            "_ret1",
            21,
            "max",
        )
        selected_max_return = _selected_full_series(selected, max_return)
        factor = _rank(-selected["residual"], dates_series) * _rank(
            -selected_max_return, dates_series
        )
    elif handler == "reversal20_growth_net":
        grouped = frame.groupby("instrument", sort=False, observed=True)
        ret20 = frame["close_qfq"].div(grouped["close_qfq"].shift(20)).sub(1.0)
        factor = _rank(1.0 - _selected_full_series(selected, ret20), dates_series) + _rank(
            growth_net, dates_series
        )
    elif handler == "growth_broad_reversal20":
        grouped = frame.groupby("instrument", sort=False, observed=True)
        ret20 = frame["close_qfq"].div(grouped["close_qfq"].shift(20)).sub(1.0)
        factor = (
            _rank(growth_revenue, dates_series)
            + _rank(growth_operating, dates_series)
            + _rank(growth_net, dates_series)
            + _rank(growth_ocf, dates_series)
        ) / 4.0 - _rank(_selected_full_series(selected, ret20), dates_series)
    elif handler == "growth_operating_cashflow_reversal20":
        grouped = frame.groupby("instrument", sort=False, observed=True)
        ret20 = frame["close_qfq"].div(grouped["close_qfq"].shift(20)).sub(1.0)
        factor = (
            _rank(growth_operating, dates_series)
            + _rank(growth_ocf, dates_series)
        ) / 2.0 - _rank(_selected_full_series(selected, ret20), dates_series)
    elif handler == "growth_revenue":
        factor = _rank(growth_revenue, dates_series)
    elif handler == "growth_roe":
        growth_roe = _historical_ttm_growth_rank(
            frame,
            dates,
            cache,
            ["ttm_n_income_attr_p", "ttm_n_income"],
            ["total_hldr_eqy_exc_min_int"],
        )
        factor = selected["row_id"].map(growth_roe)
    elif handler == "growth_net_profit":
        factor = _rank(growth_net, dates_series)
    elif handler == "growth_ocf":
        factor = _rank(growth_ocf, dates_series)
    elif handler == "quality_roe":
        factor = _rank(quality_roe, dates_series)
    elif handler == "quality_roe_lyr":
        factor = _rank(_coalesce_numeric(selected, ["roe_lyr"]), dates_series)
    elif handler == "quality_cash_debt":
        factor = _rank(quality_cash_debt, dates_series)
    elif handler == "quality_roic":
        factor = _rank(quality_roic, dates_series)
    elif handler == "quality_roa_tsrank756":
        ratio = _historical_ttm_ratio_rank(
            frame,
            dates,
            cache,
            ["ttm_n_income", "ttm_n_income_attr_p"],
            ["total_assets"],
            756,
        )
        factor = selected["row_id"].map(ratio)
    elif handler == "quality_roe_tsrank756":
        ratio = _historical_indicator_rank(frame, dates, cache, "roe", 756)
        factor = selected["row_id"].map(ratio)
    elif handler == "quality_gross_margin_tsrank756":
        ratio = _historical_indicator_rank(frame, dates, cache, "grossprofit_margin", 756)
        factor = selected["row_id"].map(ratio)
    elif handler == "quality_oper_profit_tsrank756":
        ratio = _historical_ttm_ratio_rank(
            frame,
            dates,
            cache,
            ["ttm_operate_profit"],
            ["ttm_n_income", "ttm_n_income_attr_p"],
            756,
        )
        factor = selected["row_id"].map(ratio)
    elif handler == "quality_net_margin_tsrank378":
        ratio = _historical_indicator_rank(frame, dates, cache, "netprofit_margin", 378)
        factor = selected["row_id"].map(ratio)
    elif handler == "quality_asset_turnover_tsrank378":
        ratio = _historical_indicator_rank(frame, dates, cache, "assets_turn", 378)
        factor = selected["row_id"].map(ratio)
    elif handler == "value_ep":
        factor = selected["ratio_ep_ttm"]
    elif handler == "value_pcf":
        factor = selected["ratio_pcf_ocf_ttm"]
    elif handler == "value_ep_tsrank126":
        ratio = _historical_ratio_rank(frame, dates, cache, "ep", 126, "ts_rank")
        factor = selected["row_id"].map(ratio)
    elif handler == "cash_conversion":
        factor = _rank(selected["cfd_surplus_cash_multi_ttm"], dates_series)
    elif handler == "profitability":
        factor = _rank(profitability, dates_series)
    elif handler == "reversal_bm_ep":
        factor = (
            selected["rev_rank"] + selected["bm_rank"] + selected["ep_rank"]
        ) / 3.0
    elif handler == "reversal_bm_ep_cfp":
        factor = (
            selected["rev_rank"]
            + selected["bm_rank"]
            + selected["ep_rank"]
            + selected["cfp_rank"]
        ) / 4.0
    elif handler == "reversal_bm_roe_eq":
        factor = (
            selected["rev_rank"]
            + selected["bm_rank"]
            + _rank(quality_roe, dates_series)
        ) / 3.0
    elif handler == "reversal_ep_eq":
        factor = (selected["rev_rank"] + selected["ep_rank"]) / 2.0
    elif handler == "reversal_bm_ep_roe":
        factor = (
            selected["rev_rank"]
            + selected["bm_rank"]
            + selected["ep_rank"]
            + _rank(quality_roe, dates_series)
        ) / 4.0
    elif handler == "value_eq":
        factor = (
            selected["bm_rank"]
            + selected["ep_rank"]
            + selected["sp_rank"]
            - selected["pcf_rank"]
        ) / 4.0
    elif handler == "style_eq":
        grouped = frame.groupby("instrument", sort=False, observed=True)
        ret20 = frame["close_qfq"].div(grouped["close_qfq"].shift(20)).sub(1.0)
        turn21 = _rolling(frame, "turnover", 21, "mean")
        volatility = _rolling(frame.assign(_ret1=frame["close_qfq"].div(grouped["close_qfq"].shift(1)).sub(1.0)), "_ret1", 21, "std")
        factor = (
            selected["bm_rank"]
            + _rank(growth_net, dates_series)
            + _rank(quality_roe, dates_series)
            + _rank(1.0 - _selected_full_series(selected, ret20), dates_series)
            + _rank(1.0 - _selected_full_series(selected, turn21), dates_series)
            + _rank(1.0 - _selected_full_series(selected, volatility), dates_series)
        ) / 6.0
    else:
        raise KeyError(f"Unsupported financial handler: {handler}")

    return _materialize_factor(frame, selected, factor)
