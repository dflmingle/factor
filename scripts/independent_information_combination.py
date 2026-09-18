#!/usr/bin/env python3
"""Screen independent local information and test incremental combinations.

This is an offline analysis.  It uses only saved platform results and the
canonical local full-A cache; it never creates a factor or calls PandaAI.

The workflow is deliberately split into two questions:

1. Is a candidate sufficiently different from the factors already selected?
   This is measured by the mean daily cross-sectional Spearman correlation of
   direction-aligned scores.
2. Does adding that candidate improve a portfolio?  Candidates are added by
   training-period cost-adjusted net excess, then the same sequence is
   evaluated on the untouched later period.

The platform-positive and local-alignment filters are fixed before the local
combination search.  The local test is therefore a research proxy, not an
official platform pool backtest.
"""

from __future__ import annotations

import argparse
import csv
import gc
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from pca_seven_class_combination import usable_signal_dates  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
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
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    forward_returns,
    panel_close,
    saved_records,
)
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
START = pd.Timestamp(ALIGNMENT_START)
END = pd.Timestamp(ALIGNMENT_END)
TRAIN_END = pd.Timestamp("2024-09-06")
GROUPS = ALIGNMENT_GROUPS
LABEL_OFFSET = ALIGNMENT_LABEL_OFFSET
ROUND_TRIP_COST = ALIGNMENT_ROUND_TRIP_COST

DEFAULT_ALIGNMENT_REPORT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports"
    / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT_PREFIX = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/independent-information-combination-20260917"
)

