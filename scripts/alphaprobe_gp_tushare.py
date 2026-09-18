#!/usr/bin/env python3
"""Run AlphaPROBE genetic programming on the local Tushare qfq cache.

AlphaPROBE's expression engine only requires a small StockData-like object.
This runner supplies that object from the project's cached Tushare Parquet
files, so Qlib is not used for data loading or calendar lookup.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALPHAPROBE_ROOT = PROJECT_ROOT / "quantlab" / "third_party" / "AlphaPROBE"
ALPHAPROBE_SRC = ALPHAPROBE_ROOT / "src"
if str(ALPHAPROBE_SRC) not in sys.path:
    sys.path.insert(0, str(ALPHAPROBE_SRC))

from alphagen.data.expression import (  # noqa: E402
    Feature,
    FeatureType,
    Ref,
)
from alphagen.models.alpha_pool import AlphaPool  # noqa: E402
from alphagen.utils.correlation import (  # noqa: E402
    batch_pearsonr,
)
from alphagen.utils.pytorch_utils import normalize_by_day  # noqa: E402
from alphagen_generic import features as generic_features  # noqa: E402
from alphagen_generic import operators as generic_operators  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from factor_formula_dedupe import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_FORMULA_REGISTRY,
    load_signatures as load_formula_signatures,
    normalize_formula,
)
from pandaai_fields_local import (  # noqa: E402
    PandaAIFieldStore,
    PRICE_VOLUME_FIELDS,
    build_pandaai_namespace,
    formula_field_name_set,
)
from search_field_policy import resolve_terminal_fields  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_CORRELATION_METHOD,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    alignment_config_snapshot,
    validate_alignment_config,
)
from utils.gplearn.fitness import make_fitness  # noqa: E402
from utils.gplearn.functions import make_function  # noqa: E402
from utils.gplearn.genetic import SymbolicRegressor  # noqa: E402


DEFAULT_CACHE_ROOT = (
    PROJECT_ROOT
    / "quantlab"
    / ".quantlab"
    / "cache"
    / "research"
    / "cn_equity"
)
DEFAULT_BATCH_ROOT = (
    DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
)
DEFAULT_FINANCIAL_ROOT = DEFAULT_CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_ROOT = (
    DEFAULT_CACHE_ROOT / "reports" / "alphaprobe_gp_tushare"
)
FEATURE_COLUMNS = {
    FeatureType.OPEN: "open",
    FeatureType.CLOSE: "close",
    FeatureType.HIGH: "high",
    FeatureType.LOW: "low",
    FeatureType.VOLUME: "volume",
}
ALL_FEATURES = list(FeatureType)
BATCH_PATTERN = re.compile(r"^batch_(\d{8})_(\d{8})$")
ALIGNED_START = pd.Timestamp(ALIGNMENT_START)
ALIGNED_END = pd.Timestamp(ALIGNMENT_END)
ALIGNED_DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
ALIGNED_CYCLE = 5
ALIGNED_LABEL_OFFSET = ALIGNMENT_LABEL_OFFSET
ALIGNED_GROUPS = ALIGNMENT_GROUPS
ALIGNED_ROUND_TRIP_COST = ALIGNMENT_ROUND_TRIP_COST
ALIGNED_CANDIDATE_RANK_CORR_THRESHOLD = 0.999
ALIGNED_DRAWDOWN_CANDIDATE_RANK_CORR_THRESHOLD = 0.90
ALIGNED_MIN_PERIODS = 200
ALIGNED_ABSOLUTE_DD_TARGET = 0.30
ALIGNED_EXCESS_DD_TARGET = 0.15
ALIGNED_ABSOLUTE_DD_WEIGHT = 0.50
ALIGNED_EXCESS_DD_WEIGHT = 0.25
ALIGNED_ABSOLUTE_DD_CEILING = 0.45
ALIGNED_EXCESS_DD_CEILING = 0.25


def parse_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    timestamp = pd.to_datetime(
        text,
        format="%Y%m%d" if len(text) == 8 and text.isdigit() else None,
        errors="raise",
    )
    return pd.Timestamp(timestamp).normalize()


def date_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return date_text(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default, allow_nan=True)
        + "\n",
        encoding="utf-8",
    )


def load_trade_dates(cache_root: Path) -> list[pd.Timestamp]:
    calendar_root = cache_root / "trade_calendar"
    paths = sorted(calendar_root.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"Tushare trade-calendar cache is missing: {calendar_root}")

    frames = []
    for path in paths:
        frame = pd.read_parquet(path, columns=["trade_date", "is_open"])
        frames.append(frame)
    calendar = pd.concat(frames, ignore_index=True)
    calendar["trade_date"] = pd.to_datetime(
        calendar["trade_date"].astype(str), format="mixed", errors="coerce"
    ).dt.normalize()
    calendar = calendar[calendar["is_open"].astype(int) == 1]
    dates = calendar["trade_date"].dropna().drop_duplicates().sort_values()
    result = [pd.Timestamp(value) for value in dates]
    if not result:
        raise RuntimeError(f"No open dates found under {calendar_root}")
    return result


def batch_bounds(path: Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    match = BATCH_PATTERN.match(path.stem)
    if match is None:
        return None
    return parse_date(match.group(1)), parse_date(match.group(2))


def batch_paths(batch_root: Path, start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    selected: list[Path] = []
    for path in sorted(batch_root.glob("batch_*.parquet")):
        bounds = batch_bounds(path)
        if bounds is None:
            continue
        batch_start, batch_end = bounds
        if batch_end >= start and batch_start <= end:
            selected.append(path)
    if not selected:
        raise FileNotFoundError(
            f"No Tushare Parquet batches overlap {date_text(start)}..{date_text(end)} "
            f"under {batch_root}"
        )
    return selected


def load_daily_rows(
    batch_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    instruments: set[str] | None,
) -> pd.DataFrame:
    wanted = [
        "date",
        "instrument",
        "open",
        "close",
        "volume",
        "amount",
        "high_qfq",
        "low_qfq",
    ]
    frames: list[pd.DataFrame] = []
    for path in batch_paths(batch_root, start, end):
        available = set(pq.ParquetFile(path).schema_arrow.names)
        columns = [column for column in wanted if column in available]
        frame = pd.read_parquet(path, columns=columns)
        if frame.empty:
            continue
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame["instrument"] = frame["instrument"].astype(str)
        frame = frame[frame["date"].between(start, end)]
        if instruments is not None:
            frame = frame[frame["instrument"].isin(instruments)]
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame(
            columns=[
                "date",
                "instrument",
                "open",
                "close",
                "volume",
                "amount",
                "high",
                "low",
            ]
        )

    frame = pd.concat(frames, ignore_index=True)
    for column in ["open", "close", "volume", "amount", "high_qfq", "low_qfq"]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        frame["date"].notna()
        & frame["instrument"].notna()
        & (frame["open"] > 0)
        & (frame["close"] > 0)
        & (frame["volume"] > 0)
    ].copy()

    # Some older cached batches predate high_qfq/low_qfq. Keep the guaranteed
    # Tushare OHLCV fields usable and make the fallback explicit in the run log.
    high = frame["high_qfq"] if "high_qfq" in frame else pd.Series(np.nan, index=frame.index)
    low = frame["low_qfq"] if "low_qfq" in frame else pd.Series(np.nan, index=frame.index)
    frame["high"] = high.fillna(frame[["open", "close"]].max(axis=1))
    frame["low"] = low.fillna(frame[["open", "close"]].min(axis=1))
    if "amount" not in frame:
        frame["amount"] = np.nan
    frame["amount"] = frame["amount"].where(
        frame["amount"].gt(0),
        frame["volume"] * frame[["open", "close"]].mean(axis=1),
    )
    frame = frame.drop_duplicates(subset=["date", "instrument"], keep="last")
    return frame[
        ["date", "instrument", "open", "close", "volume", "amount", "high", "low"]
    ].sort_values(
        ["date", "instrument"], ignore_index=True
    )


def load_stock_basic_universe(cache_root: Path) -> list[str]:
    path = cache_root / "stock_basic" / "data.parquet"
    if not path.exists():
        return []
    frame = pd.read_parquet(path, columns=["ts_code"])
    values = frame["ts_code"].dropna().astype(str).drop_duplicates().sort_values()
    return list(values)


def read_universe_file(path: Path) -> list[str]:
    values: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            values.extend(item.strip() for item in value.split(",") if item.strip())
    return list(dict.fromkeys(values))


def resolve_universe(
    cache_root: Path,
    specification: str,
    limit: int | None,
) -> list[str] | None:
    spec = specification.strip()
    if spec.lower() in {"all", "auto"}:
        values: list[str] | None = None
    elif spec.lower() == "full_a":
        values = [
            value
            for value in load_stock_basic_universe(cache_root)
            if value.endswith((".SH", ".SZ"))
        ]
        if not values:
            raise FileNotFoundError(
                "--universe full_a needs stock_basic/data.parquet with .SH/.SZ codes"
            )
    else:
        candidate = Path(spec).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if candidate.is_file():
            values = read_universe_file(candidate)
        else:
            values = list(dict.fromkeys(item.strip() for item in spec.split(",") if item.strip()))
    if limit is None:
        return values
    if limit < 1:
        raise ValueError("--universe-limit must be at least 1")
    if values is None:
        values = load_stock_basic_universe(cache_root)
        if not values:
            raise FileNotFoundError(
                "--universe-limit needs stock_basic/data.parquet when --universe is all"
            )
    return values[:limit]


class TushareStockData:
    """Minimal StockData contract consumed by AlphaPROBE expressions."""

    def __init__(
        self,
        *,
        batch_root: Path,
        calendar: Sequence[pd.Timestamp],
        instrument: Sequence[str] | None,
        start_time: str,
        end_time: str,
        max_backtrack_days: int = 756,
        max_future_days: int = 30,
        device: torch.device = torch.device("cpu"),
        freq: str = "day",
        financial_root: Path | None = None,
    ) -> None:
        if freq != "day":
            raise ValueError("The local Tushare AlphaPROBE adapter currently supports day data only")
        if max_backtrack_days < 0 or max_future_days < 0:
            raise ValueError("Lookback and future padding must be non-negative")

        self.raw = False
        self.freq = freq
        self.device = device
        self.max_backtrack_days = max_backtrack_days
        self.max_future_days = max_future_days
        self.financial_root = financial_root
        self._pandaai_field_store: PandaAIFieldStore | None = None
        self._start_time = parse_date(start_time)
        self._end_time = parse_date(end_time)
        if self._start_time > self._end_time:
            raise ValueError("start_time must not be later than end_time")
        self._features = list(ALL_FEATURES)
        self._calendar = [pd.Timestamp(value).normalize() for value in calendar]
        self._evaluation_dates = [
            value for value in self._calendar if self._start_time <= value <= self._end_time
        ]
        if not self._evaluation_dates:
            raise ValueError(
                f"No cached trading dates between {date_text(self._start_time)} "
                f"and {date_text(self._end_time)}"
            )

        before = [value for value in self._calendar if value < self._evaluation_dates[0]]
        after = [value for value in self._calendar if value > self._evaluation_dates[-1]]
        self._pre_dates = before[-max_backtrack_days:] if max_backtrack_days else []
        self._post_dates = after[:max_future_days] if max_future_days else []
        self._pre_padding = max_backtrack_days - len(self._pre_dates)
        self._post_padding = max_future_days - len(self._post_dates)
        real_dates = self._pre_dates + self._evaluation_dates + self._post_dates
        load_start = real_dates[0]
        load_end = real_dates[-1]

        requested_instruments = None if instrument is None else list(dict.fromkeys(instrument))
        instrument_filter = None if requested_instruments is None else set(requested_instruments)
        frame = load_daily_rows(batch_root, load_start, load_end, instrument_filter)
        if frame.empty:
            raise ValueError(
                f"No Tushare rows found between {date_text(load_start)} and {date_text(load_end)}"
            )

        if requested_instruments is None:
            stock_ids = sorted(frame["instrument"].dropna().astype(str).unique())
        else:
            available = set(frame["instrument"].astype(str))
            stock_ids = [value for value in requested_instruments if value in available]
        if not stock_ids:
            raise ValueError("The selected universe has no rows in the requested Tushare window")

        real_index = pd.DatetimeIndex(real_dates)
        stock_index = pd.Index(stock_ids, dtype="object")
        values = np.full(
            (len(real_dates) + self._pre_padding + self._post_padding, len(ALL_FEATURES), len(stock_ids)),
            np.nan,
            dtype=np.float32,
        )
        indexed = frame.set_index(["date", "instrument"])
        for feature, column in FEATURE_COLUMNS.items():
            wide = indexed[column].unstack("instrument")
            wide = wide.reindex(index=real_index, columns=stock_index)
            feature_values = wide.to_numpy(dtype=np.float32, copy=True)
            values[self._pre_padding : self._pre_padding + len(real_dates), int(feature), :] = feature_values

        self.data = torch.tensor(values, dtype=torch.float32, device=device)
        self._dates = pd.DatetimeIndex(
            [pd.NaT] * self._pre_padding
            + real_dates
            + [pd.NaT] * self._post_padding
        )
        self._stock_ids = stock_index
        self._n_days = len(self._evaluation_dates)
        self.df_bak = frame
        self.fallback_high_low = True

    @classmethod
    def from_aligned_frame(
        cls,
        *,
        frame: pd.DataFrame,
        calendar: Sequence[pd.Timestamp],
        instrument: Sequence[str],
        start_time: str,
        end_time: str,
        max_backtrack_days: int,
        max_future_days: int,
        device: torch.device,
        financial_root: Path | None = None,
    ) -> "TushareStockData":
        """Build an AlphaPROBE panel from the local aligned full-A snapshot.

        Price fields are forward-filled only for the expression panel.  The
        evaluator separately masks each signal date to rows observed in the
        aligned Tushare/daily_basic join, so a suspended name cannot enter a
        portfolio merely because its last price was carried forward.
        """
        if max_backtrack_days < 0 or max_future_days < 0:
            raise ValueError("Lookback and future padding must be non-negative")

        obj = cls.__new__(cls)
        obj.raw = False
        obj.freq = "day"
        obj.device = device
        obj.max_backtrack_days = max_backtrack_days
        obj.max_future_days = max_future_days
        obj.financial_root = financial_root
        obj._pandaai_field_store = None
        obj._start_time = parse_date(start_time)
        obj._end_time = parse_date(end_time)
        if obj._start_time > obj._end_time:
            raise ValueError("start_time must not be later than end_time")
        obj._features = list(ALL_FEATURES)
        obj._calendar = [pd.Timestamp(value).normalize() for value in calendar]
        obj._evaluation_dates = [
            value for value in obj._calendar if obj._start_time <= value <= obj._end_time
        ]
        if not obj._evaluation_dates:
            raise ValueError(
                f"No aligned trading dates between {date_text(obj._start_time)} "
                f"and {date_text(obj._end_time)}"
            )

        before = [value for value in obj._calendar if value < obj._evaluation_dates[0]]
        after = [value for value in obj._calendar if value > obj._evaluation_dates[-1]]
        obj._pre_dates = before[-max_backtrack_days:] if max_backtrack_days else []
        obj._post_dates = after[:max_future_days] if max_future_days else []
        obj._pre_padding = max_backtrack_days - len(obj._pre_dates)
        obj._post_padding = max_future_days - len(obj._post_dates)
        real_dates = obj._pre_dates + obj._evaluation_dates + obj._post_dates

        stock_index = pd.Index(list(dict.fromkeys(instrument)), dtype="object")
        if stock_index.empty:
            raise ValueError("The aligned full-A snapshot contains no instruments")
        indexed = frame.set_index(["date", "instrument"])
        real_index = pd.DatetimeIndex(real_dates)
        values = np.full(
            (
                len(real_dates) + obj._pre_padding + obj._post_padding,
                len(ALL_FEATURES),
                len(stock_index),
            ),
            np.nan,
            dtype=np.float32,
        )
        source_columns = {
            FeatureType.OPEN: "open_qfq",
            FeatureType.CLOSE: "close_qfq",
            FeatureType.HIGH: "high_qfq",
            FeatureType.LOW: "low_qfq",
            FeatureType.VOLUME: "volume",
        }
        for feature, column in source_columns.items():
            wide = indexed[column].unstack("instrument")
            wide = wide.reindex(index=real_index, columns=stock_index)
            if feature == FeatureType.VOLUME:
                wide = wide.fillna(0.0)
            else:
                wide = wide.ffill()
            feature_values = wide.to_numpy(dtype=np.float32, copy=True)
            values[
                obj._pre_padding : obj._pre_padding + len(real_dates),
                int(feature),
                :,
            ] = feature_values

        obj.data = torch.tensor(values, dtype=torch.float32, device=device)
        obj._dates = pd.DatetimeIndex(
            [pd.NaT] * obj._pre_padding
            + real_dates
            + [pd.NaT] * obj._post_padding
        )
        obj._stock_ids = stock_index
        obj._n_days = len(obj._evaluation_dates)
        obj.df_bak = frame
        obj.fallback_high_low = False
        return obj

    @property
    def pandaai_field_store(self) -> PandaAIFieldStore:
        if self._pandaai_field_store is None:
            self._pandaai_field_store = PandaAIFieldStore(
                data=self,
                frame=self.df_bak,
                financial_root=self.financial_root,
            )
        return self._pandaai_field_store

    def get_named_feature(
        self,
        name: str,
        period: slice = slice(0, 1),
    ) -> torch.Tensor:
        return self.pandaai_field_store.get_named_feature(name, period)

    def field_coverage(self) -> dict[str, Any]:
        return self.pandaai_field_store.coverage_report()

    @property
    def n_features(self) -> int:
        return len(self._features)

    @property
    def n_stocks(self) -> int:
        return self.data.shape[-1]

    @property
    def n_days(self) -> int:
        return self._n_days

    def make_dataframe(
        self,
        data: torch.Tensor | list[torch.Tensor],
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        if isinstance(data, list):
            data = torch.stack(data, dim=2)
        if data.ndim == 2:
            data = data.unsqueeze(2)
        if data.shape[0] != self.n_days or data.shape[1] != self.n_stocks:
            raise ValueError("The provided tensor does not match this Tushare panel")
        if columns is None:
            columns = [str(index) for index in range(data.shape[2])]
        if len(columns) != data.shape[2]:
            raise ValueError("The provided column count does not match the tensor")
        index = pd.MultiIndex.from_product(
            [self._evaluation_dates, self._stock_ids], names=["datetime", "instrument"]
        )
        return pd.DataFrame(data.detach().cpu().numpy().reshape(-1, len(columns)), index=index, columns=columns)

    def summary(self) -> dict[str, Any]:
        return {
            "start_date": date_text(self._evaluation_dates[0]),
            "end_date": date_text(self._evaluation_dates[-1]),
            "trading_days": self.n_days,
            "stocks": self.n_stocks,
            "features": [feature.name.lower() for feature in self._features],
            "device": str(self.device),
            "max_backtrack_days": self.max_backtrack_days,
            "max_future_days": self.max_future_days,
            "high_low_fallback": self.fallback_high_low,
        }


def _max_drawdown_from_returns(values: torch.Tensor) -> float | None:
    """Return the max drawdown of a finite periodic return series."""
    if values.ndim != 1 or values.numel() == 0:
        return None
    if not bool(torch.isfinite(values).all().item()):
        return None
    equity = torch.cat(
        [
            torch.ones(1, dtype=values.dtype, device=values.device),
            torch.cumprod(1.0 + values, dim=0),
        ]
    )
    if not bool(torch.isfinite(equity).all().item()) or bool((equity <= 0).any().item()):
        return None
    peaks = torch.cummax(equity, dim=0).values
    drawdown = torch.clamp_min(1.0 - equity / peaks, 0.0)
    return float(drawdown.max().detach().item())


def _relative_max_drawdown(
    portfolio_returns: torch.Tensor,
    benchmark_returns: torch.Tensor,
) -> float | None:
    """Return drawdown of portfolio equity relative to benchmark equity.

    The platform only exposes an aggregate excess-drawdown field. This
    relative-equity calculation is the local proxy used by the mining score.
    """
    if portfolio_returns.shape != benchmark_returns.shape:
        raise ValueError("Portfolio and benchmark return series must have the same shape")
    if portfolio_returns.ndim != 1 or portfolio_returns.numel() == 0:
        return None
    if not bool(torch.isfinite(portfolio_returns).all().item()) or not bool(
        torch.isfinite(benchmark_returns).all().item()
    ):
        return None
    portfolio_equity = torch.cat(
        [
            torch.ones(1, dtype=portfolio_returns.dtype, device=portfolio_returns.device),
            torch.cumprod(1.0 + portfolio_returns, dim=0),
        ]
    )
    benchmark_equity = torch.cat(
        [
            torch.ones(1, dtype=benchmark_returns.dtype, device=benchmark_returns.device),
            torch.cumprod(1.0 + benchmark_returns, dim=0),
        ]
    )
    if not bool(torch.isfinite(portfolio_equity).all().item()) or not bool(
        torch.isfinite(benchmark_equity).all().item()
    ):
        return None
    if bool((portfolio_equity <= 0).any().item()) or bool((benchmark_equity <= 0).any().item()):
        return None
    relative_equity = portfolio_equity / benchmark_equity
    peaks = torch.cummax(relative_equity, dim=0).values
    drawdown = torch.clamp_min(1.0 - relative_equity / peaks, 0.0)
    return float(drawdown.max().detach().item())


class AlignedNetExcessContext:
    """Score factors with the project's local platform-alignment proxy."""

    def __init__(
        self,
        *,
        frame: pd.DataFrame,
        calendar: Sequence[pd.Timestamp],
        data: TushareStockData,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        cycle: int,
        label_offset: int,
        groups: int,
        round_trip_cost: float,
    ) -> None:
        self.calendar = [pd.Timestamp(value).normalize() for value in calendar]
        self.data = data
        self.start_date = pd.Timestamp(start_date).normalize()
        self.end_date = pd.Timestamp(end_date).normalize()
        self.cycle = cycle
        self.label_offset = label_offset
        self.groups = groups
        self.round_trip_cost = round_trip_cost
        self.stock_ids = list(data._stock_ids)
        self._calendar_positions = {date: index for index, date in enumerate(self.calendar)}
        evaluation_positions = {
            date: index for index, date in enumerate(data._evaluation_dates)
        }

        if self.start_date not in self._calendar_positions:
            raise ValueError(f"Aligned start date is absent from the local calendar: {self.start_date}")
        start_position = self._calendar_positions[self.start_date]
        self.signal_dates: list[pd.Timestamp] = []
        self.signal_calendar_positions: list[int] = []
        self.signal_data_positions: list[int] = []
        for position in range(start_position, len(self.calendar), cycle):
            date = self.calendar[position]
            if date > self.end_date:
                break
            future_position = position + label_offset + cycle
            if future_position >= len(self.calendar):
                continue
            if date not in evaluation_positions:
                continue
            self.signal_dates.append(date)
            self.signal_calendar_positions.append(position)
            self.signal_data_positions.append(evaluation_positions[date])
        if not self.signal_dates:
            raise ValueError("No aligned rebalance dates were generated")

        indexed = frame.set_index(["date", "instrument"])
        observed = indexed["close_qfq"].unstack("instrument")
        observed = observed.reindex(index=self.calendar, columns=self.stock_ids)
        self.close_panel = observed.ffill().to_numpy(dtype=np.float32, copy=True)

        eligible = indexed["total_mv"].unstack("instrument")
        eligible = eligible.reindex(index=self.calendar, columns=self.stock_ids)
        self.eligible = eligible.notna().to_numpy(dtype=bool, copy=True)

        returns = []
        eligible_rows = []
        for position in self.signal_calendar_positions:
            current = self.close_panel[position + label_offset]
            future = self.close_panel[position + label_offset + cycle]
            returns.append(future / current - 1.0)
            eligible_rows.append(self.eligible[position])
        self.forward_returns = torch.tensor(
            np.asarray(returns, dtype=np.float32),
            dtype=torch.float32,
            device=data.device,
        )
        self.signal_eligible = torch.tensor(
            np.asarray(eligible_rows, dtype=bool),
            dtype=torch.bool,
            device=data.device,
        )

    def _selected_indices(
        self,
        start_date: pd.Timestamp | None,
        end_date: pd.Timestamp | None,
    ) -> list[int]:
        start = self.start_date if start_date is None else pd.Timestamp(start_date).normalize()
        end = self.end_date if end_date is None else pd.Timestamp(end_date).normalize()
        return [
            index
            for index, date in enumerate(self.signal_dates)
            if start <= date <= end
        ]

    def score(
        self,
        factor: torch.Tensor,
        *,
        start_date: pd.Timestamp | None = None,
        end_date: pd.Timestamp | None = None,
    ) -> dict[str, float | int | None]:
        if factor.ndim != 2:
            raise ValueError(f"Expected a two-dimensional factor panel, got shape {tuple(factor.shape)}")
        indices = self._selected_indices(start_date, end_date)
        if not indices:
            return {
                "periods": 0,
                "gross_excess": None,
                "turnover": None,
                "annual_cost": None,
                "net_excess": None,
                "absolute_max_drawdown": None,
                "excess_max_drawdown": None,
            }

        data_positions = [self.signal_data_positions[index] for index in indices]
        factor_rows = factor[data_positions]
        returns = self.forward_returns[indices]
        eligible = self.signal_eligible[indices]
        valid = torch.isfinite(factor_rows) & eligible & torch.isfinite(returns)
        counts = valid.sum(dim=1)
        keep = counts >= self.groups * 10
        if not bool(keep.any().item()):
            return {
                "periods": 0,
                "gross_excess": None,
                "turnover": None,
                "annual_cost": None,
                "net_excess": None,
                "absolute_max_drawdown": None,
                "excess_max_drawdown": None,
            }

        factor_rows = factor_rows[keep]
        returns = returns[keep]
        valid = valid[keep]
        counts = counts[keep]
        selected_counts = torch.div(
            counts + self.groups - 1,
            self.groups,
            rounding_mode="floor",
        ).to(dtype=torch.long)
        max_selected = int(selected_counts.max().item())
        ranked = torch.where(valid, factor_rows, torch.full_like(factor_rows, -torch.inf))
        selected = torch.topk(
            ranked,
            k=max_selected,
            dim=1,
            largest=True,
            sorted=True,
        ).indices
        rank_positions = torch.arange(max_selected, device=factor.device).unsqueeze(0)
        selected_rank_mask = rank_positions < selected_counts.unsqueeze(1)
        selected_returns = returns.gather(1, selected)
        gross = (
            selected_returns * selected_rank_mask.to(dtype=returns.dtype)
        ).sum(dim=1) / selected_counts.to(dtype=returns.dtype)
        benchmark = (
            torch.where(valid, returns, torch.zeros_like(returns)).sum(dim=1)
            / counts.to(dtype=returns.dtype)
        )
        gross_excess = gross - benchmark
        selected_members = torch.zeros_like(valid)
        selected_members.scatter_(1, selected, selected_rank_mask)
        turnovers = (
            1.0
            - (selected_members[1:] & selected_members[:-1]).sum(dim=1).to(dtype=returns.dtype)
            / selected_counts[1:].to(dtype=returns.dtype)
        )

        periods = int(gross_excess.shape[0])
        if periods == 0:
            return {
                "periods": 0,
                "gross_excess": None,
                "turnover": None,
                "annual_cost": None,
                "net_excess": None,
                "absolute_max_drawdown": None,
                "excess_max_drawdown": None,
            }
        years = periods * self.cycle / 252.0
        gross_annualized = float(gross_excess.sum().detach().item()) / years
        turnover = float(turnovers.mean().detach().item()) if len(turnovers) else 0.0
        annual_cost = turnover * (252.0 / self.cycle) * self.round_trip_cost
        absolute_max_drawdown = _max_drawdown_from_returns(gross)
        excess_max_drawdown = _relative_max_drawdown(gross, benchmark)
        return {
            "periods": periods,
            "gross_excess": gross_annualized,
            "turnover": turnover,
            "annual_cost": annual_cost,
            "net_excess": gross_annualized - annual_cost,
            "absolute_max_drawdown": absolute_max_drawdown,
            "excess_max_drawdown": excess_max_drawdown,
        }


