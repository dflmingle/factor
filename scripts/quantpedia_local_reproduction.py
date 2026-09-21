#!/usr/bin/env python3
"""Run a small, offline Quantpedia factor screen on the cached Tushare panel.

This script deliberately evaluates only the three selected candidates. It does
not contact PandaAI or Tushare, and it writes both the canonical five-year
window and a separate recent diagnostic window.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from machine_profile import resolve_machine_profile  # noqa: E402
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
    evaluate,
    grouped_rolling,
    panel_close,
)
from qtld60_local_reproduction import (  # noqa: E402
    detect_cache_end,
    load_calendar,
    load_minimal_full_a,
    memory_guard,
)


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
FORMAL_START = pd.Timestamp(ALIGNMENT_START)
FORMAL_END = pd.Timestamp(ALIGNMENT_END)
RECENT_START = pd.Timestamp("20260101")
GROUPS = ALIGNMENT_GROUPS
CYCLE = 21
MAX_RSS_GB = 2.60
MIN_AVAILABLE_GB = 3.00
GB = 1024**3

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / ".tushare-refresh-20260918-v2"
    / "reports"
    / "quantpedia_local_reproduction_20260919"
)

SPECS: dict[str, dict[str, Any]] = {
    "low_volatility_3y_weekly": {
        "formula": "-STDDEV(RETURNS(CLOSE,5),156)",
        "direction": 1,
        "source": "https://quantpedia.com/strategies/low-volatility-factor-effect-in-stocks",
        "mechanism": "low-risk anomaly; low historical volatility stocks",
        "note": "156 five-day returns approximate the paper's three years of weekly returns",
    },
    "momentum_12_1": {
        "formula": "DELAY(CLOSE,21)/DELAY(CLOSE,252)-1",
        "direction": 1,
        "source": "https://quantpedia.com/strategies/momentum-factor-effect-in-stocks",
        "mechanism": "underreaction and continuation of information",
        "note": "past one-year return excluding the most recent month",
    },
    "52w_high_proximity_proxy": {
        "formula": "CLOSE/TS_MAX(CLOSE,252)",
        "direction": 1,
        "source": "https://quantpedia.com/strategies/52-weeks-high-effect-in-stocks",
        "mechanism": "52-week-high anchoring and slow information diffusion",
        "note": "stock-level proxy; the source strategy also aggregates the signal by industry",
    },
}


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


def generated_signal_dates(
    calendar: list[pd.Timestamp],
    start: pd.Timestamp,
    end: pd.Timestamp,
    cycle: int,
) -> list[pd.Timestamp]:
    positions = {date: index for index, date in enumerate(calendar)}
    if start not in positions:
        raise RuntimeError(f"Signal anchor is not a trading day: {start.date()}")
    anchor = positions[start]
    dates: list[pd.Timestamp] = []
    for position in range(anchor, len(calendar), cycle):
        date = calendar[position]
        if date > end:
            break
        if position + ALIGNMENT_LABEL_OFFSET + cycle < len(calendar):
            dates.append(date)
    return dates


def build_factor(frame: pd.DataFrame, name: str) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)
    close = pd.to_numeric(frame["close_qfq"], errors="coerce")

    if name == "low_volatility_3y_weekly":
        ret5 = close.div(grouped["close_qfq"].shift(5)).sub(1.0)
        work = frame[["instrument"]].copy()
        work["ret5"] = ret5
        return -grouped_rolling(work, "ret5", 156, "std")

    if name == "momentum_12_1":
        return grouped["close_qfq"].shift(21).div(
            grouped["close_qfq"].shift(252)
        ).sub(1.0)

    if name == "52w_high_proximity_proxy":
        work = frame[["instrument"]].copy()
        work["close"] = close
        trailing_high = grouped_rolling(work, "close", 252, "max")
        return close.div(trailing_high)

    raise KeyError(f"Unknown factor: {name}")


def latest_snapshot(
    frame: pd.DataFrame,
    factor_values: pd.Series,
    latest_date: pd.Timestamp,
) -> list[dict[str, Any]]:
    snapshot = frame[["date", "instrument"]].copy()
    snapshot["factor"] = factor_values.to_numpy(dtype=float)
    snapshot = snapshot[snapshot["date"].eq(latest_date)].dropna(subset=["factor"])
    snapshot["instrument_text"] = snapshot["instrument"].astype(str)
    snapshot = snapshot.sort_values(
        ["factor", "instrument_text"], ascending=[False, True], kind="stable"
    ).head(20)
    return [
        {
            "instrument": str(row.instrument),
            "factor": float(row.factor),
        }
        for row in snapshot.itertuples(index=False)
    ]


def metric_row(
    factor_name: str,
    window_name: str,
    requested_start: pd.Timestamp,
    requested_end: pd.Timestamp,
    signal_dates: list[pd.Timestamp],
    result: dict[str, Any],
) -> dict[str, Any]:
    def pct(value: Any) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed * 100.0 if np.isfinite(parsed) else None

    return {
        "factor": factor_name,
        "window": window_name,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "signal_start": signal_dates[0] if signal_dates else None,
        "signal_end": signal_dates[-1] if signal_dates else None,
        "signal_periods": result.get("periods"),
        "direction": SPECS[factor_name]["direction"],
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


def write_outputs(
    output_root: Path,
    settings: dict[str, Any],
    rows: list[dict[str, Any]],
    snapshots: dict[str, list[dict[str, Any]]],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": settings,
        "candidates": SPECS,
        "results": rows,
        "latest_snapshots": snapshots,
    }
    json_path = output_root / "quantpedia_local_reproduction.json"
    csv_path = output_root / "quantpedia_local_reproduction.csv"
    md_path = output_root / "quantpedia_local_reproduction.md"
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

    machine = settings["machine_profile"]

    def value(row: dict[str, Any], key: str, digits: int = 2) -> str:
        item = row.get(key)
        return "n/a" if item is None else f"{float(item):.{digits}f}%"

    lines = [
        "# Quantpedia local reproduction",
        "",
        f"Machine: `{machine}` ({settings['machine_label']}).",
        "No PandaAI factor was created or run. No network data request was made.",
        f"Data provider: Tushare qfq prices joined with daily_basic.total_mv; full-A `.SH/.SZ` universe.",
        f"Alignment rule: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        f"Warm-up: `{settings['data_start']}`; label: `close(t+1) -> close(t+1+cycle)`; benchmark: `factor_valid`.",
        f"Schedule: generated every `{CYCLE}` trading days from `{FORMAL_START.date()}` as a monthly cadence proxy.",
        "The source Quantpedia results are paper-sample figures, not China A-share results.",
        "",
        "## Candidate definitions",
        "",
        "| factor | formula | direction | source note |",
        "|---|---|---:|---|",
    ]
    for name, spec in SPECS.items():
        lines.append(
            f"| `{name}` | `{spec['formula']}` | {spec['direction']} | {spec['note']} |"
        )
    lines.extend(
        [
            "",
            "## Results",
            "",
            "Recent results are diagnostics and are not mixed into the formal ranking.",
            "",
            "| factor | window | periods | stocks | RankIC | IC | gross excess | turnover | annual cost | net excess |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        rank_ic = "n/a" if row["rank_ic"] is None else f"{float(row['rank_ic']):.4f}"
        ic_mean = "n/a" if row["ic_mean"] is None else f"{float(row['ic_mean']):.4f}"
        stocks = "n/a" if row["stock_count_mean"] is None else f"{float(row['stock_count_mean']):.1f}"
        lines.append(
            f"| `{row['factor']}` | `{row['window']}` | {row['signal_periods']} | {stocks} | "
            f"{rank_ic} | {ic_mean} | {value(row, 'gross_excess_pct')} | "
            f"{value(row, 'turnover_pct')} | {value(row, 'annual_cost_pct')} | "
            f"{value(row, 'net_excess_pct')} |"
        )
    lines.extend(["", "## Latest snapshots", ""])
    for name, items in snapshots.items():
        lines.extend(
            [
                f"### `{name}`",
                "",
                "| rank | instrument | factor |",
                "|---:|---|---:|",
            ]
        )
        for index, item in enumerate(items, start=1):
            lines.append(f"| {index} | {item['instrument']} | {item['factor']:.8f} |")
        lines.append("")
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=MAX_RSS_GB)
    parser.add_argument("--min-available-gb", type=float, default=MIN_AVAILABLE_GB)
    args = parser.parse_args()

    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {args.output}")
    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)
    if not (PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT).is_file():
        raise SystemExit(f"Alignment rules document is missing: {ALIGNMENT_RULES_DOCUMENT}")

    data_end = (
        pd.Timestamp(pd.to_datetime(args.data_end, format="%Y%m%d"))
        if args.data_end
        else detect_cache_end(args.cap_root)
    ).normalize()
    if data_end < FORMAL_END:
        raise SystemExit(f"Local data end {data_end.date()} is earlier than formal end {FORMAL_END.date()}")

    print(
        f"candidates={len(SPECS)} cycle={CYCLE} data={DATA_START.date()}..{data_end.date()}",
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
    print(
        f"local_rows={len(frame)} pool={frame['instrument'].nunique()} "
        f"data={frame['date'].min().date()}..{latest_data_date.date()} calendar={len(calendar)}",
        flush=True,
    )
    memory_guard("before_panel", args.max_rss_gb, args.min_available_gb)
    close = panel_close(frame, calendar)
    memory_guard("after_panel", args.max_rss_gb, args.min_available_gb)

    formal_dates = generated_signal_dates(calendar, FORMAL_START, FORMAL_END, CYCLE)
    all_dates = generated_signal_dates(calendar, FORMAL_START, latest_data_date, CYCLE)
    recent_dates = [date for date in all_dates if RECENT_START <= date <= latest_data_date]
    if not formal_dates or not recent_dates:
        raise RuntimeError("No usable formal or recent signal dates")
    print(
        f"formal_dates={len(formal_dates)} {formal_dates[0].date()}..{formal_dates[-1].date()} "
        f"recent_dates={len(recent_dates)} {recent_dates[0].date()}..{recent_dates[-1].date()}",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    snapshots: dict[str, list[dict[str, Any]]] = {}
    for name in SPECS:
        print(f"factor_start={name}", flush=True)
        factor_values = build_factor(frame, name).replace([np.inf, -np.inf], np.nan)
        memory_guard(f"after_factor_{name}", args.max_rss_gb, args.min_available_gb)
        formal_result = evaluate(
            frame,
            factor_values,
            close,
            {},
            int(SPECS[name]["direction"]),
            formal_dates,
            calendar,
            CYCLE,
            ALIGNMENT_LABEL_OFFSET,
            None,
        )
        memory_guard(f"after_formal_{name}", args.max_rss_gb, args.min_available_gb)
        recent_result = evaluate(
            frame,
            factor_values,
            close,
            {},
            int(SPECS[name]["direction"]),
            recent_dates,
            calendar,
            CYCLE,
            ALIGNMENT_LABEL_OFFSET,
            None,
        )
        rows.append(
            metric_row(name, "formal_5y", FORMAL_START, FORMAL_END, formal_dates, formal_result)
        )
        rows.append(
            metric_row(name, "recent_diagnostic", RECENT_START, latest_data_date, recent_dates, recent_result)
        )
        snapshots[name] = latest_snapshot(frame, factor_values, latest_data_date)
        print(
            f"factor_done={name} formal_net={rows[-2]['net_excess_pct']:.4f} "
            f"recent_net={rows[-1]['net_excess_pct']:.4f}",
            flush=True,
        )
        del factor_values, formal_result, recent_result
        gc.collect()
        memory_guard(f"after_release_{name}", args.max_rss_gb, args.min_available_gb)

    machine = resolve_machine_profile()
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment_config": alignment_config,
        "machine_profile": machine["machine_profile"],
        "machine_label": machine["machine_label"],
        "data_provider": "Tushare",
        "price_source": "stk_factor qfq",
        "market_cap_source": "daily_basic.total_mv",
        "universe": "full_a",
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START,
        "formal_start": FORMAL_START,
        "formal_end": FORMAL_END,
        "recent_start": RECENT_START,
        "local_data_end": latest_data_date,
        "groups": GROUPS,
        "cycle": CYCLE,
        "label_offset": ALIGNMENT_LABEL_OFFSET,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "benchmark_mode": "factor_valid",
        "signal_schedule": "generated_calendar_21d",
        "pool_count": int(frame["instrument"].nunique()),
        "local_rows": int(len(frame)),
        "calendar_dates": int(len(calendar)),
        "formal_signal_periods": int(len(formal_dates)),
        "recent_signal_periods": int(len(recent_dates)),
        "memory_limits": {
            "max_rss_gb": args.max_rss_gb,
            "min_available_gb": args.min_available_gb,
        },
    }
    write_outputs(args.output, settings, rows, snapshots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
