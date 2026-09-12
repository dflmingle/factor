#!/usr/bin/env python3
"""Rebuild the two ST-filter workflow factors from local Tushare data.

The script is deliberately independent of PandaAI factor analysis.  It uses
the stock list returned by the completed ST-filter workflow, downloads the
daily inputs needed by both formulas, and compares local group statistics with
the archived workflow result.
"""

from __future__ import annotations

import argparse
import hashlib
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
CACHE_ROOT = QUANTLAB_ROOT / ".quantlab" / "cache" / "research" / "cn_equity"
DATA_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "stfilter_local"
BATCH_ROOT = DATA_ROOT / "daily_batches"
REPORT_ROOT = CACHE_ROOT / "reports" / "stfilter_local"
POOL_PATH = (
    CACHE_ROOT
    / "tushare_factor_recheck"
    / "reports"
    / "stfilter_platform"
    / "platform_st_pool_symbols.txt"
)
PLATFORM_RESULT_PATH = (
    CACHE_ROOT
    / "tushare_factor_recheck"
    / "reports"
    / "stfilter_platform"
    / "stfilter_platform_compare.json"
)
CALENDAR_ROOT = CACHE_ROOT / "trade_calendar"

DEFAULT_DATA_START = "20190701"
DEFAULT_START = "20210907"
DEFAULT_END = "20260907"
DEFAULT_BATCH_SIZE = 10
DEFAULT_WORKERS = 4
GROUPS = 10
REBALANCE_DAYS = 10

PLATFORM_REFERENCE: dict[str, dict[str, float]] = {
    "T10-SIZE": {
        "rank_ic": 0.1111,
        "ic_mean": 0.0712,
        "excess_annualized": 0.2292,
        "turnover": 0.3656,
    },
    "H03-T10-SINGLE": {
        "rank_ic": 0.0660,
        "ic_mean": 0.0487,
        "excess_annualized": 0.1816,
        "turnover": 0.0918,
    },
}

OUTPUT_COLUMNS = [
    "date",
    "instrument",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "open_qfq",
    "high_qfq",
    "low_qfq",
    "close_qfq",
    "turnover",
    "total_mv",
]
NUMERIC_COLUMNS = [column for column in OUTPUT_COLUMNS if column not in {"date", "instrument"}]
_thread_state = threading.local()
_stk_factor_lock = threading.Lock()
_next_stk_factor_call = 0.0
STK_FACTOR_INTERVAL_SECONDS = 0.75


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def parse_day(value: str) -> pd.Timestamp:
    text = str(value).strip()
    return pd.Timestamp(pd.to_datetime(text, format="%Y%m%d" if len(text) == 8 else None)).normalize()


def load_pool(path: Path = POOL_PATH) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing returned ST-filter pool: {path}")
    pool = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    if len(pool) < 4000:
        raise RuntimeError(f"Unexpectedly small ST-filter pool: {len(pool)}")
    return pool


def pool_hash(pool: set[str]) -> str:
    digest = hashlib.sha256()
    digest.update("\n".join(sorted(pool)).encode("utf-8"))
    return digest.hexdigest()[:16]


def tushare_client(token: str) -> Any:
    client = getattr(_thread_state, "client", None)
    if client is None:
        import tushare as ts

        client = ts.pro_api(token)
        _thread_state.client = client
    return client