def finite_as_nan(value: torch.Tensor) -> torch.Tensor:
    return torch.where(torch.isfinite(value), value, torch.full_like(value, torch.nan))


def _average_rank_by_day(value: torch.Tensor, valid: torch.Tensor) -> torch.Tensor:
    """Rank each cross-section with pandas/SciPy-compatible average ties.

    AlphaPROBE's bundled implementation builds a ``days x stocks x stocks``
    equality tensor.  The local full-A panel is too large for that path, so
    compute tie groups after sorting in linear memory instead.
    """
    safe_value = torch.where(valid, value, torch.full_like(value, torch.inf))
    order = torch.argsort(safe_value, dim=1, stable=True)
    sorted_value = safe_value.gather(1, order)
    sorted_valid = valid.gather(1, order)
    previous_value = torch.cat(
        [torch.full_like(sorted_value[:, :1], torch.inf), sorted_value[:, :-1]],
        dim=1,
    )
    previous_valid = torch.cat(
        [torch.zeros_like(sorted_valid[:, :1]), sorted_valid[:, :-1]],
        dim=1,
    )
    starts = sorted_valid & (~previous_valid | (sorted_value != previous_value))
    group_ids = torch.cumsum(starts.to(dtype=torch.long), dim=1) - 1
    safe_group_ids = group_ids.clamp_min(0)
    positions = torch.arange(value.shape[1], device=value.device, dtype=torch.float32)
    valid_float = sorted_valid.to(dtype=torch.float32)
    rank_sums = torch.zeros_like(sorted_value, dtype=torch.float32)
    rank_counts = torch.zeros_like(sorted_value, dtype=torch.float32)
    rank_sums.scatter_add_(1, safe_group_ids, positions.expand(value.shape[0], -1) * valid_float)
    rank_counts.scatter_add_(1, safe_group_ids, valid_float)
    average_sorted = rank_sums.gather(1, safe_group_ids).div(rank_counts.gather(1, safe_group_ids))
    average_sorted = torch.where(
        rank_counts.gather(1, safe_group_ids) > 0,
        average_sorted,
        torch.zeros_like(average_sorted),
    )
    ranks = torch.empty_like(safe_value, dtype=torch.float32)
    ranks.scatter_(1, order, average_sorted)
    return ranks.masked_fill(~valid, torch.nan)


