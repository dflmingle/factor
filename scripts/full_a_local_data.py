"""Load the cached full-A qfq price and daily_basic panels."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PRICE_COLUMNS = ["date", "instrument", "open", "close", "volume"]
BASIC_COLUMNS = ["date", "instrument", "turnover", "total_mv"]


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
    prices = pd.concat(
        [pd.read_parquet(path, columns=PRICE_COLUMNS) for path in price_paths],
        ignore_index=True,
    )
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["instrument"] = prices["instrument"].astype(str)
    prices = prices[
        prices["date"].between(start, end)
        & prices["instrument"].str.endswith((".SH", ".SZ"))
    ].copy()
    for column in ["open", "close", "volume"]:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    prices = prices[
        prices["open"].gt(0)
        & prices["close"].gt(0)
        & prices["volume"].gt(0)
    ].drop_duplicates(["date", "instrument"], keep="last")
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
    for column in ["turnover", "total_mv"]:
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
    return frame.sort_values(["instrument", "date"], ignore_index=True)
