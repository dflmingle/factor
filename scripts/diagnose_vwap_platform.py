#!/usr/bin/env python3
"""Offline diagnosis for the saved VWAP/volume/momentum platform run.

The saved formula is::

    ((MA(AMOUNT / VOLUME, 10) / CLOSE) - 1)
    * (VOLUME / MA(VOLUME, 20))
    * (BIAS(CLOSE, 20) / 100)

This script tests field-unit and rolling-operator hypotheses against the
archived PandaAI chart.  It never creates a factor, calls PandaAI, or changes
the canonical alignment rules.  Every variant remains a diagnostic proxy
until platform per-stock values or holdings are available.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_MODE,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_RULES_DOCUMENT,
)
from positive_factor_local_compare import rolling_stat  # noqa: E402
from tushare_factor_recheck import load_trade_dates  # noqa: E402


GROUPS = ALIGNMENT_GROUPS
SELECTED_GROUP = 10
DEFAULT_PLATFORM_RESULT = (
    PROJECT_ROOT
    / "vwap-volume-trend-raw.results"
    / "6aa518928b01f62dc51462aa.json"
)
DEFAULT_PRICE_ROOT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
)
DEFAULT_CAP_ROOT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/vwap_platform_20260917"


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def day_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def arithmetic_periods(cumulative: list[float]) -> np.ndarray:
    values = np.asarray(cumulative, dtype=float)
    if not len(values):
        return np.asarray([], dtype=float)
    return np.diff(np.concatenate(([0.0], values)))


def correlation(left: Any, right: Any) -> dict[str, Any]:
    joined = pd.DataFrame(
        {"local": np.asarray(left, dtype=float), "platform": np.asarray(right, dtype=float)}
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if joined.empty:
        return {"n": 0, "corr": None, "rmse": None, "mean_delta": None}
    delta = joined["local"] - joined["platform"]
    return {
        "n": int(len(joined)),
        "corr": finite(joined["local"].corr(joined["platform"]))
        if len(joined) > 1
        else None,
        "rmse": finite(np.sqrt(np.mean(delta**2))),
        "mean_delta": finite(delta.mean()),
    }


def make_close_panel(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    observed = frame.pivot(index="date", columns="instrument", values="close_qfq")
    return observed.reindex(calendar).sort_index(axis=1).ffill()


def panel_long(panel: pd.DataFrame, dates: list[pd.Timestamp], name: str) -> pd.DataFrame:
    work = panel.copy()
    work.index = pd.DatetimeIndex(dates)
    result = work.stack(dropna=False).rename(name).reset_index()
    return result.rename(columns={"level_0": "date", "level_1": "instrument"})


def build_returns(
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    label_offset: int,
) -> pd.DataFrame:
    positions = {date: index for index, date in enumerate(calendar)}
    current_positions = [positions[date] + label_offset for date in signal_dates]
    future_positions = [position + cycle for position in current_positions]
    if min(current_positions, default=0) < 0 or max(future_positions, default=-1) >= len(calendar):
        raise RuntimeError("Local data does not cover the requested forward label")
    current = panel_long(close.iloc[current_positions], signal_dates, "current_close")
    future = panel_long(close.iloc[future_positions], signal_dates, "future_close")
    result = current.merge(future, on=["date", "instrument"], how="left")
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    return result[["date", "instrument", "forward_return"]]


def platform_period_frame(platform: dict[str, Any]) -> pd.DataFrame:
    dates = pd.DatetimeIndex(platform["dates"]).normalize()
    rank = np.asarray(platform.get("rank_ic_values", []), dtype=float)
    if len(dates) != len(rank):
        raise RuntimeError("Platform chart dates and RankIC series lengths do not match")
    group_returns = arithmetic_periods(platform["return_cumulative"][SELECTED_GROUP - 1])
    group_excess = arithmetic_periods(platform["excess_cumulative"][SELECTED_GROUP - 1])
    if not (len(dates) == len(group_returns) == len(group_excess)):
        raise RuntimeError("Platform group-10 chart series lengths do not match")
    return pd.DataFrame(
        {
            "date": dates,
            "platform_rank_ic": rank,
            "platform_group_return": group_returns,
            "platform_excess": group_excess,
        }
    )


def factor_variants(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Build variants while sharing the expensive rolling calculations."""
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    close = pd.to_numeric(frame["close_qfq"], errors="coerce")
    amount_per_volume = amount.div(volume.replace(0.0, np.nan))
    ma_daily_vwap = rolling_stat(frame, amount_per_volume, 10, "mean")
    ma_amount = rolling_stat(frame, amount, 10, "mean")
    ma_volume10 = rolling_stat(frame, volume, 10, "mean")
    ma_volume20 = rolling_stat(frame, volume, 20, "mean")
    ma_close20 = rolling_stat(frame, close, 20, "mean")
    volume_ratio = volume.div(ma_volume20.replace(0.0, np.nan))
    bias = close.div(ma_close20.replace(0.0, np.nan)).sub(1.0)

    variants: dict[str, pd.Series] = {}
    for scale in [0.1, 1.0, 10.0, 100.0]:
        label = f"daily_vwap_mean_x{scale:g}"
        variants[label] = (ma_daily_vwap.mul(scale).div(close).sub(1.0) * volume_ratio * bias)
    aggregate_vwap = ma_amount.div(ma_volume10.replace(0.0, np.nan))
    for scale in [1.0, 10.0]:
        label = f"aggregate_vwap_x{scale:g}"
        variants[label] = (aggregate_vwap.mul(scale).div(close).sub(1.0) * volume_ratio * bias)
    return {name: value.replace([np.inf, -np.inf], np.nan) for name, value in variants.items()}