def batch_spearmanr_linear(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Calculate daily rank correlation in O(days * stocks) memory."""
    valid = torch.isfinite(x) & torch.isfinite(y)
    ranked_x = _average_rank_by_day(x, valid)
    ranked_y = _average_rank_by_day(y, valid)
    return batch_pearsonr(ranked_x, ranked_y)


def expression_namespace() -> dict[str, object]:
    namespace: dict[str, object] = {}
    from alphagen.data import expression as expression_module

    namespace.update(vars(expression_module))
    namespace.update(vars(generic_features))
    # The local adapter resolves these leaves through the PIT Tushare store.
    # Keep the full PandaAI formula namespace available even when a field is
    # unavailable in the current cache; the terminal builder filters those
    # fields before GP starts.
    namespace.update(build_pandaai_namespace())
    # Accept the operator spellings used by PandaAI formula mode when a saved
    # candidate is reproduced locally. AlphaPROBE expressions remain valid as
    # well, so this is only an alias layer.
    operator_aliases = {
        "ABS": "Abs",
        "SIGN": "Sign",
        "LOG": "Log",
        "RANK": "Rank",
        "REF": "Ref",
        "MA": "TsMean",
        "SUM": "TsSum",
        "STDDEV": "TsStd",
        "TS_IR": "TsIr",
        "TS_MAX_MIN_DIFF": "TsMinMaxDiff",
        "TS_MAX_DIFF": "TsMaxDiff",
        "TS_MIN_DIFF": "TsMinDiff",
        "VAR": "TsVar",
        "TS_SKEW": "TsSkew",
        "TS_KURT": "TsKurt",
        "TS_MAX": "TsMax",
        "TS_MIN": "TsMin",
        "TS_MEDIAN": "TsMed",
        "TS_MAD": "TsMad",
        "TS_RANK": "TsRank",
        "DIFF": "TsDelta",
        "RETURNS": "TsPctChange",
        "TS_DIV": "TsDiv",
        "WMA": "TsWMA",
        "EMA": "TsEMA",
        "COV": "TsCov",
        "CORR": "TsCorr",
        "COVARIANCE": "TsCov",
        "CORRELATION": "TsCorr",
        "TS_COV": "TsCov",
        "TS_CORR": "TsCorr",
        "POWER": "Pow",
        "MAX": "GetGreater",
        "MIN": "GetLess",
    }
    namespace.update(
        {
            alias: getattr(expression_module, target)
            for alias, target in operator_aliases.items()
        }
    )
    return namespace


def local_terminals(
    data: TushareStockData,
    *,
    mode: str = "verified",
    field_file: Path | None = None,
    allow_unverified_fields: bool = False,
    allow_blocked_fields: bool = False,
) -> list[str]:
    """Return locally resolvable terminals within the selected search boundary.

    The default boundary is the field set that passed the current alignment
    quality gate.  Broader field ranges are diagnostic-only and must be
    explicitly enabled so a local proxy cannot be mistaken for a platform
    result.
    """
    return resolve_terminal_fields(
        active_fields=data.pandaai_field_store.active_search_fields(
            include_period_variants=True
        ),
        mode=mode,
        field_file=field_file,
        price_volume_fields=PRICE_VOLUME_FIELDS,
        formula_fields=formula_field_name_set(include_period_variants=False),
        allow_unverified_fields=allow_unverified_fields,
        allow_blocked_fields=allow_blocked_fields,
    )


def write_field_coverage(
    data: TushareStockData,
    output: Path,
    alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the full field inventory and a compact human-readable summary."""
    coverage = data.field_coverage()
    coverage["alignment"] = alignment or {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "correlation_method_reference": ALIGNMENT_CORRELATION_METHOD,
    }
    write_json(output / "field_coverage.json", coverage)
    counts = coverage["status_counts"]
    lines = [
        "# PandaAI local field coverage",
        "",
        f"- Platform formula-mode base fields: `{coverage['platform_formula_fields']}`",
        f"- Platform backtest catalog fields: `{coverage['platform_catalog_fields']}`",
        f"- Platform declared fields after de-duplication: `{coverage['platform_declared_fields']}`",
        f"- Catalog statement fields with `_mrq_n` expansion: `{coverage['catalog_statement_fields']}`",
        f"- Catalog daily technical fields: `{coverage['catalog_daily_technical_fields']}`",
        f"- Formula names including period variants: `{coverage['formula_names']}`",
        f"- Active search fields: `{len(coverage['active_search_fields'])}`",
        "- Search policy: PandaAI-declared catalog; Barra, intraday, Alpha191, and known FactorBuild-rejected families excluded from local active search",
        f"- Excluded Barra fields: `{', '.join(coverage['barra_fields_excluded'])}`",
        f"- Excluded unsupported families: `{', '.join(coverage['unsupported_base_fields'])}`",
        f"- Alignment rules: `{coverage['alignment']['alignment_rule_version']}`",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(
        [
            "",
            "## Base-field status",
            "",
            "| status | count |",
            "| --- | ---: |",
        ]
    )
    for status, count in sorted(coverage["base_status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(
        [
            "",
            "## Active fields",
            "",
            ", ".join(f"`{name}`" for name in coverage["active_search_fields"]),
        ]
    )
    (output / "field_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return coverage


def evaluate_formula(formula: str, namespace: dict[str, object]) -> object:
    return eval(formula, {"__builtins__": {}}, namespace)


def metric_summary(expression: object, data: TushareStockData, target: object) -> dict[str, float]:
    factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
    factor = normalize_by_day(factor)
    target_values = finite_as_nan(target.evaluate(data))  # type: ignore[attr-defined]
    pearson = torch.nan_to_num(batch_pearsonr(factor, target_values), nan=0.0)
    spearman = torch.nan_to_num(batch_spearmanr_linear(factor, target_values), nan=0.0)
    return {
        "ic_mean": float(pearson.mean().item()),
        "rank_ic_mean": float(spearman.mean().item()),
        "observations": int(torch.isfinite(target_values).sum().item()),
    }


def pool_metrics(pool: AlphaPool, data: TushareStockData, target: object) -> tuple[float, float]:
    """Evaluate an AlphaPool while avoiding the upstream quadratic Rank IC path."""
    with torch.no_grad():
        factors = []
        for index in range(pool.size):
            factor = pool._normalize_by_day(pool.exprs[index].evaluate(data))  # type: ignore[union-attr]
            factors.append(factor * pool.weights[index])
        combined_factor = sum(factors)
        target_factor = target.evaluate(data)  # type: ignore[attr-defined]
        ic = batch_pearsonr(combined_factor, target_factor).mean().item()
        rank_ic = batch_spearmanr_linear(combined_factor, target_factor).mean().item()
        return float(ic), float(rank_ic)


def expression_to_panda_formula(formula: str) -> str:
    """Translate an AlphaPROBE expression into the closest formula-mode form."""
    tree = ast.parse(formula, mode="eval")
    panda_fields = formula_field_name_set(include_period_variants=True)
    names = {
        "open_": "OPEN",
        "Open": "OPEN",
        "OPEN": "OPEN",
        "close": "CLOSE",
        "Close": "CLOSE",
        "CLOSE": "CLOSE",
        "high": "HIGH",
        "High": "HIGH",
        "HIGH": "HIGH",
        "low": "LOW",
        "Low": "LOW",
        "LOW": "LOW",
        "volume": "VOLUME",
        "Volume": "VOLUME",
        "VOLUME": "VOLUME",
    }
    unary = {
        "Abs": "ABS",
        "Sign": "SIGN",
        "Log": "LOG",
        "Rank": "RANK",
    }
    rolling = {
        "Ref": "REF",
        "TsMean": "MA",
        "TsSum": "SUM",
        "TsStd": "STDDEV",
        "TsVar": "VAR",
        "TsSkew": "TS_SKEW",
        "TsKurt": "TS_KURT",
        "TsMax": "TS_MAX",
        "TsMin": "TS_MIN",
        "TsMed": "TS_MEDIAN",
        "TsMad": "TS_MAD",
        "TsRank": "TS_RANK",
        "TsDelta": "DIFF",
        "TsPctChange": "RETURNS",
        "TsWMA": "WMA",
        "TsEMA": "EMA",
    }
    pair_rolling = {
        # PandaAI's documented formula-mode spellings are COV/CORR.
        # AlphaPROBE keeps the Ts* names internally.
        "TsCov": "COV",
        "TsCorr": "CORR",
    }

    def render(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            if node.id not in names:
                normalized = node.id.lower()
                if normalized not in panda_fields:
                    raise ValueError(f"unsupported AlphaPROBE name: {node.id}")
                return normalized.upper()
            return names[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, int) or float(node.value).is_integer():
                return str(int(node.value))
            return repr(float(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return f"(-{render(node.operand)})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return f"(+{render(node.operand)})"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            args = [render(argument) for argument in node.args]
            if name == "Constant":
                if len(args) != 1:
                    raise ValueError("Constant expects one argument")
                return args[0]
            if name in unary:
                if len(args) != 1:
                    raise ValueError(f"{name} expects one argument")
                return f"{unary[name]}({args[0]})"
            if name == "SLog1p":
                if len(args) != 1:
                    raise ValueError("SLog1p expects one argument")
                return f"(SIGN({args[0]})*LOG(1+ABS({args[0]})))"
            if name == "Inv":
                if len(args) != 1:
                    raise ValueError("Inv expects one argument")
                return f"(1/({args[0]}))"
            if name in {"Add", "Sub", "Mul", "Div", "Pow", "Greater", "Less"}:
                if len(args) != 2:
                    raise ValueError(f"{name} expects two arguments")
                operators = {
                    "Add": "+",
                    "Sub": "-",
                    "Mul": "*",
                    "Div": "/",
                }
                if name in operators:
                    return f"({args[0]}{operators[name]}{args[1]})"
                if name == "Pow":
                    return f"POWER({args[0]},{args[1]})"
                function = "MAX" if name == "Greater" else "MIN"
                return f"{function}({args[0]},{args[1]})"
            if name == "TsDiv":
                if len(args) != 2:
                    raise ValueError("TsDiv expects an expression and a window")
                return f"({args[0]}/MA({args[0]},{args[1]}))"
            if name == "TsIr":
                if len(args) != 2:
                    raise ValueError("TsIr expects an expression and a window")
                return f"(MA({args[0]},{args[1]})/STDDEV({args[0]},{args[1]}))"
            if name == "TsMinMaxDiff":
                if len(args) != 2:
                    raise ValueError("TsMinMaxDiff expects an expression and a window")
                return f"(TS_MAX({args[0]},{args[1]})-TS_MIN({args[0]},{args[1]}))"
            if name in {"TsMaxDiff", "TsMinDiff"}:
                if len(args) != 2:
                    raise ValueError(f"{name} expects an expression and a window")
                extreme = "TS_MAX" if name == "TsMaxDiff" else "TS_MIN"
                return f"({args[0]}-{extreme}({args[0]},{args[1]}))"
            if name in pair_rolling:
                if len(args) != 3:
                    raise ValueError(f"{name} expects two expressions and a window")
                return f"{pair_rolling[name]}({args[0]},{args[1]},{args[2]})"
            if name in rolling:
                if len(args) != 2:
                    raise ValueError(f"{name} expects an expression and a window")
                return f"{rolling[name]}({args[0]},{args[1]})"
            raise ValueError(f"unsupported AlphaPROBE operator: {name}")
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow):
                return f"POWER({render(node.left)},{render(node.right)})"
            operators = {
                ast.Add: "+",
                ast.Sub: "-",
                ast.Mult: "*",
                ast.Div: "/",
            }
            operator = operators.get(type(node.op))
            if operator is None:
                raise ValueError(f"unsupported expression operator: {type(node.op).__name__}")
            return f"({render(node.left)}{operator}{render(node.right)})"
        raise ValueError(f"unsupported AlphaPROBE syntax: {type(node).__name__}")

    return render(tree.body)


def run_aligned_net_excess(
    args: argparse.Namespace,
    cache_root: Path,
    batch_root: Path,
    run_output: Path,
) -> int:
    """Run GP with the local full-A, cost-adjusted long-side objective."""
    risk_control = args.objective == "aligned_net_excess_drawdown"
    if args.universe.lower() != "full_a":
        raise ValueError("--objective aligned_net_excess requires --universe full_a")
    if args.universe_limit is not None:
        raise ValueError("--objective aligned_net_excess does not support --universe-limit")
    if args.aligned_cycle < 1 or args.aligned_cycle > 10:
        raise ValueError("--aligned-cycle must be between 1 and 10")
    if args.aligned_groups < 2 or args.aligned_groups > 10:
        raise ValueError("--aligned-groups must be between 2 and 10")
    if args.aligned_label_offset < 0:
        raise ValueError("--aligned-label-offset must be non-negative")
    if args.aligned_round_trip_cost < 0:
        raise ValueError("--aligned-round-trip-cost must be non-negative")
    if risk_control:
        if args.aligned_absolute_dd_target < 0 or args.aligned_excess_dd_target < 0:
            raise ValueError("Drawdown targets must be non-negative")
        if args.aligned_absolute_dd_weight < 0 or args.aligned_excess_dd_weight < 0:
            raise ValueError("Drawdown weights must be non-negative")
        if args.aligned_absolute_dd_ceiling <= 0 or args.aligned_excess_dd_ceiling <= 0:
            raise ValueError("Drawdown ceilings must be positive")
        if args.aligned_absolute_dd_target > args.aligned_absolute_dd_ceiling:
            raise ValueError("Absolute drawdown target must not exceed its ceiling")
        if args.aligned_excess_dd_target > args.aligned_excess_dd_ceiling:
            raise ValueError("Excess drawdown target must not exceed its ceiling")

    aligned_start = parse_date(args.aligned_start)
    aligned_end = parse_date(args.aligned_end)
    data_start = parse_date(args.aligned_data_start)
    alignment_config = alignment_config_snapshot()
    alignment_config.update(
        {
            "data_start": data_start.strftime("%Y%m%d"),
            "start": aligned_start.strftime("%Y%m%d"),
            "end": aligned_end.strftime("%Y%m%d"),
            "groups": args.aligned_groups,
            "label_offset": args.aligned_label_offset,
            "round_trip_cost": args.aligned_round_trip_cost,
        }
    )
    validate_alignment_config(alignment_config)
    if aligned_start >= aligned_end:
        raise ValueError("--aligned-start must be earlier than --aligned-end")
    calendar = load_trade_dates(cache_root)
    if aligned_start not in calendar or aligned_end not in calendar:
        raise ValueError("Aligned dates must exist in the cached trading calendar")
    data_start_position = next(
        (index for index, date in enumerate(calendar) if date >= data_start),
        None,
    )
    if data_start_position is None:
        raise ValueError(f"No cached trading date is on or after {date_text(data_start)}")
    data_start = calendar[data_start_position]
    start_position = calendar.index(aligned_start)
    lookback = max(1, args.aligned_lookback)
    if start_position - data_start_position < lookback:
        raise ValueError(
            f"The local calendar needs {lookback} trading days before {date_text(aligned_start)}"
        )
    analysis_calendar = [
        date for date in calendar if data_start <= date <= aligned_end
    ]
    cap_root = args.cap_root.expanduser().resolve()
    print(f"objective={args.objective}", flush=True)
    print("data_source=local_tushare_qfq_daily_basic", flush=True)
    print(f"price_root={batch_root}", flush=True)
    print(f"cap_root={cap_root}", flush=True)
    print(
        f"alignment={date_text(aligned_start)}..{date_text(aligned_end)} "
        f"cycle={args.aligned_cycle} label_offset={args.aligned_label_offset} "
        f"groups={args.aligned_groups} round_trip_cost={args.aligned_round_trip_cost}",
        flush=True,
    )
    if risk_control:
        print(
            "drawdown_control="
            f"absolute_target={args.aligned_absolute_dd_target} "
            f"excess_target={args.aligned_excess_dd_target} "
            f"absolute_weight={args.aligned_absolute_dd_weight} "
            f"excess_weight={args.aligned_excess_dd_weight} "
            f"absolute_ceiling={args.aligned_absolute_dd_ceiling} "
            f"excess_ceiling={args.aligned_excess_dd_ceiling}",
            flush=True,
        )

    frame = load_full_a_data(batch_root, cap_root, data_start, aligned_end)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    print(f"aligned_rows={len(frame)} aligned_instruments={len(stock_ids)}", flush=True)

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        print(f"[note] {device} is unavailable; falling back to cpu", flush=True)
        device = torch.device("cpu")
    print(f"device={device}", flush=True)
    data = TushareStockData.from_aligned_frame(
        frame=frame,
        calendar=analysis_calendar,
        instrument=stock_ids,
        start_time=date_text(aligned_start),
        end_time=date_text(aligned_end),
        max_backtrack_days=lookback,
        max_future_days=0,
        device=device,
        financial_root=args.financial_root.expanduser().resolve(),
    )
    context = AlignedNetExcessContext(
        frame=frame,
        calendar=analysis_calendar,
        data=data,
        start_date=aligned_start,
        end_date=aligned_end,
        cycle=args.aligned_cycle,
        label_offset=args.aligned_label_offset,
        groups=args.aligned_groups,
        round_trip_cost=args.aligned_round_trip_cost,
    )
    if args.aligned_min_periods < 1 or args.aligned_min_periods > len(context.signal_dates):
        raise ValueError(
            "--aligned-min-periods must be between 1 and the number of aligned signal dates "
            f"({len(context.signal_dates)})"
        )
    print(f"data={data.summary()}", flush=True)
    print(
        f"signal_dates={len(context.signal_dates)} min_periods={args.aligned_min_periods}",
        flush=True,
    )
    field_coverage = write_field_coverage(
        data,
        run_output,
        alignment={
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "correlation_method_reference": ALIGNMENT_CORRELATION_METHOD,
            "universe": "full_a",
            "price_mode": "qfq",
            "market_cap_field": "total_mv",
            "start_date": date_text(aligned_start),
            "end_date": date_text(aligned_end),
            "cycle": args.aligned_cycle,
            "label_offset": args.aligned_label_offset,
            "groups": args.aligned_groups,
            "round_trip_cost": args.aligned_round_trip_cost,
            "financial_join": "announcement_date_pit_comp_type_1_ttm",
        },
    )
    terminals = local_terminals(
        data,
        mode=args.search_field_mode,
        field_file=args.search_field_file,
        allow_unverified_fields=args.allow_unverified_fields,
        allow_blocked_fields=args.allow_blocked_fields,
    )
    print(
        f"pandaai_fields base={field_coverage['platform_base_fields']} "
        f"formula_names={field_coverage['formula_names']} active={len(terminals)}",
        flush=True,
    )
    search_leaf_names = {str(field).strip().lower() for field in terminals}

    novelty_registry = args.novelty_registry.expanduser().resolve()
    if novelty_registry.exists():
        existing_formula_signatures = load_formula_signatures(novelty_registry)
    elif args.allow_existing_formulas:
        existing_formula_signatures = set()
    else:
        raise FileNotFoundError(
            "The historical formula registry is required for a final novel-factor search: "
            f"{novelty_registry}. Build it with scripts/factor_formula_dedupe.py first, "
            "or use --allow-existing-formulas only for a diagnostic run."
        )
    print(
        f"novelty_registry={novelty_registry} existing_signatures={len(existing_formula_signatures)} "
        f"allow_existing={args.allow_existing_formulas}",
        flush=True,
    )

    namespace = expression_namespace()
    cache: dict[str, float] = {}
    cache_stats: dict[str, dict[str, float | int | None]] = {}
    cache_errors: dict[str, str] = {}

    def fitness_for_stats(stats: dict[str, float | int | None]) -> float:
        """Convert aligned metrics into the GP's scalar search fitness."""
        net_excess = stats.get("net_excess")
        periods = int(stats.get("periods") or 0)
        if net_excess is None or periods < args.aligned_min_periods:
            return -1.0
        if not risk_control:
            return float(net_excess) if np.isfinite(float(net_excess)) else -1.0

        absolute_dd = stats.get("absolute_max_drawdown")
        excess_dd = stats.get("excess_max_drawdown")
        if absolute_dd is None or excess_dd is None:
            return -1.0
        absolute_dd = float(absolute_dd)
        excess_dd = float(excess_dd)
        if not np.isfinite(absolute_dd) or not np.isfinite(excess_dd):
            return -1.0
        if (
            absolute_dd > args.aligned_absolute_dd_ceiling
            or excess_dd > args.aligned_excess_dd_ceiling
        ):
            return -1.0 - absolute_dd - excess_dd

        score = (
            float(net_excess)
            - args.aligned_absolute_dd_weight * absolute_dd
            - args.aligned_excess_dd_weight * excess_dd
        )
        stats["risk_adjusted_score"] = score
        stats["absolute_dd_target_pass"] = int(
            absolute_dd <= args.aligned_absolute_dd_target
        )
        stats["excess_dd_target_pass"] = int(
            excess_dd <= args.aligned_excess_dd_target
        )
        return score

    def score_formula(_y: object, formula_values: object, _weights: object) -> float:
        formula = str(np.asarray(formula_values, dtype=object).reshape(-1)[0])
        if formula in cache:
            return cache[formula]
        try:
            expression = evaluate_formula(formula, namespace)
            if not bool(getattr(expression, "is_featured", False)):
                score = -1.0
            elif len(
                {
                    token.lower()
                    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
                    if token.lower() in search_leaf_names
                }
            ) < args.minimum_distinct_fields:
                score = -1.0
            else:
                with torch.no_grad():
                    factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
                    stats = context.score(factor)
                cache_stats[formula] = stats
                score = fitness_for_stats(stats)
        except Exception as exc:  # Invalid generated expressions are terminal candidates.
            score = -1.0
            cache_errors[formula] = f"{type(exc).__name__}: {exc}"
        cache[formula] = score
        return score

    metric = make_fitness(function=score_formula, greater_is_better=True)
    functions = [make_function(**operator._asdict()) for operator in generic_operators.funcs]
    active_terminal_count = len(terminals)
    terminals = terminals + [
        f"Constant({value})"
        for value in [
            -30.0,
            -10.0,
            -5.0,
            -2.0,
            -1.0,
            -0.5,
            -0.01,
            0.01,
            0.5,
            1.0,
            2.0,
            5.0,
            10.0,
            30.0,
        ]
    ]
    x_train = np.asarray([terminals], dtype=object)
    y_train = np.asarray([[1]], dtype=object)
    generation_results: list[dict[str, Any]] = []

    def cached_record(formula: str, score: float) -> dict[str, Any]:
        stats = cache_stats.get(formula, {})
        return {
            "formula": formula,
            "fitness": score,
            "net_excess": stats.get("net_excess"),
            "gross_excess": stats.get("gross_excess"),
            "turnover": stats.get("turnover"),
            "annual_cost": stats.get("annual_cost"),
            "absolute_max_drawdown": stats.get("absolute_max_drawdown"),
            "excess_max_drawdown": stats.get("excess_max_drawdown"),
            "risk_adjusted_score": stats.get("risk_adjusted_score"),
            "absolute_dd_target_pass": stats.get("absolute_dd_target_pass"),
            "excess_dd_target_pass": stats.get("excess_dd_target_pass"),
            "periods": stats.get("periods"),
            "coverage": (
                float(stats["periods"]) / len(context.signal_dates)
                if stats.get("periods") is not None
                else None
            ),
        }

    def all_cached_records() -> list[dict[str, Any]]:
        return [
            cached_record(formula, score)
            for formula, score in cache.items()
            if formula in cache_stats
        ]

    def top_records(limit: int = 20) -> list[dict[str, Any]]:
        records = sorted(
            all_cached_records(),
            key=lambda item: float(item.get("fitness") or -1.0),
            reverse=True,
        )
        return records[:limit]

    def on_generation() -> None:
        generation = len(generation_results) + 1
        record = {
            "generation": generation,
            "cache_size": len(cache),
            "top_formulas": top_records(),
        }
        generation_results.append(record)
        write_json(run_output / f"generation_{generation:03d}.json", record)
        print(json.dumps(record, ensure_ascii=False, default=json_default), flush=True)

    estimator = SymbolicRegressor(
        population_size=args.population_size,
        generations=args.generations,
        init_depth=(2, 6),
        tournament_size=args.tournament_size,
        stopping_criteria=1.0,
        p_crossover=0.3,
        p_subtree_mutation=0.1,
        p_hoist_mutation=0.01,
        p_point_mutation=0.1,
        p_point_replace=0.6,
        max_samples=0.9,
        verbose=1,
        parsimony_coefficient=0.001,
        random_state=args.seed,
        function_set=functions,
        metric=metric,
        const_range=None,
        n_jobs=args.n_jobs,
    )
    estimator.fit(x_train, y_train, callback=on_generation)

    best_program = estimator._program
    if best_program is None:
        raise RuntimeError("AlphaPROBE GP did not return a best program")
    best_formula_values = best_program.execute(x_train)
    best_formula = str(np.asarray(best_formula_values, dtype=object).reshape(-1)[0])
    best_expression = evaluate_formula(best_formula, namespace)
    with torch.no_grad():
        best_factor = finite_as_nan(best_expression.evaluate(data))  # type: ignore[attr-defined]
    best_stats = context.score(best_factor)
    best_fitness = fitness_for_stats(best_stats)
    try:
        best_panda_formula = expression_to_panda_formula(best_formula)
    except ValueError:
        best_panda_formula = best_formula
    late_stats = context.score(
        best_factor,
        start_date=pd.Timestamp("2025-01-01"),
        end_date=aligned_end,
    )
    early_stats = context.score(
        best_factor,
        start_date=aligned_start,
        end_date=pd.Timestamp("2024-12-31"),
    )

    def risk_eligible(item: dict[str, Any]) -> bool:
        net_excess = item.get("net_excess")
        absolute_dd = item.get("absolute_max_drawdown")
        excess_dd = item.get("excess_max_drawdown")
        if int(item.get("periods") or 0) < args.aligned_min_periods:
            return False
        if net_excess is None or absolute_dd is None or excess_dd is None:
            return False
        try:
            net_excess = float(net_excess)
            absolute_dd = float(absolute_dd)
            excess_dd = float(excess_dd)
        except (TypeError, ValueError):
            return False
        return bool(
            np.isfinite(net_excess)
            and np.isfinite(absolute_dd)
            and np.isfinite(excess_dd)
            and net_excess > 0.0
            and absolute_dd <= args.aligned_absolute_dd_ceiling
            and excess_dd <= args.aligned_excess_dd_ceiling
        )

    def pareto_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
        """Return whether left is at least as good on all three risk objectives."""
        left_values = (
            float(left["net_excess"]),
            float(left["absolute_max_drawdown"]),
            float(left["excess_max_drawdown"]),
        )
        right_values = (
            float(right["net_excess"]),
            float(right["absolute_max_drawdown"]),
            float(right["excess_max_drawdown"]),
        )
        no_worse = (
            left_values[0] >= right_values[0]
            and left_values[1] <= right_values[1]
            and left_values[2] <= right_values[2]
        )
        strictly_better = (
            left_values[0] > right_values[0]
            or left_values[1] < right_values[1]
            or left_values[2] < right_values[2]
        )
        return no_worse and strictly_better

    all_records = all_cached_records()
    if risk_control:
        eligible_records = [item for item in all_records if risk_eligible(item)]
        pareto_records = [
            item
            for item in eligible_records
            if not any(
                pareto_dominates(other, item)
                for other in eligible_records
                if other["formula"] != item["formula"]
            )
        ]
        pareto_formulas = {str(item["formula"]) for item in pareto_records}
        role_orders = [
            (
                "return_priority",
                lambda item: (
                    -float(item["net_excess"]),
                    float(item["absolute_max_drawdown"]),
                    float(item["excess_max_drawdown"]),
                ),
            ),
            (
                "risk_adjusted_balance",
                lambda item: (
                    -float(item["risk_adjusted_score"]),
                    -float(item["net_excess"]),
                    float(item["absolute_max_drawdown"]),
                ),
            ),
            (
                "drawdown_priority",
                lambda item: (
                    float(item["absolute_max_drawdown"]),
                    float(item["excess_max_drawdown"]),
                    -float(item["net_excess"]),
                ),
            ),
        ]
        candidate_sources = [
            (
                role,
                sorted(pareto_records, key=sort_key),
                True,
            )
            for role, sort_key in role_orders
        ]
        # If correlation filtering prevents a full Pareto set, fill from the
        # remaining valid risk candidates and mark those records explicitly.
        candidate_sources.append(
            (
                "risk_fallback",
                sorted(
                    [item for item in eligible_records if item["formula"] not in pareto_formulas],
                    key=lambda item: (
                        -float(item["risk_adjusted_score"]),
                        -float(item["net_excess"]),
                        float(item["absolute_max_drawdown"]),
                    ),
                ),
                False,
            )
        )
    else:
        eligible_records = []
        pareto_records = []
        candidate_sources = [
            (
                "fitness_priority",
                top_records(limit=max(50, args.output_candidates * 10)),
                False,
            )
        ]

    selected: list[dict[str, Any]] = []
    selected_signal_factors: list[torch.Tensor] = []
    seen_formulas: set[str] = set()
    seen_signatures: set[str] = set()
    novelty_excluded = 0
    signal_factor_cache: dict[str, torch.Tensor] = {}
    selection_rank_corr_threshold = (
        args.aligned_drawdown_candidate_rank_corr_threshold
        if risk_control
        else args.aligned_candidate_rank_corr_threshold
    )

    def try_select(
        item: dict[str, Any],
        selection_role: str,
        is_pareto_frontier: bool,
    ) -> bool:
        nonlocal novelty_excluded
        raw_formula = str(item["formula"])
        if risk_control and not risk_eligible(item):
            return False
        if not risk_control and (
            item.get("gross_excess") is None
            or item.get("turnover") is None
            or int(item.get("periods") or 0) < args.aligned_min_periods
        ):
            return False
        try:
            panda_formula = expression_to_panda_formula(raw_formula)
        except ValueError:
            panda_formula = raw_formula
        if panda_formula in seen_formulas:
            return False
        formula_signature = normalize_formula(panda_formula)
        if formula_signature is not None:
            if formula_signature in existing_formula_signatures and not args.allow_existing_formulas:
                novelty_excluded += 1
                return False
            if formula_signature in seen_signatures:
                return False

        try:
            signal_factor = signal_factor_cache.get(raw_formula)
            if signal_factor is None:
                expression = evaluate_formula(raw_formula, namespace)
                if not bool(getattr(expression, "is_featured", False)):
                    return False
                with torch.no_grad():
                    factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
                    signal_factor = factor[context.signal_data_positions]
                signal_factor_cache[raw_formula] = signal_factor
            prior_rank_correlations = [
                batch_spearmanr_linear(signal_factor, prior).nanmean().item()
                for prior in selected_signal_factors
            ]
        except Exception as exc:
            cache_errors.setdefault(raw_formula, f"candidate selection: {type(exc).__name__}: {exc}")
            return False

        finite_correlations = [value for value in prior_rank_correlations if np.isfinite(value)]
        max_rank_correlation = max(finite_correlations) if finite_correlations else None
        if (
            max_rank_correlation is not None
            and max_rank_correlation >= selection_rank_corr_threshold
        ):
            return False
        seen_formulas.add(panda_formula)
        if formula_signature is not None:
            seen_signatures.add(formula_signature)
        selected_item = dict(item)
        selected_item["panda_formula"] = panda_formula
        selected_item["formula_signature"] = formula_signature
        selected_item["max_rank_corr_to_selected"] = max_rank_correlation
        selected_item["selection_role"] = selection_role
        selected_item["pareto_frontier"] = bool(is_pareto_frontier)
        selected.append(selected_item)
        selected_signal_factors.append(signal_factor)
        return True

    # Interleave the role-specific sources so one return-heavy branch cannot
    # consume all slots before balance and drawdown-priority candidates run.
    source_positions = [0 for _ in candidate_sources]
    while len(selected) < args.output_candidates:
        selected_this_round = False
        for source_index, (selection_role, source, is_pareto_frontier) in enumerate(
            candidate_sources
        ):
            while source_positions[source_index] < len(source):
                item = source[source_positions[source_index]]
                source_positions[source_index] += 1
                if try_select(item, selection_role, is_pareto_frontier):
                    selected_this_round = True
                    break
            if len(selected) >= args.output_candidates:
                break
        if not selected_this_round:
            break

    candidate_path = PROJECT_ROOT / f"{run_output.name}-candidates.txt"
    candidate_header = (
        "# AlphaPROBE local drawdown-controlled aligned-net-excess candidates; direction=1"
        if risk_control
        else "# AlphaPROBE local aligned-net-excess candidates; direction=1"
    )
    candidate_lines = [
        candidate_header,
        f"# alignment={date_text(aligned_start)}..{date_text(aligned_end)} cycle={args.aligned_cycle} "
        f"label_offset={args.aligned_label_offset} groups={args.aligned_groups} "
        f"round_trip_cost={args.aligned_round_trip_cost}",
    ]
    if risk_control:
        candidate_lines.append(
            f"# drawdown_targets=absolute:{args.aligned_absolute_dd_target} "
            f"excess_proxy:{args.aligned_excess_dd_target} "
            f"ceilings=absolute:{args.aligned_absolute_dd_ceiling} "
            f"excess_proxy:{args.aligned_excess_dd_ceiling}"
        )
    for index, item in enumerate(selected, start=1):
        candidate_lines.append(f"F-NET{index:02d} ~ {item['panda_formula']} ~ 1")
    candidate_path.write_text("\n".join(candidate_lines) + "\n", encoding="utf-8")

    result = {
        "status": "completed",
        "objective": args.objective,
        "data_source": "local_tushare_qfq_daily_basic",
        "cache_root": cache_root,
        "batch_root": batch_root,
        "cap_root": cap_root,
        "financial_root": args.financial_root.expanduser().resolve(),
        "output": run_output,
        "candidate_file": candidate_path,
        "alignment": {
            "start_date": aligned_start,
            "end_date": aligned_end,
            "cycle": args.aligned_cycle,
            "label_offset": args.aligned_label_offset,
            "groups": args.aligned_groups,
            "round_trip_cost": args.aligned_round_trip_cost,
            "signal_dates": len(context.signal_dates),
            "min_periods": args.aligned_min_periods,
            "instruments": len(stock_ids),
        },
        "settings": {
            "seed": args.seed,
            "device": str(device),
            "population_size": args.population_size,
            "generations": args.generations,
            "tournament_size": args.tournament_size,
            "aligned_lookback": lookback,
            "aligned_min_periods": args.aligned_min_periods,
            "search_field_mode": args.search_field_mode,
            "search_field_file": args.search_field_file,
            "allow_unverified_fields": args.allow_unverified_fields,
            "allow_blocked_fields": args.allow_blocked_fields,
            "search_fields": terminals,
            "search_field_count": active_terminal_count,
            "minimum_distinct_fields": args.minimum_distinct_fields,
            "novelty_registry": novelty_registry,
            "existing_formula_signatures": len(existing_formula_signatures),
            "novelty_excluded_candidates": novelty_excluded,
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "output_candidates": args.output_candidates,
            "candidate_rank_corr_threshold": args.aligned_candidate_rank_corr_threshold,
            "drawdown_candidate_rank_corr_threshold": args.aligned_drawdown_candidate_rank_corr_threshold,
            "aligned_absolute_dd_target": args.aligned_absolute_dd_target,
            "aligned_excess_dd_target": args.aligned_excess_dd_target,
            "aligned_absolute_dd_weight": args.aligned_absolute_dd_weight,
            "aligned_excess_dd_weight": args.aligned_excess_dd_weight,
            "aligned_absolute_dd_ceiling": args.aligned_absolute_dd_ceiling,
            "aligned_excess_dd_ceiling": args.aligned_excess_dd_ceiling,
        },
        "drawdown_control": {
            "enabled": risk_control,
            "absolute_dd_target": args.aligned_absolute_dd_target,
            "excess_dd_target": args.aligned_excess_dd_target,
            "absolute_dd_weight": args.aligned_absolute_dd_weight,
            "excess_dd_weight": args.aligned_excess_dd_weight,
            "absolute_dd_ceiling": args.aligned_absolute_dd_ceiling,
            "excess_dd_ceiling": args.aligned_excess_dd_ceiling,
            "excess_dd_definition": "drawdown of portfolio equity relative to factor_valid benchmark equity; local proxy",
            "candidate_rank_corr_threshold": selection_rank_corr_threshold,
        },
        "dataset": data.summary(),
        "field_coverage": {
            "platform_base_fields": field_coverage["platform_base_fields"],
            "platform_formula_fields": field_coverage["platform_formula_fields"],
            "platform_catalog_fields": field_coverage["platform_catalog_fields"],
            "platform_declared_fields": field_coverage["platform_declared_fields"],
            "catalog_statement_fields": field_coverage["catalog_statement_fields"],
            "catalog_daily_technical_fields": field_coverage["catalog_daily_technical_fields"],
            "formula_names": field_coverage["formula_names"],
            "active_search_fields": active_terminal_count,
            "status_counts": field_coverage["status_counts"],
            "barra_fields_excluded": field_coverage["barra_fields_excluded"],
            "unsupported_base_fields": field_coverage["unsupported_base_fields"],
            "base_status_counts": field_coverage["base_status_counts"],
        },
        "search": {
            "mode": args.search_field_mode,
            "field_file": args.search_field_file,
            "allow_unverified_fields": args.allow_unverified_fields,
            "allow_blocked_fields": args.allow_blocked_fields,
            "fields": terminals,
            "field_count": active_terminal_count,
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        },
        "best_formula": best_formula,
        "best_panda_formula": best_panda_formula,
        "best_train_fitness": float(best_program.raw_fitness_),
        "best_objective_fitness": best_fitness,
        "best_stats": best_stats,
        "early_stats": early_stats,
        "late_stats": late_stats,
        "top_candidates": selected,
        "selection": {
            "requested": args.output_candidates,
            "selected": len(selected),
            "eligible_risk_candidates": len(eligible_records) if risk_control else None,
            "pareto_frontier_candidates": len(pareto_records) if risk_control else None,
            "pareto_frontier_selected": sum(
                1 for item in selected if item.get("pareto_frontier")
            )
            if risk_control
            else None,
        },
        "cache_size": len(cache),
        "cache": cache,
        "cache_errors": cache_errors,
        "generation_results": generation_results,
        "run_details": estimator.run_details_,
    }
    write_json(run_output / "gp_run.json", result)
    report_title = (
        "# AlphaPROBE drawdown-controlled aligned net-excess search"
        if risk_control
        else "# AlphaPROBE aligned net-excess search"
    )
    if risk_control:
        objective_line = (
            f"- Objective: maximize annualized top `{100 / args.aligned_groups:.1f}%` net excess "
            f"minus `{args.aligned_absolute_dd_weight:.2f}` x absolute max drawdown "
            f"minus `{args.aligned_excess_dd_weight:.2f}` x excess max drawdown"
        )
        drawdown_lines = [
            f"- Drawdown targets: absolute `<= {args.aligned_absolute_dd_target:.2%}`, "
            f"excess proxy `<= {args.aligned_excess_dd_target:.2%}`",
            f"- Drawdown ceilings: absolute `<= {args.aligned_absolute_dd_ceiling:.2%}`, "
            f"excess proxy `<= {args.aligned_excess_dd_ceiling:.2%}`",
            "- Excess max drawdown is a local relative-equity proxy against the factor-valid benchmark; it is not a byte-level claim about PandaAI's internal field.",
            f"- Eligible positive-net candidates: `{len(eligible_records)}`; Pareto frontier: `{len(pareto_records)}`; selected: `{len(selected)}`",
        ]
        table_header = (
            "| rank | role | Pareto | raw AlphaPROBE formula | PandaAI formula | net excess | "
            "risk-adjusted score | abs max DD | excess max DD | turnover | coverage | max prior Rank corr |"
        )
        table_divider = (
            "| ---: | --- | :---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
        )
    else:
        objective_line = (
            f"- Objective: annualized top `{100 / args.aligned_groups:.1f}%` excess minus turnover cost; round-trip cost `{args.aligned_round_trip_cost:.4f}` "
            f"(one-way `{args.aligned_round_trip_cost / 2:.4f}`)"
        )
        drawdown_lines = []
        table_header = (
            "| rank | raw AlphaPROBE formula | PandaAI formula | net excess | gross excess | turnover | annual cost | coverage | max prior Rank corr |"
        )
        table_divider = "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"
    report_lines = [
        report_title,
        "",
        f"- Alignment: `{date_text(aligned_start)}..{date_text(aligned_end)}`",
        f"- Signals: `{len(context.signal_dates)}`; minimum candidate coverage: `{args.aligned_min_periods}` periods; cycle: `{args.aligned_cycle}` trading days",
        f"- Universe: `{len(stock_ids)}` local full-A instruments; qfq + daily_basic",
        objective_line,
        *drawdown_lines,
        f"- GP expressions scored: `{len(cache)}`; invalid: `{len(cache_errors)}`",
        f"- GP search terminals: `{len(terminals)}` via `{args.search_field_mode}`",
        f"- Minimum distinct search fields per expression: `{args.minimum_distinct_fields}`",
        f"- Candidate deduplication: positive signal-panel Rank correlation `< {selection_rank_corr_threshold:.3f}`",
        f"- Historical formula exclusion: `{novelty_excluded}` candidates matched `{novelty_registry.name}`; selected formulas are required to have a new normalized signature.",
        "",
        table_header,
        table_divider,
    ]
    for index, item in enumerate(selected, start=1):
        rank_corr = item["max_rank_corr_to_selected"]
        rank_corr_text = "n/a" if rank_corr is None else f"{float(rank_corr):.4f}"
        if risk_control:
            report_lines.append(
                f"| {index} | {item['selection_role']} | "
                f"{'yes' if item['pareto_frontier'] else 'no'} | "
                f"`{item['formula']}` | `{item['panda_formula']}` | "
                f"{float(item['net_excess']) * 100:.2f}% | "
                f"{float(item['risk_adjusted_score']) * 100:.2f}% | "
                f"{float(item['absolute_max_drawdown']) * 100:.2f}% | "
                f"{float(item['excess_max_drawdown']) * 100:.2f}% | "
                f"{float(item['turnover']) * 100:.2f}% | "
                f"{float(item['coverage']) * 100:.1f}% | "
                f"{rank_corr_text} |"
            )
        else:
            report_lines.append(
                f"| {index} | `{item['formula']}` | `{item['panda_formula']}` | "
                f"{float(item['net_excess']) * 100:.2f}% | "
                f"{float(item['gross_excess']) * 100:.2f}% | "
                f"{float(item['turnover']) * 100:.2f}% | "
                f"{float(item['annual_cost']) * 100:.2f}% | "
                f"{float(item['coverage']) * 100:.1f}% | "
                f"{rank_corr_text} |"
            )
    report_lines.extend(
        [
            "",
            "## Best formula diagnostics",
            "",
            f"- Raw AlphaPROBE formula: `{best_formula}`",
            f"- PandaAI formula: `{result['best_panda_formula']}`",
            f"- Full aligned net excess: `{float(best_stats['net_excess']) * 100:.2f}%`",
            f"- Early net excess through 2024-12-31: `{float(early_stats['net_excess']) * 100:.2f}%`",
            f"- Late net excess from 2025-01-01: `{float(late_stats['net_excess']) * 100:.2f}%`",
            *(
                [
                    f"- Full absolute max drawdown: `{float(best_stats['absolute_max_drawdown']) * 100:.2f}%`",
                    f"- Full excess max drawdown proxy: `{float(best_stats['excess_max_drawdown']) * 100:.2f}%`",
                    f"- Full risk-adjusted score: `{float(best_stats['risk_adjusted_score']) * 100:.2f}%`",
                ]
                if risk_control
                else []
            ),
            "",
            "The local score is a research proxy; no PandaAI factor was created or run by this search.",
        ]
    )
    (run_output / "aligned_net_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    print(f"best_formula={best_formula}", flush=True)
    print(f"best_panda_formula={best_panda_formula}", flush=True)
    print(f"best_net_excess={best_stats['net_excess']}", flush=True)
    print(f"candidate_file={candidate_path}", flush=True)
    print(f"result={run_output / 'gp_run.json'}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--objective",
        choices=["ic", "aligned_net_excess", "aligned_net_excess_drawdown"],
        default="ic",
        help=(
            "fitness objective; aligned_net_excess uses the local full-A alignment proxy, "
            "aligned_net_excess_drawdown adds absolute and excess drawdown control"
        ),
    )
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--batch-root", type=Path, default=None)
    parser.add_argument(
        "--financial-root",
        type=Path,
        default=DEFAULT_FINANCIAL_ROOT,
        help="PIT Tushare financial cache used by PandaAI named fields",
    )
    parser.add_argument(
        "--cap-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a",
        help="daily_basic cache used by the aligned full-A objective",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--universe", default="all", help="all, comma-separated codes, or a file")
    parser.add_argument("--universe-limit", type=int, default=None)
    parser.add_argument("--train-start", default="20180102")
    parser.add_argument("--train-end", default="20221230")
    parser.add_argument("--valid-start", default="20230101")
    parser.add_argument("--valid-end", default="20231229")
    parser.add_argument("--test-start", default="20240101")
    parser.add_argument("--test-end", default="20260907")
    parser.add_argument("--max-backtrack-days", type=int, default=756)
    parser.add_argument("--max-future-days", type=int, default=30)
    parser.add_argument("--population-size", type=int, default=1000)
    parser.add_argument("--generations", type=int, default=40)
    parser.add_argument("--tournament-size", type=int, default=600)
    parser.add_argument("--pool-sizes", default="10,20,50,100")
    parser.add_argument("--pool-opt-iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument(
        "--search-field-mode",
        choices=["verified", "all", "base", "price_volume"],
        default="verified",
        help="terminal subset used by GP; verified is the aligned default",
    )
    parser.add_argument(
        "--search-field-file",
        type=Path,
        default=None,
        help="optional newline/comma-separated terminal list overriding search-field-mode",
    )
    parser.add_argument(
        "--allow-unverified-fields",
        action="store_true",
        help="allow all/base/custom fields outside the aligned verified set (diagnostic only)",
    )
    parser.add_argument(
        "--allow-blocked-fields",
        action="store_true",
        help="allow fields blocked by the alignment failure registry (diagnostic only)",
    )
    parser.add_argument(
        "--novelty-registry",
        type=Path,
        default=DEFAULT_FORMULA_REGISTRY,
        help="historical normalized formula registry used to exclude existing factors",
    )
    parser.add_argument(
        "--allow-existing-formulas",
        action="store_true",
        help="diagnostic mode: do not exclude formulas found in the historical registry",
    )
    parser.add_argument("--aligned-start", default=date_text(ALIGNED_START).replace("-", ""))
    parser.add_argument("--aligned-end", default=date_text(ALIGNED_END).replace("-", ""))
    parser.add_argument("--aligned-cycle", type=int, default=ALIGNED_CYCLE)
    parser.add_argument("--aligned-label-offset", type=int, default=ALIGNED_LABEL_OFFSET)
    parser.add_argument("--aligned-groups", type=int, default=ALIGNED_GROUPS)
    parser.add_argument("--aligned-data-start", default=date_text(ALIGNED_DATA_START).replace("-", ""))
    parser.add_argument("--aligned-lookback", type=int, default=756)
    parser.add_argument(
        "--aligned-min-periods",
        type=int,
        default=ALIGNED_MIN_PERIODS,
        help="minimum valid aligned signal periods required for a candidate",
    )
    parser.add_argument("--output-candidates", type=int, default=3)
    parser.add_argument(
        "--minimum-distinct-fields",
        type=int,
        default=1,
        help="minimum number of distinct named search fields used by each expression",
    )
    parser.add_argument(
        "--aligned-candidate-rank-corr-threshold",
        type=float,
        default=ALIGNED_CANDIDATE_RANK_CORR_THRESHOLD,
        help="skip later candidates whose positive signal-panel Rank correlation reaches this threshold",
    )
    parser.add_argument(
        "--aligned-drawdown-candidate-rank-corr-threshold",
        type=float,
        default=ALIGNED_DRAWDOWN_CANDIDATE_RANK_CORR_THRESHOLD,
        help="risk-mode candidate Rank correlation threshold used to keep selected roles distinct",
    )
    parser.add_argument(
        "--aligned-round-trip-cost",
        type=float,
        default=ALIGNED_ROUND_TRIP_COST,
        help="round-trip cost used by the local net-excess objective",
    )
    parser.add_argument(
        "--aligned-absolute-dd-target",
        type=float,
        default=ALIGNED_ABSOLUTE_DD_TARGET,
        help="absolute max drawdown target for the drawdown-controlled objective",
    )
    parser.add_argument(
        "--aligned-excess-dd-target",
        type=float,
        default=ALIGNED_EXCESS_DD_TARGET,
        help="relative-equity excess max drawdown target for the drawdown-controlled objective",
    )
    parser.add_argument(
        "--aligned-absolute-dd-weight",
        type=float,
        default=ALIGNED_ABSOLUTE_DD_WEIGHT,
        help="penalty weight for absolute max drawdown",
    )
    parser.add_argument(
        "--aligned-excess-dd-weight",
        type=float,
        default=ALIGNED_EXCESS_DD_WEIGHT,
        help="penalty weight for relative-equity excess max drawdown",
    )
    parser.add_argument(
        "--aligned-absolute-dd-ceiling",
        type=float,
        default=ALIGNED_ABSOLUTE_DD_CEILING,
        help="hard ceiling for absolute max drawdown",
    )
    parser.add_argument(
        "--aligned-excess-dd-ceiling",
        type=float,
        default=ALIGNED_EXCESS_DD_CEILING,
        help="hard ceiling for relative-equity excess max drawdown",
    )
    return parser


def parse_pool_sizes(value: str) -> list[int]:
    sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not sizes or any(size < 1 for size in sizes):
        raise ValueError("--pool-sizes must contain positive integers")
    return list(dict.fromkeys(sizes))


def main() -> int:
    args = build_parser().parse_args()
    cache_root = args.cache_root.expanduser().resolve()
    batch_root = (args.batch_root or cache_root / "tushare_factor_recheck" / "qfq" / "daily_batches").expanduser().resolve()
    run_output = args.output
    if run_output is None:
        run_output = DEFAULT_OUTPUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_output = run_output.expanduser().resolve()
    run_output.mkdir(parents=True, exist_ok=True)

    if args.population_size < 2:
        raise ValueError("--population-size must be at least 2")
    if args.generations < 1:
        raise ValueError("--generations must be at least 1")
    if args.tournament_size < 1:
        raise ValueError("--tournament-size must be at least 1")
    if args.output_candidates < 1:
        raise ValueError("--output-candidates must be at least 1")
    if args.minimum_distinct_fields < 1:
        raise ValueError("--minimum-distinct-fields must be at least 1")
    if not 0.0 <= args.aligned_candidate_rank_corr_threshold <= 1.0:
        raise ValueError("--aligned-candidate-rank-corr-threshold must be between 0 and 1")
    if not 0.0 <= args.aligned_drawdown_candidate_rank_corr_threshold <= 1.0:
        raise ValueError(
            "--aligned-drawdown-candidate-rank-corr-threshold must be between 0 and 1"
        )
    pool_sizes = parse_pool_sizes(args.pool_sizes)
    if args.objective in {"aligned_net_excess", "aligned_net_excess_drawdown"}:
        return run_aligned_net_excess(args, cache_root, batch_root, run_output)
    calendar = load_trade_dates(cache_root)
    universe = resolve_universe(cache_root, args.universe, args.universe_limit)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        print(f"[note] {device} is unavailable; falling back to cpu")
        device = torch.device("cpu")

    print("data_source=local_tushare_qfq")
    print(f"batch_root={batch_root}")
    print(f"universe={'dynamic' if universe is None else len(universe)}")
    print(f"device={device}")
    train_data = TushareStockData(
        batch_root=batch_root,
        calendar=calendar,
        instrument=universe,
        start_time=args.train_start,
        end_time=args.train_end,
        max_backtrack_days=args.max_backtrack_days,
        max_future_days=args.max_future_days,
        device=device,
        financial_root=args.financial_root.expanduser().resolve(),
    )
    valid_data = TushareStockData(
        batch_root=batch_root,
        calendar=calendar,
        instrument=universe,
        start_time=args.valid_start,
        end_time=args.valid_end,
        max_backtrack_days=args.max_backtrack_days,
        max_future_days=args.max_future_days,
        device=device,
        financial_root=args.financial_root.expanduser().resolve(),
    )
    test_data = TushareStockData(
        batch_root=batch_root,
        calendar=calendar,
        instrument=universe,
        start_time=args.test_start,
        end_time=args.test_end,
        max_backtrack_days=args.max_backtrack_days,
        max_future_days=args.max_future_days,
        device=device,
        financial_root=args.financial_root.expanduser().resolve(),
    )
    print(f"train={train_data.summary()}")
    print(f"valid={valid_data.summary()}")
    print(f"test={test_data.summary()}")
    field_coverage = write_field_coverage(train_data, run_output)
    terminals = local_terminals(
        train_data,
        mode=args.search_field_mode,
        field_file=args.search_field_file,
        allow_unverified_fields=args.allow_unverified_fields,
        allow_blocked_fields=args.allow_blocked_fields,
    )
    print(
        f"pandaai_fields base={field_coverage['platform_base_fields']} "
        f"formula_names={field_coverage['formula_names']} active={len(terminals)}",
    )

    close = Feature(FeatureType.CLOSE)
    target = Ref(close, -20) / close - 1
    target_factor = finite_as_nan(target.evaluate(train_data))
    namespace = expression_namespace()
    cache: dict[str, float] = {}
    cache_errors: dict[str, str] = {}

    def score_formula(_y: object, formula_values: object, _weights: object) -> float:
        formula = str(np.asarray(formula_values, dtype=object).reshape(-1)[0])
        if formula in cache:
            return cache[formula]
        try:
            expression = evaluate_formula(formula, namespace)
            if not bool(getattr(expression, "is_featured", False)):
                score = -1.0
            else:
                factor = finite_as_nan(expression.evaluate(train_data))  # type: ignore[attr-defined]
                factor = normalize_by_day(factor)
                score = float(torch.nan_to_num(batch_pearsonr(factor, target_factor), nan=0.0).mean().item())
                if not np.isfinite(score):
                    score = -1.0
        except Exception as exc:  # Invalid generated expressions are terminal candidates.
            score = -1.0
            cache_errors[formula] = f"{type(exc).__name__}: {exc}"
        cache[formula] = score
        return score

    metric = make_fitness(function=score_formula, greater_is_better=True)
    functions = [make_function(**operator._asdict()) for operator in generic_operators.funcs]
    active_terminal_count = len(terminals)
    terminals = terminals + [
        f"Constant({value})"
        for value in [-30.0, -10.0, -5.0, -2.0, -1.0, -0.5, -0.01, 0.01, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    ]
    x_train = np.asarray([terminals], dtype=object)
    y_train = np.asarray([[1]], dtype=object)
    generation_results: list[dict[str, Any]] = []

    def ranked_expressions(limit: int) -> list[object]:
        expressions: list[object] = []
        for formula, _score in sorted(cache.items(), key=lambda item: item[1], reverse=True):
            try:
                expression = evaluate_formula(formula, namespace)
            except Exception:
                continue
            if not bool(getattr(expression, "is_featured", False)):
                continue
            expressions.append(expression)
            if len(expressions) >= limit:
                break
        return expressions

    def pool_result(capacity: int) -> dict[str, Any]:
        expressions = ranked_expressions(capacity)
        if not expressions:
            return {"capacity": capacity, "expression_count": 0, "error": "no valid expressions"}
        try:
            pool = AlphaPool(
                capacity=capacity,
                stock_data=train_data,
                target=target,
                ic_lower_bound=None,
            )
            pool.force_load_exprs(expressions)
            if pool.size > 1:
                pool._optimize(alpha=5e-3, lr=5e-4, n_iter=args.pool_opt_iterations)
            ic_test, rank_ic_test = pool_metrics(pool, test_data, target)
            ic_valid, rank_ic_valid = pool_metrics(pool, valid_data, target)
            return {
                "capacity": capacity,
                "expression_count": len(expressions),
                "train_ensemble_ic": float(pool.evaluate_ensemble()),
                "valid_ensemble_ic": float(torch.nan_to_num(torch.as_tensor(ic_valid), nan=0.0).item()),
                "valid_ensemble_rank_ic": float(torch.nan_to_num(torch.as_tensor(rank_ic_valid), nan=0.0).item()),
                "test_ensemble_ic": float(torch.nan_to_num(torch.as_tensor(ic_test), nan=0.0).item()),
                "test_ensemble_rank_ic": float(torch.nan_to_num(torch.as_tensor(rank_ic_test), nan=0.0).item()),
                "expressions": [str(expression) for expression in expressions],
            }
        except Exception as exc:
            return {
                "capacity": capacity,
                "expression_count": len(expressions),
                "error": f"{type(exc).__name__}: {exc}",
            }

    def on_generation() -> None:
        generation = len(generation_results) + 1
        record = {
            "generation": generation,
            "cache_size": len(cache),
            "top_formulas": [
                {"formula": formula, "train_ic": score}
                for formula, score in sorted(cache.items(), key=lambda item: item[1], reverse=True)[:20]
            ],
            "pools": [pool_result(capacity) for capacity in pool_sizes],
        }
        generation_results.append(record)
        write_json(run_output / f"generation_{generation:03d}.json", record)
        print(json.dumps(record, ensure_ascii=False, default=json_default))

    estimator = SymbolicRegressor(
        population_size=args.population_size,
        generations=args.generations,
        init_depth=(2, 6),
        tournament_size=args.tournament_size,
        stopping_criteria=1.0,
        p_crossover=0.3,
        p_subtree_mutation=0.1,
        p_hoist_mutation=0.01,
        p_point_mutation=0.1,
        p_point_replace=0.6,
        max_samples=0.9,
        verbose=1,
        parsimony_coefficient=0.001,
        random_state=args.seed,
        function_set=functions,
        metric=metric,
        const_range=None,
        n_jobs=args.n_jobs,
    )
    estimator.fit(x_train, y_train, callback=on_generation)

    best_program = estimator._program
    if best_program is None:
        raise RuntimeError("AlphaPROBE GP did not return a best program")
    # The GP function names include the window (for example ``TsCorr40``),
    # while their wrapper emits the executable AlphaPROBE expression
    # ``TsCorr(...,40)``. Evaluate the program against the string terminals so
    # the wrapper, rather than ``_Program.__str__``, preserves that parameter.
    best_formula_values = best_program.execute(x_train)
    best_formula = str(np.asarray(best_formula_values, dtype=object).reshape(-1)[0])
    best_expression = evaluate_formula(best_formula, namespace)
    result = {
        "status": "completed",
        "data_source": "local_tushare_qfq",
        "cache_root": cache_root,
        "batch_root": batch_root,
        "output": run_output,
        "universe": "dynamic" if universe is None else list(universe),
        "settings": {
            "seed": args.seed,
            "device": str(device),
            "population_size": args.population_size,
            "generations": args.generations,
            "tournament_size": args.tournament_size,
            "pool_sizes": pool_sizes,
            "max_backtrack_days": args.max_backtrack_days,
            "max_future_days": args.max_future_days,
            "search_field_mode": args.search_field_mode,
            "search_field_file": args.search_field_file,
            "allow_unverified_fields": args.allow_unverified_fields,
            "allow_blocked_fields": args.allow_blocked_fields,
            "search_fields": terminals,
            "search_field_count": active_terminal_count,
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        },
        "datasets": {
            "train": train_data.summary(),
            "valid": valid_data.summary(),
            "test": test_data.summary(),
        },
        "financial_root": args.financial_root.expanduser().resolve(),
        "field_coverage": {
            "platform_base_fields": field_coverage["platform_base_fields"],
            "platform_formula_fields": field_coverage["platform_formula_fields"],
            "platform_catalog_fields": field_coverage["platform_catalog_fields"],
            "platform_declared_fields": field_coverage["platform_declared_fields"],
            "catalog_statement_fields": field_coverage["catalog_statement_fields"],
            "catalog_daily_technical_fields": field_coverage["catalog_daily_technical_fields"],
            "formula_names": field_coverage["formula_names"],
            "active_search_fields": active_terminal_count,
            "status_counts": field_coverage["status_counts"],
            "barra_fields_excluded": field_coverage["barra_fields_excluded"],
            "unsupported_base_fields": field_coverage["unsupported_base_fields"],
            "base_status_counts": field_coverage["base_status_counts"],
        },
        "search": {
            "mode": args.search_field_mode,
            "field_file": args.search_field_file,
            "allow_unverified_fields": args.allow_unverified_fields,
            "allow_blocked_fields": args.allow_blocked_fields,
            "fields": terminals,
            "field_count": active_terminal_count,
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        },
        "best_formula": best_formula,
        "best_train_fitness": float(best_program.raw_fitness_),
        "best_metrics": {
            "train": metric_summary(best_expression, train_data, target),
            "valid": metric_summary(best_expression, valid_data, target),
            "test": metric_summary(best_expression, test_data, target),
        },
        "cache_size": len(cache),
        "cache": cache,
        "cache_errors": cache_errors,
        "generation_results": generation_results,
        "run_details": estimator.run_details_,
    }
    write_json(run_output / "gp_run.json", result)
    print(f"best_formula={best_formula}")
    print(f"result={run_output / 'gp_run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
