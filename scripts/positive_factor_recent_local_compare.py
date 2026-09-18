#!/usr/bin/env python3
"""Evaluate every saved platform-net-positive factor in a recent local window.

This is a diagnostic companion to ``positive_factor_local_compare.py``.  The
factor values still use the canonical 2018 warm-up, while portfolio statistics
are calculated only from the requested recent signal dates.  The saved
platform result remains the five-year selection source and is never treated as
the recent-window return.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    alignment_config_snapshot,
    validate_alignment_config,
)
from positive_factor_local_compare import (  # noqa: E402
    DATA_START,
    END,
    build_factor,
    evaluate,
    formula_catalog,
    infer_cycle,
    panel_close,
    saved_records,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DEFAULT_RECENT_START = pd.Timestamp("2026-01-01")
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/positive-factor-recent-20260918"
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def pct(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number * 100.0 if np.isfinite(number) else None


def usable_recent_dates(
    dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    cycle: int,
    recent_start: pd.Timestamp,
) -> list[pd.Timestamp]:
    positions = {date: position for position, date in enumerate(calendar)}
    result: list[pd.Timestamp] = []
    for value in dates:
        date = pd.Timestamp(value).normalize()
        position = positions.get(date)
        if date < recent_start or position is None:
            continue
        if position + ALIGNMENT_LABEL_OFFSET + cycle >= len(calendar):
            continue
        result.append(date)
    return list(dict.fromkeys(result))


def output_paths(output_root: Path) -> dict[str, Path]:
    return {
        "json": output_root / "positive_factor_recent_local_compare.json",
        "csv": output_root / "positive_factor_recent_local_compare.csv",
        "md": output_root / "positive_factor_recent_local_compare.md",
    }


def refuse_overwrite(paths: dict[str, Path]) -> None:
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite recent diagnostic output: "
            + ", ".join(str(path) for path in existing)
        )


def write_outputs(
    paths: dict[str, Path],
    settings: dict[str, Any],
    rows: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
) -> None:
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": settings,
        "results": rows,
        "unsupported": unsupported,
    }
    paths["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    fields: list[str] = []
    for row in rows + unsupported:
        for field in row:
            if field not in fields:
                fields.append(field)
    with paths["csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows + unsupported)

    ordered = sorted(
        rows,
        key=lambda row: (
            row.get("recent_net_excess_pct") is None,
            -(row.get("recent_net_excess_pct") or 0.0),
        ),
    )
    lines = [
        "# Recent local diagnostics for platform-net-positive factors",
        "",
        "This report is a recent-window diagnostic, not a replacement for the canonical five-year alignment report.",
        f"Alignment rules: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        f"Factor values use `{settings['data_start']}` warm-up; portfolio statistics use signal dates from `{settings['recent_start']}`.",
        "The platform net column is the saved full-window screening result. It is not a recent-window platform return.",
        "",
        f"- positive platform records: `{settings['platform_positive_records']}`",
        f"- locally reproduced: `{settings['locally_reproduced_records']}`",
        f"- no local handler or no usable recent dates: `{settings['unsupported_records']}`",
        f"- recent signal dates: `{settings['recent_signal_dates_min']}` to `{settings['recent_signal_dates_max']}`",
        "",
        "## Recent results",
        "",
        "Net, gross and cost values are arithmetic annualized percentages over the recent signal dates.",
        "",
        "| name | handler | cycle | recent periods | platform net full window | recent local net | recent gross | annual cost | turnover | RankIC |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        def value(name: str, digits: int = 2) -> str:
            item = row.get(name)
            return "n/a" if item is None else f"{float(item):.{digits}f}%"

        rank_ic = row.get("recent_rank_ic")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["name"]),
                    str(row["handler"]),
                    str(row["cycle"]),
                    str(row["recent_periods"]),
                    value("platform_net_excess_pct"),
                    value("recent_net_excess_pct"),
                    value("recent_gross_excess_pct"),
                    value("recent_annual_cost_pct"),
                    value("recent_turnover_pct"),
                    "n/a" if rank_ic is None else f"{float(rank_ic):.4f}",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Not locally reproduced",
            "",
            "| name | handler | cycle | platform net full window | reason |",
            "|---|---|---:|---:|---|",
        ]
    )
    for row in unsupported:
        platform_net = row.get("platform_net_excess_pct")
        platform_text = "n/a" if platform_net is None else f"{float(platform_net):.2f}%"
        lines.append(
            f"| {row['name']} | {row.get('handler') or 'n/a'} | {row.get('cycle') or 'n/a'} | {platform_text} | {row.get('reason', 'n/a')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- The recent window is short and regime-sensitive; it is not a standalone factor acceptance test.",
            "- Local values follow the canonical qfq/full-A/total_mv/label-1 contract. Proxy and alignment status remain attached to the original five-year catalog.",
            "- A positive recent local net excess does not override a large five-year local/platform mismatch.",
        ]
    )
    paths["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recent-start", default=DEFAULT_RECENT_START.strftime("%Y%m%d"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    args = parser.parse_args()

    recent_start = pd.Timestamp(
        pd.to_datetime(args.recent_start, format="%Y%m%d" if len(args.recent_start) == 8 else None)
    ).normalize()
    if recent_start < DATA_START or recent_start > END:
        raise SystemExit(f"--recent-start must be between {DATA_START.date()} and {END.date()}")

    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)
    paths = output_paths(args.output)
    refuse_overwrite(paths)

    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    catalog = formula_catalog()
    supported, unsupported = saved_records(catalog, "positive")
    platform_positive_count = len(supported) + len(unsupported)
    print(
        f"platform_positive_records={platform_positive_count} "
        f"supported={len(supported)} unsupported={len(unsupported)}",
        flush=True,
    )

    frame = load_full_a_data(args.price_root, args.cap_root, DATA_START, END)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    close = panel_close(frame, calendar)
    print(f"local_rows={len(frame)}", flush=True)

    financial: dict[str, pd.DataFrame] | None = None
    if any(record.get("handler") in FINANCIAL_HANDLERS for record in supported):
        financial = load_financial_cache(args.financial_root)
        print("financial_cache=loaded", flush=True)

    prepared: list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int]] = []
    for record in supported:
        raw_result = record.get("raw_result")
        if not raw_result or not (PROJECT_ROOT / str(raw_result)).is_file():
            record["reason"] = f"saved platform result is missing: {raw_result}"
            unsupported.append(record)
            continue
        platform = read_platform_run(PROJECT_ROOT / str(raw_result))
        full_dates = [pd.Timestamp(value).normalize() for value in platform.get("dates", [])]
        try:
            cycle = int(record.get("configured_cycle") or infer_cycle(calendar, full_dates))
        except (TypeError, ValueError, RuntimeError) as exc:
            record["reason"] = f"cannot determine rebalance cycle: {exc}"
            unsupported.append(record)
            continue
        recent_dates = usable_recent_dates(full_dates, calendar, cycle, recent_start)
        if not recent_dates:
            record["reason"] = "no usable signal dates in the recent window"
            record["cycle"] = cycle
            unsupported.append(record)
            continue
        prepared.append((record, platform, recent_dates, cycle))

    by_handler: dict[str, list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int]]] = {}
    for item in prepared:
        by_handler.setdefault(str(item[0]["handler"]), []).append(item)

    rows: list[dict[str, Any]] = []
    for handler, items in by_handler.items():
        handler_dates = sorted({date for _, _, dates, _ in items for date in dates})
        print(f"building={handler} records={len(items)}", flush=True)
        values = build_factor(
            frame,
            handler,
            financial=financial,
            signal_dates=handler_dates,
        )
        for record, platform, signal_dates, cycle in items:
            result = evaluate(
                frame,
                values,
                close,
                platform,
                int(record["direction"]),
                signal_dates,
                calendar,
                cycle,
                ALIGNMENT_LABEL_OFFSET,
                handler,
            )
            rows.append(
                {
                    "id": record["id"],
                    "name": record["name"],
                    "report": record["report"],
                    "formula": record.get("formula"),
                    "handler": handler,
                    "direction": int(record["direction"]),
                    "cycle": cycle,
                    "platform_net_excess_pct": record["platform_net_excess_pct"],
                    "platform_periods_full_window": len(platform.get("dates", [])),
                    "recent_start": signal_dates[0],
                    "recent_end": signal_dates[-1],
                    "recent_periods": result["periods"],
                    "recent_stock_count_mean": result["stock_count_mean"],
                    "recent_rank_ic": result["rank_ic"],
                    "recent_ic_mean": result["ic_mean"],
                    "recent_gross_excess_pct": pct(result["gross_excess"]),
                    "recent_turnover_pct": pct(result["turnover"]),
                    "recent_annual_cost_pct": pct(result["annual_cost"]),
                    "recent_net_excess_pct": pct(result["net_excess"]),
                    "fidelity": record.get("fidelity"),
                }
            )
        del values

    for record in unsupported:
        record.setdefault("cycle", record.get("configured_cycle"))
        record.setdefault("platform_net_excess_pct", record.get("platform_net_excess_pct"))

    rows.sort(key=lambda row: (row["recent_net_excess_pct"] is None, -(row["recent_net_excess_pct"] or 0.0)))
    recent_dates = [row["recent_start"] for row in rows] + [row["recent_end"] for row in rows]
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment_config": alignment_config,
        "universe": "full_a",
        "price_mode": "qfq",
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START,
        "end": END,
        "recent_start": recent_start,
        "recent_signal_dates_min": min(recent_dates) if recent_dates else None,
        "recent_signal_dates_max": max(recent_dates) if recent_dates else None,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "label_offset": ALIGNMENT_LABEL_OFFSET,
        "platform_positive_records": platform_positive_count,
        "locally_reproduced_records": len(rows),
        "unsupported_records": len(unsupported),
        "cycle_counts": dict(Counter(row["cycle"] for row in rows)),
        "five_year_reference": str(
            PROJECT_ROOT
            / "quantlab/.quantlab/cache/research/cn_equity/reports"
            / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
            / "all_factor_local_compare.json"
        ),
    }
    write_outputs(paths, settings, rows, unsupported)
    print(f"report={paths['md']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
