#!/usr/bin/env python3
"""Diagnose the invalid level-0 Python implementation locally.

This intentionally reproduces the earlier bug: with PandaAI's [date, symbol]
MultiIndex, groupby(level=0) applies a 60-row rolling quantile within the
same date, in symbol order. It is a diagnostic proxy, not a QTLD60 result.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from machine_profile import resolve_machine_profile  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import evaluate, panel_close  # noqa: E402
from qtld60_local_reproduction import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_START,
    CYCLE,
    DIRECTION,
    GROUPS,
    load_calendar,
    load_minimal_full_a,
    memory_guard,
    reference_signal_dates,
    usable_dates,
    extend_signal_dates,
)


WINDOW = 60
QUANTILE = 0.2
DEFAULT_PLATFORM_RESULT = (
    PROJECT_ROOT
    / "qtld60-platform-python-20260919-candidates.results"
    / "6aae8c145d52c44d2f55d25c.json"
)
DEFAULT_SIGNAL_REFERENCE = (
    PROJECT_ROOT
    / "h03-t10-single-20260911-candidates.results"
    / "6aa36bd3ecb163ea7228cffe.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / ".tushare-refresh-20260918-v2"
    / "reports"
    / "qtld60_wrong_index_diagnostic_20260919"
)


def wrong_index_factor(frame: pd.DataFrame) -> pd.Series:
    """Reproduce groupby(level=0) on a [date, symbol] runtime index."""
    ordered = frame.assign(_symbol=frame["instrument"].astype(str)).sort_values(
        ["date", "_symbol"], kind="stable"
    )
    grouped = ordered.groupby("date", sort=False, observed=True)["close_qfq"]
    quantile = grouped.rolling(
        window=WINDOW,
        min_periods=WINDOW,
    ).quantile(QUANTILE)
    quantile = quantile.reset_index(level=0, drop=True).reindex(ordered.index)
    values = quantile.div(ordered["close_qfq"])
    return values.reindex(frame.index)


def spearman_by_date(
    frame: pd.DataFrame,
    values: pd.Series,
    dates: list[pd.Timestamp],
) -> float | None:
    data = frame[["date", "close_qfq"]].copy()
    data["factor"] = values.to_numpy(dtype=float)
    data = data[data["date"].isin(dates)].replace([np.inf, -np.inf], np.nan).dropna()
    correlations: list[float] = []
    for _, current in data.groupby("date", sort=True):
        if len(current) < 3:
            continue
        corr = current["factor"].rank(method="average").corr(
            (-current["close_qfq"]).rank(method="average")
        )
        if pd.notna(corr):
            correlations.append(float(corr))
    return float(np.mean(correlations)) if correlations else None


def latest_price_diagnostic(
    frame: pd.DataFrame,
    values: pd.Series,
    latest_date: pd.Timestamp,
) -> dict[str, Any]:
    current = frame[["date", "instrument", "close_qfq"]].copy()
    current["factor"] = values.to_numpy(dtype=float)
    current = current[current["date"].eq(latest_date)].dropna()
    current = current.sort_values(["factor", "instrument"], ascending=[False, True])
    prices = current["close_qfq"]
    top = current.head(20)
    return {
        "date": latest_date,
        "valid_rows": int(len(current)),
        "price_q20": float(prices.quantile(0.2)) if len(prices) else None,
        "price_median": float(prices.median()) if len(prices) else None,
        "price_under_10_pct": float((prices < 10).mean() * 100.0) if len(prices) else None,
        "top20": [
            {
                "instrument": str(row.instrument),
                "factor": float(row.factor),
                "close_qfq": float(row.close_qfq),
            }
            for row in top.itertuples(index=False)
        ],
    }


def pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value * 100.0 if np.isfinite(value) else None


def metric_row(name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "window": name,
        "periods": result.get("periods"),
        "stock_count_mean": result.get("stock_count_mean"),
        "rank_ic": result.get("rank_ic"),
        "ic_mean": result.get("ic_mean"),
        "gross_excess_pct": pct(result.get("gross_excess")),
        "turnover_pct": pct(result.get("turnover")),
        "annual_cost_pct": pct(result.get("annual_cost")),
        "net_excess_pct": pct(result.get("net_excess")),
    }


def write_outputs(
    output: Path,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "diagnostic.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    fields = list(rows[0]) if rows else []
    with (output / "diagnostic.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# QTLD60 Wrong-Index Local Diagnostic",
        "",
        f"Machine: `{payload['machine_profile']}` ({payload['machine_label']}).",
        "",
        "This is an invalid implementation diagnostic, not a formal QTLD60 reproduction.",
        "The calculation uses the PandaAI Python runtime's observed [date, symbol] index and",
        "deliberately applies the 60-row rolling quantile within each date in symbol order.",
        "",
        "| window | periods | mean stocks | RankIC | IC | gross excess | turnover | annual cost | net excess |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        def show(key: str, digits: int = 2) -> str:
            value = row.get(key)
            return "n/a" if value is None else f"{float(value):.{digits}f}%"

        lines.append(
            f"| {row['window']} | {row['periods']} | {row['stock_count_mean']:.1f} | "
            f"{row['rank_ic']:.4f} | {row['ic_mean']:.4f} | {show('gross_excess_pct')} | "
            f"{show('turnover_pct')} | {show('annual_cost_pct')} | {show('net_excess_pct')} |"
        )
    latest = payload["latest_price_diagnostic"]
    lines.extend(
        [
            "",
            "## Latest cross-section",
            "",
            f"- date: `{latest['date']}`; valid rows: `{latest['valid_rows']}`",
            f"- q20 close: `{latest['price_q20']:.2f}`; median close: `{latest['price_median']:.2f}`",
            f"- close < 10: `{latest['price_under_10_pct']:.2f}%`",
            f"- mean daily Spearman(wrong factor, -close): `{payload['mean_daily_spearman_inverse_close']}`",
            "",
            "The current Top20 is retained in diagnostic.json. A strong inverse-price relation would",
            "mean that the invalid implementation is mainly selecting low nominal-price stocks,",
            "possibly mixed with board, size, or symbol-order exposure.",
            "",
        ]
    )
    (output / "diagnostic.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--price-root", type=Path, required=True)
    parser.add_argument("--cap-root", type=Path, required=True)
    parser.add_argument("--calendar-root", type=Path, required=True)
    parser.add_argument("--platform-result", type=Path, default=DEFAULT_PLATFORM_RESULT)
    parser.add_argument(
        "--signal-reference",
        type=Path,
        default=DEFAULT_SIGNAL_REFERENCE,
        help="saved result whose chart dates provide the 10-day signal-date template",
    )
    parser.add_argument("--data-end", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=2.60)
    parser.add_argument("--min-available-gb", type=float, default=1.50)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {args.output}")

    platform = read_platform_run(args.platform_result)
    reference_dates = reference_signal_dates(args.signal_reference)
    machine = resolve_machine_profile()
    data_end = (
        pd.Timestamp(pd.to_datetime(args.data_end, format="%Y%m%d"))
        if args.data_end
        else pd.Timestamp("2026-09-07")
    ).normalize()

    memory_guard("start", args.max_rss_gb, args.min_available_gb)
    frame = load_minimal_full_a(
        args.price_root,
        args.cap_root,
        pd.Timestamp(ALIGNMENT_DATA_START),
        data_end,
        max_rss_gb=args.max_rss_gb,
        min_available_gb=args.min_available_gb,
    )
    calendar = load_calendar(args.calendar_root, pd.Timestamp(ALIGNMENT_DATA_START), data_end)
    factor_values = wrong_index_factor(frame).replace([np.inf, -np.inf], np.nan)
    memory_guard("after_factor", args.max_rss_gb, args.min_available_gb)
    close = panel_close(frame, calendar)
    memory_guard("after_close_panel", args.max_rss_gb, args.min_available_gb)

    formal_dates = usable_dates(reference_dates, calendar, pd.Timestamp(ALIGNMENT_START), pd.Timestamp(ALIGNMENT_END))
    extended_dates = extend_signal_dates(reference_dates, calendar, data_end)
    recent_dates = usable_dates(extended_dates, calendar, pd.Timestamp("2026-01-01"), data_end)
    formal = evaluate(frame, factor_values, close, platform, DIRECTION, formal_dates, calendar, CYCLE, ALIGNMENT_LABEL_OFFSET)
    memory_guard("after_formal", args.max_rss_gb, args.min_available_gb)
    recent = evaluate(frame, factor_values, close, platform, DIRECTION, recent_dates, calendar, CYCLE, ALIGNMENT_LABEL_OFFSET)
    memory_guard("after_recent", args.max_rss_gb, args.min_available_gb)

    rows = [metric_row("formal_5y", formal), metric_row("recent_diagnostic", recent)]
    latest = latest_price_diagnostic(frame, factor_values, pd.Timestamp(frame["date"].max()).normalize())
    payload = {
        "machine_profile": machine["machine_profile"],
        "machine_label": machine["machine_label"],
        "formula": "rolling 20th percentile of close over 60 rows within each date / current close",
        "status": "diagnostic_only_invalid_qtld60_implementation",
        "platform_result": str(args.platform_result),
        "signal_reference": str(args.signal_reference),
        "alignment_rule_version": "full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1",
        "signal_periods": {"formal": len(formal_dates), "recent": len(recent_dates)},
        "results": rows,
        "platform_reference": {
            "rank_ic": platform.get("metrics", {}).get("Rank_IC"),
            "ic_mean": platform.get("metrics", {}).get("IC_mean"),
            "monotonicity": platform.get("metrics", {}).get("monotonicity"),
            "long_excess_pct": platform.get("group_metrics", {}).get(10, {}).get("excessAnnualized"),
            "turnover_pct": platform.get("group_metrics", {}).get(10, {}).get("turnoverRate"),
        },
        "mean_daily_spearman_inverse_close": spearman_by_date(frame, factor_values, formal_dates),
        "latest_price_diagnostic": latest,
    }
    write_outputs(args.output, payload, rows)
    print(f"formal_rank_ic={formal.get('rank_ic')} formal_net_excess={formal.get('net_excess')}", flush=True)
    print(f"output={args.output / 'diagnostic.md'}", flush=True)
    del close, frame, factor_values
    gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
