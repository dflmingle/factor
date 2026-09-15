#!/usr/bin/env python3
"""Offline diagnosis of the components used by the T10 composites.

The script uses saved platform result JSON files for chart dates and standalone
component comparisons. It never creates or runs a PandaAI factor.
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

import financial_factor_local as financial_local  # noqa: E402
from financial_factor_local import load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    END,
    GROUPS,
    ROUND_TRIP_COST,
    assign_groups,
    evaluate,
    forward_returns,
    panel_close,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DATA_START = pd.Timestamp("2018-01-01")
PLATFORM_START = pd.Timestamp("2021-09-07")
LABEL_OFFSET = 1

PLATFORM_FILES = {
    "reversal": "positive-cycle10-candidates.results/6a9fcd2e6df2a192a47e765c.json",
    "chip": "nonht-report-directions-20260909-formula.results/6aa1239c6df2a192a47e78d5.json",
    "turnover_bias": "positive-cycle10-candidates.results/6a9fcdb23e7967143f8faaee.json",
    "size": "size-only-20260911-candidates.results/6aa3b8576df2a192a47e7cfe.json",
    "h03": "h03-t10-single-20260911-candidates.results/6aa36bd3ecb163ea7228cffe.json",
    "abs_impact": "verify-field-scan-cycle10-20260910-candidates.results/6aa28ea43e7967143f8fae33.json",
    "t10_base": "t10-newdirections-20260911-candidates.results/6aa368586df2a192a47e7c5e.json",
    "t10_g13": "t10-additions-20260911-candidates.results/6aa3c61451cdfe29b2e0bcdd.json",
    "t10_fscore": "t10-more-additions-20260911-candidates.results/6aa3c986a7f535324660ba77.json",
}

COMPONENT_FORMULAS = {
    "reversal": "RANK(1-RETURNS(CLOSE,40))",
    "chip": "RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)",
    "turnover_bias": "MA(TURNOVER,21)/MA(TURNOVER,504)-1",
    "size": "RANK(-ZSCORE(RANK(MARKET_CAP)))",
    "h03": "RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))",
    "abs_impact": "RANK(SUM(ABS(CLOSE/DELAY(CLOSE,1)-1)/(AMOUNT+1),60)/60)",
    "fscore": (
        "RANK((IF(oper_roa_net_ttm > 0,1,0) + "
        "IF(cfd_ocf_to_debt_ttm > 0,1,0) + "
        "IF(oper_roa_net_ttm > oper_roa_net_lyr,1,0) + "
        "IF(cfd_surplus_cash_multi_ttm > 1,1,0) + "
        "IF(fin_debt_to_asset_ttm < fin_debt_to_asset_lyr,1,0) + "
        "IF(fin_current_ratio_ttm > fin_current_ratio_lyr,1,0) + "
        "IF(oper_gross_margin_ttm > oper_gross_margin_lyr,1,0) + "
        "IF(oper_total_asset_turnover_ttm > oper_total_asset_turnover_lyr,1,0)) / 8)"
    ),
}

T10_FORMULAS = {
    "t10_base": "(reversal + chip + turnover + size + h03) / 5",
    "t10_g13": "(reversal + chip + turnover + size + h03 + abs_impact) / 6",
    "t10_fscore": "(reversal + chip + turnover + size + h03 + fscore) / 6",
}


def build_fscore_rank(selected: pd.DataFrame, dates: pd.Series) -> pd.Series:
    numeric = financial_local._numeric_series
    positive = financial_local._positive
    comparison = financial_local._comparison

    roa_cur = numeric(selected, "roa_yearly_cur")
    roa_lyr = numeric(selected, "roa_yearly_lyr")
    if roa_cur.isna().all():
        roa_cur = numeric(selected, "roa_cur")
    if roa_lyr.isna().all():
        roa_lyr = numeric(selected, "roa_lyr")
    debt_cur = numeric(selected, "debt_to_assets_cur")
    debt_lyr = numeric(selected, "debt_to_assets_lyr")
    current_cur = numeric(selected, "current_ratio_cur")
    current_lyr = numeric(selected, "current_ratio_lyr")
    gross_cur = numeric(selected, "grossprofit_margin_cur")
    gross_lyr = numeric(selected, "grossprofit_margin_lyr")
    turn_cur = numeric(selected, "assets_turn_cur")
    turn_lyr = numeric(selected, "assets_turn_lyr")
    ocf_debt = numeric(selected, "ocf_to_debt_cur")
    cash_multi = numeric(selected, "cfd_surplus_cash_multi_ttm")
    score = sum(
        [
            positive(roa_cur),
            positive(ocf_debt),
            comparison(roa_cur, roa_lyr, ">"),
            positive(cash_multi.sub(1.0)),
            comparison(debt_lyr, debt_cur, ">"),
            comparison(current_cur, current_lyr, ">"),
            comparison(gross_cur, gross_lyr, ">"),
            comparison(turn_cur, turn_lyr, ">"),
        ]
    )
    return financial_local._rank(score, dates)


def build_components(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
) -> dict[str, pd.Series]:
    financial_local._FINANCIAL_CACHE = cache
    selected = financial_local._base_signal(frame, dates)
    financial_local._add_market_ranks(selected)
    date_series = selected["date"]

    def impact_rank(variant: str) -> pd.Series:
        raw = financial_local._market_raw(frame, variant)
        return financial_local._rank(
            financial_local._selected_full_series(selected, raw), date_series
        )

    components = {
        "reversal": selected["rev_rank"],
        "chip": selected["chip_rank"],
        # The standalone saved run is the raw ratio-1 formula with direction 0.
        # T10 itself uses the opposite cross-sectional rank as a component.
        "turnover_bias": -selected["turn_signal"],
        "turnover_rank": selected["turn_rank"],
        # T10's small-size rank has the same ordering as cap rank with direction 0.
        "size": selected["cap_rank"],
        "h03": impact_rank("h03"),
        "abs_impact": impact_rank("abs_return"),
        "fscore": build_fscore_rank(selected, date_series),
    }
    return {
        name: financial_local._materialize_factor(frame, selected, values)
        for name, values in components.items()
    }


def period_excess(
    frame: pd.DataFrame,
    values: pd.Series,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    direction: int,
) -> pd.DataFrame:
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = values.to_numpy(dtype=float)
    factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]
    returns = forward_returns(close, calendar, signal_dates, cycle, LABEL_OFFSET)
    data = factor_frame.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    selected_group = GROUPS if direction == 1 else 1
    rows: list[dict[str, Any]] = []
    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = assign_groups(current["factor"])
        benchmark = float(current["forward_return"].mean())
        group = current[current["group"].eq(selected_group)]
        rows.append(
            {
                "date": date,
                "excess": float(group["forward_return"].mean() - benchmark),
            }
        )
    return pd.DataFrame(rows)


def correlation(left: pd.Series, right: pd.Series) -> float | None:
    joined = pd.concat([left.rename("local"), right.rename("platform")], axis=1).dropna()
    if len(joined) < 2:
        return None
    value = joined["local"].corr(joined["platform"])
    return None if pd.isna(value) else float(value)


def platform_net(platform: dict[str, Any], direction: int, cycle: int) -> float | None:
    group = GROUPS if direction == 1 else 1
    metrics = platform.get("group_metrics", {}).get(group, {})
    gross = metrics.get("excessAnnualized")
    turnover = metrics.get("turnoverRate")
    if gross is None or turnover is None:
        return None
    return float(gross - turnover * (252.0 / cycle) * ROUND_TRIP_COST)


def component_record(
    name: str,
    values: pd.Series,
    frame: pd.DataFrame,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    platform: dict[str, Any] | None,
    dates: list[pd.Timestamp],
    direction: int,
    cycle: int,
    role: str,
) -> dict[str, Any]:
    local = evaluate(
        frame,
        values,
        close,
        platform or {},
        direction,
        dates,
        calendar,
        cycle,
        LABEL_OFFSET,
    )
    local_periods = period_excess(
        frame, values, close, calendar, dates, cycle, direction
    )
    platform_corr = None
    if platform and platform.get("dates") and platform.get("excess_cumulative"):
        group = GROUPS if direction == 1 else 1
        cumulative = platform["excess_cumulative"][group - 1]
        platform_periods = pd.DataFrame(
            {
                "date": pd.to_datetime(platform["dates"]).normalize(),
                "excess": np.diff(np.concatenate(([0.0], cumulative))),
            }
        )
        joined = local_periods.merge(
            platform_periods, on="date", suffixes=("_local", "_platform")
        )
        platform_corr = correlation(
            joined["excess_local"], joined["excess_platform"]
        )

    selected_group = GROUPS if direction == 1 else 1
    group_metrics = (platform or {}).get("group_metrics", {}).get(selected_group, {})
    saved_net = platform_net(platform, direction, cycle) if platform else None
    return {
        "name": name,
        "role": role,
        "formula": COMPONENT_FORMULAS.get(name) or T10_FORMULAS.get(name),
        "direction": direction,
        "cycle": cycle,
        "periods": int(local["periods"]),
        "platform_rank_ic": local["platform_rank_ic"] if platform else None,
        "local_rank_ic": local["rank_ic"],
        "rank_ic_delta": (
            None
            if not platform or local["platform_rank_ic"] is None
            else local["rank_ic"] - local["platform_rank_ic"]
        ),
        "platform_gross_excess_pct": (
            None
            if group_metrics.get("excessAnnualized") is None
            else 100.0 * group_metrics["excessAnnualized"]
        ),
        "local_gross_excess_pct": (
            None if local["gross_excess"] is None else 100.0 * local["gross_excess"]
        ),
        "platform_turnover_pct": (
            None
            if group_metrics.get("turnoverRate") is None
            else 100.0 * group_metrics["turnoverRate"]
        ),
        "local_turnover_pct": (
            None if local["turnover"] is None else 100.0 * local["turnover"]
        ),
        "platform_net_excess_pct": (
            None if saved_net is None else 100.0 * saved_net
        ),
        "local_net_excess_pct": (
            None if local["net_excess"] is None else 100.0 * local["net_excess"]
        ),
        "delta_net_pp": (
            None
            if saved_net is None or local["net_excess"] is None
            else 100.0 * (local["net_excess"] - saved_net)
        ),
        "period_excess_corr": platform_corr,
        "top20_overlap": local["top20_overlap"],
        "platform_result": platform.get("path") if platform else None,
    }


def load_platform(name: str) -> dict[str, Any]:
    path = PROJECT_ROOT / PLATFORM_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing saved platform result: {path}")
    return read_platform_run(path)


def write_report(payload: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "t10_component_diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# T10 component diagnosis",
        "",
        "Offline comparison using saved platform runs. No factor was created or run.",
        "",
        "- label: close(t+1) -> close(t+1+cycle)",
        "- price: qfq; universe: full-A .SH/.SZ; groups: 10; one-way cost: 0.30%",
        "- standalone platform rows are compared only when a matching saved run exists",
        "",
        "| component | role | platform RankIC | local RankIC | platform net | local net | delta pp | period excess corr | Top20 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        def fmt(value: Any, percent: bool = False) -> str:
            if value is None:
                return "n/a"
            return f"{float(value):.2f}%" if percent else f"{float(value):.4f}"

        lines.append(
            f"| {row['name']} | {row['role']} | {fmt(row['platform_rank_ic'])} | "
            f"{fmt(row['local_rank_ic'])} | {fmt(row['platform_net_excess_pct'], True)} | "
            f"{fmt(row['local_net_excess_pct'], True)} | {fmt(row['delta_net_pp'])} | "
            f"{fmt(row['period_excess_corr'])} | "
            f"{row['top20_overlap'] if row['top20_overlap'] is not None else 'n/a'}/20 |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "fscore has no pure saved platform run; its row is a local component diagnostic on the T10-FScore chart dates. T10 composite rows use the corresponding saved platform result.",
            "",
            "## Local components used",
            "",
            "| composite | local construction |",
            "|---|---|",
        ]
    )
    for name in ["t10_base", "t10_g13", "t10_fscore"]:
        lines.append(f"| {name} | {T10_FORMULAS[name]} |")
    (output / "t10_component_diagnosis.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run(args: argparse.Namespace) -> int:
    data_start = pd.Timestamp(pd.to_datetime(args.data_start, format="%Y%m%d"))
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(data_start, END, token=None)
    ]
    frame = load_full_a_data(
        Path(args.price_root), Path(args.cap_root), data_start, END
    )
    frame = select_market_cap(frame, args.market_cap_field).sort_values(
        ["instrument", "date"], ignore_index=True
    )
    close = panel_close(frame, calendar)
    financial = load_financial_cache(Path(args.financial_root))

    platform_runs = {name: load_platform(name) for name in PLATFORM_FILES}
    chart_dates = {
        pd.Timestamp(value).normalize()
        for platform in platform_runs.values()
        for value in platform.get("dates", [])
    }
    top_dates = {
        pd.Timestamp(row["date"]).normalize()
        for platform in platform_runs.values()
        for row in platform.get("top", [])
        if row.get("date")
    }
    component_dates = sorted(chart_dates | top_dates)
    components = build_components(frame, component_dates, financial)

    results: list[dict[str, Any]] = []
    standalone = {
        "reversal": 1,
        "chip": 1,
        "turnover_bias": 0,
        "size": 0,
        "h03": 1,
        "abs_impact": 1,
    }
    for name, direction in standalone.items():
        platform = platform_runs[name]
        dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
        results.append(
            component_record(
                name, components[name], frame, close, calendar, platform,
                dates, direction, 10, "standalone"
            )
        )

    fscore_platform = platform_runs["t10_fscore"]
    fscore_dates = [pd.Timestamp(value).normalize() for value in fscore_platform["dates"]]
    results.append(
        component_record(
            "fscore", components["fscore"], frame, close, calendar, None,
            fscore_dates, 1, 10, "local-only; no pure platform run"
        )
    )

    composite_values = {
        "t10_base": (
            components["reversal"] + components["chip"] + components["turnover_rank"]
            + (1.0 - components["size"]) + components["h03"]
        ) / 5.0,
        "t10_g13": (
            components["reversal"] + components["chip"] + components["turnover_rank"]
            + (1.0 - components["size"]) + components["h03"] + components["abs_impact"]
        ) / 6.0,
        "t10_fscore": (
            components["reversal"] + components["chip"] + components["turnover_rank"]
            + (1.0 - components["size"]) + components["h03"] + components["fscore"]
        ) / 6.0,
    }
    for name in ["t10_base", "t10_g13", "t10_fscore"]:
        platform = platform_runs[name]
        dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
        results.append(
            component_record(
                name, composite_values[name], frame, close, calendar, platform,
                dates, 1, 10, "composite"
            )
        )

    payload = {
        "settings": {
            "data_start": data_start.strftime("%Y%m%d"),
            "end": END.strftime("%Y%m%d"),
            "start": PLATFORM_START.strftime("%Y%m%d"),
            "label_offset": LABEL_OFFSET,
            "universe": "full-A qfq + daily_basic filtered to .SH/.SZ",
            "groups": GROUPS,
            "round_trip_cost": ROUND_TRIP_COST,
            "market_cap_field": args.market_cap_field,
        },
        "results": results,
    }
    write_report(payload, Path(args.output))
    for row in results:
        print(
            f"{row['name']}: local_net={row['local_net_excess_pct']}% "
            f"platform_net={row['platform_net_excess_pct']}% "
            f"local_rank_ic={row['local_rank_ic']} top20={row['top20_overlap']}",
            flush=True,
        )
    print(f"report={Path(args.output) / 't10_component_diagnosis.md'}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-start", default=DATA_START.strftime("%Y%m%d"))
    parser.add_argument(
        "--price-root",
        default=str(CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"),
    )
    parser.add_argument(
        "--cap-root", default=str(CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a")
    )
    parser.add_argument(
        "--market-cap-field",
        choices=["total_mv", "circ_mv"],
        default="total_mv",
        help="daily_basic market-cap field used by MARKET_CAP in the local reconstruction",
    )
    parser.add_argument(
        "--financial-root", default=str(CACHE_ROOT / "financial_full_a")
    )
    parser.add_argument(
        "--output",
        default=str(CACHE_ROOT / "reports" / "t10_component_diagnosis_full_a_label1"),
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