SCHEDULE_SPECS = {
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


def normalize_formula(formula: Any) -> str:
    return re.sub(r"\s+", "", str(formula or "")).upper()


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def candidate_direction(candidate: dict[str, Any]) -> int:
    value = candidate.get("platform_factor_direction")
    if value is None or (isinstance(value, str) and not value.strip()):
        value = candidate.get("direction", 1)
    return 1 if int(value) == 1 else 0


def parse_thresholds(value: str) -> list[float]:
    thresholds = []
    for item in value.split(","):
        if not item.strip():
            continue
        threshold = float(item)
        if not 0.0 < threshold < 1.0:
            raise ValueError("correlation thresholds must be between 0 and 1")
        thresholds.append(threshold)
    if not thresholds:
        raise ValueError("at least one correlation threshold is required")
    return list(dict.fromkeys(thresholds))


def load_candidates(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    settings = payload.get("settings") or {}
    if settings.get("alignment_rule_version") != ALIGNMENT_RULE_VERSION:
        raise ValueError(
            "alignment report uses a different rule version: "
            f"{settings.get('alignment_rule_version')!r}; required {ALIGNMENT_RULE_VERSION!r}"
        )
    if settings.get("platform_net_filter") != "all":
        raise ValueError("the alignment report must be the canonical all-record report")

    by_cycle_formula: dict[tuple[int, str], dict[str, Any]] = {}
    duplicate_ids: dict[tuple[int, str], list[str]] = {}
    for source in payload.get("results", []):
        platform_net = finite(source.get("platform_net_excess_pct"))
        cycle = int(source.get("cycle") or 0)
        if (
            platform_net is None
            or platform_net <= 0.0
            or not source.get("local_mining_eligible")
            or cycle not in SCHEDULE_SPECS
            or not source.get("handler")
            or not source.get("formula")
        ):
            continue
        key = (cycle, normalize_formula(source["formula"]))
        duplicate_ids.setdefault(key, []).append(str(source.get("id")))
        previous = by_cycle_formula.get(key)
        if previous is None or (
            platform_net,
            finite(source.get("local_net_excess")) or -np.inf,
        ) > (
            finite(previous.get("platform_net_excess_pct")) or -np.inf,
            finite(previous.get("local_net_excess")) or -np.inf,
        ):
            by_cycle_formula[key] = dict(source)

    candidates: list[dict[str, Any]] = []
    for index, ((cycle, formula_key), source) in enumerate(
        sorted(by_cycle_formula.items(), key=lambda item: (item[0][0], item[0][1]))
    ):
        source["candidate_key"] = f"C{cycle}-{index + 1:03d}"
        source["cycle"] = cycle
        source["formula_key"] = formula_key
        source["formula_duplicate_count"] = len(duplicate_ids[(cycle, formula_key)])
        source["formula_duplicate_ids"] = duplicate_ids[(cycle, formula_key)]
        source["platform_net_excess_pct"] = float(source["platform_net_excess_pct"])
        source["local_net_excess_pct"] = (
            None
            if source.get("local_net_excess") is None
            else float(source["local_net_excess"]) * 100.0
        )
        candidates.append(source)
    if not candidates:
        raise ValueError("no positive, alignment-eligible candidates were found")
    return payload, candidates


def find_saved_record(
    records: list[dict[str, Any]], report: str, name: str
) -> dict[str, Any]:
    for record in records:
        if record.get("report") == report and record.get("name") == name:
            return record
    raise KeyError(f"saved schedule record not found: {report}:{name}")


def build_schedules(
    supported: list[dict[str, Any]],
    calendar: list[pd.Timestamp],
) -> dict[int, list[pd.Timestamp]]:
    schedules: dict[int, list[pd.Timestamp]] = {}
    for cycle, (report, name) in SCHEDULE_SPECS.items():
        record = find_saved_record(supported, report, name)
        raw_result = record.get("raw_result")
        if not raw_result:
            raise RuntimeError(f"schedule has no saved raw result: {report}:{name}")
        platform = read_platform_run(PROJECT_ROOT / str(raw_result))
        dates = usable_signal_dates(platform["dates"], calendar, cycle)
        if not dates:
            raise RuntimeError(f"no usable signal dates for cycle {cycle}")
        schedules[cycle] = dates
    return schedules


def cross_sectional_scores(
    signal_frame: pd.DataFrame,
    raw_values: dict[str, pd.Series],
    candidates: list[dict[str, Any]],
) -> pd.DataFrame:
    dates = signal_frame["date"]
    score_columns: dict[str, pd.Series] = {}
    for candidate in candidates:
        handler = str(candidate["handler"])
        oriented = pd.to_numeric(raw_values[handler], errors="coerce")
        if candidate_direction(candidate) == 0:
            oriented = -oriented
        score_columns[str(candidate["candidate_key"])] = oriented.groupby(
            dates, sort=False, observed=True
        ).rank(method="average", pct=True)
    return pd.DataFrame(score_columns, index=signal_frame.index)


def daily_correlations(
    dates: pd.Series,
    scores: pd.DataFrame,
    candidate_keys: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = dates.groupby(dates, sort=True).groups
    for left_key, right_key in itertools.combinations(candidate_keys, 2):
        values_left = scores[left_key]
        values_right = scores[right_key]
        correlations: list[float] = []
        common_counts: list[int] = []
        for index in grouped.values():
            left = values_left.loc[index]
            right = values_right.loc[index]
            valid = left.notna() & right.notna()
            count = int(valid.sum())
            if count < 3:
                continue
            correlation = left.loc[valid].corr(right.loc[valid])
            if pd.notna(correlation):
                correlations.append(float(correlation))
                common_counts.append(count)
        mean = float(np.mean(correlations)) if correlations else None
        rows.append(
            {
                "candidate_a": left_key,
                "candidate_b": right_key,
                "correlation": mean,
                "abs_correlation": None if mean is None else abs(mean),
                "days": len(correlations),
                "correlation_std": (
                    float(np.std(correlations, ddof=1))
                    if len(correlations) > 1
                    else None
                ),
                "common_stocks_mean": (
                    float(np.mean(common_counts)) if common_counts else None
                ),
                "common_stocks_min": min(common_counts) if common_counts else None,
            }
        )
    return rows


def correlation_map(rows: list[dict[str, Any]]) -> dict[frozenset[str], float]:
    result: dict[frozenset[str], float] = {}
    for row in rows:
        value = finite(row.get("correlation"))
        if value is not None:
            result[frozenset((str(row["candidate_a"]), str(row["candidate_b"]))) ] = value
    return result


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * GROUPS / len(values)).astype(int).clip(1, GROUPS)


def collect_periods(
    signal_frame: pd.DataFrame,
    score: pd.Series,
    returns: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
) -> pd.DataFrame:
    data = signal_frame[["date", "instrument"]].copy()
    data["score"] = pd.to_numeric(score, errors="coerce").to_numpy(dtype=float)
    data = data.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    previous: set[str] | None = None
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
                "date": date,
                "stock_count": int(len(current)),
                "held_count": int(len(held)),
                "benchmark_return": benchmark,
                "held_return": held_return,
                "gross_excess": held_return - benchmark,
                "turnover": turnover,
                "rank_ic": rank_ic,
                "ic": ic,
            }
        )
    return pd.DataFrame(period_rows)


