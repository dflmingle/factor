"""Load the cached full-A qfq price and daily_basic panels."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pandas as pd


PRICE_COLUMNS = ["date", "instrument", "open", "close", "volume"]
OPTIONAL_PRICE_COLUMNS = ["high", "low", "high_qfq", "low_qfq", "amount"]
BASIC_COLUMNS = ["date", "instrument", "turnover", "total_mv", "circ_mv"]


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


def load_full_a_data(
    price_root: Path,
    cap_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Join full-A qfq prices with same-day turnover and market cap."""
    price_paths = sorted(price_root.glob("batch_*.parquet"))
    if not price_paths:
        raise FileNotFoundError(f"No full-A price batches found under {price_root}")
    prices = pd.concat([_read_price_batch(path) for path in price_paths], ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["instrument"] = prices["instrument"].astype(str)
    prices = prices[
        prices["date"].between(start, end)
        & prices["instrument"].str.endswith((".SH", ".SZ"))
    ].copy()
    rich_columns = [
        column
        for column in ["high_qfq", "low_qfq", "high", "low", "amount"]
        if column in prices.columns
    ]
    if rich_columns:
        # Older snapshots in this directory use a different batch split and
        # contain only the base five columns. Prefer a richer duplicate before
        # applying any field-level proxy fallback.
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
    # The original snapshot kept only open/close/volume.  Keep the loader
    # usable with it while making the approximation explicit in report attrs.
    prices.loc[missing_high, "high_qfq"] = prices.loc[missing_high, ["open", "close"]].max(axis=1)
    prices.loc[missing_low, "low_qfq"] = prices.loc[missing_low, ["open", "close"]].min(axis=1)
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
        raise RuntimeError("Full-A qfq price cache contains no usable rows")

    cap_paths = sorted(cap_root.glob("daily_basic_*.parquet"))
    if not cap_paths:
        raise FileNotFoundError(f"No full-A daily_basic snapshots found under {cap_root}")
    wanted_dates = set(prices["date"].dropna().unique())
    cap_frames: list[pd.DataFrame] = []
    for path in cap_paths:
        part = pd.read_parquet(path, columns=BASIC_COLUMNS)
        part["date"] = pd.to_datetime(part["date"], errors="coerce").dt.normalize()
        part["instrument"] = part["instrument"].astype(str)
        part = part[
            part["date"].isin(wanted_dates)
            & part["instrument"].str.endswith((".SH", ".SZ"))
        ]
        if not part.empty:
            cap_frames.append(part)
    if not cap_frames:
        raise RuntimeError("Full-A daily_basic cache contains no dates matching prices")
    caps = pd.concat(cap_frames, ignore_index=True)
    for column in ["turnover", "total_mv", "circ_mv"]:
        caps[column] = pd.to_numeric(caps[column], errors="coerce")
    caps = caps.drop_duplicates(["date", "instrument"], keep="last")

    frame = prices.merge(caps, on=["date", "instrument"], how="inner")
    frame = frame.rename(columns={"open": "open_qfq", "close": "close_qfq"})
    frame = frame[
        frame["turnover"].notna()
        & frame["total_mv"].notna()
        & frame["total_mv"].gt(0)
    ].copy()
    if frame.empty:
        raise RuntimeError("No full-A rows remain after joining daily_basic")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    frame.attrs["market_field_sources"] = {
        "high_qfq": "cached" if not missing_high.any() else "open/close range proxy",
        "low_qfq": "cached" if not missing_low.any() else "open/close range proxy",
        "amount": "cached" if not missing_amount.any() else "volume * average(open, close) proxy",
    }
    return frame


def select_market_cap(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    """Expose the requested market-cap field through the local canonical column."""
    if field not in {"total_mv", "circ_mv"}:
        raise ValueError(f"Unsupported market-cap field: {field}")
    if field not in frame.columns:
        raise RuntimeError(f"Full-A cache does not contain market-cap field: {field}")
    result = frame.copy()
    result["total_mv"] = pd.to_numeric(result[field], errors="coerce")
    result = result[result["total_mv"].gt(0)].copy()
    result.attrs.update(frame.attrs)
    result.attrs["market_cap_field"] = field
    return result
