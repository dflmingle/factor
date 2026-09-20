#!/usr/bin/env python3
"""Recheck one promising local factor combination on three canonical windows."""

from __future__ import annotations

import argparse
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

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
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
    compact_financial_instruments,
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
MAX_RSS_GB = 1.60
MIN_AVAILABLE_GB = 2.50

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "quantpedia-combination-local-reproduction-20260920"
)

COMPONENTS = (
    {"key": "SIZE", "handler": "size_only", "direction": 0},
    {"key": "H03", "handler": "impact60", "direction": 1},
    {"key": "RESVOL", "handler": "residual_volatility", "direction": 1},
)

WITHOUT_SIZE_COMPONENTS = (
    {"key": "H03", "handler": "impact60", "direction": 1},
    {"key": "RESVOL", "handler": "residual_volatility", "direction": 1},
)

VARIANT_SPECS = {
    "with_size": {
        "components": COMPONENTS,
        "name": "SIZE+H03+RESVOL",
        "formula": "(RANK(-MARKET_CAP) + RANK(H03) + RANK(-RESIDUAL_VOLATILITY)) / 3",
        "stem": "quantpedia_combination_local_reproduction",
    },
    "without_size": {
        "components": WITHOUT_SIZE_COMPONENTS,
        "name": "H03+RESVOL",
        "formula": "(RANK(H03) + RANK(-RESIDUAL_VOLATILITY)) / 2",
        "stem": "quantpedia_combination_without_size_local_reproduction",
    },
    "h03_only": {
        "components": (COMPONENTS[1],),
        "name": "H03",
        "formula": "RANK(H03)",
        "stem": "h03_single_common_schedule_reproduction",
    },
    "resvol_only": {
        "components": (COMPONENTS[2],),
        "name": "RESVOL",
        "formula": "RANK(-RESIDUAL_VOLATILITY)",
        "stem": "resvol_single_common_schedule_reproduction",
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


def pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number * 100.0 if np.isfinite(number) else None


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


def run(args: argparse.Namespace) -> int:
    variant = VARIANT_SPECS[args.variant]
    components = variant["components"]
    combination_name = variant["name"]
    formula = variant["formula"]
    result_stem = variant["stem"]
    output_root = args.output.resolve()
    result_path = output_root / f"{result_stem}.json"
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

    print(f"combination={combination_name} cycle={CYCLE} data={DATA_START.date()}..{data_end.date()}", flush=True)
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
    frame, categories = compact_full_a_frame(frame)
    latest_data_date = pd.Timestamp(frame["date"].max()).normalize()
    calendar = load_calendar(args.calendar_root, DATA_START, latest_data_date)
    if latest_data_date > calendar[-1]:
        latest_data_date = calendar[-1]
    memory_guard("loaded_market", args.max_rss_gb, args.min_available_gb)
    all_dates = generated_signal_dates(calendar, FORMAL_START, latest_data_date)
    windows = {
        "formal_5y": [date for date in all_dates if date <= FORMAL_END],
        "recent_2026": [date for date in all_dates if RECENT_START <= date <= latest_data_date],
        "since_2026_06_01": [date for date in all_dates if MID_START <= date <= latest_data_date],
    }
    signal_dates = sorted(set(date for dates in windows.values() for date in dates))
    print(
        f"local_rows={len(frame)} instruments={frame['instrument'].nunique()} "
        f"signal_dates={len(signal_dates)} formal={len(windows['formal_5y'])} "
        f"recent={len(windows['recent_2026'])} mid={len(windows['since_2026_06_01'])}",
        flush=True,
    )

    financial = None
    if any(item["handler"] in FINANCIAL_HANDLERS for item in components):
        financial = load_financial_cache(args.financial_root)
        compact_financial_instruments(financial, categories)
        print("financial_cache=loaded provider=Tushare-cache", flush=True)
    signal_mask = frame["date"].isin(signal_dates)
    component_values: dict[str, pd.Series] = {}
    for item in components:
        print(f"building={item['handler']}", flush=True)
        raw = build_factor(
            frame,
            item["handler"],
            financial=financial,
            signal_dates=signal_dates,
        )
        oriented = raw if item["direction"] == 1 else raw.mul(-1.0)
        signal_values = pd.to_numeric(oriented.loc[signal_mask], errors="coerce")
        ranks = signal_values.groupby(
            frame.loc[signal_mask, "date"], sort=False, observed=True
        ).rank(method="average", pct=True)
        component_values[item["key"]] = ranks
        del raw, oriented, signal_values, ranks
        gc.collect()
        memory_guard(f"after_{item['key']}", args.max_rss_gb, args.min_available_gb)

    combo = pd.Series(np.nan, index=frame.index, dtype=float)
    combo.loc[signal_mask] = pd.concat(component_values, axis=1).mean(axis=1).to_numpy(dtype=float)
    del component_values, financial
    gc.collect()
    memory_guard("built_combination", args.max_rss_gb, args.min_available_gb)
    close = panel_close(frame, calendar)
    memory_guard("built_close_panel", args.max_rss_gb, args.min_available_gb)

    results: dict[str, dict[str, Any]] = {}
    for name, dates in windows.items():
        result = evaluate(
            frame,
            combo,
            close,
            {},
            1,
            dates,
            calendar,
            CYCLE,
            ALIGNMENT_LABEL_OFFSET,
            "",
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
        "combination": combination_name,
        "formula": formula,
        "status": "local_combination_proxy",
        "source": "Offline exhaustive representative combination search; components are saved positive mechanisms.",
        "notes": [
            "SIZE is the low-market-cap direction of RANK(MARKET_CAP).",
            "H03 is the saved 60-day high-low/amount impact mechanism.",
            "RESVOL is a local market-model residual-volatility proxy for the unavailable platform Barra field.",
            "The equal-weight combination is a local portfolio proxy, not a PandaAI official pool score.",
        ],
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
        "components": components,
        "results": results,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    csv_path = output_root / f"{result_stem}.csv"
    pd.DataFrame(
        [
            {"combination": payload["combination"], "formula": payload["formula"], "window": window, **result,
             "gross_excess_pct": pct(result.get("gross_excess")),
             "net_excess_pct": pct(result.get("net_excess")),
             "turnover_pct": pct(result.get("turnover")),
             "annual_cost_pct": pct(result.get("annual_cost"))}
            for window, result in results.items()
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")
    md_path = output_root / f"{result_stem}.md"
    lines = [
        f"# Promising local combination: {combination_name} three-window reproduction",
        "",
        f"Machine: `{machine['machine_profile']}` ({machine['machine_label']}).",
        "No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.",
        f"Alignment rule: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        "Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+1+cycle)`; 10 groups; `factor_valid`; one-way cost `0.30%`.",
        "",
        "## Candidate",
        "",
        f"`{combination_name}` is an equal-weight local combination selected by an offline exhaustive search from saved positive single-mechanism representatives. It is a research candidate, not a platform result.",
        "",
        f"Formula: `{formula}`",
        "",
        "- `SIZE`: long the low-market-cap side of `RANK(MARKET_CAP)` (included only in the with-size variant).",
        "- `H03`: 60-day high-low range relative to lagged close, scaled by 60-day amount.",
        "- `RESVOL`: long low local market-model residual volatility; this is explicitly a proxy for the unavailable platform Barra field.",
        "",
        "## Results",
        "",
        "| window | periods | RankIC | gross excess | net excess | turnover | annual cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for window, result in results.items():
        def show(value: Any) -> str:
            return "n/a" if value is None else f"{float(value):.2f}%"

        rank_ic = "n/a" if result.get("rank_ic") is None else f"{float(result['rank_ic']):.4f}"
        lines.append(
            f"| `{window}` | {result['periods']} | {rank_ic} | {show(pct(result.get('gross_excess')))} | "
            f"{show(pct(result.get('net_excess')))} | {show(pct(result.get('turnover')))} | "
            f"{show(pct(result.get('annual_cost')))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A positive result in all three windows supports offline follow-up. It does not establish platform equivalence, and the RESVOL component must remain labeled as a proxy until separately verified.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"json={result_path}", flush=True)
    print(f"csv={csv_path}", flush=True)
    print(f"md={md_path}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "tushare_factor_recheck" / "qfq" / "daily_batches")
    parser.add_argument("--cap-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "tushare_factor_recheck" / "daily_basic_full_a")
    parser.add_argument("--financial-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "financial_full_a")
    parser.add_argument("--calendar-root", type=Path, default=PROJECT_ROOT / ".tushare-refresh-20260918-v2" / "trade_calendar")
    parser.add_argument("--data-end", default=None)
    parser.add_argument("--variant", choices=sorted(VARIANT_SPECS), default="with_size")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=MAX_RSS_GB)
    parser.add_argument("--min-available-gb", type=float, default=MIN_AVAILABLE_GB)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
