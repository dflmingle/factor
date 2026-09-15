#!/usr/bin/env python3
"""Compare the saved AlphaPROBE factor with saved positive-net factors.

This is an offline calculation. It uses the aligned local Tushare cache and
does not contact PandaAI or start a backtest. The primary statistic is the
arithmetic mean of daily cross-sectional Spearman correlations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_CORRELATION_DESCRIPTION,
    ALIGNMENT_CORRELATION_METHOD,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE_LABEL,
)
from positive_factor_local_compare import build_factor  # noqa: E402
from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


TARGET_NAME = "F-NET01"
TARGET_FORMULA = "WMA((((1/LOW)/LOW)/VOLUME),40)"
TARGET_HANDLER = "wma_low_volume40"

DEFAULT_RECORDS = (
    CACHE_ROOT
    / "reports"
    / "positive_factor_compare_full_a_label1_cfpfix2"
    / "positive_factor_local_compare.json"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "target-vs-positive-factor-correlation-20260915"
)


def parse_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    return pd.Timestamp(
        pd.to_datetime(text, format="%Y%m%d" if len(text) == 8 else None)
    ).normalize()


def finite_pair(frame: pd.DataFrame, left: pd.Series, right: pd.Series) -> pd.DataFrame:
    left_values = pd.to_numeric(left, errors="coerce")
    right_values = pd.to_numeric(right, errors="coerce")
    mask = (
        left_values.notna()
        & right_values.notna()
        & np.isfinite(left_values.to_numpy())
        & np.isfinite(right_values.to_numpy())
    )
    return pd.DataFrame(
        {
            "date": frame.loc[mask, "date"].to_numpy(),
            "target": left_values.loc[mask].to_numpy(dtype=float),
            "factor": right_values.loc[mask].to_numpy(dtype=float),
        }
    )


def daily_spearman(
    frame: pd.DataFrame,
    target_values: pd.Series,
    factor_values: pd.Series,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Calculate per-date Spearman correlation on the pairwise valid set."""
    paired = finite_pair(frame, target_values, factor_values)
    if paired.empty:
        empty = pd.DataFrame(columns=["date", "common_stocks", "spearman"])
        return {
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "days": 0,
            "pair_rows": 0,
            "common_stocks_mean": None,
            "common_stocks_min": None,
            "common_stocks_max": None,
        }, empty

    dates = paired["date"]
    grouped = paired.groupby("date", sort=True, observed=True)
    target_rank = grouped["target"].rank(method="average")
    factor_rank = grouped["factor"].rank(method="average")
    target_centered = target_rank - target_rank.groupby(dates, sort=False).transform("mean")
    factor_centered = factor_rank - factor_rank.groupby(dates, sort=False).transform("mean")
    numerator = (target_centered * factor_centered).groupby(dates, sort=True).sum()
    target_ss = (target_centered * target_centered).groupby(dates, sort=True).sum()
    factor_ss = (factor_centered * factor_centered).groupby(dates, sort=True).sum()
    denominator = (target_ss * factor_ss).pow(0.5)
    values = numerator.div(denominator.replace(0.0, np.nan))
    counts = grouped.size().rename("common_stocks")
    daily = pd.concat([counts, values.rename("spearman")], axis=1).reset_index()
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    valid = pd.to_numeric(daily["spearman"], errors="coerce").dropna()
    count_values = daily["common_stocks"].to_numpy(dtype=float)
    summary = {
        "mean": float(valid.mean()) if not valid.empty else None,
        "median": float(valid.median()) if not valid.empty else None,
        "std": float(valid.std(ddof=1)) if len(valid) > 1 else (0.0 if len(valid) else None),
        "min": float(valid.min()) if not valid.empty else None,
        "max": float(valid.max()) if not valid.empty else None,
        "days": int(len(valid)),
        "pair_rows": int(len(paired)),
        "common_stocks_mean": float(np.mean(count_values)) if len(count_values) else None,
        "common_stocks_min": int(np.min(count_values)) if len(count_values) else None,
        "common_stocks_max": int(np.max(count_values)) if len(count_values) else None,
    }
    return summary, daily


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("results", [])
    if not isinstance(records, list):
        raise ValueError(f"Expected a results list in {path}")
    valid: list[dict[str, Any]] = []
    for record in records:
        if not record.get("formula") or not record.get("handler"):
            raise ValueError(f"Record is missing formula or handler: {record.get('id')}")
        valid.append(record)
    return valid


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