def evaluate_variant(
    frame: pd.DataFrame,
    values: pd.Series,
    returns: pd.DataFrame,
    platform_periods: pd.DataFrame,
    platform: dict[str, Any],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    label_offset: int,
    name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    data = frame[["date", "instrument"]].copy()
    data["factor"] = pd.to_numeric(values.to_numpy(), errors="coerce")
    data = data[data["date"].isin(signal_dates)]
    data = data.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    rows: list[dict[str, Any]] = []
    previous_members: set[str] | None = None
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
        benchmark = float(current["forward_return"].mean())
        selected = current[current["group"].eq(SELECTED_GROUP)]
        members = set(selected["instrument"].astype(str))
        turnover = (
            float(1.0 - len(members.intersection(previous_members)) / len(members))
            if previous_members
            else np.nan
        )
        previous_members = members
        group_return = float(selected["forward_return"].mean())
        rows.append(
            {
                "name": name,
                "date": date,
                "label_offset": label_offset,
                "stock_count": int(len(current)),
                "rank_ic": finite(rank_ic),
                "benchmark": benchmark,
                "group_return": group_return,
                "excess": group_return - benchmark,
                "turnover": finite(turnover),
                "selected_count": int(len(selected)),
            }
        )
    local = pd.DataFrame(rows)
    if local.empty:
        raise RuntimeError(f"No valid local periods for {name}, label={label_offset}")
    joined = local.merge(platform_periods, on="date", how="inner")
    periods_per_year = 252.0 / cycle
    years = len(local) / periods_per_year
    gross_excess = float(local["excess"].sum() / years)
    turnover_values = local["turnover"].dropna()
    turnover = float(turnover_values.mean()) if not turnover_values.empty else None
    annual_cost = (
        turnover * periods_per_year * ALIGNMENT_ROUND_TRIP_COST
        if turnover is not None
        else None
    )
    net_excess = gross_excess - annual_cost if annual_cost is not None else None
    platform_metric = platform_periods.attrs["group_metrics"][SELECTED_GROUP]
    platform_gross = platform_metric["excessAnnualized"]
    platform_turnover = platform_metric["turnoverRate"]
    platform_cost = platform_turnover * periods_per_year * ALIGNMENT_ROUND_TRIP_COST
    local_net_platform_cost = gross_excess - platform_cost
    top_date = max(
        [pd.Timestamp(row["date"]).normalize() for row in platform.get("top", []) if row.get("date")],
        default=signal_dates[-1],
    )
    latest = frame[frame["date"].eq(top_date)][["instrument"]].copy()
    latest["factor"] = values.reindex(latest.index).to_numpy()
    latest = latest.dropna().sort_values(["factor", "instrument"], ascending=[False, True])
    local_top = latest.head(20)["instrument"].astype(str).tolist()
    platform_top = [
        str(row["symbol"])
        for row in platform.get("top", [])
        if row.get("date") and pd.Timestamp(row["date"]).normalize() == top_date
    ]
    output = {
        "variant": name,
        "label_offset": label_offset,
        "periods": int(len(local)),
        "platform_periods": int(len(platform_periods)),
        "local_rank_ic": finite(local["rank_ic"].mean()),
        "platform_rank_ic": finite(platform["metrics"].get("Rank_IC")),
        "rank_ic_delta": finite(local["rank_ic"].mean() - platform["metrics"].get("Rank_IC")),
        "gross_excess": gross_excess,
        "platform_gross_excess": platform_gross,
        "gross_delta_pp": finite((gross_excess - platform_gross) * 100.0),
        "turnover": turnover,
        "platform_turnover": platform_turnover,
        "turnover_delta_pp": finite((turnover - platform_turnover) * 100.0)
        if turnover is not None
        else None,
        "annual_cost": annual_cost,
        "net_excess": net_excess,
        "platform_net_excess": finite(platform_gross - platform_cost),
        "net_delta_pp": finite((net_excess - (platform_gross - platform_cost)) * 100.0)
        if net_excess is not None
        else None,
        "local_net_using_platform_turnover": local_net_platform_cost,
        "platform_turnover_sensitivity_delta_pp": finite(
            (local_net_platform_cost - (platform_gross - platform_cost)) * 100.0
        ),
        "rank_ic_sequence": correlation(joined["rank_ic"], joined["platform_rank_ic"]),
        "group_return_sequence": correlation(
            joined["group_return"], joined["platform_group_return"]
        ),
        "excess_sequence": correlation(joined["excess"], joined["platform_excess"]),
        "cumulative_excess_sequence": correlation(
            joined["excess"].cumsum(), joined["platform_excess"].cumsum()
        ),
        "top_date": day_text(top_date),
        "top20_overlap": len(set(local_top).intersection(platform_top)),
        "local_top20": local_top,
        "platform_top20": platform_top,
    }
    return output, local


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# VWAP 平台结果离线诊断",
        "",
        "本报告只读取已保存的 PandaAI 结果和本地 Tushare 缓存，不创建因子、不发起平台回测。",
        "",
        f"- 规则版本：`{ALIGNMENT_RULE_VERSION}`；规则文档：`{ALIGNMENT_RULES_DOCUMENT}`",
        f"- 平台结果：`{payload['platform']['path']}`；平台公式：`{payload['platform']['formula']}`",
        f"- 正式本地基础口径：全 A、qfq、`{ALIGNMENT_MARKET_CAP_FIELD}`、平台信号日、10 组、`{ALIGNMENT_BENCHMARK_MODE}`、{ALIGNMENT_ONE_WAY_COST:.2%} 单边成本",
        "- 这些 variant 是诊断代理；没有平台逐股票因子值时，不把任何 variant 宣称为平台内部等价实现。",
        "",
        "## 关键结果",
        "",
        "| variant | label | RankIC local/platform | RankIC delta | gross excess local/platform | gross delta | net local/platform | net delta | platform-cost sensitivity delta | turnover local/platform | Top20 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        def pct(value: Any) -> str:
            return "n/a" if value is None else f"{float(value) * 100.0:.2f}%"

        def num(value: Any) -> str:
            return "n/a" if value is None else f"{float(value):.4f}"

        lines.append(
            f"| {row['variant']} | {row['label_offset']} | {num(row['local_rank_ic'])}/{num(row['platform_rank_ic'])} | {num(row['rank_ic_delta'])} | "
            f"{pct(row['gross_excess'])}/{pct(row['platform_gross_excess'])} | {pct(row['gross_delta_pp'] / 100.0) if row['gross_delta_pp'] is not None else 'n/a'} | "
            f"{pct(row['net_excess'])}/{pct(row['platform_net_excess'])} | {pct(row['net_delta_pp'] / 100.0) if row['net_delta_pp'] is not None else 'n/a'} | "
            f"{pct(row['platform_turnover_sensitivity_delta_pp'] / 100.0) if row['platform_turnover_sensitivity_delta_pp'] is not None else 'n/a'} | "
            f"{pct(row['turnover'])}/{pct(row['platform_turnover'])} | {row['top20_overlap']}/20 |"
        )
    lines.extend(
        [
            "",
            "`gross delta`、`net delta` 和 `platform-cost sensitivity delta` 均为本地减平台；敏感性只把平台摘要换手代入本地毛超额的成本计算，不替代正式本地净超额。",
            "",
            "## 序列相关",
            "",
            "| variant | label | RankIC sequence corr | group-return corr | excess corr | cumulative-excess corr |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["results"]:
        lines.append(
            f"| {row['variant']} | {row['label_offset']} | {num((row['rank_ic_sequence'] or {}).get('corr'))} | "
            f"{num((row['group_return_sequence'] or {}).get('corr'))} | {num((row['excess_sequence'] or {}).get('corr'))} | "
            f"{num((row['cumulative_excess_sequence'] or {}).get('corr'))} |"
        )
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 单位缩放只有在 RankIC、毛超额路径和 Top20 同时改善时，才可作为字段语义线索；净超额接近本身不够。",
            "- `AMOUNT/VOLUME` 的 Tushare 数据单位通常表现为千元/手，因此 `x10` 是有数据依据的诊断假设；本报告不据此自动改正式规则。",
            "- 若所有变体仍未同时通过 RankIC、收益路径和 Top20 门槛，结论保持 `field_or_path_mismatch`，不能用单位或成本调参抹平。",
            "",
            "## 数据与文件",
            "",
            f"- 本地 frame：`{payload['data']['rows']:,}` 行，`{payload['data']['instruments']}` 只股票；信号日：`{payload['data']['signal_dates']}` 期。",
            f"- 平台图表日期：`{payload['platform']['chart_start']}..{payload['platform']['chart_end']}`；Top20 日期：`{payload['platform']['top_date']}`。",
            "- `results.json`：机器可读的全部 variant 指标；`periods_*.csv`：逐期本地/平台序列对照。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


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


def run(args: argparse.Namespace) -> int:
    platform_path = Path(args.platform_result)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    platform = read_platform_run(platform_path)
    platform_periods = platform_period_frame(platform)
    platform_periods.attrs["group_metrics"] = platform["group_metrics"]
    signal_dates = [pd.Timestamp(value).normalize() for value in platform["dates"]]
    calendar = [
        pd.Timestamp(value).normalize()
        for value in load_trade_dates(pd.Timestamp(args.data_start), pd.Timestamp(args.end))
    ]
    print(
        f"platform_periods={len(signal_dates)} chart={day_text(signal_dates[0])}..{day_text(signal_dates[-1])}",
        flush=True,
    )
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        pd.Timestamp(args.data_start),
        pd.Timestamp(args.end),
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(
        f"local_rows={len(frame)} instruments={frame['instrument'].nunique()} dates={frame['date'].nunique()}",
        flush=True,
    )
    close = make_close_panel(frame, calendar)
    variants = factor_variants(frame)
    results: list[dict[str, Any]] = []
    data_payload: dict[str, Any] = {
        "rows": int(len(frame)),
        "instruments": int(frame["instrument"].nunique()),
        "dates": int(frame["date"].nunique()),
        "signal_dates": len(signal_dates),
        "calendar_days": len(calendar),
    }
    for name, values in variants.items():
        for label_offset in [1, 0]:
            print(f"evaluating={name} label={label_offset}", flush=True)
            returns = build_returns(close, calendar, signal_dates, 10, label_offset)
            result, periods = evaluate_variant(
                frame,
                values,
                returns,
                platform_periods,
                platform,
                signal_dates,
                10,
                label_offset,
                name,
            )
            results.append(result)
            periods.to_csv(output / f"periods_{name}_label{label_offset}.csv", index=False)
            print(
                f"{name} label={label_offset} rank={result['local_rank_ic']:.4f} "
                f"gross={result['gross_excess']:.4f} net={result['net_excess']:.4f} "
                f"top20={result['top20_overlap']}/20",
                flush=True,
            )
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "data_start": day_text(args.data_start),
            "end": day_text(args.end),
            "cycle": 10,
            "groups": GROUPS,
            "label_offsets": [1, 0],
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "diagnostic_only": True,
        },
        "platform": {
            "path": str(platform_path),
            "formula": "((MA(AMOUNT / VOLUME, 10) / CLOSE) - 1) * (VOLUME / MA(VOLUME, 20)) * (BIAS(CLOSE, 20) / 100)",
            "metrics": platform["metrics"],
            "group10": platform["group_metrics"][SELECTED_GROUP],
            "chart_periods": len(signal_dates),
            "chart_start": day_text(signal_dates[0]),
            "chart_end": day_text(signal_dates[-1]),
            "top_date": day_text(
                max(
                    [pd.Timestamp(row["date"]).normalize() for row in platform.get("top", []) if row.get("date")],
                    default=signal_dates[-1],
                )
            ),
        },
        "data": data_payload,
        "results": results,
    }
    (output / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    write_report(output / "diagnosis.md", payload)
    print(f"report={output / 'diagnosis.md'}", flush=True)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-result", default=str(DEFAULT_PLATFORM_RESULT))
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--end", default=ALIGNMENT_END)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    args.data_start = pd.Timestamp(pd.to_datetime(args.data_start, format="%Y%m%d"))
    args.end = pd.Timestamp(pd.to_datetime(args.end, format="%Y%m%d"))
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
