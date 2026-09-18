#!/usr/bin/env python3
"""Offline combination test for the seven correlation-PCA directions.

The script reads the existing saved factor catalog and local Tushare cache. It
does not create factors, call PandaAI, or add any platform backtests.

Each component is converted to a daily cross-sectional percentile rank after
its saved platform direction is applied. Combination scores are equal-weight
averages of those ranks. The canonical portfolio uses the seven representatives
selected from the earlier correlation PCA; leave-one-out rows are diagnostics,
not a post-hoc optimized portfolio.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_DESCRIPTION,
    ALIGNMENT_BENCHMARK_MODE,
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
    annualized_turnover_cost,
    validate_alignment_config,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    forward_returns,
    panel_close,
    saved_records,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
PLATFORM_START = pd.Timestamp(ALIGNMENT_START)
END = pd.Timestamp(ALIGNMENT_END)
GROUPS = ALIGNMENT_GROUPS
LABEL_OFFSET = ALIGNMENT_LABEL_OFFSET
ROUND_TRIP_COST = ALIGNMENT_ROUND_TRIP_COST

DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "pca-seven-class-combination-20260917"
)


# These are the representatives used in the preceding seven-direction
# interpretation. The PC7 momentum representative is tested separately because
# residual volatility and 120-day momentum had similar PC7 loadings.
#
# ``size_only`` is kept outside the historical canonical tuple so the old
# output remains reproducible. The size-aware portfolios below replace the
# impact representative with the direct small-cap factor: the pair report
# shows that these two exposures are a duplicate cluster (abs(rho) ~= 0.81
# after direction alignment), but the direct size factor has the stronger
# saved net excess.
CANONICAL_HANDLERS = (
    "reversal_chip_turn_paper",
    "impact_abs_return60",
    "book_to_market_lf_plus_impact",
    "turn_signal",
    "asset_growth",
    "fscore_interact",
    "residual_volatility",
)
ALTERNATIVE_PC7_HANDLER = "momentum120"
SIZE_HANDLER = "size_only"
ALL_HANDLERS = CANONICAL_HANDLERS + (ALTERNATIVE_PC7_HANDLER, SIZE_HANDLER)
CORE_PC1_TO_PC4 = CANONICAL_HANDLERS[:4]
SIZE_AWARE_CORE = (
    "reversal_chip_turn_paper",
    SIZE_HANDLER,
    "book_to_market_lf_plus_impact",
    "turn_signal",
)
SIZE_AWARE_SEVEN = (
    "reversal_chip_turn_paper",
    SIZE_HANDLER,
    "book_to_market_lf_plus_impact",
    "turn_signal",
    "asset_growth",
    "fscore_interact",
    "residual_volatility",
)

HANDLER_LABELS = {
    "reversal_chip_turn_paper": "反转/筹码/换手/基本面",
    "impact_abs_return60": "冲击/流动性",
    "book_to_market_lf_plus_impact": "价值/账面价值/冲击",
    "turn_signal": "换手方向",
    "asset_growth": "资产成长",
    "fscore_interact": "质量/财务健康",
    "residual_volatility": "残差波动风险",
    "momentum120": "动量/波动替代",
    "size_only": "市值/小市值",
}

HANDLER_RECORDS = {
    "reversal_chip_turn_paper": (
        "combo-direct-4factor-paper-20260909-candidates.report.csv",
        "COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ",
    ),
    "impact_abs_return60": (
        "verify-field-scan-cycle10-20260910-candidates.report.csv",
        "VERIFY10-G260910-13",
    ),
    "book_to_market_lf_plus_impact": (
        "verify-field-scan-cycle10-20260910-candidates.report.csv",
        "VERIFY10-F260910-12",
    ),
    "turn_signal": (
        "huatai-turn-bias-positive.report.csv",
        "HT13-TURN-BIAS-1M-POS",
    ),
    "asset_growth": (
        "paper-derived-full.report.csv",
        "paper-derived-asset-growth",
    ),
    "fscore_interact": (
        "literature-rankic-optimization-20260909-formula.report.csv",
        "NONHT-FSCORELIKE-REV40-INTERACT",
    ),
    "residual_volatility": (
        "nonhuatai-factor-6-20260909.report.csv",
        "NONHT-RESVOL-LOW",
    ),
    "momentum120": (
        "ht13-momentum-120d-d0.report.csv",
        "HT13-MOMENTUM-120D-D0",
    ),
    "size_only": (
        "size-only-20260911-candidates.report.csv",
        "SIZE-ONLY-20260911",
    ),
}

SCHEDULE_RECORDS = {
    5: (
        "verify-field-scan-20260910-candidates.report.csv",
        "VERIFY-F260910-12",
    ),
    10: (
        "verify-field-scan-cycle10-20260910-candidates.report.csv",
        "VERIFY10-F260910-12",
    ),
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


def find_record(
    records: list[dict[str, Any]],
    report: str,
    name: str,
) -> dict[str, Any]:
    for record in records:
        if record.get("report") == report and record.get("name") == name:
            if record.get("platform_net_excess_pct", 0.0) <= 0.0:
                raise RuntimeError(
                    f"Selected representative is not platform-net-positive: {report}:{name}"
                )
            if not record.get("raw_result"):
                raise RuntimeError(f"Selected representative has no saved result: {report}:{name}")
            result = dict(record)
            result["raw_result_path"] = PROJECT_ROOT / str(record["raw_result"])
            if not result["raw_result_path"].is_file():
                raise FileNotFoundError(result["raw_result_path"])
            return result
    raise KeyError(f"Saved record not found: {report}:{name}")


def usable_signal_dates(
    dates: list[pd.Timestamp],
    calendar: list[pd.Timestamp],
    cycle: int,
) -> list[pd.Timestamp]:
    calendar_positions = {date: position for position, date in enumerate(calendar)}
    result = []
    for value in dates:
        date = pd.Timestamp(value).normalize()
        position = calendar_positions.get(date)
        if position is None:
            continue
        if position + LABEL_OFFSET + cycle >= len(calendar):
            continue
        if date < PLATFORM_START or date > END:
            continue
        result.append(date)
    return list(dict.fromkeys(result))


def cross_sectional_scores(
    signal_frame: pd.DataFrame,
    raw_values: dict[str, pd.Series],
    directions: dict[str, int],
) -> pd.DataFrame:
    """Rank each component cross-sectionally after applying its saved direction."""
    scores: dict[str, pd.Series] = {}
    dates = signal_frame["date"]
    for handler, values in raw_values.items():
        oriented = pd.to_numeric(values, errors="coerce")
        if directions[handler] == 0:
            oriented = -oriented
        scores[handler] = oriented.groupby(dates, sort=False, observed=True).rank(
            method="average", pct=True
        )
    return pd.DataFrame(scores, index=signal_frame.index)


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def evaluate_portfolio(
    signal_frame: pd.DataFrame,
    score: pd.Series,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    portfolio_name: str,
    component_count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    returns = forward_returns(close, calendar, signal_dates, cycle, LABEL_OFFSET)
    data = signal_frame[["date", "instrument"]].copy()
    data["score"] = pd.to_numeric(score, errors="coerce").to_numpy(dtype=float)
    data = data.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    previous: set[str] | None = None
    rank_ics: list[float] = []
    ics: list[float] = []
    period_rows: list[dict[str, Any]] = []
    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = assign_groups(current["score"])
        rank_ic = current["score"].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        ic = current["score"].corr(current["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))

        held = current[current["group"].eq(GROUPS)]
        members = set(held["instrument"].astype(str))
        turnover = np.nan
        if previous is not None and members:
            turnover = 1.0 - len(members.intersection(previous)) / len(members)
        previous = members
        benchmark = float(current["forward_return"].mean())
        held_return = float(held["forward_return"].mean())
        period_rows.append(
            {
                "portfolio": portfolio_name,
                "cycle": cycle,
                "date": date,
                "stock_count": int(len(current)),
                "held_count": int(len(held)),
                "benchmark_return": benchmark,
                "held_return": held_return,
                "gross_excess": held_return - benchmark,
                "turnover": turnover,
                "component_count": component_count,
            }
        )

    periods = pd.DataFrame(period_rows)
    period_count = len(periods)
    years = period_count * cycle / 252.0
    if period_count == 0 or years <= 0:
        empty = {
            "portfolio": portfolio_name,
            "cycle": cycle,
            "component_count": component_count,
            "periods": 0,
            "first_signal_date": None,
            "last_signal_date": None,
            "mean_stock_count": None,
            "rank_ic": None,
            "ic_mean": None,
            "ic_ir": None,
            "gross_excess_pct": None,
            "turnover_pct": None,
            "annual_cost_pct": None,
            "net_excess_pct": None,
            "sharpe_after_cost": None,
            "max_drawdown_pct": None,
            "monthly_win_rate_pct": None,
        }
        return empty, period_rows

    turnover_values = periods["turnover"].dropna()
    turnover = float(turnover_values.mean()) if not turnover_values.empty else None
    gross_excess = float(periods["gross_excess"].sum() / years)
    annual_cost = annualized_turnover_cost(turnover, cycle, ROUND_TRIP_COST)
    net_excess = (
        gross_excess - annual_cost
        if annual_cost is not None
        else None
    )

    period_cost = periods["turnover"].fillna(0.0) * ROUND_TRIP_COST
    after_cost_returns = periods["held_return"] - period_cost
    return_mean = float(after_cost_returns.mean())
    return_std = float(after_cost_returns.std(ddof=1))
    sharpe = (
        return_mean / return_std * np.sqrt(252.0 / cycle)
        if return_std > 0.0
        else None
    )
    curve = (1.0 + after_cost_returns.to_numpy(dtype=float)).cumprod()
    running_max = np.maximum.accumulate(curve)
    drawdown = curve / running_max - 1.0
    max_drawdown = float(-drawdown.min() * 100.0)
    monthly = periods.assign(month=periods["date"].dt.to_period("M")).groupby(
        "month", sort=True
    )["gross_excess"].sum()
    monthly_win_rate = float(monthly.gt(0.0).mean() * 100.0) if len(monthly) else None
    ic_std = float(np.std(ics, ddof=1)) if len(ics) > 1 else None
    ic_mean = float(np.mean(ics)) if ics else None
    ic_ir = ic_mean / ic_std if ic_mean is not None and ic_std and ic_std > 0 else None

    result = {
        "portfolio": portfolio_name,
        "cycle": cycle,
        "component_count": component_count,
        "periods": period_count,
        "first_signal_date": periods["date"].min(),
        "last_signal_date": periods["date"].max(),
        "mean_stock_count": float(periods["stock_count"].mean()),
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": ic_mean,
        "ic_ir": ic_ir,
        "gross_excess_pct": gross_excess * 100.0,
        "turnover_pct": None if turnover is None else turnover * 100.0,
        "annual_cost_pct": None if annual_cost is None else annual_cost * 100.0,
        "net_excess_pct": None if net_excess is None else net_excess * 100.0,
        "sharpe_after_cost": None if sharpe is None else float(sharpe),
        "max_drawdown_pct": max_drawdown,
        "monthly_win_rate_pct": monthly_win_rate,
    }
    return result, period_rows


def format_value(value: Any, suffix: str = "") -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n/a"
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if suffix == "%":
        return f"{float(value):.2f}%"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.4f}"
    return str(value)


def write_outputs(
    output_prefix: Path,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_prefix.with_suffix(".json")
    csv_path = output_prefix.with_suffix(".csv")
    periods_path = output_prefix.with_name(output_prefix.name + ".periods.csv")
    md_path = output_prefix.with_suffix(".md")
    for path in (json_path, csv_path, periods_path, md_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing combination output: {path}")

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    period_fields = list(period_rows[0].keys()) if period_rows else []
    with periods_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=period_fields)
        writer.writeheader()
        writer.writerows(period_rows)

    settings = payload["settings"]
    lines = [
        "# PCA seven-direction local combination test",
        "",
        f"规则版本：`{settings['alignment_rule_version']}`；规则文档：`{settings['alignment_rules_document']}`。",
        "",
        "这是本地 proxy 组合测试，不是 PandaAI 官方组合回测。组合方法为：每个代表因子先按信号日做截面百分位秩，再按保存的平台方向统一为高分持有，最后等权平均。组合净超额使用组合自身有效股票截面的 `factor_valid` 基准和本地实际成员换手。",
        "",
        "## 代表因子",
        "",
        "| 统计方向 | handler | 平台方向 | 平台净超额 | 说明 |",
        "|---|---|---:|---:|---|",
    ]
    for item in payload["representatives"]:
        lines.append(
            f"| {item['class_label']} | `{item['handler']}` | {item['platform_direction']} | {item['platform_net_excess_pct']:.2f}% | {item['name']}；{item['report']} |"
        )
    lines.extend(
        [
            "",
            "`momentum120` 是 PC7 的替代代表，单独作为敏感性组合测试；它没有替换主组合中的 `residual_volatility`。平台方向为 0 的 `asset_growth`（以及替代的 `momentum120`）在合成前已反向。",
            "历史 `four_core` 是预先固定的 PC1-PC4 核心组合；`five_core_*` 只是在该核心上各加入一个第 5-7 方向，用来观察弱方向是否改善，而不是权重搜索。",
            "`five_size_aware_core` 和 `seven_size_replace_impact` 是市值修正版：用独立的 `size_only` 替换与其方向对齐后高度相关的 `impact_abs_return60`，不把市值重复计权。`eight_equal_all_with_size` 则保留原 7 类并额外加入市值，作为不替换的敏感性测试。",
            "市值修正的依据来自已保存的相关性结果：`SIZE-ONLY-20260911` 与 `VERIFY10-G260910-13` 的原始 rho 为约 -0.8056，按两者平台方向对齐后约为 +0.8056；但纯小市值平台净超额为 21.43%，高于冲击代表的 13.94%。",
            "",
            "## 结果",
            "",
            "净超额为算术年化毛超额减本地实际换手成本；Sharpe 和最大回撤是组合持有端、扣除逐期换手成本后的本地风险 proxy。月度胜率统计月度毛超额大于 0 的月份。",
            "",
            "| 调仓 | 组合 | 因子数 | 期数 | RankIC | IC | 毛超额 | 换手 | 年化成本 | 净超额 | Sharpe | 最大回撤 | 月胜率 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["cycle"]),
                    row["portfolio"],
                    str(row["component_count"]),
                    str(row["periods"]),
                    format_value(row["rank_ic"]),
                    format_value(row["ic_mean"]),
                    format_value(row["gross_excess_pct"], "%"),
                    format_value(row["turnover_pct"], "%"),
                    format_value(row["annual_cost_pct"], "%"),
                    format_value(row["net_excess_pct"], "%"),
                    format_value(row["sharpe_after_cost"]),
                    format_value(row["max_drawdown_pct"], "%"),
                    format_value(row["monthly_win_rate_pct"], "%"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- 7 个方向来自相关矩阵 PCA 的统计方向，不是严格互斥的经济类别；等权秩组合是可解释的基准，不是针对本区间优化出的最优权重。",
            "- 逐一剔除行仅用于判断单个方向对组合的边际影响，不能把最高的一行当作无条件样本外结论。",
            "- 本地财务字段、残差波动率和冲击字段含规则文档中说明的 proxy；结果不能宣称与平台内部字段字节等价。",
            "- 信号日来自保存的平台结果；为使 5 日、10 日组合可比较，所有代表因子都在同一公共调仓日集合上重建。因子尚未形成有效值的早期日期会被组合 complete-case 排除，实际期数已在表中列出。",
            "",
            "详细逐期持仓端统计见：",
            f"`{periods_path}`",
            "",
            "机器可读汇总见：",
            f"`{json_path}` 和 `{csv_path}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--financial-root", default=str(DEFAULT_FINANCIAL_ROOT))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT_PREFIX))
    parser.add_argument(
        "--cycles",
        default="5,10",
        help="Comma-separated common rebalance cycles to test; supported saved schedules are 5 and 10.",
    )
    args = parser.parse_args()

    cycles = [int(value.strip()) for value in args.cycles.split(",") if value.strip()]
    if not cycles or any(cycle not in SCHEDULE_RECORDS for cycle in cycles):
        raise SystemExit("--cycles must contain only 5 and/or 10")
    alignment_config = {
        "universe": "full_a",
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START.strftime("%Y%m%d"),
        "start": ALIGNMENT_START,
        "end": END.strftime("%Y%m%d"),
        "groups": GROUPS,
        "label_offset": LABEL_OFFSET,
        "round_trip_cost": ROUND_TRIP_COST,
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
        "correlation_method": "daily_cross_sectional_spearman_mean",
        "platform_turnover_high_threshold": 0.85,
        "local_turnover_low_threshold": 0.50,
        "turnover_gap_alert_threshold": 0.25,
        "platform_turnover_over_100_threshold": 1.0,
        "turnover_sensitivity_method": (
            "local gross excess minus annualized cost using saved platform turnover; diagnostic only"
        ),
    }
    validate_alignment_config(alignment_config)

    catalog = formula_catalog()
    supported, _ = saved_records(catalog, "positive")
    records = {
        handler: find_record(supported, *HANDLER_RECORDS[handler])
        for handler in ALL_HANDLERS
    }
    schedule_records = {
        cycle: find_record(supported, *SCHEDULE_RECORDS[cycle]) for cycle in cycles
    }

    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    schedules: dict[int, list[pd.Timestamp]] = {}
    for cycle, record in schedule_records.items():
        platform = read_platform_run(record["raw_result_path"])
        dates = usable_signal_dates(platform["dates"], calendar, cycle)
        if not dates:
            raise RuntimeError(f"No usable saved signal dates for cycle {cycle}")
        schedules[cycle] = dates
        print(
            f"schedule cycle={cycle} dates={len(dates)} first={dates[0].date()} last={dates[-1].date()}",
            flush=True,
        )

    all_dates = sorted({date for dates in schedules.values() for date in dates})
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        DATA_START,
        END,
    )
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(f"local_rows={len(frame)} pool={frame['instrument'].nunique()}", flush=True)

    close = panel_close(frame, calendar)
    signal_mask = frame["date"].isin(all_dates)
    signal_frame = frame.loc[signal_mask, ["date", "instrument"]].copy()
    signal_frame.reset_index(drop=True, inplace=True)
    if signal_frame.duplicated(["date", "instrument"]).any():
        raise RuntimeError("Duplicate date/instrument rows in the common signal panel")

    financial = None
    if any(handler in FINANCIAL_HANDLERS for handler in ALL_HANDLERS):
        financial = load_financial_cache(Path(args.financial_root))
        print(f"financial_cache=loaded tables={len(financial)}", flush=True)

    raw_values: dict[str, pd.Series] = {}
    directions: dict[str, int] = {}
    representative_payload: list[dict[str, Any]] = []
    for handler in ALL_HANDLERS:
        record = records[handler]
        directions[handler] = int(record["direction"])
        print(f"building={handler} rows={len(frame)}", flush=True)
        values = build_factor(
            frame,
            handler,
            financial=financial,
            signal_dates=all_dates,
        )
        raw_values[handler] = pd.to_numeric(
            values.loc[signal_mask].reset_index(drop=True), errors="coerce"
        )
        representative_payload.append(
            {
                "class_label": HANDLER_LABELS[handler],
                "handler": handler,
                "name": record["name"],
                "report": record["report"],
                "formula": record["formula"],
                "platform_direction": directions[handler],
                "platform_net_excess_pct": record["platform_net_excess_pct"],
                "platform_rank_ic": record["platform_rank_ic"],
                "platform_turnover_pct": record["platform_turnover_pct"],
                "configured_cycle": record["configured_cycle"],
                "raw_result": record["raw_result"],
            }
        )
        del values
        gc.collect()

    scores = cross_sectional_scores(signal_frame, raw_values, directions)
    del raw_values
    gc.collect()

    portfolio_sets: dict[str, tuple[str, ...]] = {
        "four_core": CORE_PC1_TO_PC4,
        "five_size_aware_core": SIZE_AWARE_CORE,
        "five_core_residual": CORE_PC1_TO_PC4 + ("residual_volatility",),
        "five_core_quality": CORE_PC1_TO_PC4 + ("fscore_interact",),
        "five_core_growth": CORE_PC1_TO_PC4 + ("asset_growth",),
        "seven_equal_residual": CANONICAL_HANDLERS,
        "seven_size_replace_impact": SIZE_AWARE_SEVEN,
        "eight_equal_all_with_size": CANONICAL_HANDLERS + (SIZE_HANDLER,),
        "seven_equal_momentum": tuple(
            handler for handler in CANONICAL_HANDLERS if handler != "residual_volatility"
        )
        + (ALTERNATIVE_PC7_HANDLER,),
    }
    # Leave-one-out results are deliberately fixed before looking at the local
    # portfolio outcomes, so they diagnose contribution rather than optimize it.
    for omitted in CANONICAL_HANDLERS:
        portfolio_sets[f"seven_without_{omitted}"] = tuple(
            handler for handler in CANONICAL_HANDLERS if handler != omitted
        )

    rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    for cycle in cycles:
        signal_dates = schedules[cycle]
        for portfolio_name, handlers in portfolio_sets.items():
            score = scores[list(handlers)].mean(axis=1, skipna=False)
            result, periods = evaluate_portfolio(
                signal_frame,
                score,
                close,
                calendar,
                signal_dates,
                cycle,
                portfolio_name,
                len(handlers),
            )
            result["handlers"] = ",".join(handlers)
            rows.append(result)
            period_rows.extend(periods)
            print(
                f"result cycle={cycle} portfolio={portfolio_name} periods={result['periods']} net={result['net_excess_pct']}",
                flush=True,
            )

        for handler in ALL_HANDLERS:
            result, periods = evaluate_portfolio(
                signal_frame,
                scores[handler],
                close,
                calendar,
                signal_dates,
                cycle,
                f"single_{handler}",
                1,
            )
            result["handlers"] = handler
            rows.append(result)
            period_rows.extend(periods)
            print(
                f"result cycle={cycle} portfolio=single_{handler} periods={result['periods']} net={result['net_excess_pct']}",
                flush=True,
            )

    rows.sort(key=lambda row: (row["cycle"], row["net_excess_pct"] is None, -(row["net_excess_pct"] or -np.inf)))
    period_rows.sort(key=lambda row: (row["cycle"], row["portfolio"], row["date"]))

    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_config": alignment_config,
            "universe": "沪深全A",
            "price_mode": ALIGNMENT_PRICE_MODE,
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "data_start": DATA_START.strftime("%Y%m%d"),
            "comparison_start": PLATFORM_START.strftime("%Y%m%d"),
            "comparison_end": END.strftime("%Y%m%d"),
            "label": "close(t+1) -> close(t+1+cycle)",
            "groups": GROUPS,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ROUND_TRIP_COST,
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
            "combination_method": "direction-adjusted cross-sectional percentile rank mean",
            "schedule_source": "saved platform signal dates",
            "cycles": cycles,
            "schedule_dates": {str(cycle): len(dates) for cycle, dates in schedules.items()},
            "local_market_field_sources": frame.attrs.get("market_field_sources", {}),
        },
        "representatives": representative_payload,
        "portfolio_sets": {
            name: list(handlers) for name, handlers in portfolio_sets.items()
        },
        "results": rows,
        "artifacts": {
            "summary_csv": str(Path(args.output_prefix).with_suffix(".csv")),
            "period_csv": str(
                Path(args.output_prefix).with_name(
                    Path(args.output_prefix).name + ".periods.csv"
                )
            ),
        },
    }
    write_outputs(Path(args.output_prefix), payload, rows, period_rows)
    print(f"report={Path(args.output_prefix).with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
