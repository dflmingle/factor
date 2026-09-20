#!/usr/bin/env python3
"""Reproduce the locally supported Quantpedia candidate from cached Tushare data.

The source strategy combines six-month momentum and volatility, skips the most
recent week, restricts the universe to large caps, and buys the high-return
stocks inside the high-volatility subset.  The local cache cannot express the
source strategy's overlapping six-month holdings without adding a separate
portfolio simulator, so this report uses a clearly labelled 21-trading-day
holding proxy and reports both the top-group and long-short results.

This script is offline.  It does not call Tushare or PandaAI and it refuses to
overwrite an existing non-empty output directory.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from machine_profile import resolve_machine_profile  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
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
from positive_factor_local_compare import grouped_rolling, panel_close  # noqa: E402
from qtld60_local_reproduction import (  # noqa: E402
    detect_cache_end,
    load_calendar,
    load_minimal_full_a,
    memory_guard,
)


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
FORMAL_START = pd.Timestamp(ALIGNMENT_START)
FORMAL_END = pd.Timestamp(ALIGNMENT_END)
RECENT_START = pd.Timestamp("20260101")
CYCLE = 21
LOOKBACK = 126
SKIP_RECENT = 5
GROUPS = ALIGNMENT_GROUPS
CAP_FRACTION = 0.50
VOL_FRACTION = 0.50
MAX_RSS_GB = 2.60
MIN_AVAILABLE_GB = 3.00
GB = 1024**3

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "quantpedia-additional-local-reproduction-20260920"
)

SOURCE_URL = (
    "https://quantpedia.com/strategies/"
    "momentum-and-reversal-combined-with-volatility-effect-in-stocks"
)

CANDIDATES: dict[str, dict[str, Any]] = {
    "momentum_reversal_volatility": {
        "status": "computed_proxy",
        "source": SOURCE_URL,
        "formula": "large-cap & high-volatility subset; rank RET126 and skip 5 days",
        "direction": 1,
        "note": (
            "Local proxy: RET126 = CLOSE/DELAY(CLOSE,126)-1, VOL126 = "
            "STDDEV(RETURNS(CLOSE,1),126), both shifted by 5 trading days. "
            "Top 50% total_mv, then top 50% VOL126; top/bottom RET126 deciles."
        ),
    },
    "ncav_market_cap": {
        "status": "unsupported",
        "source": "https://quantpedia.com/strategies/net-current-asset-value-effect",
        "formula": "NCAV / MARKET_CAP",
        "direction": 1,
        "note": (
            "Unsupported: the local financial cache does not contain a reliable "
            "current-assets field required by the source definition."
        ),
    },
    "accrual_anomaly": {
        "status": "unsupported",
        "source": "https://quantpedia.com/strategies/accrual-anomaly",
        "formula": "BS_ACC / TOTAL_ASSETS",
        "direction": -1,
        "note": (
            "Unsupported: the local cache lacks the cash, short-term debt, "
            "income-tax payable, and depreciation fields needed for the source "
            "balance-sheet accrual formula."
        ),
    },
}


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if value is pd.NA:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def generated_signal_dates(
    calendar: list[pd.Timestamp],
    start: pd.Timestamp,
    end: pd.Timestamp,
    cycle: int,
) -> list[pd.Timestamp]:
    positions = {date: index for index, date in enumerate(calendar)}
    if start not in positions:
        raise RuntimeError(f"Signal anchor is not a trading day: {start.date()}")
    anchor = positions[start]
    dates: list[pd.Timestamp] = []
    for position in range(anchor, len(calendar), cycle):
        date = calendar[position]
        if date > end:
            break
        if position + ALIGNMENT_LABEL_OFFSET + cycle < len(calendar):
            dates.append(date)
    return dates


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def build_features(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Build six-month return and volatility with a five-day information lag."""
    grouped = frame.groupby("instrument", sort=False, observed=True)
    close = _to_float(frame["close_qfq"])
    return_1 = close.div(grouped["close_qfq"].shift(1)).sub(1.0)
    return_126 = close.div(grouped["close_qfq"].shift(LOOKBACK)).sub(1.0)

    work = frame[["instrument"]].copy()
    work["return_1"] = return_1
    volatility_126 = grouped_rolling(work, "return_1", LOOKBACK, "std")

    by_instrument = frame.groupby("instrument", sort=False, observed=True)
    return_signal = return_126.groupby(
        frame["instrument"], sort=False, observed=True
    ).shift(SKIP_RECENT)
    volatility_signal = volatility_126.groupby(
        frame["instrument"], sort=False, observed=True
    ).shift(SKIP_RECENT)
    del work, return_1, return_126, volatility_126, grouped, by_instrument
    gc.collect()
    return return_signal, volatility_signal


