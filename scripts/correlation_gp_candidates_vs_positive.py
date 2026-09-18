#!/usr/bin/env python3
"""Compare local AlphaPROBE candidates with the saved positive factor set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alphaprobe_gp_tushare import (  # noqa: E402
    TushareStockData,
    evaluate_formula,
    expression_namespace,
    finite_as_nan,
)
from correlation_vs_positive_factors import (  # noqa: E402
    daily_spearman,
    parse_date,
)
from correlation_positive_factors import load_records as load_aligned_records  # noqa: E402
from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_CORRELATION_DESCRIPTION,
    ALIGNMENT_CORRELATION_METHOD,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE_LABEL,
)
from positive_factor_local_compare import build_factor  # noqa: E402
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DEFAULT_CANDIDATES = (
    CACHE_ROOT
    / "reports"
    / "local_safe_financial_blends_20260918"
    / "results.json"
)
DEFAULT_RECORDS = (
    CACHE_ROOT
    / "reports"
    / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "safe-financial-candidates-vs-aligned-positive-20260918"
)


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


def load_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        candidates = payload.get("top_candidates", [])
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"No candidates or top_candidates found in {path}")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(candidates, start=1):
        raw = str(item.get("raw_formula") or item.get("formula") or "").strip()
        panda = str(item.get("panda_formula") or item.get("formula") or "").strip()
        if not raw or not panda or panda in seen:
            continue
        seen.add(panda)
        name = str(item.get("name") or f"F-NET{index:02d}").strip()
        if any(row["name"] == name for row in result):
            name = f"{name}-{index:02d}"
        result.append(
            {
                "name": name,
                "raw_formula": raw,
                "formula": panda,
                "net_excess_pct": percentage(item.get("net_excess")),
                "gross_excess_pct": percentage(item.get("gross_excess")),
                "turnover_pct": percentage(item.get("turnover")),
                "annual_cost_pct": percentage(item.get("annual_cost")),
                "coverage": number(item.get("coverage"), default=0.0),
            }
        )
    if not result:
        raise ValueError(f"No usable candidates found in {path}")
    return result


def number(value: Any, *, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def percentage(value: Any) -> float | None:
    parsed = number(value)
    return None if parsed is None else parsed * 100.0


def format_percent(value: Any) -> str:
    parsed = number(value)
    return "n/a" if parsed is None else f"{parsed:.2f}%"


def load_positive_records(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Load only platform-positive records accepted by the alignment gate."""
    _payload, records = load_aligned_records(path, "platform")
    eligible = [
        record
        for record in records
        if record.get("alignment_quality") == "aligned"
        and bool(record.get("local_mining_eligible"))
    ]
    if len(eligible) < 2:
        raise ValueError(
            f"Only {len(eligible)} aligned positive records found in {path}"
        )
    return eligible, "platform_net_excess>0 AND alignment_quality=aligned"


def signal_dates_for(
    calendar: list[pd.Timestamp],
    start: pd.Timestamp,
    end: pd.Timestamp,
    cycle: int = 5,
    label_offset: int = 1,
) -> list[pd.Timestamp]:
    start_position = calendar.index(start)
    return [
        calendar[position]
        for position in range(start_position, len(calendar), cycle)
        if calendar[position] <= end
        and position + label_offset + cycle < len(calendar)
    ]


def candidate_series(
    values: torch.Tensor,
    data: TushareStockData,
    comparison_frame: pd.DataFrame,
) -> pd.Series:
    array = values.detach().cpu().numpy()
    panel = pd.DataFrame(
        array,
        index=pd.DatetimeIndex(data._evaluation_dates),
        columns=[str(value) for value in data._stock_ids],
    )
    panel.columns.name = "instrument"
    long = panel.rename_axis("date").stack(dropna=False).rename("value").reset_index()
    long["instrument"] = long["instrument"].astype(str)
    lookup = long.set_index(["date", "instrument"])["value"]
    keys = pd.MultiIndex.from_frame(comparison_frame[["date", "instrument"]])
    return pd.Series(lookup.reindex(keys).to_numpy(dtype=float), index=comparison_frame.index)


