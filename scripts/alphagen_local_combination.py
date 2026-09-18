#!/usr/bin/env python3
"""Run constrained AlphaGen-style local factor combinations.

The factor pool contains atomic information sources rather than the saved
paper composite.  AlphaGen's MSE pool is used for static selection, while the
AlphaPROBE-style expanding selector changes membership through time.  Both
outputs are projected to simple signed equal weights so the local test does
not turn into a continuous-weight search.
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
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
ALPHAGEN_ROOT = PROJECT_ROOT / "quantlab/third_party/AlphaGen"
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(ALPHAGEN_ROOT))

from alphagen.data.calculator import TensorAlphaCalculator  # noqa: E402
from alphagen.data.expression import Expression  # noqa: E402
from alphagen.models.linear_alpha_pool import MseAlphaPool  # noqa: E402
from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from independent_information_combination import (  # noqa: E402
    collect_periods,
    summarize_periods,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_START,
)
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    formula_catalog,
    forward_returns,
    panel_close,
    saved_records,
)
from pca_seven_class_combination import usable_signal_dates  # noqa: E402
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
START = pd.Timestamp(ALIGNMENT_START)
END = pd.Timestamp(ALIGNMENT_END)
TRAIN_END = pd.Timestamp("2024-09-06")
CYCLE = 10
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
    / "research_reports/platform_alignment/alphagen-local-combination-20260918"
)


# The first five entries split paper-derived-composite into its four atomic
# terms plus the previously validated impact source. The last three add price
# reversal, drawdown and turnover-aware reversal as separate sources.
FACTOR_SPECS: list[dict[str, Any]] = [
    {
        "name": "size_component",
        "handler": "paper_size_component",
        "source": "size",
        "formula": "-ZSCORE(RANK(MARKET_CAP))",
        "status": "local_component_proxy",
    },
    {
        "name": "impact60",
        "handler": "impact60",
        "source": "impact_liquidity",
        "formula": "RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))",
        "status": "saved_aligned_factor",
    },
    {
        "name": "value_component",
        "handler": "paper_bm_component",
        "source": "value",
        "formula": "ZSCORE(RANK(book_to_market_ratio_lyr))",
        "status": "local_component_proxy",
    },
    {
        "name": "roe_component",
        "handler": "paper_roe_component",
        "source": "profitability",
        "formula": "ZSCORE(RANK(oper_roe_lyr))",
        "status": "local_component_proxy",
    },
    {
        "name": "low_asset_growth_component",
        "handler": "paper_asset_growth_component",
        "source": "asset_growth",
        "formula": "-ZSCORE(RANK(gr_total_asset_lyr))",
        "status": "local_component_proxy",
    },
    {
        "name": "reversal40",
        "handler": "reversal40",
        "source": "price_reversal",
        "formula": "RANK(1-RETURNS(CLOSE,40))",
        "status": "saved_aligned_factor",
    },
    {
        "name": "drawdown120",
        "handler": "drawdown120",
        "source": "drawdown_risk",
        "formula": "RANK(1-CLOSE/TS_MAX(CLOSE,120))",
        "status": "saved_aligned_factor",
    },
    {
        "name": "weighted_reversal_lowturn",
        "handler": "weighted_reversal_lowturn",
        "source": "turnover_reversal",
        "formula": "(RANK(-SUM(TURNOVER*RETURNS(CLOSE,1),21)/SUM(TURNOVER,21))+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/2",
        "status": "saved_aligned_factor",
    },
]


class NamedExpression(Expression):
    """An AlphaGen expression backed by an already materialized local tensor."""

    def __init__(self, name: str) -> None:
        self.name = name

    def evaluate(self, data: Any, period: slice = slice(0, 1)) -> torch.Tensor:
        raise RuntimeError("NamedExpression is evaluated by LocalTensorCalculator")

    @property
    def is_featured(self) -> bool:
        return True

    def __str__(self) -> str:
        return self.name


class LocalTensorCalculator(TensorAlphaCalculator):
    def __init__(self, values: dict[str, torch.Tensor], target: torch.Tensor) -> None:
        super().__init__(target)
        self.values = values

    @property
    def n_days(self) -> int:
        return int(self.target.shape[0])

    def evaluate_alpha(self, expr: Expression) -> torch.Tensor:
        return self.values[str(expr)]


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if pd.isna(value):
        return None
    return value


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def find_schedule_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    report = "verify-field-scan-cycle10-20260910-candidates.report.csv"
    name = "VERIFY10-F260910-12"
    for record in records:
        if record.get("report") == report and record.get("name") == name:
            if not record.get("raw_result"):
                break
            return record
    raise KeyError(f"missing saved 10-day schedule: {report}:{name}")


def load_signal_dates(calendar: list[pd.Timestamp]) -> list[pd.Timestamp]:
    supported, _ = saved_records(formula_catalog(), "positive")
    record = find_schedule_record(supported)
    platform = read_platform_run(PROJECT_ROOT / str(record["raw_result"]))
    dates = usable_signal_dates(platform["dates"], calendar, CYCLE)
    if not dates:
        raise RuntimeError("saved platform schedule has no usable signal dates")
    return dates


def to_panel(
    signal_frame: pd.DataFrame,
    values: pd.Series,
    dates: list[pd.Timestamp],
    symbols: list[str],
) -> pd.DataFrame:
    data = signal_frame[["date", "instrument"]].copy()
    data["value"] = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    return (
        data.pivot(index="date", columns="instrument", values="value")
        .reindex(index=dates, columns=symbols)
        .sort_index()
    )


def rank_panel(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.rank(axis=1, method="average", pct=True)


def panel_to_series(panel: pd.DataFrame, signal_frame: pd.DataFrame) -> pd.Series:
    lookup = panel.stack(dropna=False)
    keys = pd.MultiIndex.from_frame(signal_frame[["date", "instrument"]])
    return pd.Series(lookup.reindex(keys).to_numpy(dtype=float), index=signal_frame.index)


def daily_rank_ic(
    score_panels: dict[str, pd.DataFrame], target: pd.DataFrame
) -> pd.DataFrame:
    """Return one cross-sectional RankIC observation per date and factor."""
    rows: list[dict[str, Any]] = []
    names = list(score_panels)
    for date in target.index:
        row: dict[str, Any] = {"date": date}
        target_row = target.loc[date]
        for name in names:
            left = score_panels[name].loc[date]
            valid = left.notna() & target_row.notna()
            if int(valid.sum()) < 3:
                row[name] = np.nan
                continue
            row[name] = left[valid].rank(method="average").corr(
                target_row[valid].rank(method="average")
            )
        rows.append(row)
    return pd.DataFrame(rows).set_index("date")


def static_mse_selection(
    score_panels: dict[str, pd.DataFrame],
    target: pd.DataFrame,
    train_dates: list[pd.Timestamp],
    capacity: int,
) -> tuple[list[str], dict[str, float], dict[str, float]]:
    names = list(score_panels)
    train_scores = {name: score_panels[name].loc[train_dates] for name in names}
    train_target = target.loc[train_dates]
    tensors = {
        name: torch.tensor(
            train_scores[name].to_numpy(dtype=np.float32),
            dtype=torch.float32,
        )
        for name in names
    }
    target_tensor = torch.tensor(
        train_target.to_numpy(dtype=np.float32),
        dtype=torch.float32,
    )
    calculator = LocalTensorCalculator(tensors, target_tensor)
    expressions = [NamedExpression(name) for name in names]
    pool = MseAlphaPool(
        capacity=len(expressions),
        calculator=calculator,
        l1_alpha=5e-3,
        device=torch.device("cpu"),
    )
    pool.force_load_exprs(expressions)
    loaded_names = [str(expr) for expr in pool.exprs[:pool.size]]
    raw_weights = {
        name: float(weight)
        for name, weight in zip(loaded_names, pool.weights)
    }
    single_ics = {
        name: float(calculator.calc_single_IC_ret(NamedExpression(name)))
        for name in loaded_names
    }
    order = sorted(
        loaded_names,
        key=lambda name: (-abs(raw_weights.get(name, 0.0)), name),
    )
    selected = order[: min(capacity, len(order))]
    return selected, raw_weights, single_ics


def alpha_probe_selection(
    score_panels: dict[str, pd.DataFrame],
    target: pd.DataFrame,
    dates: list[pd.Timestamp],
    train_count: int,
    n_factors: int,
    min_history: int = 20,
    threshold_ric: float = 0.015,
    threshold_ricir: float = 0.15,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    daily_ric = daily_rank_ic(score_panels, target)
    symbols = list(next(iter(score_panels.values())).columns)
    dynamic = pd.DataFrame(np.nan, index=dates, columns=symbols)
    selection_rows: list[dict[str, Any]] = []
    for position, date in enumerate(dates):
        if position < min_history:
            continue
        history = daily_ric.iloc[:position]
        mean = history.mean(axis=0, skipna=True)
        std = history.std(axis=0, ddof=1, skipna=True)
        ricir = mean.div(std.replace(0.0, np.nan))
        metrics = pd.DataFrame({"ric": mean, "ricir": ricir}).dropna()
        eligible = metrics[
            metrics["ric"].abs().gt(threshold_ric)
            & metrics["ricir"].abs().gt(threshold_ricir)
        ]
        ranked = eligible.sort_values(
            ["ricir", "ric"],
            key=lambda values: values.abs(),
            ascending=False,
        )
        if len(ranked) < 1:
            ranked = metrics.reindex(
                metrics["ricir"].abs().sort_values(ascending=False).index
            )
        selected = list(ranked.index[:n_factors])
        if not selected:
            continue
        weights = {
            name: (1.0 if mean[name] >= 0.0 else -1.0) / len(selected)
            for name in selected
        }
        dynamic.loc[date, :] = sum(
            (
                score_panels[name].loc[date].mul(weight)
                for name, weight in weights.items()
            ),
            start=pd.Series(0.0, index=symbols),
        )
        selection_rows.append(
            {
                "date": date,
                "position": position,
                "history_days": position,
                "selected": ",".join(selected),
                "selected_count": len(selected),
                "weights": ";".join(
                    f"{name}:{weights[name]:.6f}" for name in selected
                ),
                "ric": ";".join(f"{name}:{mean[name]:.6f}" for name in selected),
                "ricir": ";".join(f"{name}:{ricir[name]:.6f}" for name in selected),
                "is_validation": bool(position >= train_count),
            }
        )
    return dynamic, selection_rows


def evaluate_model(
    model: str,
    score_panel: pd.DataFrame,
    signal_frame: pd.DataFrame,
    returns: pd.DataFrame,
    dates: list[pd.Timestamp],
    selected: list[str],
    weights: dict[str, float],
    selected_label: str | None = None,
    weights_label: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    score = panel_to_series(score_panel, signal_frame)
    periods = collect_periods(signal_frame, score, returns, dates)
    selected_text = selected_label or ",".join(selected)
    weights_text = weights_label or ";".join(
        f"{name}:{weights.get(name, 0.0):.6f}" for name in selected
    )
    rows: list[dict[str, Any]] = []
    for label, subset in (
        ("full", periods),
        ("train", periods[periods["date"] <= TRAIN_END]),
        ("validation", periods[periods["date"] > TRAIN_END]),
    ):
        summary = summarize_periods(subset, CYCLE, label)
        summary.pop("period_label", None)
        summary.update(
            {
                "model": model,
                "period": label,
                "selected": selected_text,
                "weights": weights_text,
            }
        )
        rows.append(summary)
    period_rows = periods.copy()
    if not period_rows.empty:
        period_rows["model"] = model
        period_rows["selected"] = selected_text
        period_rows["weights"] = weights_text
        period_records = period_rows.to_dict("records")
    else:
        period_records = []
    return rows, period_records


def simple_score(scores: pd.DataFrame, selected: list[str], weights: dict[str, float]) -> pd.DataFrame:
    weighted = scores[selected].mul(pd.Series(weights)).sum(axis=1, skipna=False)
    # The input is a long-form row index when called from a panel; this helper
    # is retained for scalar weights and is not used for dynamic selection.
    return weighted


def build_static_score(
    scores: pd.DataFrame,
    selected: list[str],
    weights: dict[str, float],
) -> pd.DataFrame:
    return scores[selected].mul(pd.Series(weights), axis=1).sum(axis=1, skipna=False)


def write_outputs(
    output_prefix: Path,
    payload: dict[str, Any],
    result_rows: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
) -> None:
    paths = {
        "json": output_prefix.with_suffix(".json"),
        "csv": output_prefix.with_suffix(".csv"),
        "periods": output_prefix.with_name(output_prefix.name + ".periods.csv"),
        "selections": output_prefix.with_name(output_prefix.name + ".selections.csv"),
        "md": output_prefix.with_suffix(".md"),
    }
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    for key, rows in (
        ("csv", result_rows),
        ("periods", period_rows),
        ("selections", selection_rows),
    ):
        fields = list(rows[0].keys()) if rows else []
        with paths[key].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    lines = [
        "# AlphaGen local constrained combination",
        "",
        f"Alignment rules: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`.",
        "",
        "The saved paper composite is removed from the pool and represented by four atomic terms. All factors are direction-aligned and cross-sectionally ranked before combination.",
        "MseAlphaPool is used for static IC/mutual-IC selection. AlphaPROBE-style expanding selection uses historical RankIC/RankICIR. Final weights are simple signed equal weights; the continuous optimizer weights are audit diagnostics only.",
        "",
        "## Factor pool",
        "",
        "| name | source | handler | status | formula |",
        "|---|---|---|---|---|",
    ]
    for item in payload["factor_specs"]:
        lines.append(
            f"| {item['name']} | {item['source']} | `{item['handler']}` | {item['status']} | `{item['formula']}` |"
        )
    lines.extend(
        [
            "",
            "## Results",
            "",
            "Net excess is arithmetic annualized gross excess minus local turnover cost under the alignment contract.",
            "",
            "| model | period | factors | weights | net excess | turnover | Sharpe | max drawdown | RankIC |",
            "|---|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in result_rows:
        def fmt(value: Any, suffix: str = "") -> str:
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                return "n/a"
            return f"{float(value):.2f}{suffix}" if suffix else f"{float(value):.4f}"

        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["model"]),
                    str(row["period"]),
                    str(row["selected"]),
                    str(row["weights"]),
                    fmt(row.get("net_excess_pct"), "%"),
                    fmt(row.get("turnover_pct"), "%"),
                    fmt(row.get("sharpe_after_cost")),
                    fmt(row.get("max_drawdown_pct"), "%"),
                    fmt(row.get("rank_ic")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "- Component terms without an individual saved positive platform run are labeled `local_component_proxy`; they are not presented as independent platform factors.",
            "- AlphaPROBE uses expanding historical selection only. Its original continuous least-squares coefficients are not used in the reported combination, so the result tests adaptive membership rather than a rolling coefficient search.",
            "- The validation period is a holdout for the static MSE fit and for each expanding selection decision; factor-set choice still comes from the existing research catalog.",
            "",
            f"Detailed periods: `{paths['periods']}`; rolling selections: `{paths['selections']}`.",
        ]
    )
    paths["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-report", type=Path, default=DEFAULT_ALIGNMENT_REPORT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--output-prefix", type=Path, default=DEFAULT_OUTPUT_PREFIX)
    args = parser.parse_args()

    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    signal_dates = load_signal_dates(calendar)
    train_dates = [date for date in signal_dates if date <= TRAIN_END]
    if len(train_dates) < 20:
        raise RuntimeError("not enough training signal dates")
    frame = load_full_a_data(args.price_root, args.cap_root, DATA_START, END)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    signal_mask = frame["date"].isin(signal_dates)
    signal_frame = frame.loc[signal_mask, ["date", "instrument"]].copy().reset_index(drop=True)
    symbols = sorted(signal_frame["instrument"].astype(str).unique())
    if signal_frame.duplicated(["date", "instrument"]).any():
        raise RuntimeError("duplicate signal date/instrument rows")

    financial = load_financial_cache(args.financial_root)
    raw_panels: dict[str, pd.DataFrame] = {}
    for index, spec in enumerate(FACTOR_SPECS, start=1):
        handler = str(spec["handler"])
        if handler not in FINANCIAL_HANDLERS and handler not in {"impact60", "reversal40", "drawdown120", "weighted_reversal_lowturn"}:
            raise RuntimeError(f"factor handler is not registered: {handler}")
        print(f"building={spec['name']} handler={handler} ({index}/{len(FACTOR_SPECS)})", flush=True)
        values = build_factor(
            frame,
            handler,
            financial=financial,
            signal_dates=signal_dates,
        )
        raw_panels[str(spec["name"])] = to_panel(
            signal_frame,
            values.loc[signal_mask].reset_index(drop=True),
            signal_dates,
            symbols,
        )
        del values
        gc.collect()

    # Build the original composite only as a transparent comparison baseline.
    composite_values = build_factor(
        frame,
        "paper_composite",
        financial=financial,
        signal_dates=signal_dates,
    )
    raw_panels["paper_composite_baseline"] = to_panel(
        signal_frame,
        composite_values.loc[signal_mask].reset_index(drop=True),
        signal_dates,
        symbols,
    )
    del composite_values
    gc.collect()

    score_panels: dict[str, pd.DataFrame] = {}
    for name in raw_panels:
        score_panels[name] = rank_panel(raw_panels[name]).reindex(
            index=signal_dates, columns=symbols
        )
    target_long = forward_returns(
        panel_close(frame, calendar),
        calendar,
        signal_dates,
        CYCLE,
        LABEL_OFFSET,
    )
    target = target_long.pivot(
        index="date", columns="instrument", values="forward_return"
    ).reindex(index=signal_dates, columns=symbols)
    returns = target_long

    pool_names = [str(spec["name"]) for spec in FACTOR_SPECS]

    result_rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []

    # Baselines: the two strongest saved sources, the original composite, and
    # the full atomic pool with simple equal weights.
    baseline_specs = [
        ("baseline_size_only", ["size_component"], {"size_component": 1.0}),
        ("baseline_impact_only", ["impact60"], {"impact60": 1.0}),
        (
            "baseline_size_impact",
            ["size_component", "impact60"],
            {"size_component": 0.5, "impact60": 0.5},
        ),
        (
            "baseline_size_impact_value",
            ["size_component", "impact60", "value_component"],
            {"size_component": 0.5, "impact60": 0.25, "value_component": 0.25},
        ),
        ("baseline_paper_composite", ["paper_composite_baseline"], {"paper_composite_baseline": 1.0}),
        (
            "baseline_atomic_equal",
            pool_names,
            {name: 1.0 / len(pool_names) for name in pool_names},
        ),
    ]
    for model, selected, weights in baseline_specs:
        panel = sum(
            (score_panels[name].mul(weight) for name, weight in weights.items()),
            start=pd.DataFrame(0.0, index=signal_dates, columns=symbols),
        )
        rows, periods = evaluate_model(
            model,
            panel,
            signal_frame,
            returns,
            signal_dates,
            selected,
            weights,
        )
        result_rows.extend(rows)
        period_rows.extend(periods)

    # Static AlphaGen MSE selection on the training window.
    mse_selected, mse_raw, mse_single_ics = static_mse_selection(
        {name: score_panels[name] for name in pool_names},
        target,
        train_dates,
        capacity=5,
    )
    mse_weights = {
        name: (1.0 if mse_raw.get(name, 0.0) >= 0.0 else -1.0) / len(mse_selected)
        for name in mse_selected
    }
    mse_panel = sum(
        (score_panels[name].mul(weight) for name, weight in mse_weights.items()),
        start=pd.DataFrame(0.0, index=signal_dates, columns=symbols),
    )
    mse_rows, mse_periods = evaluate_model(
        "MseAlphaPool_simple",
        mse_panel,
        signal_frame,
        returns,
        signal_dates,
        mse_selected,
        mse_weights,
    )
    result_rows.extend(mse_rows)
    period_rows.extend(mse_periods)

    # AlphaPROBE-style expanding selection. It uses strict prior-date
    # RankIC/RankICIR history and equal signed weights after direction alignment.
    probe_panel, probe_selection_rows = alpha_probe_selection(
        {name: score_panels[name] for name in pool_names},
        target,
        signal_dates,
        len(train_dates),
        n_factors=5,
    )
    for row in probe_selection_rows:
        row["model"] = "AlphaPROBE_expanding_simple"
    selection_rows.extend(probe_selection_rows)
    probe_rows, probe_periods = evaluate_model(
        "AlphaPROBE_expanding_simple",
        probe_panel,
        signal_frame,
        returns,
        signal_dates,
        [],
        {},
        selected_label="dynamic_top5",
        weights_label="signed_equal_1/N_per_period",
    )
    result_rows.extend(probe_rows)
    period_rows.extend(probe_periods)

    for row in result_rows:
        row["alignment_rule_version"] = ALIGNMENT_RULE_VERSION
    result_rows.sort(key=lambda row: (str(row["model"]), str(row["period"])))
    period_rows.sort(key=lambda row: (str(row.get("model")), row.get("date")))
    selection_rows.sort(key=lambda row: (str(row.get("model")), row.get("date")))

    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "universe": "full_a",
            "price_mode": "qfq",
            "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
            "data_start": DATA_START.strftime("%Y%m%d"),
            "start": START.strftime("%Y%m%d"),
            "end": END.strftime("%Y%m%d"),
            "cycle": CYCLE,
            "label_offset": LABEL_OFFSET,
            "round_trip_cost": ROUND_TRIP_COST,
            "train_end": TRAIN_END.strftime("%Y-%m-%d"),
            "signal_dates": len(signal_dates),
            "train_dates": len(train_dates),
            "validation_dates": len(signal_dates) - len(train_dates),
            "mse_l1_alpha": 5e-3,
            "mse_capacity": 5,
            "alphaprobe_window": "expanding",
            "alphaprobe_n_factors": 5,
            "alphaprobe_min_history": 20,
            "alphaprobe_threshold_ric": 0.015,
            "alphaprobe_threshold_ricir": 0.15,
            "continuous_weights_used_for_final": False,
        },
        "factor_specs": FACTOR_SPECS,
        "mse_selection": {
            "selected": mse_selected,
            "raw_weights": mse_raw,
            "single_ics": mse_single_ics,
            "simple_weights": mse_weights,
        },
        "results": result_rows,
    }
    write_outputs(args.output_prefix, payload, result_rows, period_rows, selection_rows)
    print(f"report={args.output_prefix.with_suffix('.md')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