def ensure_calendar(start: pd.Timestamp, end: pd.Timestamp, token: str | None) -> list[pd.Timestamp]:
    CALENDAR_ROOT.mkdir(parents=True, exist_ok=True)
    years = range(start.year, end.year + 1)
    missing = [year for year in years if not (CALENDAR_ROOT / f"{year}.parquet").exists()]
    if missing:
        if not token:
            raise RuntimeError(
                "Trade-calendar cache is missing years "
                + ", ".join(map(str, missing))
                + "; provide TUSHARE_TOKEN for download mode"
            )
        client = tushare_client(token)
        raw = client.trade_cal(
            exchange="SSE",
            start_date=f"{min(missing)}0101",
            end_date=f"{max(missing)}1231",
            fields="exchange,cal_date,is_open,pretrade_date",
        )
        if raw is None or raw.empty:
            raise RuntimeError("Tushare trade_cal returned no rows")
        raw = raw.rename(columns={"cal_date": "trade_date"})
        raw["trade_date"] = pd.to_datetime(raw["trade_date"].astype(str), format="%Y%m%d")
        for year in missing:
            part = raw[raw["trade_date"].dt.year.eq(year)].copy()
            if part.empty:
                raise RuntimeError(f"Tushare trade_cal returned no rows for {year}")
            part.to_parquet(CALENDAR_ROOT / f"{year}.parquet", index=False)

    frames = []
    for year in years:
        path = CALENDAR_ROOT / f"{year}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path, columns=["trade_date", "is_open"]))
    calendar = pd.concat(frames, ignore_index=True)
    if not pd.api.types.is_datetime64_any_dtype(calendar["trade_date"]):
        calendar["trade_date"] = pd.to_datetime(calendar["trade_date"], format="mixed")
    calendar = calendar[calendar["is_open"].astype(int).eq(1)]
    dates = sorted(calendar.loc[calendar["trade_date"].between(start, end), "trade_date"].unique())
    return [pd.Timestamp(value).normalize() for value in dates]


def sanitize_error(exc: BaseException, token: str) -> str:
    return " ".join(str(exc).replace(token, "<redacted>").split())[:500]


def normalize_day(
    prices: pd.DataFrame,
    basics: pd.DataFrame,
    trade_date: pd.Timestamp,
    pool: set[str],
) -> pd.DataFrame:
    if prices is None or prices.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    price_columns = {
        "ts_code",
        "open",
        "high",
        "low",
        "close",
        "vol",
        "amount",
        "open_qfq",
        "high_qfq",
        "low_qfq",
        "close_qfq",
    }
    missing = price_columns.difference(prices.columns)
    if missing:
        raise RuntimeError(f"stk_factor response is missing columns: {sorted(missing)}")
    price = prices[
        [
            "ts_code",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "amount",
            "open_qfq",
            "high_qfq",
            "low_qfq",
            "close_qfq",
        ]
    ].copy()
    price = price.rename(columns={"ts_code": "instrument", "vol": "volume"})
    price["instrument"] = price["instrument"].astype(str)
    price = price[price["instrument"].isin(pool)]

    if basics is None or basics.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    basic = basics[["ts_code", "turnover_rate", "total_mv"]].copy()
    basic = basic.rename(columns={"ts_code": "instrument", "turnover_rate": "turnover"})
    basic["instrument"] = basic["instrument"].astype(str)
    result = price.merge(basic, on="instrument", how="inner")
    result["date"] = pd.Timestamp(trade_date)
    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result[
        (result["volume"] > 0)
        & (result["close"] > 0)
        & (result["close_qfq"] > 0)
        & (result["amount"] > 0)
    ]
    return result[OUTPUT_COLUMNS].drop_duplicates(["date", "instrument"], keep="last")


def fetch_one_day(
    trade_date: pd.Timestamp,
    token: str,
    pool: set[str],
    retries: int = 5,
) -> pd.DataFrame:
    date_text = day_text(trade_date)
    last_error: str | None = None
    for attempt in range(retries):
        try:
            client = tushare_client(token)
            global _next_stk_factor_call
            with _stk_factor_lock:
                wait = _next_stk_factor_call - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                _next_stk_factor_call = time.monotonic() + STK_FACTOR_INTERVAL_SECONDS
            prices = client.stk_factor(
                    trade_date=date_text,
                    fields=(
                        "ts_code,trade_date,open,high,low,close,vol,amount,"
                        "open_qfq,high_qfq,low_qfq,close_qfq"
                    ),
                )
            basics = client.daily_basic(
                trade_date=date_text,
                fields="ts_code,trade_date,turnover_rate,total_mv",
            )
            return normalize_day(prices, basics, trade_date, pool)
        except Exception as exc:
            last_error = sanitize_error(exc, token)
            if attempt + 1 >= retries:
                break
            time.sleep(min(30.0, 1.5 * (2**attempt)) + random.random() * 0.5)
    raise RuntimeError(f"Tushare data failed for {date_text}: {last_error}")


