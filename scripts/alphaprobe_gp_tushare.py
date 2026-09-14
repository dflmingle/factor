#!/usr/bin/env python3
"""Run AlphaPROBE genetic programming on the local Tushare qfq cache.

AlphaPROBE's expression engine only requires a small StockData-like object.
This runner supplies that object from the project's cached Tushare Parquet
files, so Qlib is not used for data loading or calendar lookup.
"""

from __future__ import annotations

import argparse
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
    batch_spearmanr,
)
from alphagen.utils.pytorch_utils import normalize_by_day  # noqa: E402
from alphagen_generic import features as generic_features  # noqa: E402
from alphagen_generic import operators as generic_operators  # noqa: E402
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
    wanted = ["date", "instrument", "open", "close", "volume", "high_qfq", "low_qfq"]
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
            columns=["date", "instrument", "open", "close", "volume", "high", "low"]
        )

    frame = pd.concat(frames, ignore_index=True)
    for column in ["open", "close", "volume", "high_qfq", "low_qfq"]:
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
    frame = frame.drop_duplicates(subset=["date", "instrument"], keep="last")
    return frame[["date", "instrument", "open", "close", "volume", "high", "low"]].sort_values(
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
    if spec.lower() in {"all", "auto", "full_a"}:
        values: list[str] | None = None
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


def finite_as_nan(value: torch.Tensor) -> torch.Tensor:
    return torch.where(torch.isfinite(value), value, torch.full_like(value, torch.nan))


def expression_namespace() -> dict[str, object]:
    namespace: dict[str, object] = {}
    from alphagen.data import expression as expression_module

    namespace.update(vars(expression_module))
    namespace.update(vars(generic_features))
    return namespace


def evaluate_formula(formula: str, namespace: dict[str, object]) -> object:
    return eval(formula, {"__builtins__": {}}, namespace)


def metric_summary(expression: object, data: TushareStockData, target: object) -> dict[str, float]:
    factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
    factor = normalize_by_day(factor)
    target_values = finite_as_nan(target.evaluate(data))  # type: ignore[attr-defined]
    pearson = torch.nan_to_num(batch_pearsonr(factor, target_values), nan=0.0)
    spearman = torch.nan_to_num(batch_spearmanr(factor, target_values), nan=0.0)
    return {
        "ic_mean": float(pearson.mean().item()),
        "rank_ic_mean": float(spearman.mean().item()),
        "observations": int(torch.isfinite(target_values).sum().item()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--batch-root", type=Path, default=None)
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
    pool_sizes = parse_pool_sizes(args.pool_sizes)
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
    )
    print(f"train={train_data.summary()}")
    print(f"valid={valid_data.summary()}")
    print(f"test={test_data.summary()}")

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
    terminals = [
        "open_",
        "close",
        "high",
        "low",
        "volume",
        *[f"Constant({value})" for value in [-30.0, -10.0, -5.0, -2.0, -1.0, -0.5, -0.01, 0.01, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]],
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
            ic_test, rank_ic_test = pool.test_ensemble(test_data, target)
            ic_valid, rank_ic_valid = pool.test_ensemble(valid_data, target)
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
        },
        "datasets": {
            "train": train_data.summary(),
            "valid": valid_data.summary(),
            "test": test_data.summary(),
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
