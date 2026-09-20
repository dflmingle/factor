#!/usr/bin/env python3
"""Reproduce QTLD60 locally under the canonical platform-alignment rules.

This is a standalone one-factor run.  It reads the already downloaded
Tushare qfq and daily_basic caches, never contacts PandaAI, and evaluates:

    Quantile(close, 60, 0.2) / close

The loader keeps only rows that pass the canonical full-A/qfq/daily_basic
filters and drops unused market columns before the rolling calculation.  A
memory guard stops the process before it can exhaust the desktop.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from machine_profile import resolve_machine_profile  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_START,
    alignment_config_snapshot,
    validate_alignment_config,
)
from positive_factor_local_compare import (  # noqa: E402
    END,
    evaluate,
    panel_close,
)


FORMULA = "Quantile(close, 60, 0.2) / close"
HANDLER = "qtld60"
WINDOW = 60
QUANTILE = 0.2
DIRECTION = 1
CYCLE = 10
DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
FORMAL_START = pd.Timestamp(ALIGNMENT_START)
FORMAL_END = pd.Timestamp(ALIGNMENT_END)
GROUPS = ALIGNMENT_GROUPS
DEFAULT_SIGNAL_REFERENCE = (
    PROJECT_ROOT
    / "h03-t10-single-20260911-candidates.results"
    / "6aa36bd3ecb163ea7228cffe.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / ".tushare-refresh-20260918-v2"
    / "reports"
    / "qtld60_local_reproduction_20260919"
)
GB = 1024**3


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if value is pd.NA:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def memory_guard(label: str, max_rss_gb: float, min_available_gb: float) -> None:
    process = psutil.Process(os.getpid())
    rss = process.memory_info().rss / GB
    available = psutil.virtual_memory().available / GB
    print(
        f"memory label={label} rss_gb={rss:.2f} available_gb={available:.2f}",
        flush=True,
    )
    if rss > max_rss_gb:
        raise MemoryError(
            f"RSS guard stopped the run at {rss:.2f} GB; limit is {max_rss_gb:.2f} GB"
        )
    if available < min_available_gb:
        raise MemoryError(
            f"available-memory guard stopped the run at {available:.2f} GB; "
            f"minimum is {min_available_gb:.2f} GB"
        )


def _numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _price_columns(path: Path) -> list[str]:
    available = set(pq.ParquetFile(path).schema_arrow.names)
    required = ["date", "instrument", "open", "close", "volume", "amount"]
    optional = ["high_qfq", "low_qfq", "high", "low"]
    missing = set(required).difference(available)
    if missing:
        raise RuntimeError(f"Price batch {path} is missing columns: {sorted(missing)}")
    return [column for column in required + optional if column in available]


def load_minimal_full_a(
    price_root: Path,
    cap_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    max_rss_gb: float,
    min_available_gb: float,
) -> pd.DataFrame:
    """Load only the canonical rows and QTLD60's close input."""
    price_paths = sorted(price_root.glob("batch_*.parquet"))
    cap_paths = sorted(cap_root.glob("daily_basic_*.parquet"))
    if not price_paths:
        raise FileNotFoundError(f"No price batches found under {price_root}")
    if not cap_paths:
        raise FileNotFoundError(f"No daily_basic files found under {cap_root}")
    cap_by_date = {
        path.stem.removeprefix("daily_basic_"): path for path in cap_paths
    }

    parts: list[pd.DataFrame] = []
    total_rows = 0
    for index, price_path in enumerate(price_paths, start=1):
        columns = _price_columns(price_path)
        prices = pd.read_parquet(price_path, columns=columns)
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
        prices["instrument"] = prices["instrument"].astype(str)
        prices = prices[
            prices["date"].between(start, end)
            & prices["instrument"].str.endswith((".SH", ".SZ"))
        ].copy()
        if prices.empty:
            del prices
            continue

        # Match the canonical full_a_local_data filters before dropping the
        # columns that QTLD60 does not use.
        if "high_qfq" not in prices.columns:
            prices["high_qfq"] = prices["high"] if "high" in prices.columns else prices[["open", "close"]].max(axis=1)
        if "low_qfq" not in prices.columns:
            prices["low_qfq"] = prices["low"] if "low" in prices.columns else prices[["open", "close"]].min(axis=1)
        _numeric(
            prices,
            ["open", "close", "volume", "high_qfq", "low_qfq", "amount"],
        )
        prices = prices[
            prices["open"].gt(0)
            & prices["close"].gt(0)
            & prices["volume"].gt(0)
            & prices["high_qfq"].gt(0)
            & prices["low_qfq"].gt(0)
            & prices["amount"].gt(0)
        ][["date", "instrument", "close"]].copy()
        prices = prices.drop_duplicates(["date", "instrument"], keep="last")

        cap_frames: list[pd.DataFrame] = []
        for value in sorted(prices["date"].dropna().unique()):
            key = pd.Timestamp(value).strftime("%Y%m%d")
            cap_path = cap_by_date.get(key)
            if cap_path is None:
                continue
            caps = pd.read_parquet(
                cap_path,
                columns=["date", "instrument", "turnover", "total_mv"],
            )
            caps["date"] = pd.to_datetime(caps["date"], errors="coerce").dt.normalize()
            caps["instrument"] = caps["instrument"].astype(str)
            caps = caps[caps["instrument"].str.endswith((".SH", ".SZ"))].copy()
            _numeric(caps, ["turnover", "total_mv"])
            cap_frames.append(caps)
        if cap_frames:
            caps = pd.concat(cap_frames, ignore_index=True)
            caps = caps.drop_duplicates(["date", "instrument"], keep="last")
            joined = prices.merge(caps, on=["date", "instrument"], how="inner")
            joined = joined[
                joined["turnover"].notna()
                & joined["total_mv"].notna()
                & joined["total_mv"].gt(0)
            ][["date", "instrument", "close"]].rename(
                columns={"close": "close_qfq"}
            )
            if not joined.empty:
                parts.append(joined)
                total_rows += len(joined)
            del caps, joined, cap_frames
        del prices
        if index == 1 or index % 10 == 0 or index == len(price_paths):
            print(
                f"loaded_price_batches={index}/{len(price_paths)} canonical_rows={total_rows}",
                flush=True,
            )
            memory_guard(f"load_batch_{index}", max_rss_gb, min_available_gb)
        gc.collect()

    if not parts:
        raise RuntimeError("No canonical full-A rows were loaded")
    frame = pd.concat(parts, ignore_index=True)
    del parts
    frame = frame.drop_duplicates(["date", "instrument"], keep="last")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    categories = pd.Index(frame["instrument"].astype(str).unique(), dtype=object)
    frame["instrument"] = pd.Categorical(
        frame["instrument"].astype(str), categories=categories, ordered=False
    )
    frame["close_qfq"] = pd.to_numeric(frame["close_qfq"], errors="coerce")
    frame = frame[frame["close_qfq"].gt(0)].reset_index(drop=True)
    memory_guard("loaded_frame", max_rss_gb, min_available_gb)
    return frame


