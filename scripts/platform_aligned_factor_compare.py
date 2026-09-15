#!/usr/bin/env python3
"""Compare locally rebuilt price factors with archived platform runs.

This is an offline diagnostic.  It reads the existing qfq Tushare cache and
saved PandaAI result JSON files; it never creates or runs a platform factor.

The local calculation intentionally follows the platform behaviours that are
observable from the saved runs:

* use the platform's own chart dates as the rebalance dates;
* use one common trading-calendar target date for the forward label;
* use qfq prices and a short as-of window for sparse/suspended rows;
* report arithmetic cumulative curves, which is what the platform charts use;
* keep the executable top-20 check separate from the platform-like panel.

The as-of age limit is a reproducibility parameter, not a claim about a
hard-coded platform rule.  It prevents an indefinitely suspended instrument
from remaining in the current cross-section merely because its last price was
forward-filled.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tushare_factor_recheck import (  # noqa: E402
    GROUPS,
    REBALANCE_DAYS,
    RECHECK_ROOT,
    load_daily_batches,
    load_trade_dates,
)


DEFAULT_START = pd.Timestamp("2021-09-07")
DEFAULT_END = pd.Timestamp("2026-09-07")
DEFAULT_WARMUP = pd.Timestamp("2021-01-01")
DEFAULT_MAX_PRICE_AGE_DAYS = 10
DEFAULT_PRICE_ROOT = RECHECK_ROOT / "qfq" / "daily_batches"
DEFAULT_OUTPUT = RECHECK_ROOT / "reports" / "platform_aligned"

DEFAULT_PLATFORM_RESULTS = {
    "reversal20": PROJECT_ROOT
    / "turnover-cost-cycle10-candidates.results"
    / "6a9fb8400f6165ec8f7f34e4.json",
    "reversal40": PROJECT_ROOT
    / "positive-cycle10-candidates.results"
    / "6a9fcd2e6df2a192a47e765c.json",
    "drawdown120": PROJECT_ROOT
    / "positive-cycle10-candidates.results"
    / "6a9fcd73ecb163ea7228cbee.json",
}

FACTOR_SPECS = {
    "reversal20": {
        "formula": "1 - RETURNS(CLOSE,20)",
        "direction": 1,
        "platform_name": "OSR2-RET20",
    },
    "reversal40": {
        "formula": "RANK(1 - RETURNS(CLOSE,40))",
        "direction": 1,
        "platform_name": "OSR2-RET40",
    },
    "drawdown120": {
        "formula": "RANK(1 - CLOSE / TS_MAX(CLOSE,120))",
        "direction": 1,
        "platform_name": "OSR2-DD120",
    },
    "momentum120": {
        "formula": "RETURNS(CLOSE,120)",
        "direction": 0,
        "platform_name": "HT13-MOMENTUM-120D-D0",
    },
}

# The direction-audited momentum result was saved without chart series/top-20
# payloads, but its headline metrics and group statistics are available in the
# compact report.  Keep them as a reference while leaving the series fields
# explicitly unavailable.
MOMENTUM_REFERENCE = {
    "rank_ic": -0.0665,
    "ic_mean": -0.0438,
    "ic_ir": -0.2947,
    "long_excess_pct": 7.73,
    "turnover_pct": 35.97,
}


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(value, format="%Y%m%d" if len(value) == 8 else None)).normalize()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.number)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100.0
        return float(text)
    except ValueError:
        return None


def chart_series(chart: dict[str, Any] | None) -> tuple[list[pd.Timestamp], list[list[float]]]:
    if not chart:
        return [], []
    x = chart.get("x") or []
    y = chart.get("y") or []
    if not x or not x[0].get("data"):
        return [], []
    dates = [pd.Timestamp(value).normalize() for value in x[0]["data"]]
    values = [[float(value) for value in series.get("data", [])] for series in y]
    return dates, values


def factor_analysis_payload(raw: dict[str, Any]) -> dict[str, Any]:
    direct = raw.get("results", {}).get("factor_analysis")
    if isinstance(direct, dict):
        return direct

    # Some saved CLI responses retain the analysis JSON only inside a node.
    nodes = raw.get("results", {}).get("nodes", {})
    for node in nodes.values():
        if not isinstance(node, dict) or not node.get("result_json"):
            continue
        try:
            nested = json.loads(node["result_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(nested, dict):
            return nested
    return {}


def read_platform_run(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    analysis = factor_analysis_payload(raw)
    factor_rows = analysis.get("query_factor_analysis_data") or analysis.get("factor_data_analysis") or []
    metrics = {
        str(row.get("indicator")): as_float(
            row.get("factor1") if row.get("factor1") is not None else row.get("factor_value")
        )
        for row in factor_rows
        if isinstance(row, dict)
    }

    dates, rank_ic_values = chart_series(analysis.get("query_rank_ic_sequence_chart"))
    _, returns = chart_series(analysis.get("query_return_chart"))
    _, excess = chart_series(analysis.get("query_factor_excess_chart"))
    groups = analysis.get("query_group_return_analysis") or analysis.get("group_return_analysis") or []
    group_metrics: dict[int, dict[str, float | None]] = {}
    for row in groups:
        if not isinstance(row, dict):
            continue
        label = str(row.get("group", ""))
        digits = "".join(character for character in label if character.isdigit())
        if not digits:
            continue
        group_metrics[int(digits)] = {
            key: as_float(row.get(key))
            for key in ["annualizedReturn", "excessAnnualized", "turnoverRate", "sharpeRatio"]
        }

    top = analysis.get("query_last_date_top_factor") or []
    return {
        "path": str(path),
        "metrics": metrics,
        "dates": dates,
        "rank_ic_values": rank_ic_values[0] if rank_ic_values else [],
        "return_cumulative": returns,
        "excess_cumulative": excess,
        "group_metrics": group_metrics,
        "top": top,
    }


def validate_chart_dates(runs: dict[str, dict[str, Any]]) -> list[pd.Timestamp]:
    available = [run["dates"] for run in runs.values() if run["dates"]]
    if not available:
        raise RuntimeError("No saved platform result contains chart dates")
    reference = available[0]
    for dates in available[1:]:
        if dates != reference:
            raise RuntimeError("Saved platform runs use different chart dates; compare them separately")
    return reference


def arithmetic_periods(cumulative: list[float]) -> np.ndarray:
    values = np.asarray(cumulative, dtype=float)
    if not len(values):
        return np.asarray([], dtype=float)
    return np.diff(np.concatenate(([0.0], values)))


def panel_prices(
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
) -> tuple[pd.DataFrame, np.ndarray]:
    observed = frame.pivot(index="date", columns="instrument", values="close").reindex(calendar)
    observed = observed.sort_index(axis=1)
    observed_mask = observed.notna().to_numpy(dtype=bool)
    date_indices = np.arange(len(calendar), dtype=np.int32)[:, None]
    last_seen = np.maximum.accumulate(np.where(observed_mask, date_indices, -1), axis=0)
    close = observed.ffill()
    return close, last_seen


def factor_panels(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "reversal20": 1.0 - close.div(close.shift(20)),
        "reversal40": 1.0 - close.div(close.shift(40)),
        "drawdown120": 1.0 - close.div(close.rolling(120, min_periods=120).max()),
        "momentum120": close.div(close.shift(120)).sub(1.0),
    }


def signal_frame(
    panels: dict[str, pd.DataFrame],
    close: pd.DataFrame,
    last_seen: np.ndarray,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    max_price_age_days: int,
) -> pd.DataFrame:
    positions = [calendar.index(date) for date in signal_dates]
    columns = close.columns
    calendar_values = np.asarray(calendar, dtype="datetime64[ns]")
    rows: list[pd.DataFrame] = []
    for name, panel in panels.items():
        values = panel.iloc[positions].copy()
        values.index = signal_dates
        long = values.stack(dropna=False).rename(name).reset_index()
        long = long.rename(columns={"level_0": "date", "level_1": "instrument"})
        if name == next(iter(panels)):
            rows.append(long)
        else:
            rows[-1] = rows[-1].merge(long, on=["date", "instrument"], how="outer")

    age_values = last_seen[positions]
    age_rows = []
    for row_position, date in enumerate(signal_dates):
        seen = age_values[row_position]
        age = np.full(len(columns), np.inf, dtype=float)
        valid = seen >= 0
        age[valid] = (
            calendar_values[positions[row_position]] - calendar_values[seen[valid]]
        ).astype("timedelta64[D]").astype(float)
        age_rows.append(pd.DataFrame({"date": date, "instrument": columns, "price_age_days": age}))
    result = rows[0].merge(pd.concat(age_rows, ignore_index=True), on=["date", "instrument"], how="left")
    result = result[result["price_age_days"] <= max_price_age_days].copy()
    return result


def add_forward_returns(
    signals: pd.DataFrame,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
) -> pd.DataFrame:
    positions = [calendar.index(date) + REBALANCE_DAYS for date in signal_dates]
    if max(positions, default=-1) >= len(calendar):
        raise RuntimeError("A platform chart date has no common future target date")
    target = close.iloc[positions].copy()
    target.index = signal_dates
    target = target.stack(dropna=False).rename("future_close").reset_index()
    target = target.rename(columns={"level_0": "date", "level_1": "instrument"})
    current = close.loc[signal_dates].copy()
    current = current.stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    result = signals.merge(target, on=["date", "instrument"], how="left").merge(
        current, on=["date", "instrument"], how="left"
    )
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    result = result.replace([np.inf, -np.inf], np.nan)
    return result


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def correlation(left: Iterable[float], right: Iterable[float]) -> dict[str, float | int | None]:
    left_values = list(left)
    right_values = list(right)
    size = min(len(left_values), len(right_values))
    joined = pd.DataFrame({"local": left_values[:size], "platform": right_values[:size]}).replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if joined.empty:
        return {"n": 0, "corr": None, "mean_delta": None, "rmse": None}
    delta = joined["local"] - joined["platform"]
    return {
        "n": int(len(joined)),
        "corr": float(joined["local"].corr(joined["platform"])) if len(joined) > 1 else None,
        "mean_delta": float(delta.mean()),
        "rmse": float(np.sqrt(np.mean(delta**2))),
    }


def evaluate_factor(
    data: pd.DataFrame,
    name: str,
    platform: dict[str, Any],
    signal_dates: list[pd.Timestamp],
) -> tuple[dict[str, Any], pd.DataFrame]:
    factor_data = data[["date", "instrument", name, "forward_return"]].copy()
    factor_data = factor_data.replace([np.inf, -np.inf], np.nan).dropna()
    periods: list[dict[str, Any]] = []
    previous: dict[int, set[str]] = {}
    rank_ics: list[float] = []
    ics: list[float] = []
    group_returns: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}
    group_turnovers: dict[int, list[float]] = {group: [] for group in range(1, GROUPS + 1)}

    for date in signal_dates:
        current = factor_data[factor_data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = assign_groups(current[name])
        rank_ic = current[name].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        ic = current[name].corr(current["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))
        benchmark = float(current["forward_return"].mean())
        row: dict[str, Any] = {
            "date": day_text(date),
            "stock_count": int(len(current)),
            "benchmark_return": benchmark,
        }
        for group in range(1, GROUPS + 1):
            members = set(current.loc[current["group"].eq(group), "instrument"])
            group_return = float(current.loc[current["group"].eq(group), "forward_return"].mean())
            old_members = previous.get(group)
            turnover = (
                float(1.0 - len(members.intersection(old_members)) / len(members))
                if old_members
                else np.nan
            )
            previous[group] = members
            group_returns[group].append(group_return)
            if np.isfinite(turnover):
                group_turnovers[group].append(turnover)
            row[f"group_{group}"] = group_return
            row[f"excess_{group}"] = group_return - benchmark
            row[f"turnover_{group}"] = turnover
        periods.append(row)

    local_periods = pd.DataFrame(periods)
    if not local_periods.empty:
        local_periods["date"] = pd.to_datetime(local_periods["date"])
    years = len(local_periods) * REBALANCE_DAYS / 252.0
    low = GROUPS if FACTOR_SPECS[name]["direction"] == 1 else 1
    group_summary: dict[str, Any] = {}
    for group in range(1, GROUPS + 1):
        values = np.asarray(group_returns[group], dtype=float)
        excess = local_periods[f"excess_{group}"].to_numpy(dtype=float) if not local_periods.empty else values
        group_summary[str(group)] = {
            "arithmetic_cumulative_return": float(values.sum()) if len(values) else None,
            "platform_style_annualized_return": float(values.sum() / years) if years and len(values) else None,
            "platform_style_annualized_excess": float(excess.sum() / years) if years and len(excess) else None,
            "turnover": float(np.nanmean(group_turnovers[group])) if group_turnovers[group] else None,
            "periods": int(len(values)),
        }

    local_metric = group_summary[str(low)]
    platform_metric = platform.get("group_metrics", {}).get(low, {})
    local_period_values = local_periods[f"group_{low}"].to_numpy(dtype=float) if not local_periods.empty else []
    local_excess_values = local_periods[f"excess_{low}"].to_numpy(dtype=float) if not local_periods.empty else []
    platform_return_values = []
    platform_excess_values = []
    if len(platform.get("return_cumulative", [])) >= low:
        platform_return_values = arithmetic_periods(platform["return_cumulative"][low - 1])
    if len(platform.get("excess_cumulative", [])) >= low:
        platform_excess_values = arithmetic_periods(platform["excess_cumulative"][low - 1])

    output = {
        "formula": FACTOR_SPECS[name]["formula"],
        "direction": FACTOR_SPECS[name]["direction"],
        "platform_result": platform.get("path"),
        "periods": int(len(local_periods)),
        "rank_ic": float(np.nanmean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.nanmean(ics)) if ics else None,
        "ic_ir": float(np.nanmean(ics) / np.nanstd(ics, ddof=1))
        if len(ics) > 1 and np.nanstd(ics, ddof=1) > 0
        else None,
        "direction_selected_group": low,
        "direction_selected": local_metric,
        "platform_reference_group": platform_metric,
        "comparison": {
            "rank_ic": correlation(rank_ics, platform.get("rank_ic_values", [])),
            "period_return": correlation(local_period_values, platform_return_values),
            "cumulative_return": correlation(
                np.cumsum(local_period_values), platform.get("return_cumulative", [[]])[low - 1]
                if len(platform.get("return_cumulative", [])) >= low
                else [],
            ),
            "period_excess": correlation(local_excess_values, platform_excess_values),
            "cumulative_excess": correlation(
                np.cumsum(local_excess_values), platform.get("excess_cumulative", [[]])[low - 1]
                if len(platform.get("excess_cumulative", [])) >= low
                else [],
            ),
            "turnover_pct": {
                "local": None if local_metric["turnover"] is None else local_metric["turnover"] * 100.0,
                "platform": platform_metric.get("turnoverRate"),
            },
        },
    }
    return output, local_periods


def top_overlap(
    data: pd.DataFrame,
    name: str,
    platform: dict[str, Any],
    latest_date: pd.Timestamp,
) -> dict[str, Any] | None:
    platform_rows = [
        row
        for row in platform.get("top", [])
        if row.get("date") and pd.Timestamp(row["date"]).normalize() == latest_date
    ]
    if not platform_rows:
        return None
    current = data[data["date"].eq(latest_date)][["instrument", name, "price_age_days"]].dropna()
    ascending = FACTOR_SPECS[name]["direction"] == 0
    local_symbols = (
        current.sort_values([name, "instrument"], ascending=[ascending, True])
        .head(len(platform_rows))["instrument"]
        .astype(str)
        .tolist()
    )
    platform_symbols = [str(row.get("symbol")) for row in platform_rows]
    platform_set = set(platform_symbols)
    local_set = set(local_symbols)
    return {
        "date": day_text(latest_date),
        "platform_top_n": len(platform_symbols),
        "local_top_n": len(local_symbols),
        "overlap": len(platform_set & local_set),
        "overlap_pct": len(platform_set & local_set) / len(platform_set),
        "platform_symbols": platform_symbols,
        "local_symbols": local_symbols,
        "platform_only": sorted(platform_set - local_set),
        "local_only": sorted(local_set - platform_set),
    }


def write_report(result: dict[str, Any], output: Path) -> None:
    lines = [
        "# Platform-aligned local factor comparison",
        "",
        "This is an offline comparison of the cached Tushare qfq data and archived platform result JSON files.",
        "",
        f"- window: `{result['settings']['start']}..{result['settings']['end']}`; warm-up: `{result['settings']['warmup']}`",
        f"- market: `{result['settings']['market']}`; rebalance: `{REBALANCE_DAYS}` trading days; groups: `{GROUPS}`",
        f"- as-of price age limit: `{result['settings']['max_price_age_days']}` calendar days",
        "- platform-style cumulative curves use arithmetic cumulative returns; local executable output is not substituted for them.",
        "",
        "| factor | direction | local RankIC | platform RankIC | local annual excess | platform annual excess | local turnover | platform turnover | top20 overlap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in result["factors"].items():
        selected = item["direction_selected"]
        reference = item["platform_reference_group"]
        platform_rank_ic = item.get("platform_metrics", {}).get("Rank_IC")
        local_turnover = selected.get("turnover")
        platform_turnover = reference.get("turnoverRate")
        overlap = item.get("latest_top20_overlap")
        lines.append(
            "| {name} | {direction} | {local_rank} | {platform_rank} | {local_excess} | {platform_excess} | {local_turnover} | {platform_turnover} | {overlap} |".format(
                name=name,
                direction=FACTOR_SPECS[name]["direction"],
                local_rank="n/a" if item.get("rank_ic") is None else f"{item['rank_ic']:.4f}",
                platform_rank="n/a" if platform_rank_ic is None else f"{platform_rank_ic:.4f}",
                local_excess="n/a"
                if selected.get("platform_style_annualized_excess") is None
                else f"{100 * selected['platform_style_annualized_excess']:.2f}%",
                platform_excess="n/a"
                if reference.get("excessAnnualized") is None
                else f"{100 * reference['excessAnnualized']:.2f}%",
                local_turnover="n/a" if local_turnover is None else f"{100 * local_turnover:.2f}%",
                platform_turnover="n/a"
                if platform_turnover is None
                else f"{100 * platform_turnover:.2f}%",
                overlap="n/a" if overlap is None else f"{overlap['overlap']}/{overlap['platform_top_n']}",
            )
        )
    lines.extend(
        [
            "",
            "The momentum direction-audit result has headline metrics but no chart/top-20 payload in its saved response, so sequence and overlap comparisons are intentionally unavailable for that row.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def analyze(
    start: pd.Timestamp,
    end: pd.Timestamp,
    warmup: pd.Timestamp,
    price_root: Path,
    output_root: Path,
    market: str,
    max_price_age_days: int,
    platform_paths: dict[str, Path],
) -> dict[str, Any]:
    platform = {name: read_platform_run(path) for name, path in platform_paths.items()}
    chart_dates = validate_chart_dates(platform)
    chart_dates = [date for date in chart_dates if start <= date <= end]
    if not chart_dates:
        raise RuntimeError("No platform chart dates fall inside the requested window")

    top_dates = []
    for run in platform.values():
        top_dates.extend(
            pd.Timestamp(row["date"]).normalize()
            for row in run.get("top", [])
            if row.get("date")
        )
    latest_date = max(top_dates, default=end)
    signal_dates = sorted(set(chart_dates + [latest_date]))

    frame = load_daily_batches(warmup, end, price_root, market=market)
    calendar = load_trade_dates(warmup, end)
    close, last_seen = panel_prices(frame, calendar)
    panels = factor_panels(close)
    signals = signal_frame(panels, close, last_seen, calendar, signal_dates, max_price_age_days)
    evaluated = add_forward_returns(signals[signals["date"].isin(chart_dates)].copy(), close, calendar, chart_dates)

    factors: dict[str, Any] = {}
    period_frames: dict[str, pd.DataFrame] = {}
    for name in FACTOR_SPECS:
        platform_run = platform.get(name, {})
        if not platform_run:
            platform_run = {
                "path": None,
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
        local, periods = evaluate_factor(evaluated, name, platform_run, chart_dates)
        local["platform_metrics"] = platform_run.get("metrics", {})
        local["latest_top20_overlap"] = top_overlap(signals, name, platform_run, latest_date)
        factors[name] = local
        period_frames[name] = periods

    output_root.mkdir(parents=True, exist_ok=True)
    serializable = {
        "settings": {
            "start": day_text(start),
            "end": day_text(end),
            "warmup": day_text(warmup),
            "market": market,
            "rebalance_days": REBALANCE_DAYS,
            "groups": GROUPS,
            "max_price_age_days": max_price_age_days,
            "price_root": str(price_root),
            "platform_chart_dates": len(chart_dates),
            "latest_top_date": day_text(latest_date),
        },
        "data": {
            "rows": int(len(frame)),
            "instruments": int(frame["instrument"].nunique()),
            "panel_dates": int(len(calendar)),
            "panel_instruments": int(len(close.columns)),
            "signal_rows": int(len(signals)),
            "evaluated_rows": int(len(evaluated)),
        },
        "factors": factors,
    }
    (output_root / "platform_aligned_result.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    for name, periods in period_frames.items():
        periods.to_csv(output_root / f"{name}_periods.csv", index=False, encoding="utf-8-sig")
    write_report(serializable, output_root / "platform_aligned_report.md")
    return serializable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="20210907")
    parser.add_argument("--end", default="20260907")
    parser.add_argument("--warmup", default="20210101")
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--market", choices=["all", "hs"], default="hs")
    parser.add_argument("--max-price-age-days", type=int, default=DEFAULT_MAX_PRICE_AGE_DAYS)
    args = parser.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end)
    warmup = parse_date(args.warmup)
    if not warmup <= start <= end:
        raise SystemExit("Require warmup <= start <= end")
    missing = [str(path) for path in DEFAULT_PLATFORM_RESULTS.values() if not path.exists()]
    if missing:
        raise SystemExit("Missing archived platform result(s): " + "; ".join(missing))

    result = analyze(
        start,
        end,
        warmup,
        Path(args.price_root),
        Path(args.output),
        args.market,
        max(0, args.max_price_age_days),
        DEFAULT_PLATFORM_RESULTS,
    )
    print(f"report={Path(args.output) / 'platform_aligned_report.md'}")
    for name, item in result["factors"].items():
        selected = item["direction_selected"]
        overlap = item.get("latest_top20_overlap")
        print(
            f"{name}: rank_ic={item.get('rank_ic')!s} "
            f"annual_excess={selected.get('platform_style_annualized_excess')!s} "
            f"turnover={selected.get('turnover')!s} "
            f"top20={overlap.get('overlap')}/{overlap.get('platform_top_n')}" if overlap else
            f"{name}: rank_ic={item.get('rank_ic')!s} top20=n/a",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
