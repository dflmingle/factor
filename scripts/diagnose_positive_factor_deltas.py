#!/usr/bin/env python3
"""Break down large local/platform net-excess differences.

This is an offline diagnostic.  It reads the saved ``*.report.csv`` records,
uses each row's explicit ``raw_result`` path, and rebuilds the selected local
factor with the existing Tushare implementation.  It never creates or runs a
PandaAI factor.
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

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    DATA_START,
    END,
    GROUPS,
    ROUND_TRIP_COST,
    build_factor,
    formula_catalog,
    positive_records,
)
from stfilter_local_recheck import (  # noqa: E402
    CACHE_ROOT,
    ensure_calendar,
    load_data as load_st_data,
    load_pool as load_st_pool,
    panel_close,
)


DEFAULT_START = pd.Timestamp("2021-09-07")
DEFAULT_OUTPUT = CACHE_ROOT / "reports" / "positive_factor_delta_diagnosis"
DEFAULT_MIN_DELTA_PP = 2.0


def parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(
        pd.to_datetime(value, format="%Y%m%d" if len(value) == 8 else None)
    ).normalize()


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def asof_price_panel(
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    observed = frame.pivot(index="date", columns="instrument", values="close_qfq")
    observed = observed.reindex(calendar).sort_index(axis=1)
    close = observed.ffill()
    observed_mask = observed.notna().to_numpy(dtype=bool)
    date_indices = np.arange(len(calendar), dtype=np.int32)[:, None]
    last_seen = np.maximum.accumulate(np.where(observed_mask, date_indices, -1), axis=0)
    age = np.full(last_seen.shape, np.inf, dtype=float)
    valid = last_seen >= 0
    row_indices = np.arange(len(calendar), dtype=np.int32)[:, None]
    age[valid] = (row_indices - last_seen)[valid]
    age_frame = pd.DataFrame(age, index=calendar, columns=close.columns)
    return close, age_frame


def platform_period_frame(platform: dict[str, Any], group: int) -> pd.DataFrame:
    dates = pd.DatetimeIndex(
        pd.to_datetime(platform.get("dates", []), errors="coerce")
    ).normalize()
    returns = np.asarray(platform.get("return_cumulative", [[]]), dtype=float)
    excess = np.asarray(platform.get("excess_cumulative", [[]]), dtype=float)
    if returns.ndim != 2 or returns.shape[0] < group:
        raise RuntimeError(f"Platform result has no return chart for group {group}")
    if excess.ndim != 2 or excess.shape[0] < group:
        raise RuntimeError(f"Platform result has no excess chart for group {group}")
    if len(dates) != len(returns[group - 1]) or len(dates) != len(excess[group - 1]):
        raise RuntimeError("Platform chart date/value lengths do not match")
    group_cumulative = returns[group - 1]
    excess_cumulative = excess[group - 1]
    group_period = np.diff(np.concatenate(([0.0], group_cumulative)))
    excess_period = np.diff(np.concatenate(([0.0], excess_cumulative)))
    return pd.DataFrame(
        {
            "date": dates.normalize(),
            "platform_group_return": group_period,
            "platform_group_cumulative": group_cumulative,
            "platform_excess": excess_period,
            "platform_excess_cumulative": excess_cumulative,
            "platform_benchmark": group_period - excess_period,
        }
    )


def local_factor_periods(
    frame: pd.DataFrame,
    factor_values: pd.Series,
    close: pd.DataFrame,
    price_age: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    direction: int,
    max_age_trade_days: int | None,
    label_offset: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = {date: index for index, date in enumerate(calendar)}
    if any(date not in positions for date in signal_dates):
        raise RuntimeError("A platform signal date is absent from the local trade calendar")
    current_positions = [positions[date] + label_offset for date in signal_dates]
    target_positions = [position + cycle for position in current_positions]
    if min(current_positions, default=0) < 0:
        raise RuntimeError("A platform signal date has no local current label date")
    if max(target_positions, default=-1) >= len(calendar):
        raise RuntimeError("Local data does not cover the platform forward target")

    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = pd.to_numeric(factor_values.to_numpy(), errors="coerce")
    factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]

    current = close.iloc[current_positions].copy()
    current.index = signal_dates
    current = current.stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    future = close.iloc[target_positions].copy()
    future.index = signal_dates
    future = future.stack(dropna=False).rename("future_close").reset_index()
    future = future.rename(columns={"level_0": "date", "level_1": "instrument"})
    current["date"] = pd.to_datetime(current["date"], errors="coerce").dt.normalize()
    future["date"] = pd.to_datetime(future["date"], errors="coerce").dt.normalize()
    returns = current.merge(future, on=["date", "instrument"], how="left")
    returns["forward_return"] = returns["future_close"].div(returns["current_close"]).sub(1.0)

    if max_age_trade_days is not None:
        current_age = price_age.iloc[current_positions].copy()
        current_age.index = signal_dates
        current_age = current_age.stack(dropna=False).rename("current_age").reset_index()
        current_age = current_age.rename(columns={"level_0": "date", "level_1": "instrument"})
        target_age = price_age.iloc[target_positions].copy()
        target_age.index = signal_dates
        target_age = target_age.stack(dropna=False).rename("target_age").reset_index()
        target_age = target_age.rename(columns={"level_0": "date", "level_1": "instrument"})
        returns = returns.merge(current_age, on=["date", "instrument"], how="left")
        returns = returns.merge(target_age, on=["date", "instrument"], how="left")
        returns = returns[
            returns["current_age"].le(max_age_trade_days)
            & returns["target_age"].le(max_age_trade_days)
        ]

    data = factor_frame.merge(
        returns[["date", "instrument", "forward_return"]],
        on=["date", "instrument"],
        how="left",
    )
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    selected_group = GROUPS if direction == 1 else 1
    previous: dict[int, set[str]] = {}
    rows: list[dict[str, Any]] = []
    for date in signal_dates:
        current_data = data[data["date"].eq(date)].copy()
        if len(current_data) < GROUPS * 10:
            continue
        current_data["group"] = np.ceil(
            current_data["factor"].rank(method="first") * GROUPS / len(current_data)
        ).astype(int).clip(1, GROUPS)
        benchmark = float(current_data["forward_return"].mean())
        rank_ic = current_data["factor"].rank(method="average").corr(
            current_data["forward_return"].rank(method="average")
        )
        row: dict[str, Any] = {
            "date": date,
            "local_stock_count": int(len(current_data)),
            "local_benchmark": benchmark,
            "local_rank_ic": clean_float(rank_ic),
        }
        for group in range(1, GROUPS + 1):
            members = set(current_data.loc[current_data["group"].eq(group), "instrument"])
            group_return = float(
                current_data.loc[current_data["group"].eq(group), "forward_return"].mean()
            )
            old_members = previous.get(group)
            turnover = (
                float(1.0 - len(members.intersection(old_members)) / len(members))
                if old_members
                else np.nan
            )
            previous[group] = members
            row[f"local_group_{group}"] = group_return
            row[f"local_excess_{group}"] = group_return - benchmark
            row[f"local_turnover_{group}"] = clean_float(turnover)
            if group == selected_group:
                row["selected_members"] = ",".join(sorted(members))
        rows.append(row)

    periods = pd.DataFrame(rows)
    if periods.empty:
        return periods, data
    return periods, data


def add_platform_columns(local_periods: pd.DataFrame, platform: dict[str, Any], group: int) -> pd.DataFrame:
    platform_periods = platform_period_frame(platform, group)
    result = local_periods.merge(platform_periods, on="date", how="inner")
    result["delta_group_return"] = result[f"local_group_{group}"] - result["platform_group_return"]
    result["delta_excess"] = result[f"local_excess_{group}"] - result["platform_excess"]
    result["delta_benchmark"] = result["local_benchmark"] - result["platform_benchmark"]
    result["local_cumulative_group"] = (1.0 + result[f"local_group_{group}"]).cumprod() - 1.0
    result["local_cumulative_excess"] = (1.0 + result[f"local_excess_{group}"]).cumprod() - 1.0
    result["delta_cumulative_group"] = (
        result["local_cumulative_group"] - result["platform_group_cumulative"]
    )
    result["delta_cumulative_excess"] = (
        result["local_cumulative_excess"] - result["platform_excess_cumulative"]
    )
    return result


def correlation(left: pd.Series, right: pd.Series) -> float | None:
    joined = pd.concat([left.rename("local"), right.rename("platform")], axis=1).dropna()
    if len(joined) < 2:
        return None
    return clean_float(joined["local"].corr(joined["platform"]))


def metric_summary(
    periods: pd.DataFrame,
    platform: dict[str, Any],
    group: int,
    record: dict[str, Any],
    max_age_trade_days: int | None,
) -> dict[str, Any]:
    if periods.empty:
        raise RuntimeError(f"No local periods for {record['id']}")
    local_excess = periods[f"local_excess_{group}"]
    local_group = periods[f"local_group_{group}"]
    local_turnover = periods[f"local_turnover_{group}"].dropna()
    cycle = int(record["configured_cycle"] or 0)
    years = len(periods) * cycle / 252.0
    local_gross = float(local_excess.sum() / years)
    local_turn = float(local_turnover.mean()) if not local_turnover.empty else None
    local_cost = (
        local_turn * (252.0 / cycle) * ROUND_TRIP_COST
        if local_turn is not None and cycle
        else None
    )
    local_net = local_gross - local_cost if local_cost is not None else None
    platform_group = platform.get("group_metrics", {}).get(group, {})
    platform_excess = periods["platform_excess"]
    excess_delta = periods["delta_excess"]
    largest = periods.loc[excess_delta.abs().idxmax()]
    cumulative_last = periods.iloc[-1]
    return {
        "id": record["id"],
        "name": record["name"],
        "handler": record["handler"],
        "cycle": cycle,
        "direction": int(record["direction"]),
        "selected_group": group,
        "max_age_trade_days": max_age_trade_days,
        "periods": int(len(periods)),
        "local_stock_count_mean": float(periods["local_stock_count"].mean()),
        "local_stock_count_min": int(periods["local_stock_count"].min()),
        "local_stock_count_max": int(periods["local_stock_count"].max()),
        "platform_net_excess_pct": record["platform_net_excess_pct"],
        "platform_gross_excess_pct": record["platform_gross_excess_pct"],
        "platform_turnover_pct": record["platform_turnover_pct"],
        "local_gross_excess_pct": local_gross * 100.0,
        "local_turnover_pct": None if local_turn is None else local_turn * 100.0,
        "local_net_excess_pct": None if local_net is None else local_net * 100.0,
        "delta_net_pp": None if local_net is None else local_net * 100.0 - record["platform_net_excess_pct"],
        "delta_gross_pp": local_gross * 100.0 - record["platform_gross_excess_pct"],
        "delta_turnover_pp": (
            None if local_turn is None else local_turn * 100.0 - record["platform_turnover_pct"]
        ),
        "period_group_return_corr": correlation(local_group, periods["platform_group_return"]),
        "period_excess_corr": correlation(local_excess, platform_excess),
        "period_benchmark_corr": correlation(
            periods["local_benchmark"], periods["platform_benchmark"]
        ),
        "cumulative_excess_corr": correlation(
            periods["local_cumulative_excess"], periods["platform_excess_cumulative"]
        ),
        "mean_delta_excess_pp": float(excess_delta.mean() * 100.0),
        "rmse_delta_excess_pp": float(np.sqrt(np.mean(excess_delta**2)) * 100.0),
        "largest_abs_delta_date": day_text(pd.Timestamp(largest["date"])),
        "largest_abs_delta_excess_pp": float(largest["delta_excess"] * 100.0),
        "last_cumulative_delta_excess_pp": float(
            cumulative_last["delta_cumulative_excess"] * 100.0
        ),
        "platform_group_excess_pct": (
            None if platform_group.get("excessAnnualized") is None else platform_group["excessAnnualized"] * 100.0
        ),
        "raw_result": record["raw_result"],
    }


def latest_top_check(
    frame: pd.DataFrame,
    values: pd.Series,
    platform: dict[str, Any],
    direction: int,
) -> dict[str, Any] | None:
    rows = [row for row in platform.get("top", []) if row.get("symbol") and row.get("date")]
    if not rows:
        return None
    dates = [pd.Timestamp(row["date"]).normalize() for row in rows]
    latest_date = max(dates)
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = pd.to_numeric(values.to_numpy(), errors="coerce")
    current = factor_frame[factor_frame["date"].eq(latest_date)].dropna()
    ascending = direction == 0
    local_symbols = (
        current.sort_values(["factor", "instrument"], ascending=[ascending, True])
        .head(len(rows))["instrument"]
        .astype(str)
        .tolist()
    )
    platform_symbols = [str(row["symbol"]) for row in rows if pd.Timestamp(row["date"]).normalize() == latest_date]
    overlap = len(set(local_symbols) & set(platform_symbols))
    st_names = [str(row.get("name", "")) for row in rows if str(row.get("name", "")).startswith("*ST")]
    return {
        "date": day_text(latest_date),
        "platform_top_n": len(platform_symbols),
        "local_top_n": len(local_symbols),
        "overlap": overlap,
        "overlap_pct": overlap / len(platform_symbols) if platform_symbols else None,
        "platform_st_name_count": len(st_names),
        "platform_symbols": platform_symbols,
        "local_symbols": local_symbols,
        "platform_only": sorted(set(platform_symbols) - set(local_symbols)),
        "local_only": sorted(set(local_symbols) - set(platform_symbols)),
    }


def write_markdown(
    summary: list[dict[str, Any]],
    output: Path,
    settings: dict[str, Any],
    top_checks: dict[str, Any],
) -> None:
    lines = [
        "# Large platform/local factor deltas",
        "",
        "Offline diagnosis of saved platform runs. The platform side is read from each report row's explicit `raw_result`.",
        "",
        f"- local data start: `{settings['data_start']}`",
        f"- local pool: `{settings['pool_count']}` {settings['universe']}",
        f"- price: qfq; window: `{settings['start']}..{settings['end']}`; groups: `{GROUPS}`",
        f"- stale-price rule: `{settings['max_age_trade_days']}` trade days; `null` means the prior comparison's indefinite forward-fill",
        f"- selected records: `{len(summary)}`; threshold: `{settings['min_delta_pp']:.2f}` pp absolute net-excess delta",
        "",
        "## Summary",
        "",
        "| factor | cycle | platform net | local net | delta pp | gross delta pp | turnover delta pp | period excess corr | cumulative excess corr | largest delta date |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(summary, key=lambda item: abs(item["delta_net_pp"] or 0), reverse=True):
        def number(key: str, suffix: str = "") -> str:
            value = row.get(key)
            return "n/a" if value is None else f"{value:.2f}{suffix}"

        lines.append(
            f"| {row['name']} | {row['cycle']} | {row['platform_net_excess_pct']:.2f}% | "
            f"{number('local_net_excess_pct', '%')} | {number('delta_net_pp')} | "
            f"{number('delta_gross_pp')} | {number('delta_turnover_pp')} | "
            f"{number('period_excess_corr')} | {number('cumulative_excess_corr')} | "
            f"{row['largest_abs_delta_date']} ({row['largest_abs_delta_excess_pp']:.2f} pp) |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The period correlations compare local group-selected returns with the period differences of the platform cumulative chart. A high RankIC match with a low return-path match points away from factor direction and toward portfolio membership, price/return labeling, or missing-row handling.",
            "",
            "## Latest top-20 checks",
            "",
            "| factor | date | overlap | platform *ST names |",
            "|---|---|---:|---:|",
        ]
    )
    for item in top_checks.values():
        if item:
            lines.append(
                f"| {item['name']} | {item['date']} | {item['overlap']}/{item['platform_top_n']} | {item['platform_st_name_count']} |"
            )
    lines.extend(
        [
            "",
            "Detailed per-period files are named `<factor>_periods.csv`; the matching `<factor>.json` includes the top-20 symbol lists and paths.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    data_start = parse_date(args.data_start)
    if data_start > DATA_START:
        raise SystemExit("--data-start cannot be later than the platform comparison start")
    catalog = formula_catalog()
    supported, _ = positive_records(catalog)
    comparison_path = Path(args.compare_json)
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison_by_id = {
        str(item["id"]): item for item in comparison.get("results", [])
    }
    records = [
        row
        for row in supported
        if row["raw_result"]
        and (PROJECT_ROOT / row["raw_result"]).exists()
        and row["id"] in comparison_by_id
        and comparison_by_id[row["id"]].get("local_net_excess") is not None
        and abs(
            100.0 * comparison_by_id[row["id"]]["local_net_excess"]
            - row["platform_net_excess_pct"]
        )
        >= args.min_delta_pp
    ]
    chart_records = []
    for record in records:
        platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
        selected_group = GROUPS if record["direction"] == 1 else 1
        returns = np.asarray(platform.get("return_cumulative", [[]]), dtype=float)
        excess = np.asarray(platform.get("excess_cumulative", [[]]), dtype=float)
        if (
            not platform.get("dates")
            or returns.ndim != 2
            or excess.ndim != 2
            or returns.shape[0] < selected_group
            or excess.shape[0] < selected_group
        ):
            print(
                f"skip={record['name']}: saved platform result has no complete return chart",
                flush=True,
            )
            continue
        chart_records.append(record)
    records = chart_records
    if not records:
        raise RuntimeError("No positive records meet the requested delta threshold")

    print(f"selected_records={len(records)}", flush=True)
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
    calendar = [pd.Timestamp(value).normalize() for value in ensure_calendar(data_start, END, token=None)]
    close, price_age = asof_price_panel(frame, calendar)

    financial: dict[str, pd.DataFrame] | None = None
    if any(row["handler"] in FINANCIAL_HANDLERS for row in records):
        financial = load_financial_cache(Path(args.financial_root))
        print(f"financial_cache=loaded endpoints={len(financial)}", flush=True)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["handler"], []).append(record)

    all_summary: list[dict[str, Any]] = []
    all_top_checks: dict[str, Any] = {}
    for handler, handler_records in grouped.items():
        signal_dates = sorted(
            {
                pd.Timestamp(value).normalize()
                for record in handler_records
                for value in read_platform_run(PROJECT_ROOT / record["raw_result"])["dates"]
            }
            | {
                pd.Timestamp(row["date"]).normalize()
                for record in handler_records
                for row in read_platform_run(PROJECT_ROOT / record["raw_result"]).get("top", [])
                if row.get("date")
            }
        )
        values = build_factor(frame, handler, financial=financial, signal_dates=signal_dates)
        for record in handler_records:
            platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
            signal_dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
            cycle = int(record["configured_cycle"] or 0)
            if not cycle:
                raise RuntimeError(f"Missing configured cycle for {record['id']}")
            selected_group = GROUPS if record["direction"] == 1 else 1
            periods, _ = local_factor_periods(
                frame,
                values,
                close,
                price_age,
                calendar,
                signal_dates,
                cycle,
                record["direction"],
                args.max_age_trade_days,
                args.label_offset,
            )
            periods = add_platform_columns(periods, platform, selected_group)
            stem = record["id"].replace(":", "__").replace("/", "_")
            periods.to_csv(output / f"{stem}_periods.csv", index=False, encoding="utf-8-sig")
            top = latest_top_check(frame, values, platform, record["direction"])
            if top:
                top["name"] = record["name"]
                all_top_checks[record["id"]] = top
            summary = metric_summary(
                periods,
                platform,
                selected_group,
                record,
                args.max_age_trade_days,
            )
            summary["top20_overlap"] = top["overlap"] if top else None
            summary["platform_rank_ic"] = record["platform_rank_ic"]
            summary["local_rank_ic"] = float(periods["local_rank_ic"].mean())
            summary["rank_ic_delta"] = summary["local_rank_ic"] - record["platform_rank_ic"]
            (output / f"{stem}.json").write_text(
                json.dumps(
                    {
                        "summary": summary,
                        "top20": top,
                        "raw_result": record["raw_result"],
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
                + "\n",
                encoding="utf-8",
            )
            all_summary.append(summary)
            print(
                f"{record['name']}: periods={len(periods)} delta_net={summary['delta_net_pp']:.2f}pp "
                f"period_excess_corr={summary['period_excess_corr']!s} "
                f"largest={summary['largest_abs_delta_date']}({summary['largest_abs_delta_excess_pp']:.2f}pp)",
                flush=True,
            )
        del values

    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "start": day_text(DEFAULT_START),
        "end": day_text(END),
        "data_start": day_text(data_start),
        "pool_count": len(pool),
        "universe": (
            "full-A qfq + daily_basic proxy filtered to .SH/.SZ"
            if args.universe == "full_a"
            else "fixed ST-filter workflow symbols"
        ),
        "min_delta_pp": args.min_delta_pp,
        "max_age_trade_days": args.max_age_trade_days,
        "label_offset": args.label_offset,
        "groups": GROUPS,
        "round_trip_cost": ROUND_TRIP_COST,
    }
    payload = {"settings": settings, "summary": all_summary, "top_checks": all_top_checks}
    (output / "diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    write_markdown(all_summary, output / "diagnosis.md", settings, all_top_checks)
    print(f"report={output / 'diagnosis.md'}", flush=True)
    return 0


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
    parser.add_argument("--financial-root", default=str(CACHE_ROOT / "financial_full_a"))
    parser.add_argument("--data-start", default=DATA_START.strftime("%Y%m%d"))
    parser.add_argument(
        "--compare-json",
        default=str(CACHE_ROOT / "reports" / "positive_factor_compare" / "positive_factor_local_compare.json"),
    )
    parser.add_argument("--min-delta-pp", type=float, default=DEFAULT_MIN_DELTA_PP)
    parser.add_argument(
        "--max-age-trade-days",
        type=int,
        default=None,
        help="drop a price if it has been forward-filled for more than N trade days; omit for no cap",
    )
    parser.add_argument(
        "--label-offset",
        type=int,
        default=ALIGNMENT_LABEL_OFFSET,
        help="Trading-day offset applied to both current and future close in the forward label.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