def summarize_periods(
    periods: pd.DataFrame,
    cycle: int,
    period_label: str,
) -> dict[str, Any]:
    if periods.empty:
        return {
            "period_label": period_label,
            "periods": 0,
            "first_signal_date": None,
            "last_signal_date": None,
            "mean_stock_count": None,
            "rank_ic": None,
            "ic_mean": None,
            "gross_excess_pct": None,
            "turnover_pct": None,
            "annual_cost_pct": None,
            "net_excess_pct": None,
            "sharpe_after_cost": None,
            "max_drawdown_pct": None,
            "monthly_win_rate_pct": None,
        }
    years = len(periods) * cycle / 252.0
    turnover_values = periods["turnover"].dropna()
    turnover = float(turnover_values.mean()) if not turnover_values.empty else None
    gross = float(periods["gross_excess"].sum() / years)
    cost = annualized_turnover_cost(turnover, cycle, ROUND_TRIP_COST)
    net = gross - cost if cost is not None else None
    after_cost = periods["held_return"] - periods["turnover"].fillna(0.0) * ROUND_TRIP_COST
    std = float(after_cost.std(ddof=1)) if len(after_cost) > 1 else None
    mean = float(after_cost.mean()) if len(after_cost) else None
    sharpe = (
        mean / std * np.sqrt(252.0 / cycle)
        if mean is not None and std is not None and std > 0.0
        else None
    )
    curve = (1.0 + after_cost.to_numpy(dtype=float)).cumprod()
    running_max = np.maximum.accumulate(curve)
    max_drawdown = float(-(curve / running_max - 1.0).min() * 100.0)
    monthly = periods.assign(month=periods["date"].dt.to_period("M")).groupby(
        "month", sort=True
    )["gross_excess"].sum()
    return {
        "period_label": period_label,
        "periods": len(periods),
        "first_signal_date": periods["date"].min(),
        "last_signal_date": periods["date"].max(),
        "mean_stock_count": float(periods["stock_count"].mean()),
        "rank_ic": float(periods["rank_ic"].mean()),
        "ic_mean": float(periods["ic"].mean()),
        "gross_excess_pct": gross * 100.0,
        "turnover_pct": None if turnover is None else turnover * 100.0,
        "annual_cost_pct": None if cost is None else cost * 100.0,
        "net_excess_pct": None if net is None else net * 100.0,
        "sharpe_after_cost": None if sharpe is None else float(sharpe),
        "max_drawdown_pct": max_drawdown,
        "monthly_win_rate_pct": float(monthly.gt(0.0).mean() * 100.0)
        if len(monthly)
        else None,
    }


