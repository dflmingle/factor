#!/usr/bin/env python3
"""Compare three previously tested platform factors with local Tushare data.

No platform calls are made here.  The script uses the returned fixed pool from
the ST-filter workflow so the comparison is focused on formula and backtest
semantics rather than a moving stock-universe definition.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from stfilter_local_recheck import (  # noqa: E402
    BATCH_ROOT,
    GROUPS,
    REBALANCE_DAYS,
    REPORT_ROOT as STFILTER_REPORT_ROOT,
    ensure_calendar,
    grouped_rolling,
    load_data,
    load_pool,
    parse_day,
    panel_close,
)


DATA_START = pd.Timestamp("2019-07-01")
START = pd.Timestamp("2021-09-07")
END = pd.Timestamp("2026-09-07")
OUTPUT_ROOT = STFILTER_REPORT_ROOT.parent / "extra_factor_compare"

PLATFORM_RESULTS = {
    "HT13-TURN-BIAS-1M": PROJECT_ROOT
    / "positive-cycle10-candidates.results"
    / "6a9fcdb23e7967143f8faaee.json",
    "HT-WREV-LOWTURN-21D": PROJECT_ROOT
    / "turnover-cost-cycle10-candidates.results"
    / "6a9fb7b46df2a192a47e762c.json",
    "OSR-RSI14-20D": PROJECT_ROOT
    / "turnover-cost-cycle10-candidates.results"
    / "6a9fb8c9a7f535324660b2f6.json",
}

SPECS = {
    "HT13-TURN-BIAS-1M": {
        "formula": "MA(TURNOVER,21) / MA(TURNOVER,504) - 1",
        "direction": 0,
    },
    "HT-WREV-LOWTURN-21D": {
        "formula": "(RANK(-SUM(TURNOVER * RETURNS(CLOSE,1),21) / SUM(TURNOVER,21)) + RANK(1 - MA(TURNOVER,21) / MA(TURNOVER,504))) / 2",
        "direction": 1,
    },
    "OSR-RSI14-20D": {
        "formula": "RANK(1 - RSI(CLOSE,14) / 100)",
        "direction": 1,
    },
}


def cross_rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates, sort=False, observed=True).rank(method="average", pct=True)


def wilder_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    grouped = close.groupby(_FRAME_INSTRUMENT, sort=False, observed=True)
    delta = close - grouped.shift(1)
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    gain_mean = gain.groupby(_FRAME_INSTRUMENT, sort=False, observed=True).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean().reset_index(level=0, drop=True).reindex(close.index)
    loss_mean = loss.groupby(_FRAME_INSTRUMENT, sort=False, observed=True).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean().reset_index(level=0, drop=True).reindex(close.index)
    denominator = gain_mean + loss_mean
    result = 100.0 * gain_mean.div(denominator)
    result = result.mask((loss_mean.eq(0)) & gain_mean.gt(0), 100.0)
    result = result.mask((gain_mean.eq(0)) & loss_mean.gt(0), 0.0)
    return result


_FRAME_INSTRUMENT: pd.Series


def build_factors(frame: pd.DataFrame) -> pd.DataFrame:
    global _FRAME_INSTRUMENT
    _FRAME_INSTRUMENT = frame["instrument"]
    result = frame.copy()
    grouped = result.groupby("instrument", sort=False, observed=True)
    close = result["close_qfq"]
    turnover = result["turnover"]
    ret1 = close.div(grouped["close_qfq"].shift(1)).sub(1.0)
    turn21 = grouped_rolling(result, "turnover", 21, "mean")
    turn504 = grouped_rolling(result, "turnover", 504, "mean")
    sum_turn21 = grouped_rolling(result.assign(_turn_ret=turnover * ret1), "turnover", 21, "sum")
    sum_turn_ret21 = grouped_rolling(
        result.assign(_turn_ret=turnover * ret1), "_turn_ret", 21, "sum"
    )
    turn_bias = pd.Series(turn21 / turn504 - 1.0, index=result.index)
    weighted_reversal = pd.Series(-sum_turn_ret21 / sum_turn21, index=result.index)
    result["HT13-TURN-BIAS-1M"] = turn_bias
    result["HT-WREV-LOWTURN-21D"] = (
        cross_rank(weighted_reversal, result["date"])
        + cross_rank(pd.Series(1.0 - turn21 / turn504, index=result.index), result["date"])
    ) / 2.0
    rsi = wilder_rsi(close)
    result["OSR-RSI14-20D"] = cross_rank(1.0 - rsi / 100.0, result["date"])
    return result


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def evaluate_factor(
    factor_frame: pd.DataFrame,
    name: str,
    platform: dict[str, Any],
    signal_dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
) -> tuple[dict[str, Any], pd.DataFrame]:
    close = panel_close(factor_frame, calendar, "qfq")
    date_to_position = {date: position for position, date in enumerate(calendar)}
    target_dates = [calendar[date_to_position[date] + REBALANCE_DAYS] for date in signal_dates]
    current = close.loc[signal_dates].stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    future = close.loc[target_dates].copy()
    future.index = signal_dates
    future = future.stack(dropna=False).rename("future_close").reset_index()
    future = future.rename(columns={"level_0": "date", "level_1": "instrument"})
    returns = current.merge(future, on=["date", "instrument"], how="left")
    returns["forward_return"] = returns["future_close"].div(returns["current_close"]).sub(1.0)

    data = factor_frame[factor_frame["date"].isin(signal_dates)][
        ["date", "instrument", name]
    ].merge(
        returns[["date", "instrument", "forward_return"]],
        on=["date", "instrument"],
        how="left",
    )
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    previous: dict[int, set[str]] = {}
    rank_ics: list[float] = []
    ics: list[float] = []
    group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    group_turnover: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    period_rows: list[dict[str, Any]] = []

    for date in signal_dates:
        current_data = data[data["date"].eq(date)].copy()
        if len(current_data) < GROUPS * 10:
            continue
        current_data["group"] = assign_groups(current_data[name])
        rank_ic = current_data[name].rank(method="average").corr(
            current_data["forward_return"].rank(method="average")
        )
        ic = current_data[name].corr(current_data["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))
        benchmark = float(current_data["forward_return"].mean())
        row: dict[str, Any] = {"date": date, "stock_count": len(current_data), "benchmark": benchmark}
        for group in range(1, GROUPS + 1):
            members = set(current_data.loc[current_data["group"].eq(group), "instrument"])
            group_return = float(current_data.loc[current_data["group"].eq(group), "forward_return"].mean())
            old_members = previous.get(group)
            turnover = (
                1.0 - len(members.intersection(old_members)) / len(members)
                if old_members
                else np.nan
            )
            previous[group] = members
            group_returns[group].append(group_return)
            if np.isfinite(turnover):
                group_turnover[group].append(float(turnover))
            row[f"group_{group}"] = group_return
            row[f"excess_{group}"] = group_return - benchmark
            row[f"turnover_{group}"] = turnover
        period_rows.append(row)

    periods = pd.DataFrame(period_rows)
    years = len(periods) * REBALANCE_DAYS / 252.0
    groups: dict[str, Any] = {}
    for group in range(1, GROUPS + 1):
        values = np.asarray(group_returns[group], dtype=float)
        excess = periods[f"excess_{group}"].to_numpy(dtype=float) if not periods.empty else np.array([])
        groups[str(group)] = {
            "annualized_return": float(values.sum() / years) if years and len(values) else None,
            "excess_annualized": float(excess.sum() / years) if years and len(excess) else None,
            "turnover": float(np.mean(group_turnover[group])) if group_turnover[group] else None,
            "periods": len(values),
        }
    direction = SPECS[name]["direction"]
    selected_group = 1 if direction == 0 else GROUPS
    top_data = factor_frame[factor_frame["date"].eq(END)][["instrument", name]].dropna()
    local_top = top_data.sort_values([name, "instrument"], ascending=[False, True]).head(20)["instrument"].tolist()
    platform_top = [str(row.get("symbol")) for row in platform.get("top", []) if row.get("symbol")]
    result = {
        "formula": SPECS[name]["formula"],
        "direction": direction,
        "selected_group": selected_group,
        "periods": len(periods),
        "stock_count_mean": float(periods["stock_count"].mean()) if not periods.empty else None,
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.mean(ics)) if ics else None,
        "ic_ir": float(np.mean(ics) / np.std(ics, ddof=1))
        if len(ics) > 1 and np.std(ics, ddof=1) > 0
        else None,
        "groups": groups,
        "platform": {
            "rank_ic": platform.get("metrics", {}).get("Rank_IC"),
            "ic_mean": platform.get("metrics", {}).get("IC_mean"),
            "ic_ir": platform.get("metrics", {}).get("IC_IR"),
            "selected_group": platform.get("group_metrics", {}).get(selected_group, {}),
        },
        "top20_overlap": len(set(local_top) & set(platform_top)) if platform_top else None,
        "local_top20": local_top,
        "platform_top20": platform_top,
    }
    return result, periods.assign(factor=name) if not periods.empty else periods


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def write_report(results: dict[str, Any], periods: pd.DataFrame) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "extra_factor_compare.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    periods.to_csv(OUTPUT_ROOT / "extra_factor_periods.csv", index=False, encoding="utf-8-sig")
    lines = [
        "# Previously tested factor local comparison",
        "",
        "The local side uses the fixed 4,879-symbol pool returned by the completed ST-filter workflow. No new platform run was created.",
        "",
        "| factor | local RankIC | platform RankIC | local IC | platform IC | local selected excess | platform selected excess | local turnover | platform turnover | Top20 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in results["factors"].items():
        group = item["groups"][str(item["selected_group"])]
        platform_group = item["platform"]["selected_group"]
        lines.append(
            "| {name} | {lr:.4f} | {pr:.4f} | {li:.4f} | {pi:.4f} | {le:.2%} | {pe:.2%} | {lt:.2%} | {pt:.2%} | {top}/20 |".format(
                name=name,
                lr=item["rank_ic"],
                pr=item["platform"]["rank_ic"],
                li=item["ic_mean"],
                pi=item["platform"]["ic_mean"],
                le=group["excess_annualized"],
                pe=platform_group.get("excessAnnualized"),
                lt=group["turnover"],
                pt=platform_group.get("turnoverRate"),
                top=item["top20_overlap"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation aids",
            "",
            "- `HT13-TURN-BIAS-1M` isolates the turnover moving-average implementation.",
            "- `HT-WREV-LOWTURN-21D` tests turnover-weighted return plus the same turnover-bias component used by T10-SIZE.",
            "- `OSR-RSI14-20D` is a price-only control; its local RSI uses Wilder exponential smoothing.",
            "",
        ]
    )
    (OUTPUT_ROOT / "extra_factor_compare.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    frame = load_data(DATA_START, END)
    pool = load_pool()
    frame = frame[frame["instrument"].isin(pool)].copy()
    calendar = ensure_calendar(DATA_START, END, token=None)
    platforms = {name: read_platform_run(path) for name, path in PLATFORM_RESULTS.items()}
    factors = build_factors(frame)
    factor_results: dict[str, Any] = {}
    period_frames: list[pd.DataFrame] = []
    for name in SPECS:
        signal_dates = platforms[name]["dates"]
        if max(calendar.index(date) + REBALANCE_DAYS for date in signal_dates) >= len(calendar):
            raise RuntimeError(f"The local data end does not cover the final forward target for {name}")
        item, periods = evaluate_factor(factors, name, platforms[name], signal_dates, calendar)
        factor_results[name] = item
        if not periods.empty:
            period_frames.append(periods)
    results = {
        "settings": {
            "data_start": DATA_START.strftime("%Y%m%d"),
            "start": START.strftime("%Y%m%d"),
            "end": END.strftime("%Y%m%d"),
            "rebalance_days": REBALANCE_DAYS,
            "groups": GROUPS,
            "pool_count": len(pool),
            "rows": len(frame),
            "price_mode": "qfq",
        },
        "factors": factor_results,
    }
    periods = pd.concat(period_frames, ignore_index=True) if period_frames else pd.DataFrame()
    write_report(results, periods)
    print(f"report={OUTPUT_ROOT / 'extra_factor_compare.md'}")
    for name, item in factor_results.items():
        group = item["groups"][str(item["selected_group"])]
        print(
            f"{name}: rank_ic={item['rank_ic']:.4f} ic={item['ic_mean']:.4f} "
            f"selected_excess={group['excess_annualized']:.2%} "
            f"turnover={group['turnover']:.2%} top20={item['top20_overlap']}/20",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