def load_calendar(
    calendar_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[pd.Timestamp]:
    years = range(start.year, end.year + 1)
    frames = []
    for year in years:
        path = calendar_root / f"{year}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing cached trade calendar: {path}")
        frames.append(pd.read_parquet(path, columns=["trade_date", "is_open"]))
    calendar = pd.concat(frames, ignore_index=True)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"], errors="coerce").dt.normalize()
    calendar = calendar[
        calendar["is_open"].astype(int).eq(1)
        & calendar["trade_date"].between(start, end)
    ]
    return [pd.Timestamp(value).normalize() for value in sorted(calendar["trade_date"].unique())]


def rolling_quantile_factor(frame: pd.DataFrame) -> pd.Series:
    """Build the per-instrument trailing 20th percentile ratio."""
    grouped = frame.groupby("instrument", sort=False, observed=True)["close_qfq"]
    quantile = grouped.rolling(
        window=WINDOW,
        min_periods=WINDOW,
    ).quantile(QUANTILE)
    quantile = quantile.reset_index(level=0, drop=True).reindex(frame.index)
    return quantile.div(frame["close_qfq"])


def reference_signal_dates(path: Path) -> list[pd.Timestamp]:
    if not path.is_file():
        raise FileNotFoundError(f"Signal-date reference result is missing: {path}")
    platform = read_platform_run(path)
    dates = [pd.Timestamp(value).normalize() for value in platform.get("dates", [])]
    dates = [date for date in dates if FORMAL_START <= date <= FORMAL_END]
    if len(dates) < 2:
        raise RuntimeError(f"Reference result has too few usable signal dates: {path}")
    return list(dict.fromkeys(dates))


