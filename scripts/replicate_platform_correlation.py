#!/usr/bin/env python3
"""Reproduce one saved PandaAI factor-correlation workflow locally.

This is an offline diagnostic. It reads the cached Tushare full-A data and the
existing local factor handlers; it never contacts PandaAI or spends credits.
The primary statistic follows the bundled PandaAI workflow convention: compute
the cross-sectional Spearman correlation for each date, then average those
daily correlations.
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

from financial_factor_local import build_market_factor  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_CORRELATION_DESCRIPTION,
    ALIGNMENT_CORRELATION_METHOD,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE_LABEL,
)
from positive_factor_local_compare import build_factor  # noqa: E402
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


PLATFORM_WORKFLOW_ID = "6aa371b551cdfe29b2e0bc34"
PLATFORM_RUN_ID = "6aa371b5ecb163ea7228d004"
PLATFORM_CORRELATION_TASK_ID = "3e07308fd6664f1096e128d2bc6b70c3"
PLATFORM_CORRELATION = 0.4151352929

T10_FORMULA = (
    "(RANK(1-RETURNS(CLOSE,40)) + "
    "RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + "
    "RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + "
    "RANK(-ZSCORE(RANK(MARKET_CAP)))) / 4"
)
H03_FORMULA = "RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))"

DEFAULT_DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
DEFAULT_START = pd.Timestamp(ALIGNMENT_START)
DEFAULT_END = pd.Timestamp(ALIGNMENT_END)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_OUTPUT_PREFIX = PROJECT_ROOT / "corr-t10-size-vs-h03-local-reproduction-20260914"


def parse_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    return pd.Timestamp(
        pd.to_datetime(text, format="%Y%m%d" if len(text) == 8 else None)
    ).normalize()


def finite_joined(left: pd.Series, right: pd.Series) -> pd.DataFrame:
    joined = pd.concat(
        [pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")],
        axis=1,
    )
    joined.columns = ["t10_size", "h03"]
    return joined.replace([np.inf, -np.inf], np.nan).dropna()


def correlation(left: pd.Series, right: pd.Series, method: str) -> float | None:
    joined = finite_joined(left, right)
    if len(joined) < 2:
        return None
    value = joined["t10_size"].corr(joined["h03"], method=method)
    return None if pd.isna(value) else float(value)


def daily_correlations(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date, current in data.groupby("date", sort=True, observed=True):
        if len(current) < 2:
            continue
        rows.append(
            {
                "date": pd.Timestamp(date),
                "stock_count": int(len(current)),
                "pearson": correlation(current["t10_size"], current["h03"], "pearson"),
                "spearman": correlation(current["t10_size"], current["h03"], "spearman"),
            }
        )
    return pd.DataFrame(rows)


def aggregate_daily(daily: pd.DataFrame, column: str) -> dict[str, Any]:
    values = pd.to_numeric(daily[column], errors="coerce").dropna()
    if values.empty:
        return {"mean": None, "median": None, "std": None, "weighted_mean": None, "days": 0}
    weights = daily.loc[values.index, "stock_count"].to_numpy(dtype=float)
    return {
        "mean": float(values.mean()),
        "median": float(values.median()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
        "weighted_mean": float(np.average(values.to_numpy(dtype=float), weights=weights)),
        "days": int(len(values)),
    }


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


def build_report(
    *,
    frame: pd.DataFrame,
    data: pd.DataFrame,
    daily: pd.DataFrame,
    data_start: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
    calendar_dates: list[pd.Timestamp],
    output_prefix: Path,
) -> dict[str, Any]:
    daily_pearson = aggregate_daily(daily, "pearson")
    daily_spearman = aggregate_daily(daily, "spearman")
    pooled_pearson = correlation(data["t10_size"], data["h03"], "pearson")
    pooled_spearman = correlation(data["t10_size"], data["h03"], "spearman")

    methods = [
        ("daily_cross_sectional_spearman_mean", daily_spearman["mean"]),
        ("daily_cross_sectional_pearson_mean", daily_pearson["mean"]),
        ("pooled_spearman", pooled_spearman),
        ("pooled_pearson", pooled_pearson),
    ]
    available = [(name, value) for name, value in methods if value is not None]
    closest_name, closest_value = min(
        available,
        key=lambda item: abs(float(item[1]) - PLATFORM_CORRELATION),
    )

    local_dates = sorted(pd.to_datetime(data["date"]).dt.normalize().unique())
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "universe": ALIGNMENT_UNIVERSE_LABEL,
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": data_start,
        "comparison_start": start,
        "comparison_end": end,
        "calendar_dates_requested": len(calendar_dates),
        "frame_rows": len(frame),
        "frame_instruments": int(frame["instrument"].nunique()),
        "frame_date_min": frame["date"].min(),
        "frame_date_max": frame["date"].max(),
        "valid_rows": len(data),
        "valid_dates": len(local_dates),
        "valid_stock_count_mean": float(data.groupby("date", observed=True).size().mean()),
        "market_field_sources": frame.attrs.get("market_field_sources", {}),
    }
    result = {
        "platform": {
            "workflow_id": PLATFORM_WORKFLOW_ID,
            "run_id": PLATFORM_RUN_ID,
            "correlation_task_id": PLATFORM_CORRELATION_TASK_ID,
            "method": "FactorCorrelationCalculationControl",
            "value": PLATFORM_CORRELATION,
            "window": f"{start:%Y-%m-%d}..{end:%Y-%m-%d}",
        },
        "inputs": {
            "t10_size": T10_FORMULA,
            "h03": H03_FORMULA,
        },
        "settings": settings,
        "local": {
            "method": ALIGNMENT_CORRELATION_METHOD,
            "method_description": ALIGNMENT_CORRELATION_DESCRIPTION,
            "daily_cross_sectional_spearman": daily_spearman,
            "daily_cross_sectional_pearson": daily_pearson,
            "pooled_spearman": pooled_spearman,
            "pooled_pearson": pooled_pearson,
            "closest_to_platform": {
                "method": closest_name,
                "value": closest_value,
                "delta": float(closest_value - PLATFORM_CORRELATION),
            },
        },
        "artifacts": {
            "daily_csv": str(output_prefix.with_suffix(".daily.csv")),
        },
    }

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(output_prefix.with_suffix(".daily.csv"), index=False, encoding="utf-8-sig")
    output_prefix.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    def number(value: float | None, digits: int = 6) -> str:
        return "n/a" if value is None else f"{float(value):.{digits}f}"

    lines = [
        "# Local reproduction of PandaAI factor correlation",
        "",
        "This is an offline reproduction using cached Tushare data. It does not contact PandaAI or spend compute credits.",
        "",
        "## Platform reference",
        "",
        f"- Workflow: `{PLATFORM_WORKFLOW_ID}`; run: `{PLATFORM_RUN_ID}`; correlation task: `{PLATFORM_CORRELATION_TASK_ID}`.",
        "- Node: `FactorCorrelationCalculationControl`.",
        f"- Window: `{start:%Y-%m-%d}..{end:%Y-%m-%d}`.",
        f"- Saved platform correlation: `{PLATFORM_CORRELATION:.10f}`.",
        "",
        "## Inputs",
        "",
        "### T10-SIZE",
        "",
        f"```text\n{T10_FORMULA}\n```",
        "",
        "### H03-T10-SINGLE",
        "",
        f"```text\n{H03_FORMULA}\n```",
        "",
        "## Local calculation",
        "",
        f"The fixed method is `{ALIGNMENT_CORRELATION_METHOD}`: intersect valid T10-SIZE and H03 values on each date, compute the cross-sectional Spearman correlation across stocks, and take the arithmetic mean across dates. Pandas average ranks are used for Spearman ties.",
        "",
        "| Calculation | Local value | Delta vs platform | Daily observations |",
        "|---|---:|---:|---:|",
        f"| Daily cross-sectional Spearman mean | {number(daily_spearman['mean'])} | {number(daily_spearman['mean'] - PLATFORM_CORRELATION)} | {daily_spearman['days']} |",
        f"| Daily cross-sectional Pearson mean | {number(daily_pearson['mean'])} | {number(daily_pearson['mean'] - PLATFORM_CORRELATION)} | {daily_pearson['days']} |",
        f"| Pooled Spearman over all stock-day rows | {number(pooled_spearman)} | {number(pooled_spearman - PLATFORM_CORRELATION)} | {len(data)} rows |",
        f"| Pooled Pearson over all stock-day rows | {number(pooled_pearson)} | {number(pooled_pearson - PLATFORM_CORRELATION)} | {len(data)} rows |",
        "",
        f"The closest local result is `{closest_name}` at `{float(closest_value):.10f}`, with a signed difference of `{float(closest_value - PLATFORM_CORRELATION):+.10f}`.",
        "",
        "## Data and fidelity",
        "",
        f"- Universe: `{ALIGNMENT_UNIVERSE_LABEL}`; qfq prices; `daily_basic.total_mv`; local warm-up starts `{data_start:%Y-%m-%d}`.",
        f"- Loaded `{len(frame):,}` rows for `{frame['instrument'].nunique():,}` instruments; valid pair rows: `{len(data):,}` across `{len(local_dates):,}` dates.",
        f"- Mean valid stocks per date: `{settings['valid_stock_count_mean']:.2f}`.",
        f"- Market-field sources recorded by the loader: `{settings['market_field_sources']}`.",
        "- Correlation does not use the forward-return label, rebalance cycle, grouping, turnover, or transaction cost.",
        "- A close match identifies the most likely aggregation method; it does not establish byte-level equivalence of PandaAI's internal data and missing-row handling.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "python scripts/replicate_platform_correlation.py",
        "```",
        "",
        f"Artifacts: `{output_prefix.with_suffix('.json')}`, `{output_prefix.with_suffix('.daily.csv')}`.",
    ]
    output_prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-start", default=DEFAULT_DATA_START.strftime("%Y%m%d"))
    parser.add_argument("--start", default=DEFAULT_START.strftime("%Y%m%d"))
    parser.add_argument("--end", default=DEFAULT_END.strftime("%Y%m%d"))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT_PREFIX))
    args = parser.parse_args()

    data_start = parse_date(args.data_start)
    start = parse_date(args.start)
    end = parse_date(args.end)
    if data_start > start:
        raise SystemExit("--data-start must be no later than --start")
    if start > end:
        raise SystemExit("--start must be no later than --end")

    print("loading local full-A data...", flush=True)
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        data_start,
        end,
    )
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

    print("building T10-SIZE...", flush=True)
    t10_values = build_factor(frame, "reversal_chip_turn_size_eq")
    print("building H03-T10-SINGLE...", flush=True)
    h03_values = build_market_factor(frame, "impact60", comparison_dates)

    data = frame[["date", "instrument"]].copy()
    data["t10_size"] = pd.to_numeric(t10_values, errors="coerce")
    data["h03"] = pd.to_numeric(h03_values, errors="coerce")
    data = data[data["date"].between(start, end)]
    data = finite_joined(data["t10_size"], data["h03"]).join(
        data[["date", "instrument"]]
    )
    # The join above preserves the frame index, so restore the explicit columns
    # and avoid silently changing the stock/date pairing during cleanup.
    data = data[["date", "instrument", "t10_size", "h03"]]
    data = data.sort_values(["date", "instrument"], ignore_index=True)
    if data.empty:
        raise SystemExit("no valid paired factor values in the comparison window")
    print(f"valid_rows={len(data)} valid_dates={data['date'].nunique()}", flush=True)

    daily = daily_correlations(data)
    if daily.empty:
        raise SystemExit("no daily cross-sectional correlations could be calculated")
    result = build_report(
        frame=frame,
        data=data,
        daily=daily,
        data_start=data_start,
        start=start,
        end=end,
        calendar_dates=comparison_dates,
        output_prefix=Path(args.output_prefix),
    )
    local = result["local"]
    print(
        "daily_spearman_mean="
        f"{local['daily_cross_sectional_spearman']['mean']:.10f} "
        f"platform={PLATFORM_CORRELATION:.10f} "
        f"delta={local['daily_cross_sectional_spearman']['mean'] - PLATFORM_CORRELATION:+.10f}",
        flush=True,
    )
    print(f"report={Path(args.output_prefix).with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
