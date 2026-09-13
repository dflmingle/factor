#!/usr/bin/env python3
"""Diagnose the remaining platform/local differences after data completion.

This is an offline report over saved platform responses and the existing local
diagnosis files.  It does not build a new factor or call PandaAI.  The report
tests the observable forward-label convention and reuses the already saved
local selected members so that label changes are isolated from factor ranking.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose_positive_factor_deltas import (  # noqa: E402
    asof_price_panel,
    platform_period_frame,
)
from financial_factor_local import FINANCIAL_HANDLERS  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    END,
    GROUPS,
    ROUND_TRIP_COST,
    formula_catalog,
    positive_records,
)
from stfilter_local_recheck import ensure_calendar  # noqa: E402


DEFAULT_DATA_START = pd.Timestamp("2018-01-01")
DEFAULT_START = pd.Timestamp("2021-09-07")
DEFAULT_END = END
DEFAULT_DIAGNOSIS = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_delta_diagnosis_full_a/diagnosis.json"
)
DEFAULT_DIAGNOSIS_ROOT = DEFAULT_DIAGNOSIS.parent
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_shift_diagnosis_full_a"
)
DEFAULT_PRICE_ROOT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
)
DEFAULT_CAP_ROOT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
)


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def load_selected_records(diagnosis_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    diagnosis_by_id = {str(row["id"]): row for row in diagnosis.get("summary", [])}
    supported, _ = positive_records(formula_catalog())
    records = [row for row in supported if row["id"] in diagnosis_by_id]
    records = [
        row
        for row in records
        if row.get("raw_result") and (PROJECT_ROOT / row["raw_result"]).exists()
    ]
    if not records:
        raise RuntimeError("No saved large-delta records are available")
    return records, diagnosis_by_id


def period_path(diagnosis_root: Path, record: dict[str, Any]) -> Path:
    stem = record["id"].replace(":", "__").replace("/", "_")
    path = diagnosis_root / f"{stem}_periods.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing saved period file: {path}")
    return path


def local_benchmark(
    close: pd.DataFrame,
    positions: dict[pd.Timestamp, int],
    dates: list[pd.Timestamp],
    cycle: int,
    current_offset: int,
    target_offset: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date in dates:
        current_position = positions[date] + current_offset
        target_position = positions[date] + cycle + target_offset
        if current_position < 0 or target_position >= len(close.index):
            continue
        current = close.iloc[current_position]
        target = close.iloc[target_position]
        returns = target.div(current).sub(1.0).replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({"date": date, "local_benchmark": float(returns.mean())})
    return pd.DataFrame(rows)


def correlation(left: pd.Series, right: pd.Series) -> float | None:
    joined = pd.concat([left.rename("local"), right.rename("platform")], axis=1).dropna()
    if len(joined) < 2:
        return None
    return finite_float(joined["local"].corr(joined["platform"]))


def benchmark_sensitivity(
    records: list[dict[str, Any]],
    close: pd.DataFrame,
    positions: dict[pd.Timestamp, int],
) -> list[dict[str, Any]]:
    by_cycle: dict[int, dict[str, Any]] = {}
    for record in records:
        cycle = int(record["configured_cycle"])
        by_cycle.setdefault(cycle, record)

    rows: list[dict[str, Any]] = []
    for cycle, record in sorted(by_cycle.items()):
        platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
        selected_group = GROUPS if record["direction"] == 1 else 1
        platform_periods = platform_period_frame(platform, selected_group)
        dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
        platform_periods = platform_periods[platform_periods["date"].isin(dates)]
        for current_offset in [0, 1]:
            for target_offset in [-1, 0, 1]:
                local = local_benchmark(
                    close,
                    positions,
                    dates,
                    cycle,
                    current_offset,
                    target_offset,
                )
                joined = local.merge(
                    platform_periods[["date", "platform_benchmark"]],
                    on="date",
                    how="inner",
                )
                delta = joined["local_benchmark"] - joined["platform_benchmark"]
                rows.append(
                    {
                        "cycle": cycle,
                        "reference_record": record["name"],
                        "current_offset": current_offset,
                        "target_offset": target_offset,
                        "periods": int(len(joined)),
                        "correlation": correlation(
                            joined["local_benchmark"], joined["platform_benchmark"]
                        ),
                        "rmse_pp": float(np.sqrt(np.mean(delta**2)) * 100.0),
                        "mean_delta_pp": float(delta.mean() * 100.0),
                    }
                )
    return rows


def shifted_selected_result(
    record: dict[str, Any],
    diagnosis_row: dict[str, Any],
    diagnosis_root: Path,
    close: pd.DataFrame,
    positions: dict[pd.Timestamp, int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
    selected_group = GROUPS if record["direction"] == 1 else 1
    cycle = int(record["configured_cycle"])
    dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
    platform_periods = platform_period_frame(platform, selected_group)
    saved = pd.read_csv(period_path(diagnosis_root, record), encoding="utf-8-sig")
    saved["date"] = pd.to_datetime(saved["date"], errors="coerce").dt.normalize()
    saved = saved.set_index("date")

    rows: list[dict[str, Any]] = []
    for date in dates:
        if date not in saved.index:
            continue
        current_position = positions[date] + 1
        target_position = positions[date] + cycle + 1
        if target_position >= len(close.index):
            continue
        current = close.iloc[current_position]
        target = close.iloc[target_position]
        returns = target.div(current).sub(1.0).replace([np.inf, -np.inf], np.nan)
        returns = returns.dropna()
        members = [
            symbol
            for symbol in str(saved.loc[date, "selected_members"]).split(",")
            if symbol
        ]
        selected_returns = returns.reindex(members).dropna()
        if selected_returns.empty:
            continue
        benchmark = float(returns.mean())
        group_return = float(selected_returns.mean())
        rows.append(
            {
                "date": date,
                "shifted_stock_count": int(len(returns)),
                "shifted_group_return": group_return,
                "shifted_benchmark": benchmark,
                "shifted_excess": group_return - benchmark,
                "saved_member_count": len(members),
                "saved_member_price_count": int(len(selected_returns)),
            }
        )

    periods = pd.DataFrame(rows)
    periods = periods.merge(platform_periods, on="date", how="inner")
    if periods.empty:
        raise RuntimeError(f"No shifted periods for {record['id']}")

    delta_group = periods["shifted_group_return"] - periods["platform_group_return"]
    delta_excess = periods["shifted_excess"] - periods["platform_excess"]
    years = len(periods) * cycle / 252.0
    turnover_column = f"local_turnover_{selected_group}"
    turnover = pd.to_numeric(saved.loc[periods["date"], turnover_column], errors="coerce")
    turnover = turnover.replace([np.inf, -np.inf], np.nan).dropna()
    turnover_mean = float(turnover.mean()) if not turnover.empty else None
    gross = float(periods["shifted_excess"].sum() / years * 100.0)
    cost = (
        turnover_mean * (252.0 / cycle) * ROUND_TRIP_COST * 100.0
        if turnover_mean is not None
        else None
    )
    net = gross - cost if cost is not None else None

    summary = {
        "id": record["id"],
        "name": record["name"],
        "handler": record["handler"],
        "cycle": cycle,
        "direction": int(record["direction"]),
        "selected_group": selected_group,
        "periods": int(len(periods)),
        "platform_net_excess_pct": record["platform_net_excess_pct"],
        "original_local_net_excess_pct": diagnosis_row.get("local_net_excess_pct"),
        "original_delta_net_pp": diagnosis_row.get("delta_net_pp"),
        "shifted_gross_excess_pct": gross,
        "shifted_turnover_pct": None if turnover_mean is None else turnover_mean * 100.0,
        "shifted_net_excess_pct": net,
        "shifted_delta_net_pp": None if net is None else net - record["platform_net_excess_pct"],
        "shifted_delta_group_rmse_pp": float(np.sqrt(np.mean(delta_group**2)) * 100.0),
        "shifted_delta_excess_rmse_pp": float(np.sqrt(np.mean(delta_excess**2)) * 100.0),
        "shifted_delta_group_mean_pp": float(delta_group.mean() * 100.0),
        "shifted_delta_excess_mean_pp": float(delta_excess.mean() * 100.0),
        "shifted_group_return_corr": correlation(
            periods["shifted_group_return"], periods["platform_group_return"]
        ),
        "shifted_excess_corr": correlation(
            periods["shifted_excess"], periods["platform_excess"]
        ),
        "latest_saved_member_count": int(periods.iloc[-1]["saved_member_count"]),
        "latest_saved_member_price_count": int(
            periods.iloc[-1]["saved_member_price_count"]
        ),
        "financial_proxy": record["handler"] in FINANCIAL_HANDLERS,
    }
    return summary, periods.to_dict(orient="records")


def write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Remaining platform/local mismatch diagnosis",
        "",
        "Offline diagnostic over saved platform responses. No factor was created and no platform backtest was run.",
        "",
        "## Forward-label check",
        "",
        "The benchmark test compares the saved platform benchmark with the full-A qfq equal-weight benchmark. `current_offset=1, target_offset=1` means close-to-close from the next trading day through the next trading day plus the configured cycle.",
        "",
        "| cycle | current offset | target offset | periods | corr | RMSE (pp) | mean delta (pp) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["benchmark_sensitivity"]:
        if row["current_offset"] == 1 and row["target_offset"] == 1:
            lines.append(
                f"| {row['cycle']} | {row['current_offset']} | {row['target_offset']} | {row['periods']} | {row['correlation']:.3f} | {row['rmse_pp']:.3f} | {row['mean_delta_pp']:.3f} |"
            )
    lines.extend(
        [
            "",
            "## Shifted-label result",
            "",
            "These rows reuse the previously saved local selected members. This isolates the return-label convention from factor-value construction.",
            "",
            "| factor | cycle | original delta (pp) | shifted delta (pp) | shifted group RMSE (pp) | group corr | financial proxy |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(payload["summary"], key=lambda item: abs(item["shifted_delta_net_pp"] or 0), reverse=True):
        lines.append(
            f"| {row['name']} | {row['cycle']} | {row['original_delta_net_pp']:.2f} | {row['shifted_delta_net_pp']:.2f} | {row['shifted_delta_group_rmse_pp']:.2f} | {row['shifted_group_return_corr']:.3f} | {'yes' if row['financial_proxy'] else 'no'} |"
        )
    improved = [
        row
        for row in payload["summary"]
        if abs(row["shifted_delta_net_pp"] or 999.0)
        < abs(row["original_delta_net_pp"] or 999.0)
    ]
    within_one = [
        row for row in payload["summary"] if abs(row["shifted_delta_net_pp"] or 999.0) < 1.0
    ]
    lines.extend(
        [
            "",
            f"The whole-day label shift improves `{len(improved)}/{len(payload['summary'])}` selected records; `{len(within_one)}/{len(payload['summary'])}` are within 1 pp after reusing the existing memberships.",
            "",
            "## Largest shifted group-return dates",
            "",
            "| date | records with abs group delta >= 2 pp | total records |",
            "|---|---:|---:|",
        ]
    )
    for row in payload["date_hotspots"][:12]:
        lines.append(f"| {row['date']} | {row['large_delta_records']} | {row['records']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    records, diagnosis_by_id = load_selected_records(Path(args.diagnosis))
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        pd.Timestamp(args.data_start),
        pd.Timestamp(args.end),
    )
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    calendar = ensure_calendar(pd.Timestamp(args.data_start), pd.Timestamp(args.end), token=None)
    close, _ = asof_price_panel(frame, calendar)
    positions = {date: index for index, date in enumerate(calendar)}

    benchmark_rows = benchmark_sensitivity(records, close, positions)
    summary: list[dict[str, Any]] = []
    period_rows: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        result, periods = shifted_selected_result(
            record,
            diagnosis_by_id[record["id"]],
            Path(args.diagnosis_root),
            close,
            positions,
        )
        summary.append(result)
        period_rows[record["id"]] = periods

    hotspot_counts: dict[str, dict[str, int]] = {}
    for rows in period_rows.values():
        for row in rows:
            date = day_text(pd.Timestamp(row["date"]))
            item = hotspot_counts.setdefault(date, {"records": 0, "large_delta_records": 0})
            item["records"] += 1
            if abs(float(row["shifted_group_return"] - row["platform_group_return"])) >= 0.02:
                item["large_delta_records"] += 1
    hotspots = [
        {"date": date, **values}
        for date, values in hotspot_counts.items()
    ]
    hotspots.sort(key=lambda row: (row["large_delta_records"], row["records"]), reverse=True)

    payload = {
        "settings": {
            "data_start": day_text(pd.Timestamp(args.data_start)),
            "start": day_text(pd.Timestamp(args.start)),
            "end": day_text(pd.Timestamp(args.end)),
            "price_mode": "qfq",
            "records": len(records),
            "label": "close(t+1) -> close(t+cycle+1)",
        },
        "benchmark_sensitivity": benchmark_rows,
        "summary": summary,
        "date_hotspots": hotspots,
        "periods": period_rows,
    }
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "remaining_mismatch_diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    write_report(payload, output / "remaining_mismatch_diagnosis.md")
    print(f"report={output / 'remaining_mismatch_diagnosis.md'}")
    print(f"records={len(summary)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnosis", default=str(DEFAULT_DIAGNOSIS))
    parser.add_argument("--diagnosis-root", default=str(DEFAULT_DIAGNOSIS_ROOT))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--data-start", default=DEFAULT_DATA_START.strftime("%Y-%m-%d"))
    parser.add_argument("--start", default=DEFAULT_START.strftime("%Y-%m-%d"))
    parser.add_argument("--end", default=DEFAULT_END.strftime("%Y-%m-%d"))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
