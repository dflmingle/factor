#!/usr/bin/env python3
"""Build the final offline platform/local alignment report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a_label1/positive_factor_local_compare.json"
)
DEFAULT_BASELINE = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a/positive_factor_local_compare.json"
)
DEFAULT_SHIFT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_shift_diagnosis_full_a/remaining_mismatch_diagnosis.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/positive_factor_alignment_20260914.md"


DIRECT_HANDLERS = {
    "momentum120",
    "turn_bias",
    "turn_signal",
    "reversal40",
    "drawdown120",
    "drawdown60",
    "chip250",
    "weighted_reversal_lowturn",
    "reversal_turn_eq",
    "reversal_chip_eq",
    "reversal_chip_turn_eq",
    "reversal_chip_turn_size_eq",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def delta(row: dict[str, Any]) -> float:
    return 100.0 * float(row["local_net_excess"]) - float(row["platform_net_excess_pct"])


def gross_delta(row: dict[str, Any]) -> float:
    return 100.0 * (
        float(row["local_gross_excess"]) - float(row["platform_gross_excess"])
    )


def turnover_delta(row: dict[str, Any]) -> float:
    return 100.0 * (float(row["local_turnover"]) - float(row["platform_turnover"]))


def category(row: dict[str, Any]) -> str:
    if int(row["periods"]) <= 20:
        return "2026 YTD / short sample"
    if row["handler"] == "residual_volatility":
        return "Barra proxy"
    if row["handler"] in DIRECT_HANDLERS:
        return "direct price / turnover"
    return "financial / paper"


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [delta(row) for row in rows]
    return {
        "n": len(rows),
        "mae": mean(abs(value) for value in deltas),
        "mean": mean(deltas),
        "within1": sum(abs(value) <= 1.0 for value in deltas),
        "within2": sum(abs(value) <= 2.0 for value in deltas),
        "large": sum(abs(value) >= 2.0 for value in deltas),
    }


def category_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(category(row), []).append(row)
    result = []
    for name, group in groups.items():
        summary = stats(group)
        result.append({"category": name, **summary})
    return sorted(result, key=lambda row: row["category"])


def label_effect(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    old_by_id = {row["id"]: row for row in baseline.get("results", [])}
    changes = []
    for row in rows:
        old = old_by_id.get(row["id"])
        if old is None:
            continue
        old_delta = 100.0 * float(old["local_net_excess"]) - float(old["platform_net_excess_pct"])
        new_delta = delta(row)
        changes.append((old_delta, new_delta))
    return {
        "n": len(changes),
        "improved": sum(abs(new) < abs(old) for old, new in changes),
        "old_mae": mean(abs(old) for old, _ in changes),
        "new_mae": mean(abs(new) for _, new in changes),
        "old_within1": sum(abs(old) <= 1.0 for old, _ in changes),
        "new_within1": sum(abs(new) <= 1.0 for _, new in changes),
        "old_large": sum(abs(old) >= 2.0 for old, _ in changes),
        "new_large": sum(abs(new) >= 2.0 for _, new in changes),
    }


def write_report(
    result: dict[str, Any],
    baseline: dict[str, Any],
    shift: dict[str, Any],
    output: Path,
) -> None:
    rows = list(result["results"])
    overall = stats(rows)
    label = label_effect(rows, baseline)
    rankic_errors = [
        abs(float(row["local_rank_ic"]) - float(row["platform_rank_ic"]))
        for row in rows
    ]
    gross_errors = [abs(gross_delta(row)) for row in rows]
    turnover_errors = [abs(turnover_delta(row)) for row in rows]
    categories = category_table(rows)
    large = sorted(
        (row for row in rows if abs(delta(row)) >= 2.0),
        key=lambda row: abs(delta(row)),
        reverse=True,
    )
    settings = result["settings"]
    benchmark = [
        row
        for row in shift.get("benchmark_sensitivity", [])
        if row.get("current_offset") == 1 and row.get("target_offset") == 1
    ]
    pools = {row.get("platform_stock_pool") for row in rows}

    lines = [
        "# Final platform/local alignment audit",
        "",
        "This is an offline audit of saved PandaAI results. It creates no factor and runs no platform backtest.",
        "",
        "## Conclusion",
        "",
        f"The data is complete enough to rebuild all `{len(rows)}/{len(rows)}` positive saved records, but the local reproduction does not fully match the platform.",
        f"With the recorded full-A proxy, qfq prices, and the corrected forward label, `{overall['within1']}/{overall['n']}` records are within 1 percentage point and `{overall['large']}/{overall['n']}` still differ by at least 2 points of annualized net excess.",
        f"The mean absolute net-excess gap is `{overall['mae']:.2f}` pp; the signed mean is `{overall['mean']:.2f}` pp, so the local result is generally lower.",
        "",
        "## Fixed configuration",
        "",
        f"- local universe: `{settings['local_universe']}`; observed instruments: `{settings['pool_count']}`",
        f"- local data start/end: `{settings['data_start']}..{settings['end']}`",
        f"- saved platform records: `{overall['n']}`; unsupported locally: `{len(result.get('unsupported', []))}`",
        f"- groups: `{settings['groups']}`; one-way cost: `{100 * float(settings['round_trip_cost']) / 2:.2f}%`",
        f"- local return label: `{settings['return_label']}`",
        f"- recorded platform pools in these rows: `{', '.join(sorted(str(pool) for pool in pools))}`",
        "",
        "The workflow registry contains 171 workflows; 167 explicitly record the full-A pool label. Two positive historical records have no current registry binding, so their historical pool cannot be independently confirmed.",
        "",
        "## Corrected label check",
        "",
        "The saved platform benchmark is almost exactly reproduced by shifting both the current and future close one trading day forward:",
        "",
        "| cycle | periods | benchmark correlation | RMSE (pp) | mean delta (pp) |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(benchmark, key=lambda item: item["cycle"]):
        lines.append(
            f"| {row['cycle']} | {row['periods']} | {row['correlation']:.3f} | {row['rmse_pp']:.3f} | {row['mean_delta_pp']:.3f} |"
        )
    lines.extend(
        [
            "",
            f"Compared with the previous same-day label, the corrected label improves absolute error for `{label['improved']}/{label['n']}` records and reduces mean absolute error from `{label['old_mae']:.2f}` to `{label['new_mae']:.2f}` pp. It changes the large-gap count only from `{label['old_large']}` to `{label['new_large']}`.",
            "",
            "This confirms a label mismatch in the old local calculation, but it does not explain the remaining factor-specific gaps.",
            "",
            "## Gap distribution",
            "",
            "| category | records | mean abs net gap (pp) | signed mean (pp) | >=2 pp | within 1 pp |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in categories:
        lines.append(
            f"| {row['category']} | {row['n']} | {row['mae']:.2f} | {row['mean']:.2f} | {row['large']} | {row['within1']} |"
        )
    lines.extend(
        [
            "",
            f"Across all rows, RankIC mean absolute error is `{mean(rankic_errors):.4f}`, gross-excess mean absolute error is `{mean(gross_errors):.2f}` pp, and turnover mean absolute error is `{mean(turnover_errors):.2f}` pp.",
            "",
            "## Records still above 2 pp",
            "",
            "The table uses the corrected label. `gross delta` and `turnover delta` are local minus platform, in percentage points.",
            "",
            "| factor | category | cycle | periods | platform net | local net | delta | gross delta | turnover delta | top20 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in large:
        lines.append(
            f"| {row['name']} | {category(row)} | {row['cycle']} | {row['periods']} | {row['platform_net_excess_pct']:.2f}% | {100 * float(row['local_net_excess']):.2f}% | {delta(row):.2f} | {gross_delta(row):.2f} | {turnover_delta(row):.2f} | {row.get('top20_overlap', 'n/a')}/20 |"
        )
    lines.extend(
        [
            "",
            "## What is still different",
            "",
            "- Direct price/turnover factors: the remaining loss is mainly in gross excess rather than turnover. qfq is materially closer than raw prices, but it is still not proof that the platform uses the same adjustment series, suspension handling, or portfolio construction.",
            "- Financial and paper factors: the point-in-time Tushare cache is present, but the platform's internal fields are not byte-equivalent to documented Tushare fields. The separate CFP proxy test finds no single cash-flow field that matches every CFP combination; differences are consistent with field definition, report-revision timing, or TTM treatment.",
            "- 2026 YTD factors: these have only 16 periods. Two of the three YTD rows remain above 2 pp, and some platform configurations end on 2026-09-09 while the local snapshot ends on 2026-09-07. They are not reliable equivalence tests.",
            "- Residual volatility: the local implementation is a market-model proxy for the platform Barra field. Its remaining gap is small, but exact field equivalence is not established.",
            "- Missing data is no longer the blocker: all 45 records rebuild, the full-A qfq/daily_basic history covers the warm-up, and the financial tables are available. The unresolved part is semantic equivalence to the platform's internal data and execution rules.",
            "",
            "## Reproduction",
            "",
            "```powershell",
            "python scripts/positive_factor_local_compare.py --universe full_a --data-start 20180101 --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a --output quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a_label1 --label-offset 1",
            "python scripts/build_final_alignment_report.py",
            "```",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--shift", type=Path, default=DEFAULT_SHIFT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_report(load(args.result), load(args.baseline), load(args.shift), args.output)
    print(f"report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
