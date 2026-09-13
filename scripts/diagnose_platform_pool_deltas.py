#!/usr/bin/env python3
"""Recheck selected large deltas with the platform's full-A stock-pool setting.

This is an offline diagnostic.  It uses the saved platform result JSON files,
the saved workflow registry, and the existing full-A qfq cache.  It never
creates or runs a PandaAI factor.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from tushare_factor_recheck import (  # noqa: E402
    RECHECK_ROOT,
    load_daily_batches,
)


CACHE_ROOT = RECHECK_ROOT.parent
FULL_A_BATCH_ROOT = RECHECK_ROOT / "qfq" / "daily_batches"
CALENDAR_ROOT = CACHE_ROOT / "trade_calendar"
OUTPUT_ROOT = CACHE_ROOT / "reports" / "platform_pool_diagnosis"
REGISTRY_PATH = PROJECT_ROOT / "pandaai-workflow-registry.json"
OLD_DIAGNOSIS_PATH = CACHE_ROOT / "reports" / "positive_factor_delta_diagnosis" / "diagnosis.json"

START = pd.Timestamp("2021-09-07")
END = pd.Timestamp("2026-09-07")
WARMUP = pd.Timestamp("2019-07-01")
GROUPS = 10
ROUND_TRIP_COST = 0.006

TARGETS: dict[str, dict[str, Any]] = {
    "OSR2-DD60": {
        "report": "oversold-rebound-recovery-candidates.report.csv",
        "window": 60,
        "handler": "drawdown",
    },
    "OSR2-DD120": {
        "report": "oversold-rebound-recovery-candidates.report.csv",
        "window": 120,
        "handler": "drawdown",
    },
    "NONHT-CHIP-COST-250": {
        "report": "nonht-report-directions-20260909-formula.report.csv",
        "window": 250,
        "handler": "chip",
    },
}


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def normalize_day(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def correlation(left: pd.Series, right: pd.Series) -> float | None:
    joined = pd.concat([left.rename("local"), right.rename("platform")], axis=1).dropna()
    if len(joined) < 2:
        return None
    return clean_float(joined["local"].corr(joined["platform"]))


def cross_rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.groupby(dates, sort=False, observed=True).rank(method="average", pct=True)


def grouped_rolling(frame: pd.DataFrame, column: str, window: int, method: str) -> pd.Series:
    grouped = frame.groupby("instrument", sort=False, observed=True)[column]
    values = getattr(grouped.rolling(window=window, min_periods=window), method)()
    return values.reset_index(level=0, drop=True).reindex(frame.index)


def load_local_trade_dates(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    frames = [pd.read_parquet(path, columns=["trade_date", "is_open"]) for path in CALENDAR_ROOT.glob("*.parquet")]
    if not frames:
        raise FileNotFoundError(f"Trade-calendar cache is missing: {CALENDAR_ROOT}")
    raw = pd.concat(frames, ignore_index=True)
    text_values = raw["trade_date"].astype(str)
    dates = pd.to_datetime(text_values, format="%Y%m%d", errors="coerce")
    dates = dates.fillna(pd.to_datetime(text_values, errors="coerce"))
    raw["trade_date"] = dates
    raw = raw[raw["is_open"].astype(int).eq(1)]
    result = sorted(raw.loc[raw["trade_date"].between(start, end), "trade_date"].dropna().unique())
    return [pd.Timestamp(value).normalize() for value in result]


def factor_values(frame: pd.DataFrame, handler: str, window: int) -> pd.Series:
    close = frame["close"]
    if handler == "drawdown":
        rolling_max = grouped_rolling(frame, "close", window, "max")
        return cross_rank(1.0 - close.div(rolling_max), frame["date"])
    weighted = frame["volume"] * (frame["open"] + frame["close"]) / 2.0
    vwap = grouped_rolling(
        frame.assign(_weighted_price=weighted), "_weighted_price", window, "sum"
    ).div(grouped_rolling(frame, "volume", window, "sum"))
    return cross_rank(vwap.div(close).sub(1.0), frame["date"])


def panel_close(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    panel = frame.pivot(index="date", columns="instrument", values="close")
    return panel.reindex(calendar).sort_index(axis=1).ffill()


def forward_returns(
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
) -> pd.DataFrame:
    positions = {date: index for index, date in enumerate(calendar)}
    target_positions = [positions[date] + cycle for date in signal_dates]
    if max(target_positions, default=-1) >= len(calendar):
        raise RuntimeError("Full-A cache does not cover the platform forward target")
    current = close.loc[signal_dates].stack(dropna=False).rename("current_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    future = close.iloc[target_positions].copy()
    future.index = signal_dates
    future = future.stack(dropna=False).rename("future_close").reset_index()
    future = future.rename(columns={"level_0": "date", "level_1": "instrument"})
    result = current.merge(future, on=["date", "instrument"], how="left")
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    return result[["date", "instrument", "forward_return"]]


def platform_periods(platform: dict[str, Any], group: int) -> pd.DataFrame:
    dates = pd.DatetimeIndex([normalize_day(value) for value in platform.get("dates", [])])
    returns = np.asarray(platform.get("return_cumulative", [[]]), dtype=float)
    excess = np.asarray(platform.get("excess_cumulative", [[]]), dtype=float)
    if returns.ndim != 2 or excess.ndim != 2 or returns.shape[0] < group or excess.shape[0] < group:
        raise RuntimeError(f"Platform result has no group-{group} return chart")
    group_cumulative = returns[group - 1]
    excess_cumulative = excess[group - 1]
    if len(dates) != len(group_cumulative) or len(dates) != len(excess_cumulative):
        raise RuntimeError("Platform chart date/value lengths do not match")
    group_period = np.diff(np.concatenate(([0.0], group_cumulative)))
    excess_period = np.diff(np.concatenate(([0.0], excess_cumulative)))
    return pd.DataFrame(
        {
            "date": dates,
            "platform_group_return": group_period,
            "platform_excess": excess_period,
            "platform_group_cumulative": group_cumulative,
            "platform_excess_cumulative": excess_cumulative,
        }
    )


def evaluate(
    frame: pd.DataFrame,
    values: pd.Series,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    platform: dict[str, Any],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    direction: int,
) -> dict[str, Any]:
    all_factor_frame = frame[["date", "instrument"]].copy()
    all_factor_frame["factor"] = pd.to_numeric(values.to_numpy(), errors="coerce")
    factor_frame = all_factor_frame.copy()
    factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]
    returns = forward_returns(close, calendar, signal_dates, cycle)
    data = factor_frame.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    selected_group = GROUPS if direction == 1 else 1
    previous: dict[int, set[str]] = {}
    rows: list[dict[str, Any]] = []
    rank_ics: list[float] = []
    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = np.ceil(
            current["factor"].rank(method="first") * GROUPS / len(current)
        ).astype(int).clip(1, GROUPS)
        rank_ic = current["factor"].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        benchmark = float(current["forward_return"].mean())
        row: dict[str, Any] = {
            "date": date,
            "stock_count": int(len(current)),
            "benchmark": benchmark,
            "rank_ic": clean_float(rank_ic),
        }
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
            row[f"group_{group}"] = group_return
            row[f"excess_{group}"] = group_return - benchmark
            row[f"turnover_{group}"] = clean_float(turnover)
            if group == selected_group:
                row["selected_members"] = ",".join(sorted(members))
        rows.append(row)

    local = pd.DataFrame(rows)
    if local.empty:
        raise RuntimeError("No valid full-A periods were produced")
    platform_frame = platform_periods(platform, selected_group)
    merged = local.merge(platform_frame, on="date", how="inner")
    local_excess = local[f"excess_{selected_group}"]
    local_turnover = local[f"turnover_{selected_group}"].dropna()
    years = len(local) * cycle / 252.0
    gross = float(local_excess.sum() / years) if years else None
    turnover = float(local_turnover.mean()) if not local_turnover.empty else None
    annual_cost = turnover * (252.0 / cycle) * ROUND_TRIP_COST if turnover is not None else None
    net = gross - annual_cost if gross is not None and annual_cost is not None else None
    platform_group = platform.get("group_metrics", {}).get(selected_group, {})

    latest_top_rows = [row for row in platform.get("top", []) if row.get("date") and row.get("symbol")]
    top_overlap = None
    if latest_top_rows:
        latest_top_date = max(normalize_day(row["date"]) for row in latest_top_rows)
        platform_symbols = [
            str(row["symbol"])
            for row in latest_top_rows
            if normalize_day(row["date"]) == latest_top_date
        ]
        latest = all_factor_frame[all_factor_frame["date"].eq(latest_top_date)].dropna()
        latest = latest.sort_values(["factor", "instrument"], ascending=[direction == 0, True])
        local_symbols = latest.head(len(platform_symbols))["instrument"].astype(str).tolist()
        top_overlap = {
            "date": day_text(latest_top_date),
            "platform_n": len(platform_symbols),
            "local_n": len(local_symbols),
            "overlap": len(set(platform_symbols).intersection(local_symbols)),
            "platform_symbols": platform_symbols,
            "local_symbols": local_symbols,
        }

    return {
        "periods": int(len(local)),
        "platform_periods": int(len(platform_frame)),
        "overlap_periods": int(len(merged)),
        "mean_stock_count": float(local["stock_count"].mean()),
        "min_stock_count": int(local["stock_count"].min()),
        "max_stock_count": int(local["stock_count"].max()),
        "local_rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "platform_rank_ic": platform.get("metrics", {}).get("Rank_IC"),
        "local_gross_excess_pct": None if gross is None else gross * 100.0,
        "local_turnover_pct": None if turnover is None else turnover * 100.0,
        "local_annual_cost_pct": None if annual_cost is None else annual_cost * 100.0,
        "local_net_excess_pct": None if net is None else net * 100.0,
        "platform_gross_excess_pct": platform_group.get("excessAnnualized", 0.0) * 100.0,
        "platform_turnover_pct": platform_group.get("turnoverRate", 0.0) * 100.0,
        "platform_net_excess_pct": None,
        "period_excess_corr": correlation(
            merged[f"excess_{selected_group}"], merged["platform_excess"]
        ),
        "period_group_return_corr": correlation(
            merged[f"group_{selected_group}"], merged["platform_group_return"]
        ),
        "top20": top_overlap,
        "period_frame": local,
    }


def read_target_record(report_name: str, name: str) -> dict[str, Any]:
    path = PROJECT_ROOT / report_name
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("name") == name and row.get("status") == "completed":
                row["raw_result"] = (row.get("raw_result") or "").replace("\\", "/")
                return row
    raise RuntimeError(f"Saved report row not found: {report_name}:{name}")


def config_indexes(registry: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_run: dict[str, dict[str, Any]] = {}
    by_factor: dict[str, dict[str, Any]] = {}
    fields = (
        "factor_id", "workflow_name", "run_id", "mode", "market", "stock_pool",
        "start_date", "end_date", "adjustment_cycle", "group_number", "factor_direction",
    )
    for workflow in registry.get("workflows", []):
        info = workflow.get("factor_info") or {}
        config = {
            "factor_id": workflow.get("_id"),
            "workflow_name": workflow.get("name"),
            "run_id": workflow.get("last_run_id"),
            **{field: info.get(field) for field in fields if field not in {"factor_id", "workflow_name", "run_id"}},
        }
        by_factor[str(config["factor_id"])] = config
        for entry in (workflow.get("local") or {}).get("entries", []):
            if entry.get("run_id"):
                by_run[str(entry["run_id"])] = config
    return by_run, by_factor


def classify_large_gap(name: str) -> tuple[str, str]:
    if name in {"OSR2-DD60", "OSR2-DD120"}:
        return "isolated_full_A", "full-A qfq price recheck is available"
    if name == "NONHT-CHIP-COST-250":
        return "isolated_full_A", "full-A qfq and daily_basic history covers the 250-observation warm-up"
    if "CFP" in name:
        return "full_A_financial_proxy", "full-A PIT financial cache is available; remaining differences are field/semantic or return-path checks"
    if "PAPER" in name:
        return "full_A_financial_proxy", "full-A PIT financial cache is available; remaining differences are field/semantic or return-path checks"
    if "SIZE" in name:
        return "full_A_fields_available", "full-A daily turnover and market-cap history is available"
    return "not_rechecked", "no full-A local field reconstruction is available for this item"


def old_gap_inventory() -> list[dict[str, Any]]:
    if not OLD_DIAGNOSIS_PATH.exists():
        return []
    payload = json.loads(OLD_DIAGNOSIS_PATH.read_text(encoding="utf-8"))
    result = []
    for row in payload.get("summary", []):
        status, reason = classify_large_gap(str(row.get("name", "")))
        result.append(
            {
                "name": row.get("name"),
                "old_st_pool_delta_net_pp": row.get("delta_net_pp"),
                "old_st_pool_local_net_pct": row.get("local_net_excess_pct"),
                "platform_net_pct": row.get("platform_net_excess_pct"),
                "status": status,
                "reason": reason,
            }
        )
    return result


def write_report(payload: dict[str, Any], path: Path) -> None:
    def value(item: dict[str, Any], key: str, digits: int = 2, suffix: str = "") -> str:
        raw = item.get(key)
        return "n/a" if raw is None else f"{float(raw):.{digits}f}{suffix}"

    lines = [
        "# Platform pool delta diagnosis",
        "",
        "This is an offline recheck of saved platform results. The local price panel uses the existing full-A qfq cache and `.SH/.SZ` instruments; no platform run was created.",
        "",
        f"- local data: `{payload['settings']['data_start']}..{payload['settings']['data_end']}`; evaluation: `{payload['settings']['start']}..{payload['settings']['end']}`",
        f"- local universe: `{payload['settings']['universe']}`; instruments observed: `{payload['settings']['instruments']}`",
        f"- groups: `{payload['settings']['groups']}`; local cost: `{payload['settings']['round_trip_cost']:.3f}` round trip",
        "- the platform configuration is copied from the local workflow registry; `沪深全A` is the recorded platform pool label.",
        "",
        "## Full-A recheck",
        "",
        "A net delta is comparable only when the local factor has complete warm-up coverage for the platform chart window.",
        "",
        "| factor | platform net | full-A local net | delta pp | local RankIC | platform RankIC | local turnover | platform turnover | periods | status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, item in payload["rechecks"].items():
        lines.append(
            f"| {name} | {value(item, 'platform_net_excess_pct', suffix='%')} | "
            f"{value(item, 'local_net_excess_pct', suffix='%')} | "
            f"{value(item, 'delta_net_pp')} | "
            f"{value(item, 'local_rank_ic', digits=4)} | "
            f"{value(item, 'platform_rank_ic', digits=4)} | "
            f"{value(item, 'local_turnover_pct', suffix='%')} | "
            f"{value(item, 'platform_turnover_pct', suffix='%')} | "
            f"{item.get('periods')} | {item.get('status')} |"
        )
    lines.extend(["", "## Configuration for rechecked runs", "", "| factor | factor_id | run_id | pool | dates | cycle | groups | direction |", "|---|---|---|---|---|---:|---:|---:|"])
    for item in payload["rechecks"].values():
        config = item["config"]
        lines.append(
            "| "
            + " | ".join(
                str(value if value is not None else "")
                for value in (
                    item["name"], config.get("factor_id"), item["run_id"], config.get("stock_pool"),
                    f"{config.get('start_date', '')}..{config.get('end_date', '')}",
                    config.get("adjustment_cycle"), config.get("group_number"), config.get("factor_direction"),
                )
            )
            + " |"
        )
    lines.extend(["", "## Remaining large-gap inventory", "", "The old delta below is the earlier ST-pool baseline. It is retained only to show why an item was selected; status is the current full-A audit state.", "", "| factor | old ST-pool delta pp | platform net | current status | reason |", "|---|---:|---:|---|---|"])
    for item in payload["large_gap_inventory"]:
        old_delta = item.get("old_st_pool_delta_net_pp")
        lines.append(
            f"| {item['name']} | {'n/a' if old_delta is None else f'{old_delta:.2f}'} | "
            f"{item['platform_net_pct']:.2f}% | {item['status']} | {item['reason']} |"
        )
    lines.extend(["", "## Caveats", "", "- The full-A qfq and daily_basic caches cover 20190701..20260907, including the 250-observation warm-up before the first 2021-09 signal.", "- Full-A point-in-time financial tables are now cached; CFP and paper-derived residuals should be investigated as field/announcement-date semantics or return-path differences.", "- The full-A proxy is restricted to `.SH/.SZ`, matching the recorded `沪深全A` pool label; it remains a Tushare reconstruction rather than the platform's internal data snapshot.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_run, by_factor = config_indexes(registry)
    calendar = load_local_trade_dates(WARMUP, END)
    frame = load_daily_batches(WARMUP, END, FULL_A_BATCH_ROOT, market="hs")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    close = panel_close(frame, calendar)
    instruments = int(frame["instrument"].nunique())
    results: dict[str, dict[str, Any]] = {}

    for name, spec in TARGETS.items():
        report_row = read_target_record(spec["report"], name)
        platform = read_platform_run(PROJECT_ROOT / report_row["raw_result"])
        signal_dates = [normalize_day(value) for value in platform["dates"]]
        config = by_run.get(str(report_row.get("run_id"))) or by_factor.get(str(report_row.get("factor_id")))
        if config is None:
            raise RuntimeError(f"No platform config for {name} run {report_row.get('run_id')}")
        direction = int(report_row["direction"])
        values = factor_values(frame, spec["handler"], int(spec["window"]))
        evaluated = evaluate(frame, values, close, calendar, platform, signal_dates, int(config["adjustment_cycle"]), direction)
        first_signal = min(signal_dates)
        history_days = calendar.index(first_signal) + 1
        warmup_complete = history_days >= int(spec["window"])
        platform_net = float(report_row["net_excess_pct"])
        evaluated["name"] = name
        evaluated["run_id"] = report_row["run_id"]
        evaluated["raw_result"] = report_row["raw_result"]
        evaluated["config"] = config
        evaluated["platform_net_excess_pct"] = platform_net
        evaluated["status"] = "isolated_full_A" if warmup_complete else "warmup_incomplete"
        evaluated["warmup_trade_days_to_first_signal"] = history_days
        evaluated["required_warmup_trade_days"] = int(spec["window"])
        evaluated["delta_net_pp"] = (
            evaluated["local_net_excess_pct"] - platform_net if warmup_complete and evaluated["local_net_excess_pct"] is not None else None
        )
        periods = evaluated.pop("period_frame")
        stem = name.lower().replace("/", "_")
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        periods.to_csv(OUTPUT_ROOT / f"{stem}_periods.csv", index=False, encoding="utf-8-sig")
        results[name] = evaluated

    payload = {
        "settings": {
            "data_start": day_text(WARMUP),
            "data_end": day_text(END),
            "start": day_text(START),
            "end": day_text(END),
            "universe": "沪深全A proxy: full-A Tushare qfq rows filtered to .SH/.SZ",
            "instruments": instruments,
            "groups": GROUPS,
            "round_trip_cost": ROUND_TRIP_COST,
            "batch_root": str(FULL_A_BATCH_ROOT),
        },
        "rechecks": results,
        "large_gap_inventory": old_gap_inventory(),
    }
    (OUTPUT_ROOT / "diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    write_report(payload, OUTPUT_ROOT / "diagnosis.md")
    print(f"report={OUTPUT_ROOT / 'diagnosis.md'}")
    for name, item in results.items():
        print(
            f"{name}: status={item['status']} platform_net={item['platform_net_excess_pct']:.2f}% "
            f"local_net={item['local_net_excess_pct']!s} delta={item['delta_net_pp']!s} "
            f"top20={item['top20']['overlap']}/{item['top20']['platform_n']}" if item.get("top20") else
            f"{name}: status={item['status']} platform_net={item['platform_net_excess_pct']:.2f}% top20=n/a",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
