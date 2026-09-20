#!/usr/bin/env python3
"""Offline local reproduction for Quantpedia-style price candidates.

Run one candidate per process so a full-A panel is released before the next
candidate starts.  The inputs are the cached Tushare qfq/daily_basic files;
the script never contacts PandaAI or Tushare.
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

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
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
    build_factor,
    compact_full_a_frame,
    evaluate,
    panel_close,
)
from qtld60_local_reproduction import (  # noqa: E402
    detect_cache_end,
    load_calendar,
    memory_guard,
)


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
FORMAL_START = pd.Timestamp(ALIGNMENT_START)
FORMAL_END = pd.Timestamp(ALIGNMENT_END)
RECENT_START = pd.Timestamp("20260101")
MID_START = pd.Timestamp("20260601")
CYCLE = 10
MAX_RSS_GB = 2.60
MIN_AVAILABLE_GB = 3.00

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "quantpedia-price-local-reproduction-20260920"
)

CANDIDATES: dict[str, dict[str, Any]] = {
    "short_term_reversal_5": {
        "handler": "reversal5",
        "formula": "RANK(1 - RETURNS(CLOSE,5))",
        "direction": 1,
        "invert": False,
        "source": "https://quantpedia.com/strategies/short-term-reversal",
        "note": "Five-day short-term reversal: recent losers are expected to rebound.",
    },
    "short_term_reversal_20": {
        "handler": "reversal20",
        "formula": "RANK(1 - RETURNS(CLOSE,20))",
        "direction": 1,
        "invert": False,
        "source": "https://quantpedia.com/strategies/short-term-reversal",
        "note": "Twenty-day short-term reversal variant, tested under the same local schedule.",
    },
    "low_volatility_21": {
        "handler": "volatility21",
        "formula": "RANK(-STDDEV(RETURNS(CLOSE,1),21))",
        "direction": 1,
        "invert": True,
        "source": "https://quantpedia.com/strategies/low-volatility-factor-effect-in-stocks",
        "note": "21-day realized volatility with an explicit negative sign so low volatility is the long direction.",
    },
}


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if value is pd.NA:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def generated_signal_dates(
    calendar: list[pd.Timestamp],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[pd.Timestamp]:
    positions = {date: index for index, date in enumerate(calendar)}
    if start not in positions:
        raise RuntimeError(f"Signal anchor is not a trading day: {start.date()}")
    anchor = positions[start]
    dates: list[pd.Timestamp] = []
    for position in range(anchor, len(calendar), CYCLE):
        date = calendar[position]
        if date > end:
            break
        if position + ALIGNMENT_LABEL_OFFSET + CYCLE < len(calendar):
            dates.append(date)
    return dates


def pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number * 100.0 if np.isfinite(number) else None


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result.get(key)
        for key in (
            "periods",
            "stock_count_mean",
            "rank_ic",
            "ic_mean",
            "gross_excess",
            "turnover",
            "annual_cost",
            "net_excess",
        )
    }


def run_candidate(args: argparse.Namespace) -> int:
    spec = CANDIDATES[args.candidate]
    output_root = args.output.resolve()
    result_dir = output_root / "candidates"
    result_path = result_dir / f"{args.candidate}.json"
    if result_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing result: {result_path}")

    alignment = alignment_config_snapshot()
    validate_alignment_config(alignment)
    if not (PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT).is_file():
        raise SystemExit(f"Missing alignment rules: {ALIGNMENT_RULES_DOCUMENT}")
    data_end = (
        pd.Timestamp(pd.to_datetime(args.data_end, format="%Y%m%d"))
        if args.data_end
        else detect_cache_end(args.cap_root)
    ).normalize()
    if data_end < FORMAL_END:
        raise SystemExit(f"Local data end {data_end.date()} is earlier than formal end {FORMAL_END.date()}")

    print(
        f"candidate={args.candidate} handler={spec['handler']} cycle={CYCLE} "
        f"data={DATA_START.date()}..{data_end.date()}",
        flush=True,
    )
    memory_guard("start", args.max_rss_gb, args.min_available_gb)
    frame = load_full_a_data(
        args.price_root,
        args.cap_root,
        DATA_START,
        data_end,
        market_cap_field=ALIGNMENT_MARKET_CAP_FIELD,
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    frame, _categories = compact_full_a_frame(frame)
    latest_data_date = pd.Timestamp(frame["date"].max()).normalize()
    calendar = load_calendar(args.calendar_root, DATA_START, latest_data_date)
    if latest_data_date > calendar[-1]:
        latest_data_date = calendar[-1]
    memory_guard("loaded_market", args.max_rss_gb, args.min_available_gb)
    print(
        f"local_rows={len(frame)} instruments={frame['instrument'].nunique()} "
        f"data={frame['date'].min().date()}..{latest_data_date.date()} calendar={len(calendar)}",
        flush=True,
    )

    all_dates = generated_signal_dates(calendar, FORMAL_START, latest_data_date)
    windows = {
        "formal_5y": [date for date in all_dates if date <= FORMAL_END],
        "recent_2026": [date for date in all_dates if RECENT_START <= date <= latest_data_date],
        "since_2026_06_01": [date for date in all_dates if MID_START <= date <= latest_data_date],
    }
    if any(not dates for dates in windows.values()):
        raise RuntimeError("No usable formal, recent, or 2026-06-01 signal dates")
    signal_dates = sorted(set(date for dates in windows.values() for date in dates))
    print(
        " ".join(f"{name}={len(dates)}" for name, dates in windows.items())
        + f" signal_dates={len(signal_dates)}",
        flush=True,
    )

    factor_values = build_factor(frame, spec["handler"], signal_dates=signal_dates)
    if spec["invert"]:
        factor_values = factor_values.mul(-1.0)
    factor_values = factor_values.replace([np.inf, -np.inf], np.nan)
    memory_guard("built_factor", args.max_rss_gb, args.min_available_gb)
    close = panel_close(frame, calendar)
    memory_guard("built_close_panel", args.max_rss_gb, args.min_available_gb)

    results: dict[str, dict[str, Any]] = {}
    for name, dates in windows.items():
        result = evaluate(
            frame,
            factor_values,
            close,
            {},
            int(spec["direction"]),
            dates,
            calendar,
            CYCLE,
            ALIGNMENT_LABEL_OFFSET,
            spec["handler"],
        )
        results[name] = compact_result(result)
        print(
            f"window={name} periods={result['periods']} rank_ic={result['rank_ic']!s} "
            f"net_excess={pct(result['net_excess'])!s}% turnover={pct(result['turnover'])!s}%",
            flush=True,
        )
        memory_guard(f"after_{name}", args.max_rss_gb, args.min_available_gb)

    machine = resolve_machine_profile()
    payload = {
        "candidate": args.candidate,
        "spec": spec,
        "settings": {
            "machine_profile": machine["machine_profile"],
            "machine_label": machine["machine_label"],
            "data_provider": "Tushare",
            "network_access": "none",
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_config": alignment,
            "data_start": DATA_START,
            "formal_start": FORMAL_START,
            "formal_end": FORMAL_END,
            "recent_start": RECENT_START,
            "mid_start": MID_START,
            "local_data_end": latest_data_date,
            "universe": "full_a",
            "price_mode": ALIGNMENT_PRICE_MODE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "groups": ALIGNMENT_GROUPS,
            "cycle": CYCLE,
            "label_offset": ALIGNMENT_LABEL_OFFSET,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "benchmark_mode": "factor_valid",
            "signal_schedule": "generated_calendar_10d_anchor_2021-09-07",
            "rows": len(frame),
            "instruments": int(frame["instrument"].nunique()),
        },
        "results": results,
    }
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    print(f"result={result_path}", flush=True)
    del factor_values, close, frame
    gc.collect()
    return 0


def load_results(output_root: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        path = output_root / "candidates" / f"{candidate}.json"
        if path.is_file():
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def aggregate(args: argparse.Namespace) -> int:
    output_root = args.output.resolve()
    payloads = load_results(output_root)
    if not payloads:
        raise SystemExit(f"No candidate results found under {output_root / 'candidates'}")
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        for window, result in payload["results"].items():
            rows.append(
                {
                    "candidate": payload["candidate"],
                    "formula": payload["spec"]["formula"],
                    "window": window,
                    **result,
                    "net_excess_pct": pct(result.get("net_excess")),
                    "gross_excess_pct": pct(result.get("gross_excess")),
                    "turnover_pct": pct(result.get("turnover")),
                    "annual_cost_pct": pct(result.get("annual_cost")),
                }
            )
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "quantpedia_price_local_reproduction.json"
    csv_path = output_root / "quantpedia_price_local_reproduction.csv"
    md_path = output_root / "quantpedia_price_local_reproduction.md"
    json_path.write_text(
        json.dumps(
            {
                "alignment_rule_version": ALIGNMENT_RULE_VERSION,
                "machine_profile": payloads[0]["settings"]["machine_profile"],
                "machine_label": payloads[0]["settings"]["machine_label"],
                "data_provider": "Tushare",
                "network_access": "none",
                "candidates": payloads,
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
        + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(rows[0])
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    window_order = {"formal_5y": 0, "recent_2026": 1, "since_2026_06_01": 2}
    lines = [
        "# Quantpedia price candidates: local reproduction",
        "",
        f"Machine: `{payloads[0]['settings']['machine_profile']}` ({payloads[0]['settings']['machine_label']}).",
        "No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.",
        f"Alignment rule: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        "Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+1+cycle)`; 10 groups; `factor_valid`; one-way cost `0.30%`.",
        f"Formal window: `{FORMAL_START.date()}..{FORMAL_END.date()}`. Diagnostics: `{RECENT_START.date()}+` and `{MID_START.date()}+`.",
        "Signal schedule: every 10 trading days anchored at `2021-09-07`; diagnostics are not mixed into formal ranking.",
        "",
        "## Results",
        "",
        "| candidate | formula | window | periods | RankIC | gross excess | net excess | turnover | annual cost |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: (item["candidate"], window_order[item["window"]])):
        def show(value: Any) -> str:
            return "n/a" if value is None else f"{float(value):.2f}%"

        rank_ic = "n/a" if row.get("rank_ic") is None else f"{float(row['rank_ic']):.4f}"
        lines.append(
            f"| `{row['candidate']}` | `{row['formula']}` | `{row['window']}` | {row['periods']} | {rank_ic} | "
            f"{show(row.get('gross_excess_pct'))} | {show(row.get('net_excess_pct'))} | "
            f"{show(row.get('turnover_pct'))} | {show(row.get('annual_cost_pct'))} |"
        )
    lines.extend(["", "## Candidate notes", ""])
    for payload in payloads:
        spec = payload["spec"]
        formal = payload["results"]["formal_5y"]
        recent = payload["results"]["recent_2026"]
        mid = payload["results"]["since_2026_06_01"]
        good = all(
            value is not None and float(value) > 0
            for value in (formal.get("net_excess"), recent.get("net_excess"), mid.get("net_excess"))
        )
        lines.extend(
            [
                f"### `{payload['candidate']}`: {'three-window positive' if good else 'not three-window positive'}",
                "",
                f"- Formula: `{spec['formula']}`",
                f"- Source: [{spec['source']}]({spec['source']}).",
                f"- Local note: {spec['note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation",
            "",
            "These are offline China A-share diagnostics using cached Tushare data. The candidates are not submitted to PandaAI; platform review remains a separate user decision.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"json={json_path}", flush=True)
    print(f"csv={csv_path}", flush=True)
    print(f"md={md_path}", flush=True)
    for payload in payloads:
        print(
            f"summary={payload['candidate']} "
            f"formal_net={pct(payload['results']['formal_5y'].get('net_excess'))}% "
            f"recent_net={pct(payload['results']['recent_2026'].get('net_excess'))}% "
            f"mid_net={pct(payload['results']['since_2026_06_01'].get('net_excess'))}%",
            flush=True,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--price-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "tushare_factor_recheck" / "qfq" / "daily_batches")
    parser.add_argument("--cap-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "tushare_factor_recheck" / "daily_basic_full_a")
    parser.add_argument("--calendar-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "trade_calendar")
    parser.add_argument("--data-end", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=MAX_RSS_GB)
    parser.add_argument("--min-available-gb", type=float, default=MIN_AVAILABLE_GB)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.aggregate:
        return aggregate(args)
    if not args.candidate:
        parser.error("choose --candidate or use --aggregate")
    return run_candidate(args)


if __name__ == "__main__":
    raise SystemExit(main())
