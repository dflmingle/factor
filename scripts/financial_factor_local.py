#!/usr/bin/env python3
"""Point-in-time financial factor construction from the local Tushare cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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
    "reversal_turn_paper",
    "reversal_turn_paper_nomcap",
    "reversal_chip_turn_paper",
    "fscore_interact",
    "fscore_eq",
    "residual_volatility",
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
    """Keep Tushare's consolidated statement when multiple report scopes exist."""
    if "comp_type" not in frame.columns:
        return frame
    consolidated = frame[frame["comp_type"].astype(str).eq("1")]
    return consolidated.copy() if not consolidated.empty else frame


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

    for instrument, group in frame.groupby("instrument", sort=False, observed=True):
        period_values: dict[pd.Timestamp, dict[str, float]] = {}
        group = group.sort_values(["ann_date", "end_date", "update_flag"])
        for row in group.itertuples(index=False):
            end_date = getattr(row, "end_date")
            ann_date = getattr(row, "ann_date")
            quarter = _quarter_number(end_date)
            if pd.isna(end_date) or pd.isna(ann_date) or quarter is None:
                continue
            values = {
                column: getattr(row, column, np.nan)
                for column in available_columns
            }
            period_values[end_date] = values

            discrete: dict[pd.Timestamp, dict[str, float]] = {}
            for period, raw_values in period_values.items():
                q = _quarter_number(period)
                if q is None:
                    continue
                discrete_values: dict[str, float] = {}
                for column, raw_value in raw_values.items():
                    if pd.isna(raw_value):
                        continue
                    value = float(raw_value)
                    if q > 1:
                        previous_period = _quarter_end(period.year, q - 1)
                        previous = period_values.get(previous_period, {}).get(column)
                        if previous is None or pd.isna(previous):
                            continue
                        value -= float(previous)
                    discrete_values[column] = value
                if discrete_values:
                    discrete[period] = discrete_values

            periods = sorted(period for period in discrete if period <= end_date)
            if len(periods) < 4:
                continue
            last_four = periods[-4:]
            result: dict[str, Any] = {
                "instrument": instrument,
                "ann_date": ann_date,
                "end_date": end_date,
            }
            for column in available_columns:
                values = [discrete[period].get(column, np.nan) for period in last_four]
                if all(pd.notna(value) for value in values):
                    result[f"ttm_{column}"] = float(np.sum(values))
            if len(result) > 3:
                output.append(result)
    return pd.DataFrame(output)


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
        ["total_revenue", "revenue", "operate_profit", "n_income", "n_income_attr_p"],
    )
    result["cashflow_ttm"] = _make_ttm(
        result["cashflow"],
        ["n_cashflow_act", "free_cashflow", "net_profit"],
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
    signal["book_to_market_ratio_lyr"] = equity_lyr.div(mv)
    signal["ratio_sp_ttm"] = revenue.div(mv)
    signal["ratio_ep_ttm"] = net_income.div(mv)
    signal["ratio_cfp_ttm"] = ocf.div(mv)
    signal["ratio_pcf_ocf_ttm"] = mv.div(ocf.where(ocf.abs() > 1e-12))
    signal["cfd_surplus_cash_multi_ttm"] = ocf.div(net_income.where(net_income.abs() > 1e-12))
    return signal


def _base_signal(frame: pd.DataFrame, dates: list[pd.Timestamp]) -> pd.DataFrame:
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
    selected = work[work["date"].isin(dates)].copy()
    selected = _financial_snapshot(selected, _FINANCIAL_CACHE)
    selected = _value_columns(selected)
    return selected


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
    ][["date", "instrument", "total_mv"]].copy()
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


_FINANCIAL_CACHE: dict[str, pd.DataFrame] = {}
_HISTORICAL_RANK_CACHE: dict[tuple[Any, ...], pd.Series] = {}


def build_financial_factor(
    frame: pd.DataFrame,
    handler: str,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
) -> pd.Series:
    global _FINANCIAL_CACHE
    _FINANCIAL_CACHE = cache
    selected = _base_signal(frame, dates)
    dates_series = selected["date"]
    selected["rev_rank"] = _rank(1.0 - selected["ret40"], dates_series)
    selected["turn_rank"] = _rank(selected["turn_signal"], dates_series)
    selected["chip_rank"] = _rank(selected["chip"], dates_series)
    selected["cap_rank"] = _rank(selected["total_mv"], dates_series)
    selected["size_rank"] = _rank(-selected["cap_rank"], dates_series)
    selected["bm_rank"] = _rank(selected["ratio_bm_ttm"], dates_series)
    selected["bm_lyr_rank"] = _rank(selected["book_to_market_ratio_lyr"], dates_series)
    selected["sp_rank"] = _rank(selected["ratio_sp_ttm"], dates_series)
    selected["cfp_rank"] = _rank(selected["ratio_cfp_ttm"], dates_series)
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

    if handler == "value_bm":
        factor = selected["ratio_bm_ttm"]
    elif handler == "value_sp":
        factor = selected["ratio_sp_ttm"]
    elif handler == "asset_growth":
        factor = selected["growth_rank"]
    elif handler == "paper_composite":
        factor = selected["paper_score"]
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
        cfp_ma_rank = _historical_ratio_rank(frame, dates, cache, "cfp", 63, "ma")
        selected["bm_ma_rank"] = selected["row_id"].map(bm_ma_rank)
        selected["cfp_ma_rank"] = selected["row_id"].map(cfp_ma_rank)
        factor = (
            selected["rev_rank"] + selected["bm_ma_rank"] + selected["cfp_ma_rank"]
        ) / 3.0
    elif handler == "reversal_bm_cfp_tsrank756":
        bm_ts_rank = _historical_ratio_rank(frame, dates, cache, "bm", 756, "ts_rank")
        cfp_ts_rank = _historical_ratio_rank(frame, dates, cache, "cfp", 756, "ts_rank")
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
    elif handler == "residual_volatility":
        residual = _residual_volatility(frame)
        selected["residual"] = residual.reindex(selected["row_id"]).to_numpy()
        factor = _rank(-selected["residual"], dates_series)
    else:
        raise KeyError(f"Unsupported financial handler: {handler}")

    values = pd.Series(np.nan, index=frame.index, dtype=float)
    values.loc[selected["row_id"].to_numpy()] = pd.to_numeric(factor, errors="coerce").to_numpy()
    return values