def evaluate_portfolio(
    name: str,
    selected: tuple[str, ...],
    scores: pd.DataFrame,
    signal_frame: pd.DataFrame,
    returns: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    cycle: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    score = scores[list(selected)].mean(axis=1, skipna=False)
    periods = collect_periods(signal_frame, score, returns, signal_dates)
    train = periods[periods["date"] <= TRAIN_END].copy()
    test = periods[periods["date"] > TRAIN_END].copy()
    full_summary = summarize_periods(periods, cycle, "full")
    train_summary = summarize_periods(train, cycle, "train")
    test_summary = summarize_periods(test, cycle, "test")
    row: dict[str, Any] = {
        "portfolio": name,
        "cycle": cycle,
        "component_count": len(selected),
        "components": ",".join(selected),
    }
    for label, summary in (
        ("full", full_summary),
        ("train", train_summary),
        ("test", test_summary),
    ):
        for key, value in summary.items():
            if key == "period_label":
                continue
            row[f"{label}_{key}"] = value
    periods = periods.copy()
    periods["portfolio"] = name
    periods["cycle"] = cycle
    periods["component_count"] = len(selected)
    periods["components"] = ",".join(selected)
    return row, periods


def choose_sequence(
    cycle: int,
    candidates: dict[str, dict[str, Any]],
    candidate_keys: list[str],
    correlations: dict[frozenset[str], float],
    scores: pd.DataFrame,
    signal_frame: pd.DataFrame,
    returns: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    threshold: float,
    max_factors: int,
    result_cache: dict[tuple[int, frozenset[str]], tuple[dict[str, Any], pd.DataFrame]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    def evaluate(selected: tuple[str, ...]) -> tuple[dict[str, Any], pd.DataFrame]:
        cache_key = (cycle, frozenset(selected))
        cached = result_cache.get(cache_key)
        if cached is not None:
            return cached
        name = "single_" + selected[0] if len(selected) == 1 else "combo_" + str(len(selected))
        result = evaluate_portfolio(
            name,
            selected,
            scores,
            signal_frame,
            returns,
            signal_dates,
            cycle,
        )
        result_cache[cache_key] = result
        return result

    selected: list[str] = []
    steps: list[dict[str, Any]] = []
    for step_number in range(1, max_factors + 1):
        available = []
        for key in candidate_keys:
            if key in selected:
                continue
            pair_values = [
                abs(correlations[frozenset((key, old))])
                for old in selected
                if frozenset((key, old)) in correlations
            ]
            if all(value < threshold for value in pair_values):
                available.append((key, max(pair_values, default=0.0)))
        if not available:
            break

        proposals: list[tuple[float, float, float, str, dict[str, Any]]] = []
        for key, max_corr in available:
            proposed = tuple(selected + [key])
            result, _ = evaluate(proposed)
            current_train: float | None = 0.0
            current_full: float | None = 0.0
            if selected:
                previous, _ = evaluate(tuple(selected))
                current_train = finite(previous.get("train_net_excess_pct"))
                current_full = finite(previous.get("full_net_excess_pct"))
            train_net = finite(result.get("train_net_excess_pct"))
            full_net = finite(result.get("full_net_excess_pct"))
            train_delta = (
                None
                if train_net is None or current_train is None
                else train_net - current_train
            )
            full_delta = (
                None
                if full_net is None or current_full is None
                else full_net - current_full
            )
            proposals.append(
                (
                    train_delta if train_delta is not None else -np.inf,
                    train_net if train_net is not None else -np.inf,
                    full_net if full_net is not None else -np.inf,
                    key,
                    {
                        "max_abs_correlation_to_selected": max_corr,
                        "train_delta_net_excess_pct": train_delta,
                        "full_delta_net_excess_pct": full_delta,
                        "result": result,
                    },
                )
            )
        proposals.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
        best_delta, _best_train, _best_full, key, proposal = proposals[0]
        # A candidate is called an incremental contributor only if it improves
        # the pre-declared training objective.  The stop rule prevents a long
        # list of low-correlation factors from diluting the portfolio.
        if selected and (not np.isfinite(best_delta) or best_delta <= 0.0):
            break
        selected.append(key)
        result = proposal["result"]
        steps.append(
            {
                "cycle": cycle,
                "threshold": threshold,
                "step": step_number,
                "candidate_key": key,
                "candidate_name": candidates[key]["name"],
                "handler": candidates[key]["handler"],
                "platform_net_excess_pct": candidates[key]["platform_net_excess_pct"],
                "local_net_excess_pct": candidates[key].get("local_net_excess_pct"),
                "max_abs_correlation_to_selected": proposal[
                    "max_abs_correlation_to_selected"
                ],
                "train_delta_net_excess_pct": proposal["train_delta_net_excess_pct"],
                "full_delta_net_excess_pct": proposal["full_delta_net_excess_pct"],
                "train_net_excess_pct": result.get("train_net_excess_pct"),
                "test_net_excess_pct": result.get("test_net_excess_pct"),
                "full_net_excess_pct": result.get("full_net_excess_pct"),
                "selected_after": ",".join(selected),
            }
        )
    return steps, [
        result_cache[(cycle, frozenset(selected))][0]
    ] if selected and (cycle, frozenset(selected)) in result_cache else []


def enrich_candidate_rows(
    candidates: list[dict[str, Any]],
    scores: pd.DataFrame,
    signal_frame: pd.DataFrame,
    schedules: dict[int, list[pd.Timestamp]],
) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        key = str(candidate["candidate_key"])
        cycle = int(candidate["cycle"])
        cycle_dates = set(schedules[cycle])
        values = scores.loc[signal_frame["date"].isin(cycle_dates), key]
        valid_by_date = values.groupby(
            signal_frame.loc[values.index, "date"], sort=False, observed=True
        ).apply(lambda series: int(series.notna().sum()))
        rows.append(
            {
                "candidate_key": key,
                "cycle": cycle,
                "name": candidate["name"],
                "handler": candidate["handler"],
                "formula": candidate["formula"],
                "direction": candidate_direction(candidate),
                "platform_net_excess_pct": candidate["platform_net_excess_pct"],
                "local_net_excess_pct": candidate.get("local_net_excess_pct"),
                "alignment_quality": candidate.get("alignment_quality"),
                "formula_duplicate_count": candidate["formula_duplicate_count"],
                "valid_signal_days": int(valid_by_date.gt(0).sum()),
                "signal_days": len(schedules[cycle]),
                "valid_row_fraction": float(values.notna().mean()) if len(values) else None,
            }
        )
    return rows


def write_outputs(
    output_prefix: Path,
    payload: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    correlation_rows: list[dict[str, Any]],
    step_rows: list[dict[str, Any]],
    portfolio_rows: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_prefix.with_suffix(".json"),
        "candidates": output_prefix.with_name(output_prefix.name + ".candidates.csv"),
        "correlations": output_prefix.with_name(output_prefix.name + ".correlations.csv"),
        "steps": output_prefix.with_name(output_prefix.name + ".steps.csv"),
        "portfolios": output_prefix.with_suffix(".csv"),
        "periods": output_prefix.with_name(output_prefix.name + ".periods.csv"),
        "markdown": output_prefix.with_suffix(".md"),
    }
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")

    payload["artifacts"] = {key: str(path) for key, path in paths.items()}
    paths["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    for key, rows in (
        ("candidates", candidate_rows),
        ("correlations", correlation_rows),
        ("steps", step_rows),
        ("portfolios", portfolio_rows),
        ("periods", period_rows),
    ):
        fields = list(rows[0].keys()) if rows else []
        with paths[key].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    settings = payload["settings"]
    lines = [
        "# Independent-information factor screening and combination",
        "",
        f"规则版本：`{settings['alignment_rule_version']}`；规则文档：`{settings['alignment_rules_document']}`。",
        "",
        "这是离线本地 proxy 分析，不创建因子、不调用 PandaAI。候选先要求平台净超额大于 0，并通过本地对齐质量门槛；完全相同公式在同一调仓周期内只保留一条。",
        "",
        "## Method",
        "",
        f"- 独立性：方向统一后，按信号日计算横截面 Spearman，再对日期取均值；筛选阈值分别为 `{', '.join(f'{x:.2f}' for x in settings['correlation_thresholds'])}`。",
        f"- 增量目标：从训练段（截至 `{settings['train_end']}`）开始，每次加入与已选因子相关性低于阈值、且使训练期成本后净超额增加的因子。",
        f"- 验证段：`{settings['test_start']}..{settings['comparison_end']}`，只用于检查已选序列是否保持，不参与选择。",
        f"- 组合：各因子先按信号日截面百分位秩，再等权平均；持有高分第 10 组；成本按本地实际成员换手和单边 `{settings['one_way_cost']:.2%}` 计算。",
        "- 这不是官方组合回测；训练期的逐步选择仍有样本内风险，验证段结果是更重要的判断依据。",
        "",
        "## Candidate pool",
        "",
        f"质量门槛前全量本地记录：`{settings['alignment_records']}`；通过门槛：`{settings['alignment_eligible_records']}`；平台净超额大于 0 且进入本分析：`{settings['candidate_count']}`。",
        "",
        "| 周期 | 因子 | handler | 平台净超额 | 本地净超额 | 公式重复数 | 有效信号日 | 有效行比例 |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(candidate_rows, key=lambda item: (item["cycle"], -item["platform_net_excess_pct"], item["candidate_key"])):
        local = "n/a" if row["local_net_excess_pct"] is None else f"{row['local_net_excess_pct']:.2f}%"
        fraction = "n/a" if row["valid_row_fraction"] is None else f"{row['valid_row_fraction']:.1%}"
        lines.append(
            f"| {row['cycle']} | {row['name']} | `{row['handler']}` | {row['platform_net_excess_pct']:.2f}% | {local} | {row['formula_duplicate_count']} | {row['valid_signal_days']}/{row['signal_days']} | {fraction} |"
        )

    lines.extend(
        [
            "",
            "## Greedy sequences",
            "",
            "主阈值固定看 `0.80`；`0.70` 和 `0.85` 是稳定性敏感性，不根据验证段挑最好的阈值。每一步只有训练期净超额增加才继续加入。",
            "",
            "| 周期 | 阈值 | 步骤 | 新加入因子 | 最大相关 | 训练期增量 | 全期增量 | 训练净超额 | 验证净超额 | 全期净超额 |",
            "|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in step_rows:
        def pct(value: Any) -> str:
            return "n/a" if value is None or not np.isfinite(float(value)) else f"{float(value):.2f}%"

        lines.append(
            f"| {row['cycle']} | {row['threshold']:.2f} | {row['step']} | {row['candidate_name']} (`{row['handler']}`) | {row['max_abs_correlation_to_selected']:.4f} | {pct(row['train_delta_net_excess_pct'])} | {pct(row['full_delta_net_excess_pct'])} | {pct(row['train_net_excess_pct'])} | {pct(row['test_net_excess_pct'])} | {pct(row['full_net_excess_pct'])} |"
        )

    lines.extend(
        [
            "",
            "## Portfolio comparison",
            "",
            "| 周期 | 组合 | 因子数 | 全期净超额 | 训练净超额 | 验证净超额 | 全期 Sharpe | 验证 Sharpe | 全期换手 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in portfolio_rows:
        def value(field: str, suffix: str = "") -> str:
            item = row.get(field)
            if item is None or (isinstance(item, float) and not np.isfinite(item)):
                return "n/a"
            return f"{float(item):.2f}{suffix}"

        lines.append(
            f"| {row['cycle']} | {row['portfolio']} | {row['component_count']} | {value('full_net_excess_pct', '%')} | {value('train_net_excess_pct', '%')} | {value('test_net_excess_pct', '%')} | {value('full_sharpe_after_cost')} | {value('test_sharpe_after_cost')} | {value('full_turnover_pct', '%')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- 相关性低只说明候选暴露不同；只有加入后训练期净超额增加、并且验证期没有失效，才称为有组合增量。",
            "- 平台净超额、对齐质量和本地结果分别保留；本地结果不能替代 PandaAI 官方组合成绩。",
            "- 未通过对齐门槛的因子没有进入候选池，即使其本地重建看起来收益很高，也不能作为独立信息证据。",
            "",
            f"完整相关矩阵：`{paths['correlations']}`；逐步筛选：`{paths['steps']}`；逐期结果：`{paths['periods']}`。",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-report", type=Path, default=DEFAULT_ALIGNMENT_REPORT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--output-prefix", type=Path, default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--thresholds", default="0.70,0.80,0.85")
    parser.add_argument("--max-factors", type=int, default=7)
    args = parser.parse_args()
    thresholds = parse_thresholds(args.thresholds)
    if args.max_factors < 1:
        raise SystemExit("--max-factors must be positive")

    alignment_config = {
        "universe": "full_a",
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": DATA_START.strftime("%Y%m%d"),
        "start": START.strftime("%Y%m%d"),
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
        "turnover_sensitivity_method": "local gross excess minus annualized cost using saved platform turnover; diagnostic only",
        "large_net_delta_pp": 5.0,
        "large_gross_delta_pp": 5.0,
        "large_rank_ic_delta": 0.02,
        "min_top20_overlap": 15,
        "min_period_coverage": 0.95,
        "turnover_dominant_max_sensitivity_delta_pp": 2.0,
    }
    validate_alignment_config(alignment_config)

    alignment_payload, candidates = load_candidates(args.alignment_report)
    candidate_by_key = {str(item["candidate_key"]): item for item in candidates}
    supported, _ = saved_records(formula_catalog(), "positive")
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    schedules = build_schedules(supported, calendar)
    all_dates = sorted({date for dates in schedules.values() for date in dates})
    frame = load_full_a_data(args.price_root, args.cap_root, DATA_START, END)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(
        f"candidates={len(candidates)} cycles="
        f"{sorted({int(item['cycle']) for item in candidates})} rows={len(frame)}",
        flush=True,
    )
    close = panel_close(frame, calendar)
    signal_mask = frame["date"].isin(all_dates)
    signal_frame = frame.loc[signal_mask, ["date", "instrument"]].copy().reset_index(drop=True)
    if signal_frame.duplicated(["date", "instrument"]).any():
        raise RuntimeError("duplicate date/instrument rows in signal panel")

    handlers = sorted({str(item["handler"]) for item in candidates})
    financial = None
    if any(handler in FINANCIAL_HANDLERS for handler in handlers):
        financial = load_financial_cache(args.financial_root)
        print(f"financial_cache=loaded tables={len(financial)}", flush=True)

    raw_values: dict[str, pd.Series] = {}
    for index, handler in enumerate(handlers, start=1):
        print(f"building={handler} ({index}/{len(handlers)})", flush=True)
        values = build_factor(frame, handler, financial=financial, signal_dates=all_dates)
        raw_values[handler] = pd.to_numeric(
            values.loc[signal_mask].reset_index(drop=True), errors="coerce"
        )
        del values
        gc.collect()
    scores = cross_sectional_scores(signal_frame, raw_values, candidates)
    del raw_values
    gc.collect()

    candidate_rows = enrich_candidate_rows(candidates, scores, signal_frame, schedules)
    correlation_rows: list[dict[str, Any]] = []
    for cycle in sorted(schedules):
        cycle_candidates = [item for item in candidates if int(item["cycle"]) == cycle]
        cycle_keys = [str(item["candidate_key"]) for item in cycle_candidates]
        cycle_mask = signal_frame["date"].isin(schedules[cycle])
        cycle_scores = scores.loc[cycle_mask, cycle_keys]
        cycle_dates = signal_frame.loc[cycle_mask, "date"]
        rows = daily_correlations(cycle_dates, cycle_scores, cycle_keys)
        for row in rows:
            row["cycle"] = cycle
        correlation_rows.extend(rows)

    returns_by_cycle = {
        cycle: forward_returns(close, calendar, schedules[cycle], cycle, LABEL_OFFSET)
        for cycle in schedules
    }
    result_cache: dict[
        tuple[int, frozenset[str]], tuple[dict[str, Any], pd.DataFrame]
    ] = {}
    portfolio_rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    threshold_sequences: dict[str, dict[str, list[str]]] = {}
    corr_map = correlation_map(correlation_rows)

    for cycle in sorted(schedules):
        cycle_candidates = [item for item in candidates if int(item["cycle"]) == cycle]
        cycle_keys = [str(item["candidate_key"]) for item in cycle_candidates]
        cycle_mask = signal_frame["date"].isin(schedules[cycle])
        cycle_signal_frame = signal_frame.loc[cycle_mask].copy()
        cycle_scores = scores.loc[cycle_mask, cycle_keys]
        cycle_threshold_sequences: dict[str, list[str]] = {}

        # Single-factor baselines are evaluated before the greedy search. The
        # primary ranking is the training-period local net excess; full/test
        # values remain visible for audit and comparison.
        for key in cycle_keys:
            result, periods = evaluate_portfolio(
                f"single_{key}",
                (key,),
                cycle_scores,
                cycle_signal_frame,
                returns_by_cycle[cycle],
                schedules[cycle],
                cycle,
            )
            result["selection_role"] = "single_baseline"
            portfolio_rows.append(result)
            period_rows.extend(periods.to_dict("records"))
            result_cache[(cycle, frozenset((key,)))] = (result, periods)

        for threshold in thresholds:
            steps, final_results = choose_sequence(
                cycle,
                candidate_by_key,
                cycle_keys,
                corr_map,
                cycle_scores,
                cycle_signal_frame,
                returns_by_cycle[cycle],
                schedules[cycle],
                threshold,
                args.max_factors,
                result_cache,
            )
            for step in steps:
                step["threshold"] = threshold
            step_rows.extend(steps)
            selected = [step["candidate_key"] for step in steps]
            cycle_threshold_sequences[f"{threshold:.2f}"] = selected
            if selected:
                final_key = (cycle, frozenset(selected))
                result, periods = result_cache[final_key]
                result = dict(result)
                result["portfolio"] = f"greedy_{threshold:.2f}"
                result["selection_role"] = "greedy_combination"
                result["threshold"] = threshold
                portfolio_rows.append(result)
                period_rows.extend(periods.to_dict("records"))
        threshold_sequences[str(cycle)] = cycle_threshold_sequences

    portfolio_rows.sort(
        key=lambda row: (
            int(row["cycle"]),
            str(row.get("selection_role")),
            str(row["portfolio"]),
        )
    )
    period_rows.sort(key=lambda row: (int(row["cycle"]), str(row["portfolio"]), row["date"]))
    candidate_rows.sort(key=lambda row: (int(row["cycle"]), -row["platform_net_excess_pct"], row["candidate_key"]))

    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "alignment_config": alignment_config,
            "alignment_report": str(args.alignment_report.resolve().relative_to(PROJECT_ROOT.resolve())),
            "alignment_records": len(alignment_payload.get("results", [])),
            "alignment_eligible_records": sum(
                bool(item.get("local_mining_eligible"))
                for item in alignment_payload.get("results", [])
            ),
            "candidate_count": len(candidates),
            "candidate_selection": "platform_net_excess_pct > 0 and local_mining_eligible=true",
            "formula_deduplication": "exact normalized formula within cycle; keep highest platform net excess",
            "correlation_method": "direction_aligned_daily_cross_sectional_spearman_mean",
            "correlation_thresholds": thresholds,
            "selection_objective": "training-period local net excess after local turnover cost",
            "train_end": TRAIN_END.strftime("%Y-%m-%d"),
            "test_start": (TRAIN_END + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "comparison_start": START.strftime("%Y%m%d"),
            "comparison_end": END.strftime("%Y%m%d"),
            "groups": GROUPS,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "round_trip_cost": ROUND_TRIP_COST,
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
            "label": "close(t+1) -> close(t+1+cycle)",
            "schedule_dates": {str(cycle): len(dates) for cycle, dates in schedules.items()},
            "threshold_sequences": threshold_sequences,
            "local_market_field_sources": frame.attrs.get("market_field_sources", {}),
        },
        "candidates": candidate_rows,
        "correlations": correlation_rows,
        "selection_steps": step_rows,
        "portfolios": portfolio_rows,
    }
    write_outputs(
        args.output_prefix,
        payload,
        candidate_rows,
        correlation_rows,
        step_rows,
        portfolio_rows,
        period_rows,
    )
    print(f"report={args.output_prefix.with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
