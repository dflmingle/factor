#!/usr/bin/env python3
"""Build and test seven strong, non-duplicate factors from the full catalog.

This is an offline workflow. It reads the saved positive-factor correlation
report and the local Tushare cache; it never creates a factor or calls PandaAI.

The historical PCA report selected one loading representative per statistical
component. That can keep a weaker factor when another candidate in the same
exposure cluster has a better saved net excess. This script instead considers
every positive saved record, collapses exact formula duplicates, and greedily
selects the highest-net candidate whose direction-aligned correlation with
each selected candidate is below the existing 0.80 duplicate threshold.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_DESCRIPTION,
    ALIGNMENT_BENCHMARK_MODE,
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
    annualized_turnover_cost,
    validate_alignment_config,
)
from pca_seven_class_combination import (  # noqa: E402
    cross_sectional_scores,
    evaluate_portfolio,
    format_value,
    json_default,
    usable_signal_dates,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    forward_returns,
    panel_close,
    saved_records,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
PLATFORM_START = pd.Timestamp(ALIGNMENT_START)
END = pd.Timestamp(ALIGNMENT_END)
GROUPS = ALIGNMENT_GROUPS
LABEL_OFFSET = ALIGNMENT_LABEL_OFFSET
ROUND_TRIP_COST = ALIGNMENT_ROUND_TRIP_COST

DEFAULT_CORRELATION_REPORT = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/positive-factor-pair-correlation-20260917.json"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/greedy-seven-factor-combination-20260917"
)


def normalize_formula(formula: str | None) -> str:
    return re.sub(r"\s+", "", str(formula or "")).upper()


def direction_sign(record: dict[str, Any]) -> int:
    direction = record.get("platform_factor_direction", record.get("direction", 1))
    return 1 if int(direction) == 1 else -1


def load_local_support() -> dict[str, dict[str, Any]]:
    supported, _ = saved_records(formula_catalog(), "positive")
    return {str(record["id"]): record for record in supported}


def select_candidates(
    correlation_payload: dict[str, Any],
    local_support: dict[str, dict[str, Any]],
    cycle: int,
    count: int,
    threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[frozenset[str], float]]:
    """Select high-net records while excluding highly correlated duplicates."""
    source_records = [
        dict(record)
        for record in correlation_payload["records"]
        if float(record.get("platform_net_excess_pct") or 0.0) > 0.0
        and int(record.get("configured_cycle") or -1) == cycle
        and str(record.get("id")) in local_support
    ]

    # A formula repeated in multiple saved windows is one candidate for class
    # selection. Keep the strongest comparable record and preserve all source
    # counts in the metadata.
    by_formula: dict[str, dict[str, Any]] = {}
    for record in source_records:
        key = normalize_formula(record.get("formula"))
        previous = by_formula.get(key)
        if previous is None or float(record["platform_net_excess_pct"]) > float(
            previous["platform_net_excess_pct"]
        ):
            by_formula[key] = record
    candidates = list(by_formula.values())
    candidate_ids = {str(record["id"]) for record in candidates}

    correlations: dict[frozenset[str], float] = {}
    for pair in correlation_payload["pairs"]:
        left = str(pair["factor_a_id"])
        right = str(pair["factor_b_id"])
        if left not in candidate_ids or right not in candidate_ids:
            continue
        aligned = float(pair["correlation"]) * direction_sign(
            local_support.get(left, pair)
        ) * direction_sign(local_support.get(right, pair))
        correlations[frozenset((left, right))] = aligned

    selected: list[dict[str, Any]] = []
    for record in sorted(
        candidates,
        key=lambda item: (
            -float(item.get("platform_net_excess_pct") or -np.inf),
            str(item.get("id")),
        ),
    ):
        record_id = str(record["id"])
        if all(
            abs(correlations[frozenset((record_id, selected_record["id"]))]) < threshold
            for selected_record in selected
        ):
            selected.append(record)
        if len(selected) >= count:
            break

    if len(selected) < count:
        raise RuntimeError(
            f"Only {len(selected)} candidates satisfy the {threshold:.2f} correlation threshold; "
            f"cannot build {count} classes"
        )

    # Attach every candidate to the strongest selected neighbor, if it has one.
    # This makes the class decision inspectable without changing selection.
    for candidate in candidates:
        candidate_id = str(candidate["id"])
        neighbors = []
        for rank, selected_record in enumerate(selected, start=1):
            selected_id = str(selected_record["id"])
            if candidate_id == selected_id:
                rho = 1.0
            else:
                rho = correlations[frozenset((candidate_id, selected_id))]
            neighbors.append((abs(rho), rho, rank, selected_record))
        abs_rho, rho, rank, representative = max(neighbors, key=lambda item: item[0])
        candidate["nearest_selected_rank"] = rank
        candidate["nearest_selected_name"] = representative["name"]
        candidate["nearest_selected_handler"] = representative["handler"]
        candidate["nearest_selected_correlation"] = rho
        candidate["nearest_selected_abs_correlation"] = abs_rho

    return selected, candidates, correlations


def find_schedule_record(
    supported: dict[str, dict[str, Any]], report: str, name: str
) -> dict[str, Any]:
    for record in supported.values():
        if record.get("report") == report and record.get("name") == name:
            return record
    raise KeyError(f"Saved schedule record not found: {report}:{name}")


def write_outputs(
    output_prefix: Path,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    allow_existing: bool = False,
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_prefix.with_suffix(".json"),
        "csv": output_prefix.with_suffix(".csv"),
        "periods": output_prefix.with_name(output_prefix.name + ".periods.csv"),
        "md": output_prefix.with_suffix(".md"),
    }
    for path in paths.values():
        if path.exists() and not allow_existing:
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    def project_path(path: Path) -> str:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))

    if not paths["json"].exists():
        paths["json"].write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
            encoding="utf-8",
        )
    if not paths["csv"].exists():
        with paths["csv"].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    if not paths["periods"].exists():
        with paths["periods"].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(period_rows[0].keys()))
            writer.writeheader()
            writer.writerows(period_rows)

    settings = payload["settings"]
    lines = [
        "# Full-catalog seven-factor combination",
        "",
        f"规则版本：`{settings['alignment_rule_version']}`；规则文档：`{settings['alignment_rules_document']}`。",
        "",
        "这是离线本地 proxy 测试，不创建因子、不调用 PandaAI。候选池先取保存记录中平台净超额大于 0 的因子，再按完全相同公式去重；在同一调仓周期内，按平台净超额从高到低贪心选择，要求新代表与已选代表的方向对齐截面相关绝对值小于 0.80。",
        "这种选择会把所有正净超额候选纳入筛选，而不是先固定 PCA 载荷代表。每类代表优先由净超额决定，相关候选仍保留在候选明细中。",
        "",
        "## Selected representatives",
        "",
        "| 类别 | handler | 因子 | 方向 | 平台净超额 | 与前面代表最大绝对相关 |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for rank, record in enumerate(payload["selected"], start=1):
        max_corr = 0.0
        if rank > 1:
            selected_ids = {str(item["id"]) for item in payload["selected"][:rank]}
            for pair in payload["selected_pair_correlations"]:
                if str(pair["left_id"]) == str(record["id"]) and str(pair["right_id"]) in selected_ids:
                    max_corr = max(max_corr, abs(float(pair["aligned_correlation"])))
                if str(pair["right_id"]) == str(record["id"]) and str(pair["left_id"]) in selected_ids:
                    max_corr = max(max_corr, abs(float(pair["aligned_correlation"])))
        lines.append(
            f"| {rank} | `{record['handler']}` | {record['name']} | {record['direction']} | {float(record['platform_net_excess_pct']):.2f}% | {max_corr:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Candidate coverage",
            "",
            "| 候选 | handler | 平台净超额 | 最近代表 | 相关系数 |",
            "|---|---|---:|---|---:|",
        ]
    )
    for record in sorted(
        candidates,
        key=lambda item: (
            int(item["nearest_selected_rank"]),
            -float(item["platform_net_excess_pct"]),
        ),
    ):
        lines.append(
            f"| {record['name']} | `{record['handler']}` | {float(record['platform_net_excess_pct']):.2f}% | {record['nearest_selected_name']} | {float(record['nearest_selected_correlation']):+.4f} |"
        )
    lines.extend(
        [
            "",
            "## Local results",
            "",
            "净超额为算术年化毛超额减本地实际换手成本；组合和单因子均使用相同信号日期、`factor_valid` 基准、qfq 全 A 和 0.30% 单边成本。",
            "",
            "| 调仓 | 组合 | 因子数 | 期数 | RankIC | 毛超额 | 换手 | 年化成本 | 净超额 | Sharpe | 最大回撤 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["cycle"]),
                    row["portfolio"],
                    str(row["component_count"]),
                    str(row["periods"]),
                    format_value(row["rank_ic"]),
                    format_value(row["gross_excess_pct"], "%"),
                    format_value(row["turnover_pct"], "%"),
                    format_value(row["annual_cost_pct"], "%"),
                    format_value(row["net_excess_pct"], "%"),
                    format_value(row["sharpe_after_cost"]),
                    format_value(row["max_drawdown_pct"], "%"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "这里的 7 类是去重后的强候选代表，不是保证组合优于单因子的优化结果。若单因子净超额高于组合，说明等权平均稀释了有效暴露；这时应保留单因子作为基准，不能为了让组合看起来更好而改变权重。",
            "",
            "完整逐期结果见：",
            f"`{project_path(paths['periods'])}`",
            "",
            "机器可读结果见：",
            f"`{project_path(paths['json'])}` 和 `{project_path(paths['csv'])}`。",
        ]
    )
    paths["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correlation-report", type=Path, default=DEFAULT_CORRELATION_REPORT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--output-prefix", type=Path, default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--cycle", type=int, default=10, choices=[5, 10])
    parser.add_argument("--test-cycles", default="5,10")
    parser.add_argument("--class-count", type=int, default=7)
    parser.add_argument("--correlation-threshold", type=float, default=0.80)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Render Markdown from an existing JSON/CSV/period output without recomputing factors",
    )
    args = parser.parse_args()

    if args.report_only:
        output_json = args.output_prefix.with_suffix(".json")
        output_csv = args.output_prefix.with_suffix(".csv")
        output_periods = args.output_prefix.with_name(args.output_prefix.name + ".periods.csv")
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        with output_csv.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        with output_periods.open("r", encoding="utf-8", newline="") as handle:
            period_rows = list(csv.DictReader(handle))
        write_outputs(
            args.output_prefix,
            payload,
            rows,
            period_rows,
            payload["candidates"],
            allow_existing=True,
        )
        print(f"report={args.output_prefix.with_suffix('.md')}", flush=True)
        return 0

    test_cycles = [int(value.strip()) for value in args.test_cycles.split(",") if value.strip()]
    if not test_cycles or any(value not in {5, 10} for value in test_cycles):
        raise SystemExit("--test-cycles must contain only 5 and/or 10")
    if args.class_count < 1 or not 0.0 < args.correlation_threshold < 1.0:
        raise SystemExit("class-count must be positive and correlation-threshold must be in (0, 1)")

    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)

    correlation_payload = json.loads(args.correlation_report.read_text(encoding="utf-8"))
    local_support = load_local_support()
    selected, candidates, correlations = select_candidates(
        correlation_payload,
        local_support,
        args.cycle,
        args.class_count,
        args.correlation_threshold,
    )
    print(
        f"candidates={len(candidates)} selected={len(selected)} selection_cycle={args.cycle} "
        f"threshold={args.correlation_threshold:.2f}",
        flush=True,
    )
    for rank, record in enumerate(selected, start=1):
        print(
            f"selected={rank} {record['name']} handler={record['handler']} "
            f"net={record['platform_net_excess_pct']:.2f}%",
            flush=True,
        )

    supported = local_support
    calendar = [pd.Timestamp(value).normalize() for value in ensure_calendar(DATA_START, END, token=None)]
    schedules: dict[int, list[pd.Timestamp]] = {}
    schedule_specs = {
        5: ("verify-field-scan-20260910-candidates.report.csv", "VERIFY-F260910-12"),
        10: ("verify-field-scan-cycle10-20260910-candidates.report.csv", "VERIFY10-F260910-12"),
    }
    for cycle in test_cycles:
        schedule_record = find_schedule_record(supported, *schedule_specs[cycle])
        platform = read_platform_run(PROJECT_ROOT / str(schedule_record["raw_result"]))
        dates = usable_signal_dates(platform["dates"], calendar, cycle)
        if not dates:
            raise RuntimeError(f"No usable saved signal dates for cycle {cycle}")
        schedules[cycle] = dates
        print(
            f"schedule cycle={cycle} dates={len(dates)} first={dates[0].date()} last={dates[-1].date()}",
            flush=True,
        )

    all_dates = sorted({date for dates in schedules.values() for date in dates})
    frame = load_full_a_data(args.price_root, args.cap_root, DATA_START, END)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(f"local_rows={len(frame)} pool={frame['instrument'].nunique()}", flush=True)
    close = panel_close(frame, calendar)
    signal_mask = frame["date"].isin(all_dates)
    signal_frame = frame.loc[signal_mask, ["date", "instrument"]].copy().reset_index(drop=True)
    if signal_frame.duplicated(["date", "instrument"]).any():
        raise RuntimeError("Duplicate date/instrument rows in the common signal panel")

    selected_handlers = [str(record["handler"]) for record in selected]
    directions = {str(record["handler"]): int(record["direction"]) for record in selected}
    financial = None
    if any(handler in FINANCIAL_HANDLERS for handler in selected_handlers):
        financial = load_financial_cache(args.financial_root)
        print(f"financial_cache=loaded tables={len(financial)}", flush=True)

    raw_values: dict[str, pd.Series] = {}
    for handler in selected_handlers:
        print(f"building={handler} rows={len(frame)}", flush=True)
        values = build_factor(frame, handler, financial=financial, signal_dates=all_dates)
        raw_values[handler] = pd.to_numeric(
            values.loc[signal_mask].reset_index(drop=True), errors="coerce"
        )
        del values
        gc.collect()
    scores = cross_sectional_scores(signal_frame, raw_values, directions)
    del raw_values
    gc.collect()

    rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    portfolios = {"greedy_seven": tuple(selected_handlers)}
    for handler in selected_handlers:
        portfolios[f"single_{handler}"] = (handler,)
    for cycle in test_cycles:
        for portfolio_name, handlers in portfolios.items():
            score = scores[list(handlers)].mean(axis=1, skipna=False)
            result, periods = evaluate_portfolio(
                signal_frame,
                score,
                close,
                calendar,
                schedules[cycle],
                cycle,
                portfolio_name,
                len(handlers),
            )
            result["handlers"] = ",".join(handlers)
            rows.append(result)
            period_rows.extend(periods)
            print(
                f"result cycle={cycle} portfolio={portfolio_name} "
                f"periods={result['periods']} net={result['net_excess_pct']}",
                flush=True,
            )

    rows.sort(key=lambda row: (row["cycle"], row["net_excess_pct"] is None, -(row["net_excess_pct"] or -np.inf)))
    period_rows.sort(key=lambda row: (row["cycle"], row["portfolio"], row["date"]))

    selected_pair_correlations = []
    for left_index, left in enumerate(selected):
        for right in selected[left_index + 1 :]:
            aligned = correlations[frozenset((str(left["id"]), str(right["id"]))) ]
            selected_pair_correlations.append(
                {
                    "left_id": left["id"],
                    "right_id": right["id"],
                    "left_name": left["name"],
                    "right_name": right["name"],
                    "aligned_correlation": aligned,
                    "absolute_correlation": abs(aligned),
                }
            )

    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_config": alignment_config,
            "universe": "沪深全A",
            "price_mode": ALIGNMENT_PRICE_MODE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "data_start": DATA_START.strftime("%Y%m%d"),
            "comparison_start": PLATFORM_START.strftime("%Y%m%d"),
            "comparison_end": END.strftime("%Y%m%d"),
            "label": "close(t+1) -> close(t+1+cycle)",
            "groups": GROUPS,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ROUND_TRIP_COST,
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
            "selection_metric": "platform_net_excess_pct",
            "selection_condition": "platform_net_excess_pct > 0",
            "selection_cycle": args.cycle,
            "selection_correlation_threshold_abs": args.correlation_threshold,
            "selection_correlation_method": "direction_aligned_daily_cross_sectional_spearman_mean",
            "selection_count": args.class_count,
            "selection_method": "exact-formula-dedup-then-greedy-high-net-with-direction-aligned-correlation-cap",
            "candidate_count_after_filter": len(candidates),
            "test_cycles": test_cycles,
            "schedule_dates": {str(cycle): len(dates) for cycle, dates in schedules.items()},
            "local_market_field_sources": frame.attrs.get("market_field_sources", {}),
        },
        "selected": selected,
        "selected_pair_correlations": selected_pair_correlations,
        "candidate_count_before_formula_dedup": sum(
            1
            for record in correlation_payload["records"]
            if float(record.get("platform_net_excess_pct") or 0.0) > 0.0
            and int(record.get("configured_cycle") or -1) == args.cycle
            and str(record.get("id")) in local_support
        ),
        "candidates": candidates,
        "results": rows,
        "artifacts": {
            "correlation_report": str(
                args.correlation_report.resolve().relative_to(PROJECT_ROOT.resolve())
            ),
        },
    }
    write_outputs(args.output_prefix, payload, rows, period_rows, candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
