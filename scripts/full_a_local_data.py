"""Load the cached full-A qfq price and daily_basic panels."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pandas as pd


PRICE_COLUMNS = ["date", "instrument", "open", "close", "volume"]
OPTIONAL_PRICE_COLUMNS = ["high", "low", "high_qfq", "low_qfq", "amount"]
BASIC_COLUMNS = ["date", "instrument", "turnover", "total_mv", "circ_mv"]
BASIC_BASE_COLUMNS = ["date", "instrument", "turnover"]


def _read_price_batch(path: Path) -> pd.DataFrame:
    """Read the compact cache and any rich fields added by later downloads."""
    available = set(pq.ParquetFile(path).schema_arrow.names)
    columns = [column for column in PRICE_COLUMNS + OPTIONAL_PRICE_COLUMNS if column in available]
    missing = set(PRICE_COLUMNS).difference(columns)
    if missing:
        raise RuntimeError(f"Price batch {path} is missing columns: {sorted(missing)}")
    return pd.read_parquet(path, columns=columns)


def _coalesce_columns(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=frame.index, dtype="Float64")
    for column in columns:
        if column in frame.columns:
            result = result.combine_first(pd.to_numeric(frame[column], errors="coerce").astype("Float64"))
    return result.astype(float)


def _basic_columns(market_cap_field: str | None) -> list[str]:
    if market_cap_field is None:
        return list(BASIC_COLUMNS)
    if market_cap_field not in {"total_mv", "circ_mv"}:
        raise ValueError(f"Unsupported market-cap field: {market_cap_field}")
    return BASIC_BASE_COLUMNS + [market_cap_field]


def load_full_a_data(
    price_root: Path,
    cap_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    market_cap_field: str | None = None,
) -> pd.DataFrame:
    """Join full-A qfq prices with same-day turnover and market cap.

    Price files are already split into short date batches.  Match each price
    batch only with its corresponding daily_basic files so the loader never
    holds the complete price panel and complete cap panel as separate copies.
    """
    price_paths = sorted(price_root.glob("batch_*.parquet"))
    if not price_paths:
        raise FileNotFoundError(f"No full-A price batches found under {price_root}")
    cap_paths = sorted(cap_root.glob("daily_basic_*.parquet"))
    if not cap_paths:
        raise FileNotFoundError(f"No full-A daily_basic snapshots found under {cap_root}")
    cap_by_date = {
        path.stem.removeprefix("daily_basic_"): path for path in cap_paths
    }
    basic_columns = _basic_columns(market_cap_field)
    parts: list[pd.DataFrame] = []
    missing_high_any = False
    missing_low_any = False
    missing_amount_any = False
    for price_path in price_paths:
        prices = _read_price_batch(price_path)
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
        prices["instrument"] = prices["instrument"].astype(str)
        prices = prices[
            prices["date"].between(start, end)
            & prices["instrument"].str.endswith((".SH", ".SZ"))
        ].copy()
        if prices.empty:
            continue

        rich_columns = [
            column
            for column in ["high_qfq", "low_qfq", "high", "low", "amount"]
            if column in prices.columns
        ]
        if rich_columns:
            prices["_rich_field_count"] = prices[rich_columns].notna().sum(axis=1)
            prices = prices.sort_values(
                ["date", "instrument", "_rich_field_count"], kind="stable"
            )
            prices = prices.drop_duplicates(["date", "instrument"], keep="last")
            prices = prices.drop(columns=["_rich_field_count"])
        for column in ["open", "close", "volume"]:
            prices[column] = pd.to_numeric(prices[column], errors="coerce")

        cached_high = _coalesce_columns(prices, ["high_qfq", "high"])
        cached_low = _coalesce_columns(prices, ["low_qfq", "low"])
        cached_amount = _coalesce_columns(prices, ["amount"])
        prices["high_qfq"] = cached_high
        prices["low_qfq"] = cached_low
        prices["amount"] = cached_amount
        missing_high = prices["high_qfq"].isna() | prices["high_qfq"].le(0)
        missing_low = prices["low_qfq"].isna() | prices["low_qfq"].le(0)
        missing_amount = prices["amount"].isna() | prices["amount"].le(0)
        missing_high_any = missing_high_any or bool(missing_high.any())
        missing_low_any = missing_low_any or bool(missing_low.any())
        missing_amount_any = missing_amount_any or bool(missing_amount.any())
        # The original snapshot kept only open/close/volume.  Keep the loader
        # usable with it while making the approximation explicit in report attrs.
        prices.loc[missing_high, "high_qfq"] = prices.loc[
            missing_high, ["open", "close"]
        ].max(axis=1)
        prices.loc[missing_low, "low_qfq"] = prices.loc[
            missing_low, ["open", "close"]
        ].min(axis=1)
        prices.loc[missing_amount, "amount"] = (
            prices.loc[missing_amount, "volume"]
            * prices.loc[missing_amount, ["open", "close"]].mean(axis=1)
        )
        prices = prices[
            prices["open"].gt(0)
            & prices["close"].gt(0)
            & prices["volume"].gt(0)
            & prices["high_qfq"].gt(0)
            & prices["low_qfq"].gt(0)
            & prices["amount"].gt(0)
        ]
        if prices.empty:
            continue

        cap_frames: list[pd.DataFrame] = []
        for value in sorted(prices["date"].dropna().unique()):
            date_key = pd.Timestamp(value).strftime("%Y%m%d")
            cap_path = cap_by_date.get(date_key)
            if cap_path is None:
                continue
            part = pd.read_parquet(cap_path, columns=basic_columns)
            part["date"] = pd.to_datetime(part["date"], errors="coerce").dt.normalize()
            part["instrument"] = part["instrument"].astype(str)
            part = part[part["instrument"].str.endswith((".SH", ".SZ"))]
            if not part.empty:
                cap_frames.append(part)
        if not cap_frames:
            continue
        caps = pd.concat(cap_frames, ignore_index=True)
        for column in ["turnover", "total_mv", "circ_mv"]:
            if column in caps.columns:
                caps[column] = pd.to_numeric(caps[column], errors="coerce")
        caps = caps.drop_duplicates(["date", "instrument"], keep="last")

        joined = prices.merge(caps, on=["date", "instrument"], how="inner")
        joined = joined.rename(columns={"open": "open_qfq", "close": "close_qfq"})
        cap_field = market_cap_field or "total_mv"
        if cap_field not in joined.columns:
            continue
        joined = joined[
            joined["turnover"].notna()
            & joined[cap_field].notna()
            & joined[cap_field].gt(0)
        ].copy()
        if not joined.empty:
            parts.append(joined)

    if not parts:
        raise RuntimeError("Full-A qfq price cache contains no rows matching daily_basic")
    frame = pd.concat(parts, ignore_index=True)
    del parts
    if frame.duplicated(["date", "instrument"], keep=False).any():
        rich_columns = [
            column
            for column in ["high_qfq", "low_qfq", "high", "low", "amount"]
            if column in frame.columns
        ]
        frame["_rich_field_count"] = frame[rich_columns].notna().sum(axis=1)
        frame = frame.sort_values(
            ["date", "instrument", "_rich_field_count"], kind="stable"
        )
        frame = frame.drop_duplicates(["date", "instrument"], keep="last")
        frame = frame.drop(columns=["_rich_field_count"])
    if frame.empty:
        raise RuntimeError("No full-A rows remain after joining daily_basic")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    frame.attrs["market_field_sources"] = {
        "high_qfq": "cached" if not missing_high_any else "open/close range proxy",
        "low_qfq": "cached" if not missing_low_any else "open/close range proxy",
        "amount": "cached" if not missing_amount_any else "volume * average(open, close) proxy",
    }
    return frame


def select_market_cap(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    """Expose the requested market-cap field through the local canonical column."""
    if field not in {"total_mv", "circ_mv"}:
        raise ValueError(f"Unsupported market-cap field: {field}")
    if field not in frame.columns:
        raise RuntimeError(f"Full-A cache does not contain market-cap field: {field}")
    result = frame if field == "total_mv" else frame.copy()
    result["total_mv"] = pd.to_numeric(result[field], errors="coerce")
    result = result[result["total_mv"].gt(0)].copy()
    result.attrs.update(frame.attrs)
    result.attrs["market_cap_field"] = field
    return result