def write_outputs(
    *,
    output_prefix: Path,
    candidates: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    data_start: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
    signal_dates: list[pd.Timestamp],
    frame: pd.DataFrame,
    gp_run: Path,
    records: Path,
    record_selection: str,
    threshold: float,
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    pair_frame = pd.DataFrame(pair_rows)
    pair_frame.to_csv(output_prefix.with_suffix(".pairs.csv"), index=False, encoding="utf-8-sig")

    summary_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows = [row for row in pair_rows if row["candidate_name"] == candidate["name"]]
        best = max(rows, key=lambda row: float(row["abs_correlation"]))
        summary_rows.append(
            {
                **candidate,
                "max_abs_correlation": best["abs_correlation"],
                "max_corr": best["correlation"],
                "closest_factor": best["existing_name"],
                "closest_handler": best["existing_handler"],
                "closest_platform_net_excess_pct": best["existing_platform_net_excess_pct"],
                "below_threshold": bool(best["abs_correlation"] < threshold),
                "existing_factor_count": len(rows),
            }
        )
    summary_rows.sort(
        key=lambda row: (
            -float(number(row["net_excess_pct"], default=-float("inf"))),
            float(row["max_abs_correlation"]),
        )
    )
    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(output_prefix.with_suffix(".summary.csv"), index=False, encoding="utf-8-sig")

    result = {
        "settings": {
            "universe": ALIGNMENT_UNIVERSE_LABEL,
            "price_mode": ALIGNMENT_PRICE_MODE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "data_start": data_start,
            "comparison_start": start,
            "comparison_end": end,
            "signal_dates": len(signal_dates),
            "cycle": 5,
            "label_offset": 1,
            "correlation_method": ALIGNMENT_CORRELATION_METHOD,
            "correlation_description": ALIGNMENT_CORRELATION_DESCRIPTION,
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "record_selection": record_selection,
            "existing_records": len(pair_rows) // len(candidates),
            "candidate_count": len(candidates),
            "independence_threshold": threshold,
        },
        "sources": {
            "candidate_report": str(gp_run),
            "positive_records": str(records),
            "positive_record_selection": record_selection,
        },
        "candidate_summary": summary_rows,
        "pair_rows": pair_rows,
        "frame_rows": len(frame),
        "frame_instruments": int(frame["instrument"].nunique()),
    }
    output_prefix.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# AlphaPROBE candidates vs existing positive-net factors",
        "",
        "This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.",
        "",
        "## Fixed inputs",
        "",
        f"- Candidates: `{len(candidates)}` from `{gp_run}`; existing records: `{len({row['existing_id'] for row in pair_rows})}` records and `{len({row['existing_handler'] for row in pair_rows})}` unique handlers.",
        f"- Existing-record filter: `{record_selection}`. Records rejected by the alignment quality gate are excluded from this redundancy screen.",
        f"- Window: `{start:%Y-%m-%d}..{end:%Y-%m-%d}`; signal sample: `{len(signal_dates)}` aligned 5-day dates; warm-up starts `{data_start:%Y-%m-%d}`.",
        f"- Universe: `{ALIGNMENT_UNIVERSE_LABEL}`; prices `{ALIGNMENT_PRICE_MODE}`; market cap `{ALIGNMENT_MARKET_CAP_FIELD}`.",
        f"- Correlation: `{ALIGNMENT_CORRELATION_METHOD}`; {ALIGNMENT_CORRELATION_DESCRIPTION}.",
        f"- Independence screen: maximum absolute correlation `< {threshold:.2f}`.",
        "",
        "## Candidate ranking",
        "",
        "| Candidate | Formula | Net excess | Gross | Cost | Turnover | Max abs corr | Closest existing factor | Handler | Pass |",
        "|---|---|---:|---:|---:|---:|---:|---|---|:---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['name']} | `{row['formula']}` | {format_percent(row['net_excess_pct'])} | {format_percent(row['gross_excess_pct'])} | {format_percent(row['annual_cost_pct'])} | {format_percent(row['turnover_pct'])} | {row['max_abs_correlation']:.4f} | {row['closest_factor']} | `{row['closest_handler']}` | {'yes' if row['below_threshold'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "The full candidate-to-existing matrix is in the pairs CSV and JSON. Correlation is a redundancy diagnostic, not a return forecast.",
            "",
            f"- Pair rows: `{len(pair_rows)}`; local rows: `{len(frame):,}`; instruments: `{frame['instrument'].nunique():,}`.",
            f"- Summary CSV: `{output_prefix.with_suffix('.summary.csv')}`.",
            f"- Pair CSV: `{output_prefix.with_suffix('.pairs.csv')}`.",
        ]
    )
    output_prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-report",
        "--gp-run",
        dest="candidate_report",
        default=str(DEFAULT_CANDIDATES),
        help="JSON report with a candidates or top_candidates list",
    )
    parser.add_argument("--records", default=str(DEFAULT_RECORDS))
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--start", default=ALIGNMENT_START)
    parser.add_argument("--end", default=ALIGNMENT_END)
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--financial-root", default=str(DEFAULT_FINANCIAL_ROOT))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT_PREFIX))
    parser.add_argument("--independence-threshold", type=float, default=0.45)
    args = parser.parse_args()

    gp_run = Path(args.candidate_report)
    records_path = Path(args.records)
    data_start = parse_date(args.data_start)
    start = parse_date(args.start)
    end = parse_date(args.end)
    candidates = load_candidates(gp_run)
    records, record_selection = load_positive_records(records_path)
    print(
        f"candidates={len(candidates)} aligned_positive_records={len(records)} "
        f"selection={record_selection}",
        flush=True,
    )

    frame = load_full_a_data(Path(args.price_root), Path(args.cap_root), data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    calendar = [pd.Timestamp(value).normalize() for value in ensure_calendar(data_start, end, token=None)]
    comparison_dates = signal_dates_for(calendar, start, end)
    comparison_frame = frame[frame["date"].isin(comparison_dates)].copy()
    print(
        f"frame_rows={len(frame)} instruments={frame['instrument'].nunique()} signal_dates={len(comparison_dates)}",
        flush=True,
    )

    financial_handlers = {str(record["handler"]) for record in records if str(record["handler"]) in FINANCIAL_HANDLERS}
    financial = load_financial_cache(Path(args.financial_root)) if financial_handlers else None
    if financial is not None:
        print(f"financial_handlers={len(financial_handlers)}", flush=True)

    analysis_calendar = [date for date in calendar if data_start <= date <= end]
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data = TushareStockData.from_aligned_frame(
        frame=frame,
        calendar=analysis_calendar,
        instrument=sorted(frame["instrument"].astype(str).unique()),
        start_time=args.start,
        end_time=args.end,
        max_backtrack_days=756,
        max_future_days=0,
        device=device,
        financial_root=Path(args.financial_root),
    )
    namespace = expression_namespace()
    candidate_values: dict[str, pd.Series] = {}
    for candidate in candidates:
        print(f"building candidate={candidate['name']} formula={candidate['formula']}", flush=True)
        expression = evaluate_formula(candidate["raw_formula"], namespace)
        with torch.no_grad():
            values = finite_as_nan(expression.evaluate(data))
        candidate_values[candidate["name"]] = candidate_series(values, data, comparison_frame)

    pair_rows: list[dict[str, Any]] = []
    handler_records: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        handler_records.setdefault(str(record["handler"]), []).append(record)
    for handler, handler_rows in handler_records.items():
        print(f"building handler={handler} records={len(handler_rows)}", flush=True)
        values = build_factor(frame, handler, financial=financial, signal_dates=comparison_dates)
        right = values.reindex(comparison_frame.index)
        for candidate in candidates:
            summary, _ = daily_spearman(comparison_frame, candidate_values[candidate["name"]], right)
            corr = float(summary["mean"]) if summary["mean"] is not None else float("nan")
            for record in handler_rows:
                pair_rows.append(
                    {
                        "candidate_name": candidate["name"],
                        "candidate_formula": candidate["formula"],
                        "candidate_net_excess_pct": candidate["net_excess_pct"],
                        "existing_id": record.get("id"),
                        "existing_name": record.get("name"),
                        "existing_handler": handler,
                        "existing_formula": record.get("formula"),
                        "existing_platform_net_excess_pct": float(record["platform_net_excess_pct"]),
                        "correlation": corr,
                        "abs_correlation": abs(corr),
                        "days": summary["days"],
                        "common_stocks_mean": summary["common_stocks_mean"],
                    }
                )
        del values

    write_outputs(
        output_prefix=Path(args.output_prefix),
        candidates=candidates,
        pair_rows=pair_rows,
        data_start=data_start,
        start=start,
        end=end,
        signal_dates=comparison_dates,
        frame=frame,
        gp_run=gp_run,
        records=records_path,
        record_selection=record_selection,
        threshold=args.independence_threshold,
    )
    print(f"report={Path(args.output_prefix).with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