def detect_cache_end(cap_root: Path) -> pd.Timestamp:
    dates: list[pd.Timestamp] = []
    for path in cap_root.glob("daily_basic_*.parquet"):
        text = path.stem.removeprefix("daily_basic_")
        try:
            dates.append(pd.Timestamp(pd.to_datetime(text, format="%Y%m%d")).normalize())
        except (TypeError, ValueError):
            continue
    if not dates:
        raise FileNotFoundError(f"Cannot detect latest daily_basic date under {cap_root}")
    return max(dates)


def extend_signal_dates(
    base_dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    end: pd.Timestamp,
) -> list[pd.Timestamp]:
    positions = {date: index for index, date in enumerate(calendar)}
    dates = list(base_dates)
    last_position = positions[dates[-1]]
    while last_position + CYCLE < len(calendar):
        next_position = last_position + CYCLE
        next_date = calendar[next_position]
        if next_date > end:
            break
        dates.append(next_date)
        last_position = next_position
    return list(dict.fromkeys(dates))


def usable_dates(
    dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[pd.Timestamp]:
    positions = {date: index for index, date in enumerate(calendar)}
    return [
        date
        for date in dates
        if start <= date <= end
        and date in positions
        and positions[date] + ALIGNMENT_LABEL_OFFSET + CYCLE < len(calendar)
    ]


def metric_row(
    result: dict[str, Any],
    *,
    name: str,
    requested_start: pd.Timestamp,
    requested_end: pd.Timestamp,
    signal_dates: list[pd.Timestamp],
) -> dict[str, Any]:
    def pct(value: Any) -> float | None:
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value * 100.0 if np.isfinite(value) else None

    return {
        "window": name,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "signal_start": signal_dates[0] if signal_dates else None,
        "signal_end": signal_dates[-1] if signal_dates else None,
        "signal_periods": result.get("periods"),
        "direction": DIRECTION,
        "cycle": CYCLE,
        "selected_group": result.get("selected_group"),
        "stock_count_mean": result.get("stock_count_mean"),
        "rank_ic": result.get("rank_ic"),
        "ic_mean": result.get("ic_mean"),
        "gross_excess_pct": pct(result.get("gross_excess")),
        "turnover_pct": pct(result.get("turnover")),
        "annual_cost_pct": pct(result.get("annual_cost")),
        "net_excess_pct": pct(result.get("net_excess")),
    }


def latest_snapshot(
    frame: pd.DataFrame,
    factor_values: pd.Series,
    latest_date: pd.Timestamp,
) -> dict[str, Any]:
    snapshot = frame[["date", "instrument"]].copy()
    snapshot["factor"] = factor_values.to_numpy(dtype=float)
    snapshot = snapshot[snapshot["date"].eq(latest_date)].dropna(subset=["factor"])
    snapshot = snapshot.sort_values(
        ["factor", "instrument"], ascending=[False, True], kind="stable"
    ).head(20)
    return {
        "date": latest_date,
        "valid_stock_count": int(
            frame["date"].eq(latest_date).sum()
        ),
        "top20": [
            {"instrument": str(row.instrument), "factor": float(row.factor)}
            for row in snapshot.itertuples(index=False)
        ],
    }


def write_report(
    output_root: Path,
    settings: dict[str, Any],
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "qtld60_local_reproduction.json"
    csv_path = output_root / "qtld60_local_reproduction.csv"
    md_path = output_root / "qtld60_local_reproduction.md"
    payload = {
        "settings": settings,
        "results": rows,
        "latest_snapshot": snapshot,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    def value(row: dict[str, Any], key: str, digits: int = 2) -> str:
        item = row.get(key)
        return "n/a" if item is None else f"{float(item):.{digits}f}%"

    machine = settings["machine_profile"]
    lines = [
        "# QTLD60 本地复现报告",
        "",
        f"电脑标记：`{machine}`（{settings['machine_label']}）。",
        f"公式：`{FORMULA}`。本地实现为每只股票对 qfq `close` 做 60 个交易日滚动 20% 分位数，再除以当日 qfq `close`。",
        f"方向：`{DIRECTION}`，取因子值最高的第 10 组；调仓周期：`{CYCLE}` 个交易日。",
        "",
        f"对齐规则：`{ALIGNMENT_RULE_VERSION}`；规则文档：`{ALIGNMENT_RULES_DOCUMENT}`。",
        "数据来源：Tushare `stk_factor` 的 qfq 行情与 `daily_basic.total_mv`，仅保留沪深 `.SH/.SZ`，并按正式全 A 过滤条件保留有效行。",
        f"暖机：`{settings['data_start']}`；label：`close(t+{ALIGNMENT_LABEL_OFFSET}) -> close(t+{ALIGNMENT_LABEL_OFFSET}+cycle)`；基准：`factor_valid`；单边成本：`{100 * ALIGNMENT_ONE_WAY_COST:.2f}%`。",
        f"10 日信号日期来自已保存平台结果：`{settings['signal_reference']}`；正式信号期数为 `{settings['formal_signal_periods']}`。",
        "",
        "## 结果",
        "",
        "数值为算术年化百分比；近期窗口仅作诊断，不替代正式五年结论。",
        "",
        "| 窗口 | 信号日期 | 期数 | 股票数 | RankIC | IC | 毛超额 | 换手 | 年化成本 | 净超额 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        dates = f"{row['signal_start']} 至 {row['signal_end']}"
        rank_ic = "n/a" if row["rank_ic"] is None else f"{float(row['rank_ic']):.4f}"
        ic_mean = "n/a" if row["ic_mean"] is None else f"{float(row['ic_mean']):.4f}"
        lines.append(
            f"| {row['window']} | {dates} | {row['signal_periods']} | "
            f"{row['stock_count_mean']:.1f} | {rank_ic} | {ic_mean} | "
            f"{value(row, 'gross_excess_pct')} | {value(row, 'turnover_pct')} | "
            f"{value(row, 'annual_cost_pct')} | {value(row, 'net_excess_pct')} |"
        )
    lines.extend(
        [
            "",
            "## 最新截面",
            "",
            f"本地缓存最新可用日期：`{snapshot['date']}`，有效股票数 `{snapshot['valid_stock_count']}`。",
            "",
            "| 排名 | 股票 | QTLD60 |",
            "|---:|---|---:|",
        ]
    )
    for index, item in enumerate(snapshot["top20"], start=1):
        lines.append(f"| {index} | {item['instrument']} | {item['factor']:.8f} |")
    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            "- 正式窗口按平台保存的 10 日信号日期计算；近期窗口从 `2026-01-01` 起，沿同一信号节奏延伸到本地数据能完成 label-1、10 日持有期的最后日期。",
            "- 近期窗口是诊断结果，不能与平台五年净超额混合排名。",
            "- 本次没有对应的已保存 PandaAI QTLD60 结果，因此报告不宣称平台数值一致性；它是当前 Tushare 缓存下的本地复现基线。",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"json={json_path}", flush=True)
    print(f"csv={csv_path}", flush=True)
    print(f"md={md_path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-root", type=Path, required=True)
    parser.add_argument("--cap-root", type=Path, required=True)
    parser.add_argument("--calendar-root", type=Path, required=True)
    parser.add_argument("--data-end", type=str, default=None)
    parser.add_argument("--signal-reference", type=Path, default=DEFAULT_SIGNAL_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=2.60)
    parser.add_argument("--min-available-gb", type=float, default=1.50)
    args = parser.parse_args()
    if args.max_rss_gb <= 0 or args.min_available_gb <= 0:
        raise SystemExit("memory limits must be positive")

    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)
    if not (PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT).is_file():
        raise SystemExit(f"Alignment rules document is missing: {ALIGNMENT_RULES_DOCUMENT}")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {args.output}")

    reference_dates = reference_signal_dates(args.signal_reference)
    if args.data_end:
        data_end = pd.Timestamp(
            pd.to_datetime(
                args.data_end,
                format="%Y%m%d" if len(args.data_end) == 8 else None,
            )
        ).normalize()
    else:
        data_end = detect_cache_end(args.cap_root)
    if data_end < FORMAL_END:
        raise SystemExit(f"Local data end {data_end.date()} is earlier than formal end {FORMAL_END.date()}")
    print(
        f"factor={HANDLER} direction={DIRECTION} cycle={CYCLE} "
        f"reference_dates={len(reference_dates)} {reference_dates[0].date()}..{reference_dates[-1].date()}",
        flush=True,
    )
    memory_guard("start", args.max_rss_gb, args.min_available_gb)

    frame = load_minimal_full_a(
        args.price_root,
        args.cap_root,
        DATA_START,
        data_end,
        max_rss_gb=args.max_rss_gb,
        min_available_gb=args.min_available_gb,
    )
    latest_data_date = pd.Timestamp(frame["date"].max()).normalize()
    calendar = load_calendar(args.calendar_root, DATA_START, latest_data_date)
    if not calendar:
        raise RuntimeError("No cached trade-calendar dates are available")
    if latest_data_date > calendar[-1]:
        latest_data_date = calendar[-1]
    print(
        f"local_rows={len(frame)} pool={frame['instrument'].nunique()} "
        f"data={frame['date'].min().date()}..{latest_data_date.date()} calendar={len(calendar)}",
        flush=True,
    )
    memory_guard("before_factor", args.max_rss_gb, args.min_available_gb)

    factor_values = rolling_quantile_factor(frame)
    factor_values = factor_values.replace([np.inf, -np.inf], np.nan)
    memory_guard("after_factor", args.max_rss_gb, args.min_available_gb)
    close = panel_close(frame, calendar)
    memory_guard("after_close_panel", args.max_rss_gb, args.min_available_gb)

    formal_dates = usable_dates(
        reference_dates,
        calendar,
        FORMAL_START,
        FORMAL_END,
    )
    extended_dates = extend_signal_dates(reference_dates, calendar, latest_data_date)
    recent_dates = usable_dates(
        extended_dates,
        calendar,
        pd.Timestamp("2026-01-01"),
        latest_data_date,
    )
    if not formal_dates or not recent_dates:
        raise RuntimeError("No usable formal or recent signal dates")
    print(
        f"formal_dates={len(formal_dates)} {formal_dates[0].date()}..{formal_dates[-1].date()} "
        f"recent_dates={len(recent_dates)} {recent_dates[0].date()}..{recent_dates[-1].date()}",
        flush=True,
    )

    formal_result = evaluate(
        frame,
        factor_values,
        close,
        {},
        DIRECTION,
        formal_dates,
        calendar,
        CYCLE,
        ALIGNMENT_LABEL_OFFSET,
        HANDLER,
    )
    memory_guard("after_formal", args.max_rss_gb, args.min_available_gb)
    recent_result = evaluate(
        frame,
        factor_values,
        close,
        {},
        DIRECTION,
        recent_dates,
        calendar,
        CYCLE,
        ALIGNMENT_LABEL_OFFSET,
        HANDLER,
    )
    memory_guard("after_recent", args.max_rss_gb, args.min_available_gb)

    rows = [
        metric_row(
            formal_result,
            name="formal_5y",
            requested_start=FORMAL_START,
            requested_end=FORMAL_END,
            signal_dates=formal_dates,
        ),
        metric_row(
            recent_result,
            name="recent_diagnostic",
            requested_start=pd.Timestamp("2026-01-01"),
            requested_end=latest_data_date,
            signal_dates=recent_dates,
        ),
    ]
    snapshot = latest_snapshot(frame, factor_values, latest_data_date)
    machine = resolve_machine_profile()
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment_config": alignment_config,
        "machine_profile": machine["machine_profile"],
        "machine_label": machine["machine_label"],
        "formula": FORMULA,
        "handler": HANDLER,
        "direction": DIRECTION,
        "cycle": CYCLE,
        "window": WINDOW,
        "quantile": QUANTILE,
        "universe": "full_a",
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START,
        "formal_start": FORMAL_START,
        "formal_end": FORMAL_END,
        "local_data_end": latest_data_date,
        "groups": GROUPS,
        "label_offset": ALIGNMENT_LABEL_OFFSET,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "benchmark_mode": "factor_valid",
        "pool_count": int(frame["instrument"].nunique()),
        "local_rows": int(len(frame)),
        "calendar_dates": int(len(calendar)),
        "formal_signal_periods": int(len(formal_dates)),
        "recent_signal_periods": int(len(recent_dates)),
        "signal_reference": str(args.signal_reference),
        "data_provider": "Tushare",
        "price_source": "stk_factor qfq",
        "market_cap_source": "daily_basic.total_mv",
        "price_root": str(args.price_root),
        "cap_root": str(args.cap_root),
        "calendar_root": str(args.calendar_root),
        "memory_limits": {
            "max_rss_gb": args.max_rss_gb,
            "min_available_gb": args.min_available_gb,
        },
    }
    write_report(args.output, settings, rows, snapshot)
    print(
        "formal_net_excess_pct="
        f"{rows[0]['net_excess_pct']:.4f} recent_net_excess_pct="
        f"{rows[1]['net_excess_pct']:.4f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