def write_outputs(
    *,
    target: dict[str, str],
    output_prefix: Path,
    records: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    daily_rows: list[pd.DataFrame],
    frame: pd.DataFrame,
    data_start: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
    source_records: Path,
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    daily = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    daily_path = output_prefix.with_suffix(".daily.csv")
    summary_path = output_prefix.with_suffix(".summary.csv")
    pd.DataFrame(rows).to_csv(summary_path, index=False, encoding="utf-8-sig")
    daily.to_csv(daily_path, index=False, encoding="utf-8-sig")

    unique_handlers = sorted({str(record["handler"]) for record in records})
    result = {
        "target": target,
        "source": {
            "positive_records": str(source_records),
            "record_count": len(records),
            "unique_handler_count": len(unique_handlers),
        },
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "universe": ALIGNMENT_UNIVERSE_LABEL,
            "price_mode": ALIGNMENT_PRICE_MODE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "data_start": data_start,
            "comparison_start": start,
            "comparison_end": end,
            "correlation_method": ALIGNMENT_CORRELATION_METHOD,
            "correlation_description": ALIGNMENT_CORRELATION_DESCRIPTION,
            "frame_rows": len(frame),
            "frame_instruments": int(frame["instrument"].nunique()),
            "frame_date_min": frame["date"].min(),
            "frame_date_max": frame["date"].max(),
            "market_field_sources": frame.attrs.get("market_field_sources", {}),
        },
        "results": rows,
        "artifacts": {
            "summary_csv": str(summary_path),
            "daily_csv": str(daily_path),
            "json": str(output_prefix.with_suffix(".json")),
            "markdown": str(output_prefix.with_suffix(".md")),
        },
    }
    output_prefix.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    ranked = sorted(rows, key=lambda row: abs(float(row["correlation"])), reverse=True)
    closest = sorted(rows, key=lambda row: abs(float(row["correlation"])))

    def fmt(value: Any, digits: int = 6) -> str:
        return "n/a" if value is None else f"{float(value):.{digits}f}"

    lines = [
        "# Yesterday's factor vs positive-net factors",
        "",
        "This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.",
        "",
        "## Fixed inputs",
        "",
        f"- Target: `{target['formula']}` (`{target['name']}`, handler `{target['handler']}`).",
        f"- Existing set: `{len(records)}` saved completed factors with platform net excess greater than zero; `{len(unique_handlers)}` unique local handlers.",
        f"- Window: `{start:%Y-%m-%d}..{end:%Y-%m-%d}`; warm-up starts `{data_start:%Y-%m-%d}`.",
        f"- Universe: `{ALIGNMENT_UNIVERSE_LABEL}`; prices `{ALIGNMENT_PRICE_MODE}`; market cap `{ALIGNMENT_MARKET_CAP_FIELD}`.",
        f"- Correlation: `{ALIGNMENT_CORRELATION_METHOD}`; {ALIGNMENT_CORRELATION_DESCRIPTION}.",
        "- Pairwise valid stocks are intersected separately on every date. Platform direction, forward returns, rebalance cycle, grouping, turnover, and transaction cost do not enter this statistic.",
        "",
        "## Highest absolute correlations",
        "",
        "| Rank | Factor | Handler | Platform net | Correlation | Abs correlation | Days | Mean stocks |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(ranked[:15], start=1):
        lines.append(
            f"| {index} | {row['name']} | `{row['handler']}` | {row['platform_net_excess_pct']:.2f}% | {row['correlation']:+.6f} | {abs(row['correlation']):.6f} | {row['days']} | {row['common_stocks_mean']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Closest to independent",
            "",
            "| Rank | Factor | Handler | Correlation | Abs correlation | Days | Mean stocks |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    for index, row in enumerate(closest[:10], start=1):
        lines.append(
            f"| {index} | {row['name']} | `{row['handler']}` | {row['correlation']:+.6f} | {abs(row['correlation']):.6f} | {row['days']} | {row['common_stocks_mean']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Complete result",
            "",
            "The complete 64-row table is in the JSON and summary CSV artifacts. The daily CSV keeps the date-level values used in each arithmetic mean.",
            "",
            f"- Local rows loaded: `{len(frame):,}`; instruments: `{frame['instrument'].nunique():,}`.",
            f"- Daily detail rows: `{len(daily):,}`.",
            f"- JSON: `{output_prefix.with_suffix('.json')}`.",
            f"- Summary CSV: `{summary_path}`.",
            f"- Daily CSV: `{daily_path}`.",
        ]
    )
    output_prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=str(DEFAULT_RECORDS))
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--start", default=ALIGNMENT_START)
    parser.add_argument("--end", default=ALIGNMENT_END)
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--financial-root", default=str(DEFAULT_FINANCIAL_ROOT))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT_PREFIX))
    parser.add_argument("--target-name", default=TARGET_NAME)
    parser.add_argument("--target-formula", default=TARGET_FORMULA)
    parser.add_argument("--target-handler", default=TARGET_HANDLER)
    args = parser.parse_args()

    data_start = parse_date(args.data_start)
    start = parse_date(args.start)
    end = parse_date(args.end)
    if data_start > start or start > end:
        raise SystemExit("dates must satisfy data-start <= start <= end")

    records = load_records(Path(args.records))
    print(f"positive_records={len(records)} unique_handlers={len({r['handler'] for r in records})}", flush=True)
    print("loading local full-A data...", flush=True)
    frame = load_full_a_data(Path(args.price_root), Path(args.cap_root), data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(data_start, end, token=None)
    ]
    comparison_dates = [date for date in calendar if start <= date <= end]
    if not comparison_dates:
        raise SystemExit("no comparison dates in the cached trade calendar")
    print(
        f"frame_rows={len(frame)} instruments={frame['instrument'].nunique()} "
        f"comparison_dates={len(comparison_dates)}",
        flush=True,
    )
    comparison_frame = frame[frame["date"].between(start, end)].copy()

    financial_handlers = {
        str(record["handler"])
        for record in records
        if str(record["handler"]) in FINANCIAL_HANDLERS
    }
    financial: dict[str, pd.DataFrame] | None = None
    if financial_handlers:
        print(f"loading financial cache for {len(financial_handlers)} handlers...", flush=True)
        financial = load_financial_cache(Path(args.financial_root))

    target = {
        "name": str(args.target_name),
        "formula": str(args.target_formula),
        "handler": str(args.target_handler),
    }
    print(f"building target {target['handler']}...", flush=True)
    target_values = build_factor(frame, target["handler"])
    rows: list[dict[str, Any]] = []
    daily_rows: list[pd.DataFrame] = []
    factor_cache: dict[str, pd.Series] = {}
    for index, record in enumerate(records, start=1):
        handler = str(record["handler"])
        if handler not in factor_cache:
            print(f"building handler={handler} ({index}/{len(records)})...", flush=True)
            factor_cache[handler] = build_factor(
                frame,
                handler,
                financial=financial,
                signal_dates=comparison_dates,
            )
        summary, daily = daily_spearman(
            comparison_frame,
            target_values.reindex(comparison_frame.index),
            factor_cache[handler].reindex(comparison_frame.index),
        )
        correlation = summary["mean"]
        if correlation is None:
            raise RuntimeError(f"No valid daily correlation for {record['id']}")
        row = {
            "id": record.get("id"),
            "name": record.get("name"),
            "report": record.get("report"),
            "formula": record.get("formula"),
            "handler": handler,
            "platform_factor_id": record.get("platform_factor_id"),
            "platform_run_id": record.get("platform_run_id"),
            "platform_net_excess_pct": float(record["platform_net_excess_pct"]),
            "platform_direction": record.get("platform_factor_direction"),
            "configured_cycle": record.get("configured_cycle"),
            "correlation": float(correlation),
            "abs_correlation": abs(float(correlation)),
            **summary,
        }
        rows.append(row)
        daily.insert(0, "factor_id", record.get("id"))
        daily.insert(1, "handler", handler)
        daily_rows.append(daily)
        print(
            f"done={record['name']} correlation={correlation:+.6f} "
            f"days={summary['days']} pairs={summary['pair_rows']}",
            flush=True,
        )

    rows.sort(key=lambda row: float(row["abs_correlation"]), reverse=True)
    write_outputs(
        target=target,
        output_prefix=Path(args.output_prefix),
        records=records,
        rows=rows,
        daily_rows=daily_rows,
        frame=frame,
        data_start=data_start,
        start=start,
        end=end,
        source_records=Path(args.records),
    )
    print(f"report={Path(args.output_prefix).with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
