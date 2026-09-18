#!/usr/bin/env python3
"""Run the canonical local alignment calculation for RSQR60.

This is a local-only diagnostic when the corresponding PandaAI run does not
produce a completed result. It keeps the platform failure separate from the
local metrics instead of fabricating a platform comparison row.
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
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE,
    alignment_config_snapshot,
    annualized_turnover_cost,
    validate_alignment_config,
)
from positive_factor_local_compare import (  # noqa: E402
    assign_groups,
    build_factor,
    forward_returns,
    panel_close,
)
from stfilter_local_recheck import ensure_calendar  # noqa: E402


FORMULA = "Rsquare(CLOSE,60)"
HANDLER = "rsquare60"
NAME = "RSQR60-ALPHA158-20260918"
DIRECTION = 1
CYCLE = 5
PLATFORM_STATE = PROJECT_ROOT / "rsqr60-platform-20260918-candidates.txt.state.json"
DEFAULT_PRICE_ROOT = (
    PROJECT_ROOT
    / "quantlab"
    / ".quantlab"
    / "cache"
    / "research"
    / "cn_equity"
    / "tushare_factor_recheck"
    / "qfq"
    / "daily_batches"
)
DEFAULT_CAP_ROOT = (
    PROJECT_ROOT
    / "quantlab"
    / ".quantlab"
    / "cache"
    / "research"
    / "cn_equity"
    / "tushare_factor_recheck"
    / "daily_basic_full_a"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "rsqr60_local_20260918"
)


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(value, format="%Y%m%d")).normalize()


def compounded_max_drawdown(returns: pd.Series) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna().to_numpy(dtype=float)
    if not len(values):
        return None
    nav = np.cumprod(1.0 + values)
    peak = np.maximum.accumulate(np.concatenate(([1.0], nav)))
    drawdown = nav / peak[1:] - 1.0
    return float(drawdown.min())


def platform_failure() -> dict[str, Any]:
    if not PLATFORM_STATE.is_file():
        return {"status": "missing_state"}
    try:
        state = json.loads(PLATFORM_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unreadable_state", "error": str(exc)}
    row = state.get(NAME) or {}
    return {
        "status": "failed" if row.get("error") else "unknown",
        "factor_id": row.get("factor_id"),
        "run_id": row.get("run_id"),
        "factor_result_status": row.get("factor_result_status"),
        "factor_analysis": row.get("factor_analysis"),
        "node_formula": row.get("node_formula"),
        "error": row.get("error"),
    }


def evaluate_local(
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    label_offset: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    close = panel_close(frame, calendar)
    factor_values = build_factor(frame, HANDLER, signal_dates=signal_dates)
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = factor_values.to_numpy(dtype=float)
    returns = forward_returns(close, calendar, signal_dates, cycle, label_offset)
    data = factor_frame[factor_frame["date"].isin(signal_dates)].merge(
        returns, on=["date", "instrument"], how="left"
    )
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    selected_group = ALIGNMENT_GROUPS if DIRECTION == 1 else 1
    previous: set[str] | None = None
    rank_ics: list[float] = []
    ics: list[float] = []
    period_rows: list[dict[str, Any]] = []

    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < ALIGNMENT_GROUPS * 10:
            continue
        current["group"] = assign_groups(current["factor"])
        rank_ic = current["factor"].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        ic = current["factor"].corr(current["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))

        benchmark = float(current["forward_return"].mean())
        selected = current[current["group"].eq(selected_group)]
        selected_return = float(selected["forward_return"].mean())
        members = set(selected["instrument"].astype(str))
        turnover = (
            np.nan
            if previous is None
            else float(1.0 - len(members.intersection(previous)) / len(members))
        )
        previous = members
        period_rows.append(
            {
                "date": date,
                "stock_count": int(len(current)),
                "benchmark_return": benchmark,
                "selected_return": selected_return,
                "selected_excess": selected_return - benchmark,
                "turnover": turnover,
            }
        )

    periods = pd.DataFrame(period_rows)
    years = len(periods) * cycle / 252.0
    gross_excess = (
        float(periods["selected_excess"].sum() / years)
        if years and not periods.empty
        else None
    )
    gross_return = (
        float(periods["selected_return"].sum() / years)
        if years and not periods.empty
        else None
    )
    turnover = (
        float(periods["turnover"].dropna().mean())
        if not periods.empty and periods["turnover"].notna().any()
        else None
    )
    annual_cost = annualized_turnover_cost(turnover, cycle, ALIGNMENT_ROUND_TRIP_COST)
    net_excess = (
        gross_excess - annual_cost
        if gross_excess is not None and annual_cost is not None
        else None
    )
    monthly = periods.assign(month=periods["date"].dt.to_period("M"))
    monthly_excess = monthly.groupby("month")["selected_excess"].mean()
    latest_date = signal_dates[-1]
    latest = factor_frame[factor_frame["date"].eq(latest_date)].dropna()
    local_top20 = (
        latest.sort_values(["factor", "instrument"], ascending=[False, True])
        .head(20)["instrument"]
        .astype(str)
        .tolist()
    )

    result = {
        "name": NAME,
        "formula": FORMULA,
        "handler": HANDLER,
        "direction": DIRECTION,
        "selected_group": selected_group,
        "periods": int(len(periods)),
        "stock_count_mean": float(periods["stock_count"].mean()) if not periods.empty else None,
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.mean(ics)) if ics else None,
        "gross_return": gross_return,
        "gross_excess": gross_excess,
        "turnover": turnover,
        "annual_cost": annual_cost,
        "net_excess": net_excess,
        "max_drawdown": compounded_max_drawdown(periods["selected_return"])
        if not periods.empty
        else None,
        "monthly_excess_win_rate": (
            float((monthly_excess > 0).mean()) if len(monthly_excess) else None
        ),
        "local_top20": local_top20,
        "date_source": "generated_calendar_due_platform_run_failure",
        "fidelity": "direct local reconstruction: 60-day rolling R-square of qfq close against the time index",
    }
    return result, periods


def write_outputs(
    output: Path,
    result: dict[str, Any],
    periods: pd.DataFrame,
    settings: dict[str, Any],
    failure: dict[str, Any],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": settings,
        "platform": failure,
        "result": result,
    }
    (output / "rsqr60_local_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    periods.to_csv(output / "rsqr60_local_periods.csv", index=False, encoding="utf-8-sig")
    row = {
        "name": result["name"],
        "formula": result["formula"],
        "direction": result["direction"],
        "periods": result["periods"],
        "rank_ic": result["rank_ic"],
        "ic_mean": result["ic_mean"],
        "gross_return": result["gross_return"],
        "gross_excess": result["gross_excess"],
        "turnover": result["turnover"],
        "annual_cost": result["annual_cost"],
        "net_excess": result["net_excess"],
        "max_drawdown": result["max_drawdown"],
        "monthly_excess_win_rate": result["monthly_excess_win_rate"],
    }
    pd.DataFrame([row]).to_csv(output / "rsqr60_local_metrics.csv", index=False, encoding="utf-8-sig")

    def pct(value: Any) -> str:
        return "n/a" if value is None else f"{100.0 * float(value):.2f}%"

    lines = [
        "# RSQR60 local alignment test",
        "",
        f"- Formula: `{result['formula']}`; handler: `{result['handler']}`; direction: `{result['direction']}`.",
        f"- Rule version: `{ALIGNMENT_RULE_VERSION}`; local universe: `{ALIGNMENT_UNIVERSE}`; price: `qfq`; market cap join: `total_mv`.",
        f"- Window: `{settings['start']}..{settings['end']}`; warm-up: `{settings['data_start']}`; cycle: `{settings['cycle']}`; groups: `{settings['groups']}`.",
        f"- Label: `{settings['label']}`; benchmark: `factor_valid`; one-way cost: `{100 * ALIGNMENT_ONE_WAY_COST:.2f}%`.",
        f"- Signal dates: `{result['date_source']}` because the PandaAI run failed and supplied no chart dates.",
        "",
        "## Platform status",
        "",
        f"- status: `{failure.get('status')}`",
        f"- factor_id: `{failure.get('factor_id') or 'n/a'}`",
        f"- run_id: `{failure.get('run_id') or 'n/a'}`",
        f"- result status: `{failure.get('factor_result_status') or 'n/a'}`; factor_analysis: `{failure.get('factor_analysis')}`",
        f"- node formula: `{failure.get('node_formula') or 'n/a'}`",
        f"- error: `{failure.get('error') or 'n/a'}`",
        "- No platform RankIC, group return, turnover, or Top20 values are available; this local result is not an alignment pass/fail comparison.",
        "",
        "## Local result",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| valid periods | {result['periods']} |",
        f"| mean stock count | {result['stock_count_mean']:.1f} |",
        f"| RankIC | {result['rank_ic']:.6f} |",
        f"| IC mean | {result['ic_mean']:.6f} |",
        f"| gross selected return | {pct(result['gross_return'])} |",
        f"| gross excess | {pct(result['gross_excess'])} |",
        f"| selected-group turnover | {pct(result['turnover'])} |",
        f"| annual turnover cost | {pct(result['annual_cost'])} |",
        f"| net excess | {pct(result['net_excess'])} |",
        f"| compounded period max drawdown proxy | {pct(result['max_drawdown'])} |",
        f"| monthly excess win rate | {pct(result['monthly_excess_win_rate'])} |",
        "",
        "The max drawdown is a diagnostic from compounded 5-day selected-group returns; it is not the platform daily max-drawdown series.",
        "",
    ]
    (output / "rsqr60_local_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    args = parser.parse_args()

    data_start = parse_date(ALIGNMENT_DATA_START)
    start = parse_date(ALIGNMENT_START)
    end = parse_date(ALIGNMENT_END)
    config = alignment_config_snapshot()
    config.update(
        {
            "universe": ALIGNMENT_UNIVERSE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "data_start": data_start.strftime("%Y%m%d"),
            "label_offset": ALIGNMENT_LABEL_OFFSET,
        }
    )
    validate_alignment_config(config)

    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(data_start, end, token=None)
    ]
    positions = list(range(calendar.index(start), len(calendar), CYCLE))
    signal_dates = [
        calendar[position]
        for position in positions
        if position + ALIGNMENT_LABEL_OFFSET + CYCLE < len(calendar)
    ]
    frame = load_full_a_data(
        Path(args.price_root), Path(args.cap_root), data_start, end
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    result, periods = evaluate_local(
        frame, calendar, signal_dates, CYCLE, ALIGNMENT_LABEL_OFFSET
    )
    failure = platform_failure()
    settings = {
        **config,
        "rule_version": ALIGNMENT_RULE_VERSION,
        "start": start,
        "end": end,
        "cycle": CYCLE,
        "groups": ALIGNMENT_GROUPS,
        "direction": DIRECTION,
        "formula": FORMULA,
        "label": "close(t+1) -> close(t+1+cycle)",
        "rows": int(len(frame)),
        "instruments": int(frame["instrument"].nunique()),
        "calendar_dates": int(len(calendar)),
        "signal_dates": int(len(signal_dates)),
        "market_field_sources": frame.attrs.get("market_field_sources", {}),
    }
    write_outputs(Path(args.output), result, periods, settings, failure)
    print(f"report={Path(args.output) / 'rsqr60_local_report.md'}")
    print(
        f"periods={result['periods']} rank_ic={result['rank_ic']} "
        f"gross_excess={result['gross_excess']} net_excess={result['net_excess']} "
        f"turnover={result['turnover']} max_drawdown={result['max_drawdown']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