def load_large_cap_sets(
    cap_root: Path,
    signal_dates: list[pd.Timestamp],
    instruments: pd.Index,
    max_rss_gb: float,
    min_available_gb: float,
) -> dict[pd.Timestamp, set[str]]:
    """Read only signal-day market caps and return the top half by total_mv."""
    instrument_set = set(instruments.astype(str))
    cap_sets: dict[pd.Timestamp, set[str]] = {}
    for index, date in enumerate(signal_dates, start=1):
        path = cap_root / f"daily_basic_{date.strftime('%Y%m%d')}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing signal-day market-cap file: {path}")
        caps = pd.read_parquet(path, columns=["instrument", "total_mv"])
        caps["instrument"] = caps["instrument"].astype(str)
        caps["total_mv"] = _to_float(caps["total_mv"])
        caps = caps[
            caps["instrument"].str.endswith((".SH", ".SZ"))
            & caps["instrument"].isin(instrument_set)
            & caps["total_mv"].gt(0)
        ].copy()
        caps = caps.sort_values(
            ["total_mv", "instrument"],
            ascending=[False, True],
            kind="stable",
        )
        count = max(1, math.ceil(len(caps) * CAP_FRACTION))
        cap_sets[date] = set(caps.head(count)["instrument"])
        del caps
        if index == 1 or index % 20 == 0 or index == len(signal_dates):
            print(
                f"loaded_signal_caps={index}/{len(signal_dates)} "
                f"large_cap_count={len(cap_sets[date])}",
                flush=True,
            )
            memory_guard(
                f"signal_caps_{index}", max_rss_gb, min_available_gb
            )
    return cap_sets


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    labels = np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)
    return pd.Series(labels, index=values.index)