def batches(values: list[pd.Timestamp], size: int) -> Iterable[list[pd.Timestamp]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def batch_path(batch: list[pd.Timestamp]) -> Path:
    return BATCH_ROOT / f"batch_{day_text(batch[0])}_{day_text(batch[-1])}.parquet"


def batch_meta_path(batch: list[pd.Timestamp]) -> Path:
    return batch_path(batch).with_suffix(".json")


def completed_batch(batch: list[pd.Timestamp], expected_pool_hash: str) -> bool:
    path = batch_path(batch)
    meta_path = batch_meta_path(batch)
    if not path.exists() or not meta_path.exists():
        return False
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        metadata.get("status") == "complete"
        and metadata.get("schema_version") == 1
        and metadata.get("pool_hash") == expected_pool_hash
        and metadata.get("requested_dates") == [day_text(value) for value in batch]
    )


def atomic_write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def download(
    dates: list[pd.Timestamp],
    token: str,
    pool: set[str],
    batch_size: int,
    workers: int,
    force: bool,
) -> dict[str, int]:
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    pool_digest = pool_hash(pool)
    date_batches = list(batches(dates, batch_size))
    reused = 0
    downloaded = 0
    rows_seen = 0
    for number, batch in enumerate(date_batches, start=1):
        path = batch_path(batch)
        if not force and completed_batch(batch, pool_digest):
            rows = len(pd.read_parquet(path, columns=["date"]))
            reused += 1
            rows_seen += rows
            print(f"[{number}/{len(date_batches)}] reuse {path.name}: rows={rows}", flush=True)
            continue

        frames: dict[pd.Timestamp, pd.DataFrame] = {}
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(batch)))) as executor:
            futures = {
                executor.submit(fetch_one_day, date, token, pool): date for date in batch
            }
            for future in as_completed(futures):
                date = futures[future]
                try:
                    frames[date] = future.result()
                except Exception as exc:
                    errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
        missing = [day_text(date) for date in batch if frames[date].empty]
        if missing:
            raise RuntimeError(f"No usable pool rows returned for dates: {missing}")
        combined = pd.concat([frames[date] for date in batch], ignore_index=True)
        combined = combined.sort_values(["date", "instrument"], ignore_index=True)
        atomic_write(combined, path)
        batch_meta_path(batch).write_text(
            json.dumps(
                {
                    "status": "complete",
                    "schema_version": 1,
                    "source": "tushare.stk_factor+daily_basic",
                    "pool_hash": pool_digest,
                    "requested_dates": [day_text(date) for date in batch],
                    "rows": int(len(combined)),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        downloaded += 1
        rows_seen += len(combined)
        print(f"[{number}/{len(date_batches)}] downloaded {path.name}: rows={len(combined)}", flush=True)
    return {"batches": len(date_batches), "reused": reused, "downloaded": downloaded, "rows": rows_seen}


def load_data(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    paths = sorted(BATCH_ROOT.glob("batch_*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No ST-filter data batches found under {BATCH_ROOT}")
    frames = [pd.read_parquet(path) for path in paths]
    frame = pd.concat(frames, ignore_index=True)
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame[frame["date"].between(start, end)].copy()
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.drop_duplicates(["date", "instrument"], keep="last")
    return frame.sort_values(["instrument", "date"], ignore_index=True)


def grouped_rolling(frame: pd.DataFrame, column: str, window: int, method: str) -> np.ndarray:
    grouped = frame.groupby("instrument", sort=False, observed=True)[column]
    values = getattr(grouped.rolling(window=window, min_periods=window), method)()
    return values.reset_index(level=0, drop=True).reindex(frame.index).to_numpy(dtype=float)


def cross_rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates, sort=False, observed=True).rank(method="average", pct=True)


def factor_values(frame: pd.DataFrame, price_mode: str) -> pd.DataFrame:
    result = frame.copy()
    suffix = "_qfq" if price_mode == "qfq" else ""
    open_col = f"open{suffix}"
    high_col = f"high{suffix}"
    low_col = f"low{suffix}"
    close_col = f"close{suffix}"
    grouped = result.groupby("instrument", sort=False, observed=True)
    prior_close = grouped[close_col].shift(1)
    close_40_ago = grouped[close_col].shift(40)

    result["t10_ret40"] = result[close_col].div(close_40_ago).sub(1.0)
    weighted_price = result["volume"] * (result[open_col] + result[close_col]) / 2.0
    result["t10_vwap"] = (
        grouped_rolling(result.assign(_weighted_price=weighted_price), "_weighted_price", 250, "sum")
        / grouped_rolling(result, "volume", 250, "sum")
    )
    result["t10_vwap_dev"] = result["t10_vwap"].div(result[close_col]).sub(1.0)
    result["t10_turn21"] = grouped_rolling(result, "turnover", 21, "mean")
    result["t10_turn504"] = grouped_rolling(result, "turnover", 504, "mean")
    result["t10_turn_signal"] = 1.0 - result["t10_turn21"].div(result["t10_turn504"])

    result["t10_c1"] = cross_rank(1.0 - result["t10_ret40"], result["date"])
    result["t10_c2"] = cross_rank(result["t10_vwap_dev"], result["date"])
    result["t10_c3"] = cross_rank(result["t10_turn_signal"], result["date"])
    cap_rank = cross_rank(result["total_mv"], result["date"])
    cap_mean = cap_rank.groupby(result["date"], sort=False, observed=True).transform("mean")
    cap_std = cap_rank.groupby(result["date"], sort=False, observed=True).transform("std")
    cap_z = cap_rank.sub(cap_mean).div(cap_std.replace(0.0, np.nan))
    result["t10_c4"] = cross_rank(-cap_z, result["date"])
    result["T10-SIZE"] = result[["t10_c1", "t10_c2", "t10_c3", "t10_c4"]].mean(axis=1)

    h03_component = (result[high_col] - result[low_col]).div(prior_close + 0.000001)
    h03_numerator = grouped_rolling(result.assign(_h03_component=h03_component), "_h03_component", 60, "sum")
    h03_denominator = grouped_rolling(result, "amount", 60, "sum")
    h03_raw = np.divide(h03_numerator, h03_denominator + 1.0)
    result["H03-T10-SINGLE"] = cross_rank(pd.Series(h03_raw, index=result.index), result["date"])
    return result


def load_signal_dates(start: pd.Timestamp, end: pd.Timestamp, calendar: list[pd.Timestamp]) -> list[pd.Timestamp]:
    if PLATFORM_RESULT_PATH.exists():
        period_path = PLATFORM_RESULT_PATH.parent / "stfilter_periods.csv"
        if period_path.exists():
            values = pd.read_csv(period_path, usecols=["date"])["date"]
            dates = sorted(set(pd.to_datetime(values).dt.normalize()))
            dates = [date for date in dates if start <= date <= end]
            if len(dates) == 120:
                return dates
    evaluation = [date for date in calendar if start <= date <= end]
    return evaluation[::REBALANCE_DAYS]


def panel_close(
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
    price_mode: str,
) -> pd.DataFrame:
    column = "close_qfq" if price_mode == "qfq" else "close"
    panel = frame.pivot(index="date", columns="instrument", values=column).reindex(calendar)
    return panel.sort_index(axis=1).ffill()


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def evaluate(
    factors: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    price_mode: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    close = panel_close(factors, calendar, price_mode)
    index_by_date = {date: index for index, date in enumerate(calendar)}
    target_dates = [calendar[index_by_date[date] + REBALANCE_DAYS] for date in signal_dates]
    current = close.loc[signal_dates].stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    future = close.loc[target_dates].copy()
    future.index = signal_dates
    future = future.stack(dropna=False).rename("future_close").reset_index()
    future = future.rename(columns={"level_0": "date", "level_1": "instrument"})
    returns = current.merge(future, on=["date", "instrument"], how="left")
    returns["forward_return"] = returns["future_close"].div(returns["current_close"]).sub(1.0)

    signal = factors[factors["date"].isin(signal_dates)][
        ["date", "instrument", "T10-SIZE", "H03-T10-SINGLE"]
    ].copy()
    evaluated = signal.merge(
        returns[["date", "instrument", "forward_return"]],
        on=["date", "instrument"],
        how="left",
    )
    periods_by_factor: dict[str, list[dict[str, Any]]] = {}
    factor_summary: dict[str, Any] = {}
    group_rows: list[dict[str, Any]] = []
    top_rows: list[dict[str, Any]] = []

    for name in PLATFORM_REFERENCE:
        data = evaluated[["date", "instrument", name, "forward_return"]].replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        previous: dict[int, set[str]] = {}
        rank_ics: list[float] = []
        ics: list[float] = []
        group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
        group_turnovers: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
        period_rows: list[dict[str, Any]] = []

        for date in signal_dates:
            current_data = data[data["date"].eq(date)].copy()
            if len(current_data) < GROUPS * 10:
                continue
            current_data["group"] = assign_groups(current_data[name])
            rank_ic = current_data[name].rank(method="average").corr(
                current_data["forward_return"].rank(method="average")
            )
            ic = current_data[name].corr(current_data["forward_return"])
            if pd.notna(rank_ic):
                rank_ics.append(float(rank_ic))
            if pd.notna(ic):
                ics.append(float(ic))
            benchmark = float(current_data["forward_return"].mean())
            row: dict[str, Any] = {"date": date, "stock_count": int(len(current_data)), "benchmark": benchmark}
            for group in range(1, GROUPS + 1):
                members = set(current_data.loc[current_data["group"].eq(group), "instrument"])
                group_return = float(current_data.loc[current_data["group"].eq(group), "forward_return"].mean())
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
                row[f"group_{group}"] = group_return
                row[f"excess_{group}"] = group_return - benchmark
                row[f"turnover_{group}"] = turnover
            period_rows.append(row)

        periods = pd.DataFrame(period_rows)
        years = len(periods) * REBALANCE_DAYS / 252.0
        groups: dict[str, Any] = {}
        for group in range(1, GROUPS + 1):
            values = np.asarray(group_returns[group], dtype=float)
            excess = periods[f"excess_{group}"].to_numpy(dtype=float) if not periods.empty else np.array([])
            groups[str(group)] = {
                "annualized_return": float(values.sum() / years) if years and len(values) else None,
                "excess_annualized": float(excess.sum() / years) if years and len(excess) else None,
                "mean_period_return": float(values.mean()) if len(values) else None,
                "turnover": float(np.mean(group_turnovers[group])) if group_turnovers[group] else None,
                "periods": int(len(values)),
            }

        factor_summary[name] = {
            "periods": len(periods),
            "stock_count_mean": float(periods["stock_count"].mean()) if not periods.empty else None,
            "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
            "ic_mean": float(np.mean(ics)) if ics else None,
            "ic_ir": float(np.mean(ics) / np.std(ics, ddof=1))
            if len(ics) > 1 and np.std(ics, ddof=1) > 0
            else None,
            "groups": groups,
            "platform": PLATFORM_REFERENCE[name],
        }
        periods_by_factor[name] = period_rows
        for group, metrics in groups.items():
            platform_groups = read_platform_groups(name)
            group_rows.append(
                {
                    "factor": name,
                    "group": int(group),
                    "local_annualized_return": metrics["annualized_return"],
                    "local_excess_annualized": metrics["excess_annualized"],
                    "local_turnover": metrics["turnover"],
                    "platform_annualized_return": platform_groups.get(group, {}).get("annualizedReturn"),
                    "platform_excess_annualized": platform_groups.get(group, {}).get("excessAnnualized"),
                    "platform_turnover": platform_groups.get(group, {}).get("turnoverRate"),
                }
            )

        # The workflow's top-factor payload is for the final run date, which
        # is after the last forward-return chart date.
        latest = factors[factors["date"].eq(max(factors["date"]))][["instrument", name]].dropna()
        local_top = latest.sort_values([name, "instrument"], ascending=[False, True]).head(20)["instrument"].tolist()
        platform_top = read_platform_top(name)
        top_rows.append(
            {
                "factor": name,
                "date": day_text(max(factors["date"])),
                "local_top20": ",".join(local_top),
                "platform_top20": ",".join(platform_top),
                "overlap": len(set(local_top) & set(platform_top)) if platform_top else None,
            }
        )

    period_frames = []
    for name, rows in periods_by_factor.items():
        if rows:
            period_frames.append(pd.DataFrame(rows).assign(factor=name))
    all_periods = pd.concat(period_frames, ignore_index=True) if period_frames else pd.DataFrame()
    return factor_summary, pd.DataFrame(group_rows), pd.concat(
        [all_periods, pd.DataFrame(top_rows)], ignore_index=True, sort=False
    )


def read_platform_payload() -> dict[str, Any]:
    if not PLATFORM_RESULT_PATH.exists():
        return {}
    return json.loads(PLATFORM_RESULT_PATH.read_text(encoding="utf-8-sig"))


def read_platform_groups(name: str) -> dict[str, dict[str, Any]]:
    payload = read_platform_payload()
    for item in payload.get("workflow", {}).get("analysis", []):
        if item.get("label") == name:
            return item.get("groups", {})
    return {}


def read_platform_top(name: str) -> list[str]:
    payload = read_platform_payload()
    for item in payload.get("workflow", {}).get("analysis", []):
        if item.get("label") == name:
            return [str(value) for value in item.get("top_symbols", [])]
    return []


def write_outputs(
    summary: dict[str, Any],
    group_metrics: pd.DataFrame,
    period_and_top: pd.DataFrame,
    output_root: Path,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "local_recheck_result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    group_metrics.to_csv(output_root / "local_group_metrics.csv", index=False, encoding="utf-8-sig")
    period_and_top.to_csv(output_root / "local_periods_and_top.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# Local reproduction of the ST-filter workflow",
        "",
        "This is an offline Tushare reconstruction. It uses the returned fixed 4,879-symbol pool and does not create or run a PandaAI factor.",
        "",
        f"- data window: `{summary['settings']['data_start']}..{summary['settings']['end']}`",
        f"- evaluation window: `{summary['settings']['start']}..{summary['settings']['end']}`",
        f"- price mode: `{summary['settings']['price_mode']}`",
        f"- pool: `{summary['settings']['pool_count']}` symbols; periods: `{summary['settings']['periods']}`; rebalance: `{REBALANCE_DAYS}`; groups: `{GROUPS}`",
        "- local excess is the platform-style arithmetic annualized excess: sum of period excess returns divided by elapsed years.",
        "",
        "## Headline comparison",
        "",
        "| factor | local RankIC | platform RankIC | local IC | platform IC | local group 10 excess | platform group 10 excess | local group 10 turnover | platform group 10 turnover |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in summary["factors"].items():
        local_group = item["groups"]["10"]
        platform = item["platform"]
        lines.append(
            f"| {name} | {item['rank_ic']:.4f} | {platform['rank_ic']:.4f} | {item['ic_mean']:.4f} | {platform['ic_mean']:.4f} | {local_group['excess_annualized']:.2%} | {platform['excess_annualized']:.2%} | {local_group['turnover']:.2%} | {platform['turnover']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Latest top-20 overlap",
            "",
            "| factor | local factor date | overlap |",
            "|---|---|---:|",
        ]
    )
    top_frame = period_and_top[period_and_top["local_top20"].notna()] if not period_and_top.empty else pd.DataFrame()
    for _, row in top_frame.iterrows():
        lines.append(f"| {row['factor']} | {row['date']} | {row['overlap']}/20 |")
    lines.extend(
        [
            "",
            "Raw and qfq are both run when `--price-mode both` is used. The qfq result is the primary comparison because the existing simple-factor alignment used qfq prices.",
            "",
        ]
    )
    (output_root / "local_recheck_report.md").write_text("\n".join(lines), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def analyze(
    data_start: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
    price_mode: str,
    output_root: Path,
) -> dict[str, Any]:
    pool = load_pool()
    frame = load_data(data_start, end)
    frame = frame[frame["instrument"].isin(pool)].copy()
    calendar = ensure_calendar(data_start, end, token=None)
    signal_dates = load_signal_dates(start, end, calendar)
    if not signal_dates:
        raise RuntimeError("No signal dates available")
    if max(calendar.index(date) + REBALANCE_DAYS for date in signal_dates) >= len(calendar):
        raise RuntimeError("The local data end does not cover the final forward-return target")

    factor_frame = factor_values(frame, price_mode)
    summary_factors, group_metrics, period_and_top = evaluate(
        factor_frame, calendar, signal_dates, price_mode
    )
    summary = {
        "settings": {
            "workflow_id": "6aa3871b51cdfe29b2e0bc47",
            "data_start": day_text(data_start),
            "start": day_text(start),
            "end": day_text(end),
            "price_mode": price_mode,
            "pool_count": len(pool),
            "rows": len(frame),
            "instruments": int(frame["instrument"].nunique()),
            "periods": len(signal_dates),
            "rebalance_days": REBALANCE_DAYS,
            "groups": GROUPS,
            "data_root": str(DATA_ROOT),
        },
        "factors": summary_factors,
    }
    write_outputs(summary, group_metrics, period_and_top, output_root)
    print(f"report={output_root / 'local_recheck_report.md'}")
    for name, item in summary_factors.items():
        group = item["groups"]["10"]
        print(
            f"{name}: rank_ic={item['rank_ic']:.4f} ic={item['ic_mean']:.4f} "
            f"group10_excess={group['excess_annualized']:.2%} turnover={group['turnover']:.2%}",
            flush=True,
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["download", "analyze", "all"], default="all")
    parser.add_argument("--data-start", default=DEFAULT_DATA_START)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--price-mode", choices=["qfq", "raw", "both"], default="both")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", default=str(REPORT_ROOT))
    args = parser.parse_args()

    data_start = parse_day(args.data_start)
    start = parse_day(args.start)
    end = parse_day(args.end)
    if not data_start <= start <= end:
        raise SystemExit("Require data-start <= start <= end")
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    dates = ensure_calendar(data_start, end, token if args.mode in {"download", "all"} else None)
    if args.mode in {"download", "all"}:
        if not token:
            raise SystemExit("TUSHARE_TOKEN is required for download/all mode")
        pool = load_pool()
        print(json.dumps(download(dates, token, pool, max(1, args.batch_size), max(1, args.workers), args.force)))
    if args.mode in {"analyze", "all"}:
        output_root = Path(args.output)
        if args.price_mode == "both":
            for mode in ("qfq", "raw"):
                analyze(data_start, start, end, mode, output_root / mode)
        else:
            analyze(data_start, start, end, args.price_mode, output_root / args.price_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
