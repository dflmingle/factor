#!/usr/bin/env python3
"""Rebuild every positive-net-excess factor supported by the local cache.

The catalog is taken from the saved ``*.report.csv`` and candidate files.  It
never calls the platform.  Factors that require financial or Barra fields not
present in the local snapshot are retained in the report as unsupported.
"""

from __future__ import annotations

import csv
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from financial_factor_local import (  # noqa: E402
    FINANCIAL_HANDLERS,
    build_financial_factor,
    load_financial_cache,
)
from stfilter_local_recheck import (  # noqa: E402
    CACHE_ROOT,
    ensure_calendar,
    load_data as load_st_data,
    load_pool as load_st_pool,
)


DATA_START = pd.Timestamp("2019-07-01")
END = pd.Timestamp("2026-09-07")
PLATFORM_START = pd.Timestamp("2021-09-07")
GROUPS = 10
ROUND_TRIP_COST = 0.006
OUTPUT_ROOT = CACHE_ROOT / "reports" / "positive_factor_compare"
REGISTRY_PATH = PROJECT_ROOT / "pandaai-workflow-registry.json"


def normalize_formula(formula: str) -> str:
    return re.sub(r"\s+", "", formula).upper()


def cross_rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates, sort=False, observed=True).rank(method="average", pct=True)


def grouped_rolling(frame: pd.DataFrame, column: str, window: int, method: str) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)[column]
    values = getattr(grouped.rolling(window=window, min_periods=window), method)()
    return values.reset_index(level=0, drop=True).reindex(frame.index)


def formula_catalog() -> dict[str, set[str]]:
    catalog: dict[str, set[str]] = {}
    for path in PROJECT_ROOT.glob("*.txt"):
        for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or " ~ " not in line:
                continue
            parts = line.split(" ~ ")
            if len(parts) < 3:
                continue
            catalog.setdefault(parts[0].strip(), set()).add(parts[1].strip())
    return catalog


def platform_configs() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for workflow in registry.get("workflows", []):
        factor_id = workflow.get("_id")
        if not factor_id:
            continue
        info = workflow.get("factor_info") or {}
        result[str(factor_id)] = {
            "factor_id": factor_id,
            "workflow_name": workflow.get("name"),
            "run_id": workflow.get("last_run_id"),
            "market": info.get("market"),
            "stock_pool": info.get("stock_pool"),
            "start_date": info.get("start_date"),
            "end_date": info.get("end_date"),
            "adjustment_cycle": info.get("adjustment_cycle"),
            "group_number": info.get("group_number"),
            "factor_direction": info.get("factor_direction"),
        }
    return result