def build_signal_frame(
    frame: pd.DataFrame,
    return_signal: pd.Series,
    volatility_signal: pd.Series,
    signal_dates: list[pd.Timestamp],
    large_cap_sets: dict[pd.Timestamp, set[str]],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Select large-cap/high-volatility names and rank them by six-month return."""
    date_mask = frame["date"].isin(signal_dates)
    signal = frame.loc[date_mask, ["date", "instrument"]].copy()
    signal["instrument"] = signal["instrument"].astype(str)
    signal["return_signal"] = return_signal.loc[date_mask].to_numpy(dtype=float)
    signal["volatility_signal"] = volatility_signal.loc[date_mask].to_numpy(dtype=float)

    selected_parts: list[pd.DataFrame] = []
    large_counts: list[int] = []
    selected_counts: list[int] = []
    for date in signal_dates:
        current = signal[signal["date"].eq(date)].copy()
        current = current.replace([np.inf, -np.inf], np.nan).dropna(
            subset=["return_signal", "volatility_signal"]
        )
        current = current[current["instrument"].isin(large_cap_sets[date])]
        large_counts.append(len(current))
        if current.empty:
            continue
        current = current.sort_values(
            ["volatility_signal", "instrument"],
            ascending=[False, True],
            kind="stable",
        )
        high_vol_count = max(1, math.ceil(len(current) * VOL_FRACTION))
        current = current.head(high_vol_count).copy()
        current["factor"] = current["return_signal"]
        selected_counts.append(len(current))
        selected_parts.append(current[["date", "instrument", "factor"]])

    if not selected_parts:
        raise RuntimeError("No valid large-cap/high-volatility signal rows")
    selected = pd.concat(selected_parts, ignore_index=True)
    selected["instrument"] = selected["instrument"].astype(str)
    diagnostics = {
        "large_cap_count_mean": float(np.mean(large_counts)) if large_counts else 0.0,
        "high_vol_count_mean": float(np.mean(selected_counts)) if selected_counts else 0.0,
        "high_vol_count_min": float(np.min(selected_counts)) if selected_counts else 0.0,
        "high_vol_count_max": float(np.max(selected_counts)) if selected_counts else 0.0,
    }
    del signal, selected_parts
    gc.collect()
    return selected, diagnostics


def _period_return(
    close: pd.DataFrame,
    positions: dict[pd.Timestamp, int],
    date: pd.Timestamp,
    instruments: pd.Series,
    cycle: int,
) -> pd.Series:
    current_position = positions[date] + ALIGNMENT_LABEL_OFFSET
    future_position = current_position + cycle
    if future_position >= len(close.index):
        raise RuntimeError(f"Forward target is unavailable for signal date {date.date()}")
    names = instruments.astype(str)
    current = close.iloc[current_position].reindex(names).to_numpy(dtype=float)
    future = close.iloc[future_position].reindex(names).to_numpy(dtype=float)
    return pd.Series(future / current - 1.0, index=instruments.index)


def evaluate_proxy(
    signal: pd.DataFrame,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
) -> dict[str, Any]:
    """Evaluate factor-valid top group and the source-style top-minus-bottom spread."""
    positions = {date: index for index, date in enumerate(calendar)}
    previous_long: set[str] | None = None
    previous_short: set[str] | None = None
    rank_ics: list[float] = []
    ics: list[float] = []
    long_excesses: list[float] = []
    long_short_returns: list[float] = []
    long_turnovers: list[float] = []
    short_turnovers: list[float] = []
    period_rows: list[dict[str, Any]] = []

    for date in signal_dates:
        current = signal[signal["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["forward_return"] = _period_return(
            close, positions, date, current["instrument"], CYCLE
        ).to_numpy(dtype=float)
        current = current.replace([np.inf, -np.inf], np.nan).dropna(
            subset=["factor", "forward_return"]
        )
        if len(current) < GROUPS * 10:
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
        long = current[current["group"].eq(GROUPS)]
        short = current[current["group"].eq(1)]
        long_return = float(long["forward_return"].mean())
        short_return = float(short["forward_return"].mean())
        long_members = set(long["instrument"])
        short_members = set(short["instrument"])
        long_turnover = (
            1.0 - len(long_members.intersection(previous_long)) / len(long_members)
            if previous_long
            else np.nan
        )
        short_turnover = (
            1.0 - len(short_members.intersection(previous_short)) / len(short_members)
            if previous_short
            else np.nan
        )
        previous_long = long_members
        previous_short = short_members
        if np.isfinite(long_turnover):
            long_turnovers.append(float(long_turnover))
        if np.isfinite(short_turnover):
            short_turnovers.append(float(short_turnover))
        long_excess = long_return - benchmark
        long_short = long_return - short_return
        long_excesses.append(long_excess)
        long_short_returns.append(long_short)
        period_rows.append(
            {
                "date": date,
                "stock_count": int(len(current)),
                "long_count": int(len(long)),
                "short_count": int(len(short)),
                "benchmark": benchmark,
                "long_return": long_return,
                "short_return": short_return,
                "long_excess": long_excess,
                "long_short": long_short,
                "long_turnover": long_turnover,
                "short_turnover": short_turnover,
            }
        )

    periods = pd.DataFrame(period_rows)
    period_count = len(periods)
    years = period_count * CYCLE / 252.0
    if not years:
        raise RuntimeError("No valid evaluation periods")
    gross_excess = float(np.sum(long_excesses) / years)
    long_short_gross = float(np.sum(long_short_returns) / years)
    long_turnover = float(np.mean(long_turnovers)) if long_turnovers else None
    short_turnover = float(np.mean(short_turnovers)) if short_turnovers else None
    long_cost = annualized_turnover_cost(long_turnover, CYCLE, ALIGNMENT_ROUND_TRIP_COST)
    short_cost = annualized_turnover_cost(short_turnover, CYCLE, ALIGNMENT_ROUND_TRIP_COST)
    combined_turnover = (
        (long_turnover + short_turnover) / 2.0
        if long_turnover is not None and short_turnover is not None
        else None
    )
    long_short_cost = annualized_turnover_cost(
        combined_turnover, CYCLE, ALIGNMENT_ROUND_TRIP_COST
    )
    return {
        "periods": period_count,
        "stock_count_mean": float(periods["stock_count"].mean()),
        "long_count_mean": float(periods["long_count"].mean()),
        "short_count_mean": float(periods["short_count"].mean()),
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.mean(ics)) if ics else None,
        "selected_group": GROUPS,
        "gross_excess": gross_excess,
        "turnover": long_turnover,
        "annual_cost": long_cost,
        "net_excess": gross_excess - long_cost if long_cost is not None else None,
        "long_short_gross": long_short_gross,
        "long_short_turnover": combined_turnover,
        "long_short_annual_cost": long_short_cost,
        "long_short_net": (
            long_short_gross - long_short_cost
            if long_short_cost is not None
            else None
        ),
        "short_turnover": short_turnover,
        "short_annual_cost": short_cost,
    }


def pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed * 100.0 if np.isfinite(parsed) else None


def metric_row(
    window: str,
    requested_start: pd.Timestamp,
    requested_end: pd.Timestamp,
    signal_dates: list[pd.Timestamp],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "factor": "momentum_reversal_volatility",
        "window": window,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "signal_start": signal_dates[0] if signal_dates else None,
        "signal_end": signal_dates[-1] if signal_dates else None,
        "signal_periods": result["periods"],
        "direction": 1,
        "selected_group": result["selected_group"],
        "stock_count_mean": result["stock_count_mean"],
        "long_count_mean": result["long_count_mean"],
        "short_count_mean": result["short_count_mean"],
        "rank_ic": result["rank_ic"],
        "ic_mean": result["ic_mean"],
        "gross_excess_pct": pct(result["gross_excess"]),
        "long_turnover_pct": pct(result["turnover"]),
        "long_annual_cost_pct": pct(result["annual_cost"]),
        "net_excess_pct": pct(result["net_excess"]),
        "long_short_gross_pct": pct(result["long_short_gross"]),
        "long_short_turnover_pct": pct(result["long_short_turnover"]),
        "long_short_annual_cost_pct": pct(result["long_short_annual_cost"]),
        "long_short_net_pct": pct(result["long_short_net"]),
        "short_turnover_pct": pct(result["short_turnover"]),
    }


def latest_snapshot(signal: pd.DataFrame, latest_date: pd.Timestamp) -> list[dict[str, Any]]:
    current = signal[signal["date"].eq(latest_date)].sort_values(
        ["factor", "instrument"], ascending=[False, True], kind="stable"
    )
    return [
        {"instrument": str(row.instrument), "factor": float(row.factor)}
        for row in current.head(20).itertuples(index=False)
    ]


def write_outputs(
    output_root: Path,
    settings: dict[str, Any],
    rows: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": settings,
        "candidates": CANDIDATES,
        "results": rows,
        "latest_snapshot": snapshots,
    }
    json_path = output_root / "quantpedia_additional_local_reproduction.json"
    csv_path = output_root / "quantpedia_additional_local_reproduction.csv"
    md_path = output_root / "quantpedia_additional_local_reproduction.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    machine = settings["machine_profile"]

    def show_pct(value: Any) -> str:
        return "n/a" if value is None else f"{float(value):.2f}%"

    lines = [
        "# Additional Quantpedia local reproduction",
        "",
        f"Machine: `{machine}` ({settings['machine_label']}).",
        "No PandaAI factor was created or run. No Tushare network request was made.",
        "Data source: cached Tushare qfq price data and signal-day daily_basic.total_mv.",
        f"Alignment rule: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        f"Universe: full-A `.SH/.SZ`; warm-up `{DATA_START.date()}`; label `close(t+1) -> close(t+1+cycle)`.",
        f"Formal window: `{FORMAL_START.date()}` to `{FORMAL_END.date()}`; recent diagnostic starts `{RECENT_START.date()}`.",
        "",
        "## Candidate status",
        "",
        "| candidate | status | formula | local treatment | source |",
        "|---|---|---|---|---|",
    ]
    for name, spec in CANDIDATES.items():
        lines.append(
            f"| `{name}` | `{spec['status']}` | `{spec['formula']}` | "
            f"{spec['note']} | [{spec['source']}]({spec['source']}) |"
        )
    lines.extend(
        [
            "",
            "## Computed proxy",
            "",
            "The supported candidate is an explicit proxy, not a byte-level reproduction of the source portfolio.",
            "",
            "- Six-month return and volatility use 126 trading days and are shifted back five trading days to skip the latest week.",
            "- The signal-day universe keeps the top 50% by `daily_basic.total_mv`, then the top 50% by lagged volatility.",
            "- Return is ranked into 10 groups; the local evaluator uses a 21-trading-day holding label because it does not model overlapping six-month positions.",
            "- `factor_valid` top-group metrics are reported separately from the source-style top-minus-bottom long-short spread.",
            "",
            "## Results",
            "",
            "Recent results are diagnostics and are not mixed into formal ranking.",
            "",
            "| window | periods | stocks | RankIC | IC | top gross excess | top cost | top net excess | long-short gross | long-short cost | long-short net | long turnover | short turnover |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        rank_ic = "n/a" if row["rank_ic"] is None else f"{float(row['rank_ic']):.4f}"
        ic_mean = "n/a" if row["ic_mean"] is None else f"{float(row['ic_mean']):.4f}"
        stocks = "n/a" if row["stock_count_mean"] is None else f"{float(row['stock_count_mean']):.1f}"
        lines.append(
            f"| `{row['window']}` | {row['signal_periods']} | {stocks} | {rank_ic} | {ic_mean} | "
            f"{show_pct(row['gross_excess_pct'])} | {show_pct(row['long_annual_cost_pct'])} | "
            f"{show_pct(row['net_excess_pct'])} | {show_pct(row['long_short_gross_pct'])} | "
            f"{show_pct(row['long_short_annual_cost_pct'])} | {show_pct(row['long_short_net_pct'])} | "
            f"{show_pct(row['long_turnover_pct'])} | {show_pct(row['short_turnover_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## Latest snapshot",
            "",
            f"Signal date: `{settings['latest_signal_date']}`.",
            "",
            "| rank | instrument | six-month return signal |",
            "|---:|---|---:|",
        ]
    )
    for index, item in enumerate(snapshots, start=1):
        lines.append(f"| {index} | {item['instrument']} | {item['factor']:.8f} |")
    lines.extend(
        [
            "",
            "## Unsupported candidates",
            "",
            "NCAV/MV and the balance-sheet accrual anomaly are intentionally not assigned proxy values. Their required fields are absent or incomplete in the local cache; substituting total assets, OCF, or other nearby fields would change the factor definition.",
            "",
            "## Interpretation",
            "",
            "This is a China A-share local diagnostic using Tushare cache data. Quantpedia source results use different markets, samples, portfolio rules, and holding periods, so their headline returns are not directly comparable to these numbers.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"json={json_path}", flush=True)
    print(f"csv={csv_path}", flush=True)
    print(f"md={md_path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-root", type=Path, required=True)
    parser.add_argument("--cap-root", type=Path, required=True)
    parser.add_argument("--calendar-root", type=Path, required=True)
    parser.add_argument("--data-end", type=str, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rss-gb", type=float, default=MAX_RSS_GB)
    parser.add_argument("--min-available-gb", type=float, default=MIN_AVAILABLE_GB)
    args = parser.parse_args()

    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {args.output}")
    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)
    if not (PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT).is_file():
        raise SystemExit(f"Alignment rules document is missing: {ALIGNMENT_RULES_DOCUMENT}")

    data_end = (
        pd.Timestamp(pd.to_datetime(args.data_end, format="%Y%m%d"))
        if args.data_end
        else detect_cache_end(args.cap_root)
    ).normalize()
    if data_end < FORMAL_END:
        raise SystemExit(f"Local data end {data_end.date()} is earlier than formal end {FORMAL_END.date()}")

    print(
        f"candidate=momentum_reversal_volatility cycle={CYCLE} "
        f"data={DATA_START.date()}..{data_end.date()}",
        flush=True,
    )
    memory_guard("start", args.max_rss_gb, args.min_available_gb)
    frame = load_minimal_full_a(
        args.price_root,
        args.cap_root,
        DATA_START,
        data_end,
        max_rss_gb=args.max_rss_gb,
        min_available_gb=args.min_available_gb,
    )
    latest_data_date = pd.Timestamp(frame["date"].max()).normalize()
    calendar = load_calendar(args.calendar_root, DATA_START, latest_data_date)
    if not calendar:
        raise RuntimeError("No cached trade-calendar dates are available")
    if latest_data_date > calendar[-1]:
        latest_data_date = calendar[-1]
    print(
        f"local_rows={len(frame)} pool={frame['instrument'].nunique()} "
        f"data={frame['date'].min().date()}..{latest_data_date.date()} "
        f"calendar={len(calendar)}",
        flush=True,
    )
    memory_guard("loaded_frame", args.max_rss_gb, args.min_available_gb)

    all_dates = generated_signal_dates(calendar, FORMAL_START, latest_data_date, CYCLE)
    formal_dates = [date for date in all_dates if date <= FORMAL_END]
    recent_dates = [date for date in all_dates if RECENT_START <= date <= latest_data_date]
    if not formal_dates or not recent_dates:
        raise RuntimeError("No usable formal or recent signal dates")
    print(
        f"formal_dates={len(formal_dates)} {formal_dates[0].date()}..{formal_dates[-1].date()} "
        f"recent_dates={len(recent_dates)} {recent_dates[0].date()}..{recent_dates[-1].date()}",
        flush=True,
    )

    memory_guard("before_features", args.max_rss_gb, args.min_available_gb)
    return_signal, volatility_signal = build_features(frame)
    memory_guard("after_features", args.max_rss_gb, args.min_available_gb)

    all_dates_for_caps = list(dict.fromkeys(all_dates))
    large_cap_sets = load_large_cap_sets(
        args.cap_root,
        all_dates_for_caps,
        pd.Index(frame["instrument"].astype(str).unique()),
        args.max_rss_gb,
        args.min_available_gb,
    )
    memory_guard("after_signal_caps", args.max_rss_gb, args.min_available_gb)
    signal, subset_diagnostics = build_signal_frame(
        frame,
        return_signal,
        volatility_signal,
        all_dates_for_caps,
        large_cap_sets,
    )
    del return_signal, volatility_signal, large_cap_sets
    gc.collect()
    memory_guard("after_signal_frame", args.max_rss_gb, args.min_available_gb)

    close = panel_close(frame, calendar)
    close.columns = pd.Index(close.columns.astype(str))
    memory_guard("after_close_panel", args.max_rss_gb, args.min_available_gb)

    rows: list[dict[str, Any]] = []
    formal_result = evaluate_proxy(signal, close, calendar, formal_dates)
    memory_guard("after_formal", args.max_rss_gb, args.min_available_gb)
    recent_result = evaluate_proxy(signal, close, calendar, recent_dates)
    memory_guard("after_recent", args.max_rss_gb, args.min_available_gb)
    rows.append(metric_row("formal_5y", FORMAL_START, FORMAL_END, formal_dates, formal_result))
    rows.append(metric_row("recent_diagnostic", RECENT_START, latest_data_date, recent_dates, recent_result))
    latest_signal_date = all_dates[-1]
    snapshots = latest_snapshot(signal, latest_signal_date)

    machine = resolve_machine_profile()
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment_config": alignment_config,
        "machine_profile": machine["machine_profile"],
        "machine_label": machine["machine_label"],
        "data_provider": "Tushare",
        "network_access": "none",
        "price_source": "stk_factor qfq",
        "market_cap_source": "daily_basic.total_mv",
        "universe": "full_a",
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START,
        "formal_start": FORMAL_START,
        "formal_end": FORMAL_END,
        "recent_start": RECENT_START,
        "local_data_end": latest_data_date,
        "latest_signal_date": latest_signal_date,
        "groups": GROUPS,
        "cycle": CYCLE,
        "label_offset": ALIGNMENT_LABEL_OFFSET,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "benchmark_mode": "factor_valid",
        "signal_schedule": "generated_calendar_21d",
        "lookback_days": LOOKBACK,
        "skip_recent_days": SKIP_RECENT,
        "large_cap_fraction": CAP_FRACTION,
        "high_volatility_fraction": VOL_FRACTION,
        "holding_period_note": "21-day label proxy; source uses overlapping six-month holdings",
        "pool_count": int(frame["instrument"].nunique()),
        "local_rows": int(len(frame)),
        "signal_rows": int(len(signal)),
        "calendar_dates": int(len(calendar)),
        "formal_signal_periods": int(len(formal_dates)),
        "recent_signal_periods": int(len(recent_dates)),
        "subset_diagnostics": subset_diagnostics,
        "memory_limits": {
            "max_rss_gb": args.max_rss_gb,
            "min_available_gb": args.min_available_gb,
        },
    }
    write_outputs(args.output, settings, rows, snapshots)
    print(
        f"formal_top_net_pct={rows[0]['net_excess_pct']:.4f} "
        f"formal_long_short_net_pct={rows[0]['long_short_net_pct']:.4f} "
        f"recent_top_net_pct={rows[1]['net_excess_pct']:.4f} "
        f"recent_long_short_net_pct={rows[1]['long_short_net_pct']:.4f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
