#!/usr/bin/env python3
"""Download Tushare daily bars and locally recheck workflow 6aa40282 factors.

The downloader is deliberately resumable.  Tushare's daily endpoint is queried
one trading day at a time because a date-range request is capped before it can
return the full A-share universe.  Completed batches are written immediately
under QuantLab's project cache and can be reused by a later analysis run.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUANTLAB_ROOT = PROJECT_ROOT / "quantlab"
DEFAULT_CACHE_ROOT = QUANTLAB_ROOT / ".quantlab" / "cache" / "research" / "cn_equity"
CACHE_ROOT = Path(
    os.environ.get("FACTOR_RESEARCH_CACHE_ROOT", str(DEFAULT_CACHE_ROOT))
).expanduser()
RECHECK_ROOT = CACHE_ROOT / "tushare_factor_recheck"
BATCH_ROOT = RECHECK_ROOT / "daily_batches"
REPORT_ROOT = RECHECK_ROOT / "reports"

DEFAULT_WARMUP = "20210101"
DEFAULT_START = "20210907"
DEFAULT_END = "20260907"
DEFAULT_BATCH_SIZE = 20
DEFAULT_WORKERS = 3
GROUPS = 10
REBALANCE_DAYS = 10

# These are the values saved in the platform-side runs.  They are only used
# for a side-by-side diagnostic; no platform API is called by this script.
PLATFORM_REFERENCE: dict[str, dict[str, float]] = {
    "close20": {"rank_ic": -0.0880, "ic_ir": -0.4035, "long_excess_pct": 10.61, "turnover_pct": 70.85},
    "open20": {"rank_ic": -0.0843, "ic_ir": -0.3901, "long_excess_pct": 10.64, "turnover_pct": 71.93},
    "python_obv": {"rank_ic": -0.0143, "ic_ir": -0.3402, "long_excess_pct": 0.39, "turnover_pct": 89.25},
    "composite_432": {"rank_ic": -0.0849, "ic_ir": -0.4092, "long_excess_pct": 10.79, "turnover_pct": 71.20},
}

DAILY_COLUMNS = ["date", "instrument", "open", "close", "volume"]
_thread_state = threading.local()


def cache_paths(price_mode: str) -> tuple[Path, Path]:
    if price_mode == "raw":
        root = RECHECK_ROOT
    else:
        root = RECHECK_ROOT / price_mode
    return root / "daily_batches", root / "reports"


def parse_day(value: str) -> pd.Timestamp:
    value = str(value).strip()
    return pd.Timestamp(pd.to_datetime(value, format="%Y%m%d" if len(value) == 8 else None))


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def iter_batches(values: list[pd.Timestamp], size: int) -> Iterable[list[pd.Timestamp]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def load_trade_dates(warmup: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    calendar_root = CACHE_ROOT / "trade_calendar"
    paths = sorted(calendar_root.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"QuantLab trade-calendar cache is missing: {calendar_root}")

    frames = [pd.read_parquet(path, columns=["trade_date", "is_open"]) for path in paths]
    calendar = pd.concat(frames, ignore_index=True)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"].astype(str), format="%Y%m%d")
    calendar = calendar[calendar["is_open"].astype(int) == 1]
    dates = sorted(calendar.loc[calendar["trade_date"].between(warmup, end), "trade_date"].unique())
    result = [pd.Timestamp(value) for value in dates]
    if not result:
        raise RuntimeError(f"No open dates in cached calendar between {warmup.date()} and {end.date()}")
    return result


def sanitize_error(exc: BaseException, token: str) -> str:
    message = str(exc).replace(token, "<redacted>")
    return " ".join(message.split())[:500]


def tushare_client(token: str) -> Any:
    client = getattr(_thread_state, "client", None)
    if client is None:
        import tushare as ts

        client = ts.pro_api(token)
        _thread_state.client = client
    return client


def normalize_daily(raw: pd.DataFrame, trade_date: pd.Timestamp, price_mode: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS)

    price_columns = {
        "raw": ("open", "close"),
        "qfq": ("open_qfq", "close_qfq"),
        "hfq": ("open_hfq", "close_hfq"),
    }
    open_column, close_column = price_columns[price_mode]
    required = {"ts_code", open_column, close_column, "vol"}
    missing = required.difference(raw.columns)
    if missing:
        raise RuntimeError(f"Tushare daily response is missing columns: {sorted(missing)}")

    result = raw[["ts_code", open_column, close_column, "vol"]].copy()
    result = result.rename(
        columns={"ts_code": "instrument", open_column: "open", close_column: "close", "vol": "volume"}
    )
    result["date"] = pd.Timestamp(trade_date)
    for column in ["open", "close", "volume"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["instrument"] = result["instrument"].astype(str)
    result = result.dropna(subset=["instrument", "open", "close", "volume"])
    result = result[(result["open"] > 0) & (result["close"] > 0) & (result["volume"] > 0)]
    return result[DAILY_COLUMNS]


def fetch_one_day(
    trade_date: pd.Timestamp, token: str, price_mode: str, retries: int = 5
) -> pd.DataFrame:
    date_text = day_text(trade_date)
    last_error: str | None = None
    for attempt in range(retries):
        try:
            client = tushare_client(token)
            if price_mode == "raw":
                raw = client.daily(trade_date=date_text)
            else:
                raw = client.stk_factor(trade_date=date_text)
            return normalize_daily(raw, trade_date, price_mode)
        except Exception as exc:  # Tushare errors are transient often enough to retry.
            last_error = sanitize_error(exc, token)
            if attempt + 1 >= retries:
                break
            delay = min(30.0, 1.5 * (2**attempt)) + random.random() * 0.5
            time.sleep(delay)
    raise RuntimeError(f"Tushare daily failed for {date_text}: {last_error}")


def batch_file(batch: list[pd.Timestamp], batch_root: Path = BATCH_ROOT) -> Path:
    return batch_root / f"batch_{day_text(batch[0])}_{day_text(batch[-1])}.parquet"


def batch_meta_file(batch: list[pd.Timestamp], batch_root: Path = BATCH_ROOT) -> Path:
    return batch_file(batch, batch_root).with_suffix(".json")


def completed_batch(batch: list[pd.Timestamp], batch_root: Path = BATCH_ROOT) -> bool:
    path = batch_file(batch, batch_root)
    meta_path = batch_meta_file(batch, batch_root)
    if not path.exists() or not meta_path.exists():
        return False
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return metadata.get("status") == "complete" and metadata.get("requested_dates") == [day_text(x) for x in batch]


def atomic_parquet_write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def download_batches(
    dates: list[pd.Timestamp],
    token: str,
    price_mode: str,
    batch_size: int,
    workers: int,
    force: bool,
    batch_root: Path = BATCH_ROOT,
) -> dict[str, Any]:
    batches = list(iter_batches(dates, batch_size))
    downloaded_batches = 0
    skipped_batches = 0
    total_rows = 0

    for batch_number, batch in enumerate(batches, start=1):
        path = batch_file(batch, batch_root)
        meta_path = batch_meta_file(batch, batch_root)
        if not force and completed_batch(batch, batch_root):
            existing = pd.read_parquet(path, columns=["date"])
            rows = len(existing)
            total_rows += rows
            skipped_batches += 1
            print(
                f"[{batch_number}/{len(batches)}] reuse {path.name}: rows={rows}",
                flush=True,
            )
            continue

        frames: dict[pd.Timestamp, pd.DataFrame] = {}
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(batch)))) as executor:
            futures = {
                executor.submit(fetch_one_day, date, token, price_mode): date for date in batch
            }
            for future in as_completed(futures):
                date = futures[future]
                try:
                    frames[date] = future.result()
                except Exception as exc:
                    errors.append(str(exc))

        if errors:
            raise RuntimeError("; ".join(errors))

        empty_dates = [day_text(date) for date in batch if frames[date].empty]
        if empty_dates:
            raise RuntimeError(f"Tushare returned no stock rows for open dates: {empty_dates}")

        combined = pd.concat([frames[date] for date in batch], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "instrument"], keep="last")
        combined = combined.sort_values(["date", "instrument"], ignore_index=True)
        atomic_parquet_write(combined, path)
        meta_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "source": "tushare.daily" if price_mode == "raw" else "tushare.stk_factor",
                    "price_mode": price_mode,
                    "requested_dates": [day_text(date) for date in batch],
                    "rows": int(len(combined)),
                    "rows_by_date": {day_text(date): int(len(frames[date])) for date in batch},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        downloaded_batches += 1
        total_rows += len(combined)
        print(
            f"[{batch_number}/{len(batches)}] downloaded {path.name}: rows={len(combined)}",
            flush=True,
        )

    return {
        "batch_count": len(batches),
        "downloaded_batches": downloaded_batches,
        "skipped_batches": skipped_batches,
        "rows_seen": int(total_rows),
        "batch_root": str(batch_root),
    }


def load_daily_batches(
    warmup: pd.Timestamp,
    end: pd.Timestamp,
    batch_root: Path = BATCH_ROOT,
    market: str = "all",
) -> pd.DataFrame:
    paths = sorted(batch_root.glob("batch_*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No downloaded Tushare batches found under {batch_root}")
    frames = [pd.read_parquet(path, columns=DAILY_COLUMNS) for path in paths]
    frame = pd.concat(frames, ignore_index=True)
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ["open", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        frame["date"].between(warmup, end)
        & (frame["open"] > 0)
        & (frame["close"] > 0)
        & (frame["volume"] > 0)
    ]
    if market == "hs":
        # Tushare also returns 北交所 (.BJ) rows; keep this as an explicit
        # sensitivity because the platform's pool label is not fully defined.
        frame = frame[frame["instrument"].astype(str).str.endswith((".SH", ".SZ"))]
    frame = frame.drop_duplicates(subset=["date", "instrument"], keep="last")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    return frame


def grouped_rolling(frame: pd.DataFrame, column: str, window: int, method: str) -> np.ndarray:
    grouped = frame.groupby("instrument", sort=False, observed=True)[column]
    rolling = grouped.rolling(window=window, min_periods=window)
    values = getattr(rolling, method)()
    values = values.reset_index(level=0, drop=True).reindex(frame.index)
    return values.to_numpy(dtype=float)


def calculate_components(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    grouped = frame.groupby("instrument", sort=False, observed=True)
    prior_close = grouped["close"].shift(20)
    frame["close20"] = frame["close"].div(prior_close).sub(1.0)
    frame["open20"] = frame["open"].div(prior_close).sub(1.0)

    one_day_return = frame["close"].div(grouped["close"].shift(1)).sub(1.0)
    obv_increment = frame["volume"] * one_day_return
    obv = obv_increment.groupby(frame["instrument"], sort=False, observed=True).cumsum()
    frame["obv"] = obv
    frame["obv_90_high"] = grouped_rolling(frame, "obv", 90, "max")
    frame["obv_30_ma"] = grouped_rolling(frame, "obv", 30, "mean")
    frame["obv_signal"] = (
        frame["obv"].eq(frame["obv_90_high"]) & frame["obv"].gt(frame["obv_30_ma"])
    ).astype(float)

    # For positive volume, TS_MAX(volume, 20) / volume is >= 1.  This is an
    # exact simplification of the supplied Python node, not an interpretation.
    large_order_volume = grouped_rolling(frame, "volume", 20, "max")
    large_order_ratio = large_order_volume / frame["volume"].to_numpy(dtype=float)
    buy_signal = (large_order_ratio > 0.01).astype(float)
    sell_signal = (large_order_ratio < 0).astype(float) * -1.0
    frame["python_obv"] = buy_signal + sell_signal + frame["obv_signal"].to_numpy(dtype=float)

    cross_section = frame.groupby("date", sort=False, observed=True)
    frame["close20_rank"] = cross_section["close20"].rank(method="average", pct=True)
    frame["open20_rank"] = cross_section["open20"].rank(method="average", pct=True)
    frame["composite_432"] = (
        4.0 * frame["close20_rank"]
        + 3.0 * frame["open20_rank"]
        + 2.0 * frame["python_obv"]
    )
    return frame


def annualized(returns: np.ndarray, periods_per_year: float) -> float | None:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None
    gross = float(np.prod(1.0 + values))
    if gross <= 0:
        return -1.0
    return float(gross ** (periods_per_year / len(values)) - 1.0)


def max_drawdown(returns: np.ndarray) -> float | None:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None
    equity = np.cumprod(1.0 + values)
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    return float(-drawdown.min())


def portfolio_metrics(
    returns: list[float],
    benchmark: list[float],
    turnover: list[float],
    periods_per_year: float,
) -> dict[str, float | None]:
    ret = np.asarray(returns, dtype=float)
    bench = np.asarray(benchmark, dtype=float)
    active = ret - bench
    result: dict[str, float | None] = {
        "annualized_return": annualized(ret, periods_per_year),
        "annualized_excess": None,
        "annualized_volatility": float(np.nanstd(ret, ddof=1) * np.sqrt(periods_per_year))
        if len(ret) > 1
        else None,
        "sharpe": float(np.nanmean(ret) / np.nanstd(ret, ddof=1) * np.sqrt(periods_per_year))
        if len(ret) > 1 and np.nanstd(ret, ddof=1) > 0
        else None,
        "max_drawdown": max_drawdown(ret),
        "turnover": float(np.nanmean(turnover)) if turnover else None,
        "periods": int(len(ret)),
        "period_win_rate": float(np.mean(ret > 0)) if len(ret) else None,
    }
    if len(ret) and len(bench):
        portfolio_growth = float(np.prod(1.0 + ret))
        benchmark_growth = float(np.prod(1.0 + bench))
        if portfolio_growth > 0 and benchmark_growth > 0:
            result["annualized_excess"] = float(
                (portfolio_growth / benchmark_growth) ** (periods_per_year / len(ret)) - 1.0
            )
    if len(active) > 1 and np.nanstd(active, ddof=1) > 0:
        result["information_ratio"] = float(
            np.nanmean(active) / np.nanstd(active, ddof=1) * np.sqrt(periods_per_year)
        )
    else:
        result["information_ratio"] = None
    return result


def evaluate_factor(
    frame: pd.DataFrame,
    factor_column: str,
    label: str,
    rebalance_dates: list[pd.Timestamp],
) -> tuple[dict[str, Any], pd.DataFrame]:
    periods: list[dict[str, Any]] = []
    group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    group_benchmarks: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    group_turnovers: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    previous_members: dict[int, set[str]] = {}
    rank_ics: list[float] = []
    ics: list[float] = []

    for date in rebalance_dates:
        current = frame.loc[frame["date"].eq(date), ["instrument", factor_column, "forward_return"]].copy()
        current = current.replace([np.inf, -np.inf], np.nan).dropna()
        if len(current) < GROUPS * 10:
            continue

        current["group"] = np.ceil(
            current[factor_column].rank(method="first") * GROUPS / len(current)
        ).astype(int).clip(1, GROUPS)
        benchmark = float(current["forward_return"].mean())
        factor_values = current[factor_column]
        returns = current["forward_return"]
        rank_ic = factor_values.rank(method="average").corr(returns.rank(method="average"))
        ic = factor_values.corr(returns)
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))

        period: dict[str, Any] = {"date": day_text(date), "stock_count": int(len(current)), "benchmark": benchmark}
        for group in range(1, GROUPS + 1):
            members = set(current.loc[current["group"].eq(group), "instrument"])
            group_return = float(current.loc[current["group"].eq(group), "forward_return"].mean())
            previous = previous_members.get(group)
            turnover = float(1.0 - len(members.intersection(previous)) / len(members)) if previous else np.nan
            previous_members[group] = members
            group_returns[group].append(group_return)
            group_benchmarks[group].append(benchmark)
            if np.isfinite(turnover):
                group_turnovers[group].append(turnover)
            period[f"group_{group}"] = group_return
            period[f"turnover_{group}"] = turnover
        periods.append(period)

    periods_per_year = 252.0 / REBALANCE_DAYS
    groups: dict[str, Any] = {}
    for group in range(1, GROUPS + 1):
        groups[str(group)] = portfolio_metrics(
            group_returns[group], group_benchmarks[group], group_turnovers[group], periods_per_year
        )

    rank_ic_array = np.asarray(rank_ics, dtype=float)
    ic_array = np.asarray(ics, dtype=float)
    low = groups["1"]
    high = groups[str(GROUPS)]
    result: dict[str, Any] = {
        "label": label,
        "factor_column": factor_column,
        "periods": len(periods),
        "rank_ic": float(np.nanmean(rank_ic_array)) if len(rank_ic_array) else None,
        "ic_mean": float(np.nanmean(ic_array)) if len(ic_array) else None,
        "ic_ir": float(np.nanmean(rank_ic_array) / np.nanstd(rank_ic_array, ddof=1))
        if len(rank_ic_array) > 1 and np.nanstd(rank_ic_array, ddof=1) > 0
        else None,
        "direction_0_low_group": low,
        "direction_1_high_group": high,
    }
    period_frame = pd.DataFrame(periods)
    return result, period_frame


def compare_to_platform(name: str, local: dict[str, Any]) -> dict[str, Any]:
    reference = PLATFORM_REFERENCE[name]
    low = local["direction_0_low_group"]
    comparisons: dict[str, Any] = {}
    for metric, platform_key, local_value in (
        ("rank_ic", "rank_ic", local.get("rank_ic")),
        ("ic_ir", "ic_ir", local.get("ic_ir")),
        ("long_excess_pct", "long_excess_pct", (low.get("annualized_excess") or 0.0) * 100.0),
        ("turnover_pct", "turnover_pct", (low.get("turnover") or 0.0) * 100.0),
    ):
        platform_value = reference[platform_key]
        comparisons[metric] = {
            "platform": platform_value,
            "local": local_value,
            "delta_local_minus_platform": None
            if local_value is None
            else float(local_value - platform_value),
        }
    return comparisons


def write_report(
    result: dict[str, Any],
    report_path: Path,
    group_path: Path,
    period_path: Path,
    group_frames: dict[str, pd.DataFrame],
) -> None:
    lines = [
        "# Tushare local recheck: workflow 6aa40282",
        "",
        f"- Data window: `{result['settings']['warmup']}..{result['settings']['end']}`",
        f"- Evaluation window: `{result['settings']['start']}..{result['settings']['end']}`",
        f"- Universe: `{result['settings']['universe']}`",
        "- Rebalance: 10 trading observations; groups: 10; equal-weight portfolios",
        "- Direction 0 is the low-value group, matching the platform comparison runs",
        f"- Data source: Tushare `daily`/`stk_factor`; price mode is `{result['settings']['price_adjustment']}`",
        "",
        "| factor | local Rank IC | platform Rank IC | local IC IR | platform IC IR | local low-group excess | platform low-group excess | local turnover | platform turnover |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in result["factors"].items():
        comparison = item["comparison"]
        lines.append(
            "| {name} | {ric:.4f} | {pric:.4f} | {iir:.4f} | {piir:.4f} | {lex:.2f}% | {plex:.2f}% | {lt:.2f}% | {plt:.2f}% |".format(
                name=name,
                ric=comparison["rank_ic"]["local"],
                pric=comparison["rank_ic"]["platform"],
                iir=comparison["ic_ir"]["local"],
                piir=comparison["ic_ir"]["platform"],
                lex=comparison["long_excess_pct"]["local"],
                plex=comparison["long_excess_pct"]["platform"],
                lt=comparison["turnover_pct"]["local"],
                plt=comparison["turnover_pct"]["platform"],
            )
        )
    lines.extend(
        [
            "",
            "The platform columns are archived reference results, not a new API call.",
            "Differences can come from adjusted-price treatment, historical universe membership, suspended rows, and factor-engine ranking/label semantics.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    combined_groups = []
    for name, frame in group_frames.items():
        item = frame.copy()
        item.insert(0, "factor", name)
        combined_groups.append(item)
    pd.concat(combined_groups, ignore_index=True).to_csv(group_path, index=False, encoding="utf-8-sig")
    pd.concat(
        [frame.assign(factor=name) for name, frame in result["period_frames"].items()],
        ignore_index=True,
    ).to_csv(period_path, index=False, encoding="utf-8-sig")


def analyze(
    warmup: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
    output_root: Path,
    price_mode: str = "raw",
    batch_root: Path = BATCH_ROOT,
    market: str = "all",
) -> dict[str, Any]:
    frame = load_daily_batches(warmup, end, batch_root, market)
    frame = calculate_components(frame)
    frame["future_close"] = frame.groupby("instrument", sort=False, observed=True)["close"].shift(-REBALANCE_DAYS)
    frame["forward_return"] = frame["future_close"].div(frame["close"]).sub(1.0)

    dates = load_trade_dates(warmup, end)
    evaluation_dates = [date for date in dates if start <= date <= end]
    rebalance_dates = evaluation_dates[::REBALANCE_DAYS]
    factors = {
        "close20": ("close20_rank", "RANK((CLOSE / DELAY(CLOSE, 20)) - 1)"),
        "open20": ("open20_rank", "RANK((OPEN / DELAY(CLOSE, 20)) - 1)"),
        "python_obv": ("python_obv", "workflow-6aa40282-python.py"),
        "composite_432": ("composite_432", "4 * close20_rank + 3 * open20_rank + 2 * python_obv"),
    }
    factor_results: dict[str, Any] = {}
    period_frames: dict[str, pd.DataFrame] = {}
    group_frames: dict[str, pd.DataFrame] = {}
    for name, (column, formula) in factors.items():
        local, periods = evaluate_factor(frame, column, name, rebalance_dates)
        local["formula"] = formula
        local["comparison"] = compare_to_platform(name, local)
        factor_results[name] = local
        period_frames[name] = periods
        group_rows = []
        for group in range(1, GROUPS + 1):
            metrics = local["direction_0_low_group"] if group == 1 else None
            # Keep every group in the CSV; the JSON retains detailed low/high metrics.
            group_rows.append({"group": group, **_group_metric_from_periods(periods, group)})
        group_frames[name] = pd.DataFrame(group_rows)

    result: dict[str, Any] = {
        "settings": {
            "workflow_id": "6aa40282ecb163ea7228d0d8",
            "warmup": day_text(warmup),
            "start": day_text(start),
            "end": day_text(end),
            "rebalance_days": REBALANCE_DAYS,
            "groups": GROUPS,
            "universe": "Tushare daily rows" if market == "all" else "Tushare daily rows with .SH/.SZ instruments",
            "price_adjustment": price_mode,
            "batch_root": str(batch_root),
        },
        "data": {
            "rows": int(len(frame)),
            "instruments": int(frame["instrument"].nunique()),
            "first_date": day_text(frame["date"].min()),
            "last_date": day_text(frame["date"].max()),
            "rebalance_periods": int(len(rebalance_dates)),
        },
        "factors": factor_results,
        "period_frames": period_frames,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    result_without_period_frames = {
        key: value for key, value in result.items() if key != "period_frames"
    }
    serializable = json.loads(
        json.dumps(result_without_period_frames, default=_json_default, ensure_ascii=False)
    )
    output_path = output_root / "local_recheck_result.json"
    output_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(
        result,
        output_root / "local_recheck_report.md",
        output_root / "local_group_metrics.csv",
        output_root / "local_period_returns.csv",
        group_frames,
    )
    print(f"analysis_result={output_path}")
    print(f"report={output_root / 'local_recheck_report.md'}")
    for name, item in factor_results.items():
        low = item["direction_0_low_group"]
        print(
            f"{name}: rank_ic={item['rank_ic']:.4f} ic_ir={item['ic_ir']:.4f} "
            f"low_excess={100 * (low['annualized_excess'] or 0):.2f}% "
            f"turnover={100 * (low['turnover'] or 0):.2f}%",
            flush=True,
        )
    return serializable


def _group_metric_from_periods(periods: pd.DataFrame, group: int) -> dict[str, Any]:
    if periods.empty:
        return {"periods": 0, "mean_return": None, "mean_excess": None, "turnover": None}
    values = periods[f"group_{group}"].to_numpy(dtype=float)
    benchmark = periods["benchmark"].to_numpy(dtype=float)
    turnover = periods[f"turnover_{group}"].to_numpy(dtype=float)
    return {
        "periods": int(len(values)),
        "mean_return": float(np.nanmean(values)),
        "mean_excess": float(np.nanmean(values - benchmark)),
        "turnover": float(np.nanmean(turnover)) if np.isfinite(turnover).any() else None,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if pd.isna(value):
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["download", "analyze", "all"], default="all")
    parser.add_argument("--warmup", default=DEFAULT_WARMUP)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--price-mode", choices=["raw", "qfq", "hfq"], default="raw")
    parser.add_argument("--market", choices=["all", "hs"], default="all")
    parser.add_argument("--force", action="store_true", help="redownload existing batches")
    parser.add_argument("--output", default=str(REPORT_ROOT))
    args = parser.parse_args()

    warmup = parse_day(args.warmup)
    start = parse_day(args.start)
    end = parse_day(args.end)
    if not warmup <= start <= end:
        raise SystemExit("Require warmup <= start <= end")
    dates = load_trade_dates(warmup, end)
    batch_root, default_report_root = cache_paths(args.price_mode)
    output_root = Path(args.output)
    if args.output == str(REPORT_ROOT):
        output_root = default_report_root

    if args.mode in {"download", "all"}:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            raise SystemExit("TUSHARE_TOKEN is required for download/all mode")
        summary = download_batches(
            dates,
            token,
            args.price_mode,
            max(1, args.batch_size),
            max(1, args.workers),
            args.force,
            batch_root,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.mode in {"analyze", "all"}:
        analyze(warmup, start, end, output_root, args.price_mode, batch_root, args.market)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
