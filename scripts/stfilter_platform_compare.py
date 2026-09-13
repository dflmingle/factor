#!/usr/bin/env python3
"""Compare existing local factor checks with a completed non-ST workflow.

The platform calls in this script are read-only.  It reads the stock pool and
factor-analysis nodes from an existing workflow run, then evaluates the
already-tested price factors against the exact returned pool and the local
沪深 universe.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clone_and_run_workflow import (  # noqa: E402
    get_run_results,
    get_workflow,
    headers,
    load_auth,
    request_json,
)
from platform_aligned_factor_compare import (  # noqa: E402
    DEFAULT_PLATFORM_RESULTS,
    FACTOR_SPECS,
    MOMENTUM_REFERENCE,
    add_forward_returns,
    as_float,
    evaluate_factor,
    factor_panels,
    load_daily_batches,
    panel_prices,
    read_platform_run,
    signal_frame,
    top_overlap,
    validate_chart_dates,
)
from tushare_factor_recheck import RECHECK_ROOT, load_trade_dates  # noqa: E402


DEFAULT_WORKFLOW_ID = "6aa3871b51cdfe29b2e0bc47"
DEFAULT_RUN_ID = "6aa38c5dcffa1665a210173c"
DEFAULT_START = pd.Timestamp("2021-09-07")
DEFAULT_END = pd.Timestamp("2026-09-07")
DEFAULT_WARMUP = pd.Timestamp("2021-01-01")
DEFAULT_OUTPUT = RECHECK_ROOT / "reports" / "stfilter_platform"


def factor_workflow_data(
    gateway: str,
    token: str,
    uid: str,
    task_id: str,
    endpoint: str,
) -> dict[str, Any]:
    response, payload = request_json(
        "GET",
        f"{gateway}/quantflow/api/factor/{endpoint}",
        request_headers=headers(token, uid),
        params={"task_id": task_id},
    )
    if response.status_code >= 400 or not isinstance(payload, dict):
        raise RuntimeError(f"factor endpoint failed: {endpoint} HTTP {response.status_code}")
    if payload.get("code") not in (0, "200", 200):
        raise RuntimeError(f"factor endpoint failed: {endpoint}: {payload}")
    return payload.get("data") or {}


def group_number(label: Any) -> int | None:
    digits = "".join(character for character in str(label) if character.isdigit())
    return int(digits) if digits else None


def read_non_st_workflow(workflow_id: str, run_id: str) -> tuple[set[str], dict[str, Any]]:
    gateway, token, uid = load_auth()
    workflow = get_workflow(gateway, token, uid, workflow_id)
    run = get_run_results(gateway, token, uid, workflow_id, run_id)

    pool_node = next(
        node for node in workflow.get("nodes", []) if node.get("name") == "CustomStockPoolControl"
    )
    pool_text = (run.get("nodes", {}).get(pool_node.get("uuid")) or {}).get("stock_list", "")
    pool = {line.strip() for line in str(pool_text).splitlines() if line.strip()}
    if not pool:
        raise RuntimeError("The completed workflow did not return a stock pool")

    formula_nodes = [node for node in workflow.get("nodes", []) if node.get("name") == "FormulaControl"]
    formulas = [
        (run.get("nodes", {}).get(node.get("uuid")) or {}).get("formulas")
        for node in formula_nodes
    ]
    analysis_nodes = [
        node for node in workflow.get("nodes", []) if node.get("name") == "FactorAnalysisControl"
    ]
    labels = ["T10-SIZE", "H03-T10-SINGLE"]
    analyses: list[dict[str, Any]] = []
    for index, node in enumerate(analysis_nodes):
        task_id = (run.get("nodes", {}).get(node.get("uuid")) or {}).get("task_id")
        if not task_id:
            continue
        metrics_data = factor_workflow_data(
            gateway, token, uid, task_id, "query_factor_analysis_data"
        )
        group_data = factor_workflow_data(
            gateway, token, uid, task_id, "query_group_return_analysis"
        )
        top_data = factor_workflow_data(
            gateway, token, uid, task_id, "query_last_date_top_factor"
        )
        rank_data = factor_workflow_data(
            gateway, token, uid, task_id, "query_rank_ic_sequence_chart"
        )
        metric_rows = metrics_data.get("factor_data_analysis") or []
        metrics = {
            str(row.get("indicator")): as_float(row.get("factor1"))
            for row in metric_rows
            if isinstance(row, dict)
        }
        groups: dict[int, dict[str, float | None]] = {}
        for row in group_data.get("group_return_analysis") or []:
            number = group_number(row.get("group"))
            if number is None:
                continue
            groups[number] = {
                key: as_float(row.get(key))
                for key in ("annualizedReturn", "excessAnnualized", "turnoverRate")
            }
        chart = rank_data.get("rank_ic_seq_chart") or {}
        chart_dates = ((chart.get("x") or [{}])[0].get("data") or [])
        top_rows = top_data.get("last_date_top_factor") or []
        analyses.append(
            {
                "label": labels[index] if index < len(labels) else f"factor_{index + 1}",
                "formula": formulas[index] if index < len(formulas) else None,
                "task_id": task_id,
                "metrics": metrics,
                "group_10": groups.get(10, {}),
                "groups": groups,
                "chart_periods": len(chart_dates),
                "chart_start": chart_dates[0] if chart_dates else None,
                "chart_end": chart_dates[-1] if chart_dates else None,
                "top_symbols": [str(row.get("symbol")) for row in top_rows],
            }
        )
    return pool, {
        "workflow_id": workflow_id,
        "run_id": run_id,
        "pool_count": len(pool),
        "analysis": analyses,
    }


def local_platform_runs() -> dict[str, dict[str, Any]]:
    runs = {name: read_platform_run(path) for name, path in DEFAULT_PLATFORM_RESULTS.items()}
    runs["momentum120"] = {
        "metrics": MOMENTUM_REFERENCE,
        "group_metrics": {
            1: {
                "excessAnnualized": MOMENTUM_REFERENCE["long_excess_pct"] / 100.0,
                "turnoverRate": MOMENTUM_REFERENCE["turnover_pct"] / 100.0,
            }
        },
        "dates": [],
        "rank_ic_values": [],
        "return_cumulative": [],
        "excess_cumulative": [],
        "top": [],
    }
    return runs


def compare_universe(
    frame: pd.DataFrame,
    pool: set[str],
    platform: dict[str, dict[str, Any]],
    warmup: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
    max_price_age_days: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    chart_dates = validate_chart_dates({name: run for name, run in platform.items() if run.get("dates")})
    chart_dates = [date for date in chart_dates if start <= date <= end]
    signal_dates = sorted(set(chart_dates + [end]))
    calendar = load_trade_dates(warmup, end)
    period_frames: list[pd.DataFrame] = []
    comparisons: dict[str, Any] = {}

    for universe_name, source in (
        ("full_hs", frame),
        ("platform_st_pool", frame[frame["instrument"].isin(pool)].copy()),
    ):
        close, last_seen = panel_prices(source, calendar)
        signals = signal_frame(
            factor_panels(close),
            close,
            last_seen,
            calendar,
            signal_dates,
            max_price_age_days,
        )
        evaluated = add_forward_returns(
            signals[signals["date"].isin(chart_dates)].copy(), close, calendar, chart_dates
        )
        universe_result: dict[str, Any] = {
            "rows": int(len(source)),
            "instruments": int(source["instrument"].nunique()),
            "signal_rows": int(len(signals)),
            "evaluated_rows": int(len(evaluated)),
            "factors": {},
        }
        for name in FACTOR_SPECS:
            local, periods = evaluate_factor(evaluated, name, platform[name], chart_dates)
            selected = local["direction_selected"]
            overlap = top_overlap(signals, name, platform[name], end)
            universe_result["factors"][name] = {
                "rank_ic": local["rank_ic"],
                "ic_mean": local["ic_mean"],
                "ic_ir": local["ic_ir"],
                "annualized_excess_pct": 100.0
                * selected["platform_style_annualized_excess"],
                "turnover_pct": 100.0 * selected["turnover"],
                "periods": local["periods"],
                "top20_overlap": None
                if overlap is None
                else f"{overlap['overlap']}/{overlap['platform_top_n']}",
                "rank_ic_sequence_corr": local["comparison"]["rank_ic"]["corr"],
                "cumulative_excess_corr": local["comparison"]["cumulative_excess"]["corr"],
            }
            if not periods.empty:
                period_frames.append(
                    periods.assign(universe=universe_name, factor=name)
                )
        comparisons[universe_name] = universe_result
    return comparisons, pd.concat(period_frames, ignore_index=True)


def write_report(
    output: Path,
    workflow: dict[str, Any],
    comparisons: dict[str, Any],
    platform: dict[str, dict[str, Any]],
) -> None:
    lines = [
        "# ST-filter workflow comparison",
        "",
        "This report reads a completed platform workflow and reuses the local qfq cache. It does not create or run a PandaAI factor.",
        "",
        f"- workflow: `{workflow['workflow_id']}`; run: `{workflow['run_id']}`",
        f"- returned custom pool: `{workflow['pool_count']}` instruments",
        "- local comparison: 2021-09-07..2026-09-07, 10 trading days, 10 groups, qfq prices",
        "- `platform_st_pool` is the exact stock list returned by the completed workflow; it is a fixed-pool sensitivity, not a historical ST-status reconstruction.",
        "",
        "## Platform workflow nodes",
        "",
        "| node | RankIC | IC mean | group 10 excess | group 10 turnover | chart periods | latest top count |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in workflow["analysis"]:
        lines.append(
            "| {label} | {rank:.4f} | {ic:.4f} | {excess:.2%} | {turnover:.2%} | {periods} | {top} |".format(
                label=item["label"],
                rank=item["metrics"].get("Rank_IC") or 0.0,
                ic=item["metrics"].get("IC_mean") or 0.0,
                excess=(item["group_10"].get("excessAnnualized") or 0.0),
                turnover=(item["group_10"].get("turnoverRate") or 0.0),
                periods=item["chart_periods"],
                top=len(item["top_symbols"]),
            )
        )

    lines.extend(
        [
            "",
            "## Existing factor cross-check",
            "",
            "The platform column below is from the previously saved factor run for the same formula, while the two local columns differ only by stock universe.",
            "",
            "| factor | platform RankIC | full A local | ST-pool local | platform excess | full A excess | ST-pool excess | platform turnover | full A turnover | ST-pool turnover |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    full = comparisons["full_hs"]["factors"]
    st_pool = comparisons["platform_st_pool"]["factors"]
    for name in FACTOR_SPECS:
        direction_group = 1 if FACTOR_SPECS[name]["direction"] == 0 else 10
        platform_metrics = platform[name].get("metrics", {})
        platform_group = platform[name].get("group_metrics", {}).get(direction_group, {})
        platform_rank_ic = platform_metrics.get("Rank_IC")
        if platform_rank_ic is None:
            platform_rank_ic = platform_metrics.get("rank_ic")
        lines.append(
            "| {name} | {prank:.4f} | {frank:.4f} | {srank:.4f} | {pex:.2%} | {fex:.2%} | {sex:.2%} | {pt:.2%} | {ft:.2%} | {st:.2%} |".format(
                name=name,
                prank=platform_rank_ic or 0.0,
                frank=full[name]["rank_ic"],
                srank=st_pool[name]["rank_ic"],
                pex=platform_group.get("excessAnnualized") or 0.0,
                fex=full[name]["annualized_excess_pct"] / 100.0,
                sex=st_pool[name]["annualized_excess_pct"] / 100.0,
                pt=platform_group.get("turnoverRate") or 0.0,
                ft=full[name]["turnover_pct"] / 100.0,
                st=st_pool[name]["turnover_pct"] / 100.0,
            )
        )
    lines.extend(
        [
            "",
            "The ST-pool line isolates the universe effect. It should not be read as proof that every excluded historical observation was ST on that date.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--start", default="20210907")
    parser.add_argument("--end", default="20260907")
    parser.add_argument("--warmup", default="20210101")
    parser.add_argument("--max-price-age-days", type=int, default=10)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    start = pd.Timestamp(pd.to_datetime(args.start, format="%Y%m%d")).normalize()
    end = pd.Timestamp(pd.to_datetime(args.end, format="%Y%m%d")).normalize()
    warmup = pd.Timestamp(pd.to_datetime(args.warmup, format="%Y%m%d")).normalize()
    if not warmup <= start <= end:
        raise SystemExit("Require warmup <= start <= end")
    missing = [str(path) for path in DEFAULT_PLATFORM_RESULTS.values() if not path.exists()]
    if missing:
        raise SystemExit("Missing archived platform result(s): " + "; ".join(missing))

    pool, workflow = read_non_st_workflow(args.workflow_id, args.run_id)
    platform = local_platform_runs()
    frame = load_daily_batches(
        warmup,
        end,
        RECHECK_ROOT / "qfq" / "daily_batches",
        market="hs",
    )
    comparisons, periods = compare_universe(
        frame,
        pool,
        platform,
        warmup,
        start,
        end,
        max(0, args.max_price_age_days),
    )

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "platform_st_pool_symbols.txt").write_text(
        "\n".join(sorted(pool)) + "\n", encoding="utf-8"
    )
    result = {
        "workflow": workflow,
        "settings": {
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "warmup": warmup.strftime("%Y%m%d"),
            "rebalance_days": 10,
            "groups": 10,
            "max_price_age_days": max(0, args.max_price_age_days),
        },
        "comparisons": comparisons,
    }
    (output / "stfilter_platform_compare.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    periods.to_csv(output / "stfilter_periods.csv", index=False, encoding="utf-8-sig")
    write_report(output / "stfilter_platform_compare.md", workflow, comparisons, platform)

    print(f"report={output / 'stfilter_platform_compare.md'}")
    print(f"pool={len(pool)}")
    for universe, item in comparisons.items():
        print(
            f"{universe}: rows={item['rows']} instruments={item['instruments']} "
            f"reversal40_rank_ic={item['factors']['reversal40']['rank_ic']:.4f} "
            f"reversal40_excess={item['factors']['reversal40']['annualized_excess_pct']:.2f}%",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