def report_cycle(report_name: str) -> int | None:
    report_path = PROJECT_ROOT / report_name.replace(".csv", ".md")
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8-sig", errors="ignore")
    match = re.search(r"Settings:\s*(\d+)-day rebalance", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def handler_for(formula: str) -> str | None:
    normalized = normalize_formula(formula)
    exact = {
        "RETURNS(CLOSE,120)": "momentum120",
        "MA(TURNOVER,21)/MA(TURNOVER,504)-1": "turn_bias",
        "1-MA(TURNOVER,21)/MA(TURNOVER,504)": "turn_signal",
        "RANK(1-RETURNS(CLOSE,40))": "reversal40",
        "RANK(1-CLOSE/TS_MAX(CLOSE,120))": "drawdown120",
        "RANK(1-CLOSE/TS_MAX(CLOSE,60))": "drawdown60",
        "RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)": "chip250",
        "(RANK(-SUM(TURNOVER*RETURNS(CLOSE,1),21)/SUM(TURNOVER,21))+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/2": "weighted_reversal_lowturn",
        "(RANK(1-RETURNS(CLOSE,40))+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/2": "reversal_turn_eq",
        "(RANK(1-RETURNS(CLOSE,40))+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1))/2": "reversal_chip_eq",
        "(RANK(1-RETURNS(CLOSE,40))+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/3": "reversal_chip_turn_eq",
        "(RANK(1-RETURNS(CLOSE,40))+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504))+RANK(-ZSCORE(RANK(MARKET_CAP))))/4": "reversal_chip_turn_size_eq",
    }
    if normalized in exact:
        return exact[normalized]

    if normalized == "RATIO_BM_TTM":
        return "value_bm"
    if normalized == "RATIO_SP_TTM":
        return "value_sp"
    if normalized == "RANK(GR_TOTAL_ASSET_LYR)":
        return "asset_growth"
    if "RESIDUAL_VOLATILITY" in normalized:
        return "residual_volatility"
    if "BOOK_TO_MARKET_RATIO_LYR" in normalized:
        if "RANK(1-RETURNS(CLOSE,40))" not in normalized:
            return "paper_composite"
        if "RANK((SUM(VOLUME" in normalized:
            return "reversal_chip_turn_paper"
        if "MARKET_CAP" in normalized:
            return "reversal_turn_paper"
        return "reversal_turn_paper_nomcap"
    if "OPER_ROA_NET_TTM" in normalized:
        return "fscore_interact" if ")*RANK((IF(" in normalized else "fscore_eq"
    if "RANK(RATIO_BM_TTM)" in normalized:
        if "RATIO_PCF_OCF_TTM" in normalized:
            return "reversal_bm_cfp_pcf"
        if "RATIO_EP_TTM" in normalized:
            return "reversal_bm_ep_cfp"
        if "RATIO_SP_TTM" in normalized:
            return "reversal_bm_cfp_sp"
        if "RATIO_CFP_TTM" in normalized and "3*RANK(1-RETURNS(CLOSE,40))" in normalized:
            return "reversal_bm_cfp_rev3"
        if "RATIO_CFP_TTM" in normalized and "2*RANK(1-RETURNS(CLOSE,40))" in normalized:
            return "reversal_bm_cfp_rev2"
        if "RATIO_CFP_TTM" in normalized and "3*RANK(RATIO_BM_TTM)" in normalized:
            return "reversal_bm_cfp_val3"
        if "2*RANK(RATIO_BM_TTM)" in normalized and "RATIO_CFP_TTM" in normalized:
            return "reversal_bm_cfp_val2"
        if "RATIO_CFP_TTM" in normalized:
            return "reversal_bm_cfp"
        if "2*RANK(1-RETURNS(CLOSE,40))" in normalized:
            return "reversal_bm_rev2"
        if "2*RANK(RATIO_BM_TTM)" in normalized:
            return "reversal_bm_val2"
        if "*" in normalized and "0.5+0.5*RANK(RATIO_BM_TTM)" in normalized:
            return "reversal_bm_interact"
        return "reversal_bm_eq"
    if "MA(RATIO_BM_TTM,63)" in normalized:
        if "MA(RATIO_CFP_TTM,63)" in normalized:
            return "reversal_bm_cfp_ma63"
        return "reversal_bm_ma63"
    if "TS_RANK(RATIO_BM_TTM,756)" in normalized:
        if "TS_RANK(RATIO_CFP_TTM,756)" in normalized:
            return "reversal_bm_cfp_tsrank756"
        return "reversal_bm_tsrank756"
    if "MA(RATIO_BM_TTM" in normalized and "RATIO_CFP_TTM" in normalized:
        return "reversal_bm_cfp_ma63"
    if "TS_RANK(RATIO_BM_TTM" in normalized and "RATIO_CFP_TTM" in normalized:
        return "reversal_bm_cfp_tsrank756"
    return None


def positive_records(catalog: dict[str, set[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for report_path in sorted(PROJECT_ROOT.glob("*.report.csv")):
        with report_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            for row in rows:
                if row.get("status") != "completed" or not row.get("net_excess_pct"):
                    continue
                platform_net = float(row["net_excess_pct"])
                if platform_net <= 0:
                    continue
                name = row["name"]
                formulas = sorted(catalog.get(name, set()))
                formula = formulas[0] if formulas else None
                handler = handler_for(formula or "")
                record = {
                    "id": f"{report_path.stem}:{name}",
                    "name": name,
                    "report": report_path.name,
                    "direction": int(row["direction"]),
                    "factor_id": row.get("factor_id"),
                    "run_id": row.get("run_id"),
                    "platform_net_excess_pct": platform_net,
                    "platform_rank_ic": float(row["rank_ic"]) if row.get("rank_ic") else None,
                    "platform_ic_mean": float(row["ic_mean"]) if row.get("ic_mean") else None,
                    "platform_turnover_pct": float(row["turnover_pct"]) if row.get("turnover_pct") else None,
                    "platform_gross_excess_pct": float(row["long_excess_pct"]) if row.get("long_excess_pct") else None,
                    "platform_annual_cost_pct": float(row["annual_cost_pct"]) if row.get("annual_cost_pct") else None,
                    "raw_result": str(row.get("raw_result", "")).replace("\\", "/"),
                    "formula": formula,
                    "handler": handler,
                    "configured_cycle": report_cycle(report_path.name),
                }
                if handler is None:
                    record["reason"] = "formula requires fields absent from the local market-data cache"
                    unsupported.append(record)
                else:
                    supported.append(record)
    return supported, unsupported


def build_factor(
    frame: pd.DataFrame,
    handler: str,
    financial: dict[str, pd.DataFrame] | None = None,
    signal_dates: list[pd.Timestamp] | None = None,
) -> pd.Series:
    if handler in FINANCIAL_HANDLERS:
        if financial is None or signal_dates is None:
            raise RuntimeError(f"Financial cache is required for handler {handler}")
        return build_financial_factor(frame, handler, signal_dates, financial)

    grouped = frame.groupby("instrument", sort=False, observed=True)
    close = frame["close_qfq"]
    open_price = frame["open_qfq"]
    turnover = frame["turnover"]
    dates = frame["date"]
    ret1 = close.div(grouped["close_qfq"].shift(1)).sub(1.0)
    ret40 = close.div(grouped["close_qfq"].shift(40)).sub(1.0)

    if handler == "momentum120":
        return close.div(grouped["close_qfq"].shift(120)).sub(1.0)

    if handler in {"turn_bias", "turn_signal", "weighted_reversal_lowturn", "reversal_turn_eq", "reversal_chip_turn_eq", "reversal_chip_turn_size_eq"}:
        turn21 = grouped_rolling(frame, "turnover", 21, "mean")
        turn504 = grouped_rolling(frame, "turnover", 504, "mean")
        turn_signal = 1.0 - turn21.div(turn504)
    else:
        turn_signal = None

    if handler == "turn_bias":
        return turn21.div(turn504).sub(1.0)
    if handler == "turn_signal":
        return turn_signal

    if handler in {"drawdown120", "drawdown60"}:
        window = 120 if handler == "drawdown120" else 60
        rolling_max = grouped["close_qfq"].rolling(window=window, min_periods=window).max()
        rolling_max = rolling_max.reset_index(level=0, drop=True).reindex(frame.index)
        return cross_rank(1.0 - close.div(rolling_max), dates)

    if handler in {"reversal40", "reversal_turn_eq", "reversal_chip_eq", "reversal_chip_turn_eq", "reversal_chip_turn_size_eq"}:
        reversal_rank = cross_rank(1.0 - ret40, dates)
    else:
        reversal_rank = None

    if handler == "reversal40":
        return reversal_rank

    if handler in {"weighted_reversal_lowturn"}:
        turnover_return = frame.assign(_turnover_return=turnover * ret1)
        weighted_reversal = -grouped_rolling(turnover_return, "_turnover_return", 21, "sum").div(
            grouped_rolling(frame, "turnover", 21, "sum")
        )
        return (
            cross_rank(weighted_reversal, dates)
            + cross_rank(turn_signal, dates)
        ) / 2.0

    if handler in {"reversal_chip_eq", "reversal_chip_turn_eq", "reversal_chip_turn_size_eq", "chip250"}:
        weighted_price = frame["volume"] * (open_price + close) / 2.0
        weighted_frame = frame.assign(_weighted_price=weighted_price)
        vwap = grouped_rolling(weighted_frame, "_weighted_price", 250, "sum").div(
            grouped_rolling(frame, "volume", 250, "sum")
        )
        chip_rank = cross_rank(vwap.div(close).sub(1.0), dates)
    else:
        chip_rank = None

    if handler == "chip250":
        return chip_rank
    if handler == "reversal_chip_eq":
        return (reversal_rank + chip_rank) / 2.0
    if handler == "reversal_turn_eq":
        return (reversal_rank + cross_rank(turn_signal, dates)) / 2.0
    if handler == "reversal_chip_turn_eq":
        return (reversal_rank + chip_rank + cross_rank(turn_signal, dates)) / 3.0
    if handler == "reversal_chip_turn_size_eq":
        cap_rank = cross_rank(frame["total_mv"], dates)
        cap_mean = cap_rank.groupby(dates, sort=False, observed=True).transform("mean")
        cap_std = cap_rank.groupby(dates, sort=False, observed=True).transform("std")
        size_rank = cross_rank(cap_rank.sub(cap_mean).div(cap_std.replace(0.0, np.nan)).mul(-1.0), dates)
        return (reversal_rank + chip_rank + cross_rank(turn_signal, dates) + size_rank) / 4.0
    raise KeyError(f"Unsupported handler: {handler}")


def fidelity_note(handler: str) -> str:
    if handler == "residual_volatility":
        return "proxy: market-model residual volatility, not the platform Barra field"
    if handler in {"reversal_bm_tsrank756", "reversal_bm_cfp_tsrank756"}:
        return "Tushare PIT ratio with strict 756-day rolling rank; local history warmup may shorten periods"
    if handler in {"reversal_bm_ma63", "reversal_bm_cfp_ma63"}:
        return "Tushare PIT ratio with strict 63-day daily moving average"
    if handler in FINANCIAL_HANDLERS:
        return "Tushare PIT financial proxy; consolidated statements and reconstructed TTM"
    return "direct local market-data reconstruction"


def infer_cycle(calendar: list[pd.Timestamp], signal_dates: list[pd.Timestamp]) -> int:
    positions = [calendar.index(date) for date in signal_dates]
    differences = [right - left for left, right in zip(positions, positions[1:]) if right > left]
    if not differences:
        raise RuntimeError("Cannot infer rebalance cycle from one platform signal date")
    return Counter(differences).most_common(1)[0][0]


def fallback_signal_dates(
    calendar: list[pd.Timestamp],
    cycle: int,
    templates: dict[int, list[pd.Timestamp]],
) -> tuple[list[pd.Timestamp], str]:
    template = templates.get(cycle)
    if template:
        return list(template), f"reference_chart_{cycle}d"

    start_position = calendar.index(PLATFORM_START)
    dates = [
        date
        for position, date in enumerate(calendar[start_position::cycle], start=start_position)
        if position + cycle < len(calendar)
    ]
    return dates, "generated_calendar"


def panel_close(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    panel = frame.pivot(index="date", columns="instrument", values="close_qfq")
    return panel.reindex(calendar).sort_index(axis=1).ffill()


def forward_returns(
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
) -> pd.DataFrame:
    positions = [calendar.index(date) + cycle for date in signal_dates]
    if max(positions, default=-1) >= len(calendar):
        raise RuntimeError("Local data does not cover the platform forward target")
    current = close.loc[signal_dates].stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    future = close.iloc[positions].copy()
    future.index = signal_dates
    future = future.stack(dropna=False).rename("future_close").reset_index()
    future = future.rename(columns={"level_0": "date", "level_1": "instrument"})
    result = current.merge(future, on=["date", "instrument"], how="left")
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    return result[["date", "instrument", "forward_return"]]


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def evaluate(
    frame: pd.DataFrame,
    factor_values: pd.Series,
    close: pd.DataFrame,
    platform: dict[str, Any],
    direction: int,
    signal_dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    cycle: int,
) -> dict[str, Any]:
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = factor_values.to_numpy(dtype=float)
    factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]
    returns = forward_returns(close, calendar, signal_dates, cycle)
    data = factor_frame.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    selected_group = GROUPS if direction == 1 else 1
    previous: dict[int, set[str]] = {}
    rank_ics: list[float] = []
    ics: list[float] = []
    group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    group_turnovers: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    period_rows: list[dict[str, Any]] = []

    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = assign_groups(current["factor"])
        rank_ic = current["factor"].rank(method="average").corr(current["forward_return"].rank(method="average"))
        ic = current["factor"].corr(current["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))
        benchmark = float(current["forward_return"].mean())
        row: dict[str, Any] = {"date": date, "stock_count": int(len(current)), "benchmark": benchmark}
        for group in range(1, GROUPS + 1):
            members = set(current.loc[current["group"].eq(group), "instrument"])
            group_return = float(current.loc[current["group"].eq(group), "forward_return"].mean())
            old_members = previous.get(group)
            turnover = (
                1.0 - len(members.intersection(old_members)) / len(members)
                if old_members
                else np.nan
            )
            previous[group] = members
            group_returns[group].append(group_return)
            if np.isfinite(turnover):
                group_turnovers[group].append(float(turnover))
            row[f"excess_{group}"] = group_return - benchmark
            row[f"turnover_{group}"] = turnover
        period_rows.append(row)

    periods = pd.DataFrame(period_rows)
    years = len(periods) * cycle / 252.0
    selected_excess = None
    selected_turnover = None
    if years and len(periods):
        selected_excess = float(periods[f"excess_{selected_group}"].sum() / years)
    if group_turnovers[selected_group]:
        selected_turnover = float(np.mean(group_turnovers[selected_group]))
    selected_cost = selected_turnover * (252.0 / cycle) * ROUND_TRIP_COST if selected_turnover is not None else None
    selected_net = selected_excess - selected_cost if selected_excess is not None and selected_cost is not None else None

    latest_date = signal_dates[-1]
    latest = factor_frame[factor_frame["date"].eq(latest_date)].dropna()
    latest = latest.sort_values(["factor", "instrument"], ascending=[direction == 0, True])
    local_top = latest.head(20)["instrument"].tolist()
    platform_top = [str(row.get("symbol")) for row in platform.get("top", []) if row.get("symbol")]
    platform_group = platform.get("group_metrics", {}).get(selected_group, {})
    platform_rank = platform.get("metrics", {}).get("Rank_IC")
    platform_ic = platform.get("metrics", {}).get("IC_mean")
    platform_net = None

    return {
        "periods": len(periods),
        "cycle": cycle,
        "stock_count_mean": float(periods["stock_count"].mean()) if not periods.empty else None,
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.mean(ics)) if ics else None,
        "selected_group": selected_group,
        "gross_excess": selected_excess,
        "turnover": selected_turnover,
        "annual_cost": selected_cost,
        "net_excess": selected_net,
        "platform_rank_ic": platform_rank,
        "platform_ic_mean": platform_ic,
        "platform_gross_excess": platform_group.get("excessAnnualized"),
        "platform_turnover": platform_group.get("turnoverRate"),
        "top20_overlap": len(set(local_top).intersection(platform_top)) if platform_top else None,
        "local_top20": local_top,
        "platform_top20": platform_top,
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


def write_outputs(
    supported: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    output_root: Path,
    universe: str,
    pool_count: int,
    data_start: pd.Timestamp,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    local_universe = (
        "full-A Tushare qfq rows joined with daily_basic and filtered to .SH/.SZ"
        if universe == "full_a"
        else "fixed ST-filter workflow pool"
    )
    payload = {
        "settings": {
            "data_start": data_start.strftime("%Y%m%d"),
            "end": END.strftime("%Y%m%d"),
            "groups": GROUPS,
            "round_trip_cost": ROUND_TRIP_COST,
            "pool_count": pool_count,
            "local_universe": local_universe,
            "supported_records": len(supported),
            "unsupported_records": len(unsupported),
        },
        "results": rows,
        "unsupported": unsupported,
    }
    (output_root / "positive_factor_local_compare.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Positive-net-excess factors: local reproduction",
        "",
        "The catalog contains every completed saved run whose platform `net_excess_pct` is greater than zero.",
        f"The local side uses `{local_universe}` and qfq Tushare daily data.",
        f"The platform pool is shown per row from the saved workflow registry; local membership follows the selected `{universe}` mode.",
        "Local net excess = arithmetic gross excess - annualized turnover cost using 0.30% one-way cost.",
        "",
        f"- positive records: `{len(supported) + len(unsupported)}`",
        f"- locally reproduced: `{len(rows)}`",
        f"- data-unavailable: `{len(unsupported)}`",
        "",
        "## Locally reproduced",
        "",
        "| run | handler | platform pool | cycle | dates | platform net | local net | delta net (pp) | platform RankIC | local RankIC | platform gross excess | local gross excess | platform turnover | local turnover | Top20 |",
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        def pct(value: Any) -> str:
            return "n/a" if value is None else f"{100 * float(value):.2f}%"

        def num(value: Any) -> str:
            return "n/a" if value is None else f"{float(value):.4f}"

        platform_net = row["platform_net_excess_pct"]
        local_net = row["local_net_excess"]
        delta = None if local_net is None else 100 * local_net - platform_net
        lines.append(
            f"| {row['id']} | {row['handler']} | {row.get('platform_stock_pool', 'unknown')} | {row['cycle']} | {row['date_source']} ({row['platform_chart_periods']}) | {platform_net:.2f}% | {pct(local_net)} | {'n/a' if delta is None else f'{delta:.2f}'} | {num(row['platform_rank_ic'])} | {num(row['local_rank_ic'])} | {pct(row['platform_gross_excess'])} | {pct(row['local_gross_excess'])} | {pct(row['platform_turnover'])} | {pct(row['local_turnover'])} | {row['top20_overlap'] if row['top20_overlap'] is not None else 'n/a'}/20 |"
        )
    lines.extend(
        [
            "",
            "## Fidelity notes",
            "",
            "- Financial records use announcement-date point-in-time joins. Tushare consolidated statements (`comp_type=1`) are selected, and quarterly cumulative statements are converted to TTM.",
            "- `MA(...,63)` and `TS_RANK(...,756)` use daily point-in-time ratios. The local daily cache starts at 2019-07-01, so 756-day formulas have a warmup gap and fewer valid periods than the platform chart.",
            "- `residual_volatility` is a market-model residual-volatility proxy, not the platform's internal Barra field.",
            "- Close net-excess differences do not prove exact field equivalence; local membership follows the selected universe mode.",
            "",
            "## Not reproducible from current local cache",
            "",
            "| run | platform net | formula | reason |",
            "|---|---:|---|---|",
        ]
    )
    for row in unsupported:
        lines.append(
            f"| {row['id']} | {row['platform_net_excess_pct']:.2f}% | `{row.get('formula') or '?'}` | {row['reason']} |"
        )
    (output_root / "positive_factor_local_compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", choices=["st_pool", "full_a"], default="st_pool")
    parser.add_argument(
        "--price-root",
        default=str(CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"),
    )
    parser.add_argument(
        "--cap-root",
        default=str(CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"),
    )
    parser.add_argument("--financial-root", default=str(CACHE_ROOT / "financial"))
    parser.add_argument("--output", default=str(OUTPUT_ROOT))
    parser.add_argument("--data-start", default=DATA_START.strftime("%Y%m%d"))
    args = parser.parse_args()

    data_start = pd.Timestamp(
        pd.to_datetime(args.data_start, format="%Y%m%d" if len(args.data_start) == 8 else None)
    ).normalize()
    if data_start > DATA_START:
        raise SystemExit("--data-start cannot be later than the platform comparison start")
    calendar = [pd.Timestamp(value).normalize() for value in ensure_calendar(data_start, END, token=None)]
    catalog = formula_catalog()
    supported, unsupported = positive_records(catalog)
    configs = platform_configs()
    for record in supported + unsupported:
        record["platform_config"] = configs.get(str(record.get("factor_id")))
    if not supported and not unsupported:
        raise SystemExit("No positive-net-excess records found")

    for record in supported + unsupported:
        if record["raw_result"] and not (PROJECT_ROOT / record["raw_result"]).exists():
            record["reason"] = f"saved platform result is missing: {record['raw_result']}"
            if record in supported:
                supported.remove(record)
                unsupported.append(record)
    supported = [record for record in supported if (PROJECT_ROOT / record["raw_result"]).exists()]

    print(f"positive_records={len(supported) + len(unsupported)} supported={len(supported)} unsupported={len(unsupported)}", flush=True)
    if args.universe == "full_a":
        frame = load_full_a_data(
            Path(args.price_root),
            Path(args.cap_root),
            data_start,
            END,
        )
        pool = set(frame["instrument"].astype(str).unique())
    else:
        frame = load_st_data(DATA_START, END)
        pool = load_st_pool()
        frame = frame[frame["instrument"].isin(pool)].copy()
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(f"local_rows={len(frame)} pool={len(pool)}", flush=True)
    close = panel_close(frame, calendar)

    financial: dict[str, pd.DataFrame] | None = None
    financial_records = [record for record in supported if record["handler"] in FINANCIAL_HANDLERS]
    if financial_records:
        try:
            financial = load_financial_cache(Path(args.financial_root))
            print(
                f"financial_cache=loaded records={len(financial_records)} "
                f"fina_rows={len(financial['fina_indicator'])}",
                flush=True,
            )
        except FileNotFoundError as exc:
            for record in list(financial_records):
                supported.remove(record)
                record["reason"] = str(exc)
                unsupported.append(record)
            financial_records = []

    chart_templates: dict[int, list[pd.Timestamp]] = {}
    chart_records: list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int]] = []
    for record in supported:
        platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
        signal_dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
        signal_dates = [date for date in signal_dates if DATA_START <= date <= END]
        configured_cycle = record.get("configured_cycle")
        if len(signal_dates) >= 2:
            inferred_cycle = infer_cycle(calendar, signal_dates)
            cycle = configured_cycle or inferred_cycle
            if configured_cycle and inferred_cycle != configured_cycle:
                print(
                    f"warning={record['id']}: report_cycle={configured_cycle} chart_cycle={inferred_cycle}; using report cycle",
                    flush=True,
                )
            if cycle not in chart_templates or len(signal_dates) > len(chart_templates[cycle]):
                chart_templates[cycle] = signal_dates
            chart_records.append((record, platform, signal_dates, cycle))
        else:
            chart_records.append((record, platform, [], configured_cycle or 0))

    prepared: list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int, str]] = []
    for record, platform, signal_dates, cycle in chart_records:
        if signal_dates:
            date_source = "platform_chart"
        elif cycle:
            signal_dates, date_source = fallback_signal_dates(calendar, cycle, chart_templates)
        else:
            raise RuntimeError(f"Cannot determine rebalance cycle for {record['id']}")
        if not signal_dates:
            raise RuntimeError(f"No signal dates available for {record['id']}")
        prepared.append((record, platform, signal_dates, cycle, date_source))

    by_handler: dict[str, list[tuple[dict[str, Any], dict[str, Any], list[pd.Timestamp], int, str]]] = {}
    for item in prepared:
        by_handler.setdefault(item[0]["handler"], []).append(item)

    rows: list[dict[str, Any]] = []
    for handler, items in by_handler.items():
        print(f"building={handler} records={len(items)}", flush=True)
        handler_dates = sorted({date for record, _, dates, _, _ in items for date in dates})
        values = build_factor(frame, handler, financial=financial, signal_dates=handler_dates)
        for record, platform, signal_dates, cycle, date_source in items:
            result = evaluate(frame, values, close, platform, record["direction"], signal_dates, calendar, cycle)
            output = {
                "id": record["id"],
                "name": record["name"],
                "report": record["report"],
                "formula": record["formula"],
                "handler": handler,
                "platform_factor_id": record.get("factor_id"),
                "platform_run_id": record.get("run_id"),
                "platform_stock_pool": (record.get("platform_config") or {}).get("stock_pool", "unknown"),
                "platform_market": (record.get("platform_config") or {}).get("market"),
                "platform_start_date": (record.get("platform_config") or {}).get("start_date"),
                "platform_end_date": (record.get("platform_config") or {}).get("end_date"),
                "platform_configured_cycle": (record.get("platform_config") or {}).get("adjustment_cycle"),
                "platform_group_number": (record.get("platform_config") or {}).get("group_number"),
                "platform_factor_direction": (record.get("platform_config") or {}).get("factor_direction"),
                "cycle": cycle,
                "platform_net_excess_pct": record["platform_net_excess_pct"],
                "local_net_excess": result["net_excess"],
                "local_gross_excess": result["gross_excess"],
                "local_turnover": result["turnover"],
                "local_rank_ic": result["rank_ic"],
                "local_ic_mean": result["ic_mean"],
                "local_stock_count_mean": result["stock_count_mean"],
                "platform_rank_ic": result["platform_rank_ic"],
                "platform_ic_mean": result["platform_ic_mean"],
                "platform_gross_excess": result["platform_gross_excess"],
                "platform_turnover": result["platform_turnover"],
                "top20_overlap": result["top20_overlap"],
                "periods": result["periods"],
                "date_source": date_source,
                "platform_chart_periods": len(platform["dates"]),
                "fidelity": fidelity_note(handler),
            }
            rows.append(output)
            print(
                f"{record['id']}: local_net={result['net_excess']!s} platform_net={record['platform_net_excess_pct'] / 100:.6f} "
                f"rank_ic={result['rank_ic']!s} top20={result['top20_overlap']!s}/20",
                flush=True,
            )
        del values

    rows.sort(key=lambda row: row["id"])
    output_root = Path(args.output)
    write_outputs(supported, unsupported, rows, output_root, args.universe, len(pool), data_start)
    print(f"report={output_root / 'positive_factor_local_compare.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
