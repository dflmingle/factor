#!/usr/bin/env python3
"""Local reproduction of Bryzgalova, Pelger and Zhu (2025) AP Trees.

This script uses the cached China A-share panel in quantlab.  It implements the
part of the paper that can be reproduced without CRSP/Compustat: a monthly
LME/OP/Investment AP Tree and global AP-Pruning.  The output is deliberately a
research artifact, not an official reproduction of the paper's U.S. results.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import Lasso
from sklearn.exceptions import ConvergenceWarning


CHAR_NAMES = ("LME", "OP", "Investment")
CHAR_COLUMNS = {
    "LME": "lme",
    "OP": "op_proxy",
    "Investment": "investment",
}
DEFAULT_CACHE_ROOT = Path("/data/games/quantlab/.quantlab/cache/research/cn_equity")
DEFAULT_OUTPUT_DIR = Path("/data/games/factor_/bpz_ap_tree_local_results")
DEFAULT_TRAIN_END = "2020-03"
DEFAULT_VALIDATION_END = "2022-03"
DEFAULT_MAX_DEPTH = 4
DEFAULT_MIN_TRAIN_VALID_FRACTION = 0.90
DEFAULT_MIN_NODE_STOCKS = 20
DEFAULT_LAMBDA0_GRID = (0.0, 0.10, 0.25, 0.50, 1.00)
DEFAULT_RIDGE_GRID = (1e-6, 1e-4, 1e-2, 1e-1, 1.0)


@dataclass(frozen=True)
class TreeNode:
    """A recursive node identified by split variables and L/H path."""

    index: int
    depth: int
    sequence: tuple[int, ...]
    path: tuple[int, ...]
    parent_index: int | None
    scale: float

    @property
    def sequence_names(self) -> tuple[str, ...]:
        return tuple(CHAR_NAMES[index] for index in self.sequence)

    @property
    def label(self) -> str:
        if self.depth == 0:
            return "market"
        sequence = ">".join(self.sequence_names)
        path = ">".join("L" if side == 0 else "H" for side in self.path)
        return f"{sequence} [{path}]"


@dataclass
class Panel:
    months: pd.PeriodIndex
    instruments: list[str]
    lme: np.ndarray
    characteristics: np.ndarray
    future_returns: np.ndarray
    monthly_close: pd.DataFrame
    monthly_lme: pd.DataFrame
    accounting_rows: int
    accounting_instruments: int
    price_rows: int
    basic_rows: int


@dataclass
class PruningResult:
    k_target: int
    candidate_count: int
    selected_count: int
    lambda0: float
    lambda2_relative: float
    lambda2_absolute: float
    lambda1: float
    alpha: float
    train_sharpe: float
    validation_sharpe: float
    test_sharpe: float
    train_mean_monthly: float
    validation_mean_monthly: float
    test_mean_monthly: float
    test_observations: int
    test_start: str
    test_end: str
    selected_node_indices: list[int]
    selected_node_labels: list[str]


def parse_period(value: str) -> pd.Period:
    """Parse YYYY-MM or YYYYMM without accepting ambiguous day dates."""
    text = str(value).strip()
    if len(text) == 6 and text.isdigit():
        text = f"{text[:4]}-{text[4:]}"
    period = pd.Period(text, freq="M")
    return period


def compact_code(stem: str) -> str:
    """Convert cache filenames such as 000001_SZ to Tushare's 000001.SZ."""
    return stem.replace("_", ".")


def finite_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def read_yearly_parquet(
    root: Path,
    dataset: str,
    columns: list[str],
    instruments: set[str],
    start_period: pd.Period,
    end_period: pd.Period,
) -> tuple[pd.DataFrame, int]:
    """Read only the requested symbols and collapse daily data to month-end."""
    dataset_root = root / dataset
    frames: list[pd.DataFrame] = []
    raw_rows = 0
    for path in sorted(dataset_root.glob("*.parquet")):
        try:
            year = int(path.stem)
        except ValueError:
            continue
        if year < start_period.year or year > end_period.year:
            continue
        frame = pd.read_parquet(path, columns=columns)
        raw_rows += len(frame)
        if instruments:
            frame = frame[frame["ts_code"].isin(instruments)]
        if frame.empty:
            continue
        dates = pd.to_datetime(frame["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
        frame = frame.loc[dates.notna()].copy()
        frame["month"] = dates.loc[frame.index].dt.to_period("M")
        frame = frame[(frame["month"] >= start_period) & (frame["month"] <= end_period)]
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[*columns, "month"]), raw_rows
    all_rows = pd.concat(frames, ignore_index=True)
    all_rows = all_rows.sort_values(["ts_code", "month", "trade_date"])
    month_end = all_rows.groupby(["month", "ts_code"], sort=False, as_index=False).tail(1)
    return month_end.reset_index(drop=True), raw_rows


def load_instruments(cache_root: Path) -> set[str]:
    """Use the intersection of cached income and balance-sheet securities."""
    income = {compact_code(path.stem) for path in (cache_root / "factor_financials" / "income").glob("*.parquet")}
    balance = {compact_code(path.stem) for path in (cache_root / "factor_financials" / "balancesheet").glob("*.parquet")}
    return income & balance


def load_annual_statement_rows(cache_root: Path, instruments: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load annual income and balance rows while preserving announcement vintages."""
    income_frames: list[pd.DataFrame] = []
    balance_frames: list[pd.DataFrame] = []
    income_root = cache_root / "factor_financials" / "income"
    balance_root = cache_root / "factor_financials" / "balancesheet"
    for code in sorted(instruments):
        stem = code.replace(".", "_")
        income_path = income_root / f"{stem}.parquet"
        balance_path = balance_root / f"{stem}.parquet"
        if not income_path.exists() or not balance_path.exists():
            continue
        income = pd.read_parquet(
            income_path,
            columns=["ts_code", "end_date", "ann_date", "operate_profit", "total_revenue"],
        )
        balance = pd.read_parquet(
            balance_path,
            columns=["ts_code", "end_date", "ann_date", "total_assets", "total_hldr_eqy_exc_min_int"],
        )
        for frame in (income, balance):
            frame["end_date"] = pd.to_datetime(frame["end_date"].astype(str), format="%Y%m%d", errors="coerce")
            frame["ann_date"] = pd.to_datetime(frame["ann_date"].astype(str), format="%Y%m%d", errors="coerce")
            frame.dropna(subset=["end_date", "ann_date"], inplace=True)
            frame.drop_duplicates(["end_date", "ann_date"], keep="last", inplace=True)
        income = income[income["end_date"].dt.month.eq(12) & income["end_date"].dt.day.eq(31)]
        balance = balance[balance["end_date"].dt.month.eq(12) & balance["end_date"].dt.day.eq(31)]
        if not income.empty:
            income_frames.append(income)
        if not balance.empty:
            balance_frames.append(balance)
    income_all = pd.concat(income_frames, ignore_index=True) if income_frames else pd.DataFrame()
    balance_all = pd.concat(balance_frames, ignore_index=True) if balance_frames else pd.DataFrame()
    return income_all, balance_all


def latest_annual_row(rows: pd.DataFrame, signal_date: pd.Timestamp) -> dict[pd.Timestamp, dict[str, object]]:
    """Return the latest announced row for every fiscal year visible at a date."""
    visible = rows[rows["ann_date"] <= signal_date]
    if visible.empty:
        return {}
    visible = visible.sort_values(["end_date", "ann_date"])
    result: dict[pd.Timestamp, dict[str, object]] = {}
    for end_date, group in visible.groupby("end_date", sort=False):
        result[pd.Timestamp(end_date)] = group.iloc[-1].to_dict()
    return result


def build_accounting_panel(
    income: pd.DataFrame,
    balance: pd.DataFrame,
    signal_months: pd.PeriodIndex,
    instruments: list[str],
) -> tuple[pd.DataFrame, int]:
    """Build OP and Investment using only statements announced by each signal date."""
    income_by_code = {code: frame for code, frame in income.groupby("ts_code")} if not income.empty else {}
    balance_by_code = {code: frame for code, frame in balance.groupby("ts_code")} if not balance.empty else {}
    op = np.full((len(signal_months), len(instruments)), np.nan, dtype=float)
    investment = np.full_like(op, np.nan)
    signal_dates = [period.to_timestamp("M") for period in signal_months]
    for column, code in enumerate(instruments):
        income_rows = income_by_code.get(code, pd.DataFrame())
        balance_rows = balance_by_code.get(code, pd.DataFrame())
        if income_rows.empty or balance_rows.empty:
            continue
        for row_index, signal_date in enumerate(signal_dates):
            income_visible = latest_annual_row(income_rows, signal_date)
            balance_visible = latest_annual_row(balance_rows, signal_date)
            common_dates = sorted(set(income_visible).intersection(balance_visible))
            if not common_dates:
                continue
            current_date = common_dates[-1]
            previous_date = pd.Timestamp(current_date) - pd.DateOffset(years=1)
            previous_date = pd.Timestamp(previous_date.year, 12, 31)
            current_income = income_visible[current_date]
            current_balance = balance_visible[current_date]
            equity = finite_float(current_balance.get("total_hldr_eqy_exc_min_int"))
            profit = finite_float(current_income.get("operate_profit"))
            assets = finite_float(current_balance.get("total_assets"))
            if equity is not None and equity > 0 and profit is not None:
                op[row_index, column] = profit / equity
            previous_balance = balance_visible.get(previous_date)
            previous_assets = finite_float(previous_balance.get("total_assets")) if previous_balance else None
            if assets is not None and previous_assets is not None and previous_assets > 0:
                investment[row_index, column] = assets / previous_assets - 1.0
    result = pd.DataFrame(index=signal_months, columns=instruments, dtype=float)
    result.index.name = "signal_month"
    result.attrs["op_definition"] = "operate_profit / total_hldr_eqy_exc_min_int; OP proxy"
    result.attrs["investment_definition"] = "annual total_assets(t-1) / total_assets(t-2) - 1"
    result.attrs["announcement_asof"] = True
    op_frame = pd.DataFrame(op, index=signal_months, columns=instruments)
    investment_frame = pd.DataFrame(investment, index=signal_months, columns=instruments)
    result = pd.concat(
        {
            "op_proxy": op_frame,
            "investment": investment_frame,
        },
        axis=1,
    )
    return result, int(income.shape[0] + balance.shape[0])


def build_monthly_panel(
    cache_root: Path,
    start_period: pd.Period,
    end_period: pd.Period,
) -> Panel:
    """Read cached prices/fundamentals and align signal month to next month return."""
    instruments_set = load_instruments(cache_root)
    if not instruments_set:
        raise RuntimeError(f"No overlapping income/balance files under {cache_root}")
    instruments = sorted(instruments_set)
    daily, daily_raw_rows = read_yearly_parquet(
        cache_root,
        "daily",
        ["ts_code", "trade_date", "close"],
        instruments_set,
        start_period,
        end_period,
    )
    daily_basic, basic_raw_rows = read_yearly_parquet(
        cache_root,
        "daily_basic",
        ["ts_code", "trade_date", "total_mv"],
        instruments_set,
        start_period,
        end_period,
    )
    if daily.empty or daily_basic.empty:
        raise RuntimeError("The cached daily or daily_basic panel is empty")
    monthly_close = daily.pivot(index="month", columns="ts_code", values="close").reindex(columns=instruments).sort_index()
    monthly_lme = daily_basic.pivot(index="month", columns="ts_code", values="total_mv").reindex(columns=instruments).sort_index()
    available_months = monthly_close.index.intersection(monthly_lme.index).sort_values()
    monthly_close = monthly_close.reindex(available_months)
    monthly_lme = monthly_lme.reindex(available_months)
    all_periods = list(available_months)
    signal_periods = [period for period in all_periods if period + 1 in monthly_close.index]
    if not signal_periods:
        raise RuntimeError("No adjacent signal/holding months in the cached panel")
    signal_months = pd.PeriodIndex(signal_periods, freq="M")
    holding_months = pd.PeriodIndex([period + 1 for period in signal_periods], freq="M")
    income, balance = load_annual_statement_rows(cache_root, instruments_set)
    accounting, accounting_rows = build_accounting_panel(income, balance, signal_months, instruments)
    lme_frame = monthly_lme.reindex(signal_months)
    close_signal = monthly_close.reindex(signal_months)
    close_holding = monthly_close.reindex(holding_months)
    # Signal and holding months are paired positionally.  Label-aligned
    # division would create the union of both indexes and add an extra row.
    future_returns_frame = pd.DataFrame(
        close_holding.to_numpy(dtype=float) / close_signal.to_numpy(dtype=float) - 1.0,
        index=signal_months,
        columns=instruments,
    )
    lme_values = lme_frame.to_numpy(dtype=float)
    lme_values[lme_values <= 0] = np.nan
    lme_log = np.log(lme_values)
    op_values = accounting["op_proxy"].to_numpy(dtype=float)
    investment_values = accounting["investment"].to_numpy(dtype=float)
    characteristics = np.stack([lme_log, op_values, investment_values], axis=2)
    if not (len(signal_months) == lme_values.shape[0] == characteristics.shape[0] == future_returns_frame.shape[0]):
        raise AssertionError("signal, characteristic, and return panels have inconsistent row counts")
    return Panel(
        months=signal_months,
        instruments=instruments,
        lme=lme_values,
        characteristics=characteristics,
        future_returns=future_returns_frame.to_numpy(dtype=float),
        monthly_close=monthly_close,
        monthly_lme=monthly_lme,
        accounting_rows=accounting_rows,
        accounting_instruments=int((accounting["op_proxy"].notna().any(axis=0) & accounting["investment"].notna().any(axis=0)).sum()),
        price_rows=daily_raw_rows,
        basic_rows=basic_raw_rows,
    )


def build_tree_nodes(max_depth: int = DEFAULT_MAX_DEPTH) -> list[TreeNode]:
    """Enumerate unique intermediate/final nodes across all characteristic orders."""
    nodes = [TreeNode(0, 0, (), (), None, 1.0)]
    key_to_index: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {((), ()): 0}
    for depth in range(1, max_depth + 1):
        for sequence in itertools.product(range(len(CHAR_NAMES)), repeat=depth):
            # The paper removes depth-four leaves generated by repeating one
            # characteristic four times; their parent nodes remain available.
            if depth == max_depth and len(set(sequence)) == 1:
                continue
            for path in itertools.product((0, 1), repeat=depth):
                parent_key = (sequence[:-1], path[:-1])
                parent_index = key_to_index.get(parent_key)
                if parent_index is None:
                    raise AssertionError(f"Missing parent for {sequence=} {path=}")
                index = len(nodes)
                key_to_index[(sequence, path)] = index
                nodes.append(
                    TreeNode(
                        index=index,
                        depth=depth,
                        sequence=tuple(sequence),
                        path=tuple(path),
                        parent_index=parent_index,
                        scale=2.0 ** (-depth / 2.0),
                    )
                )
    return nodes


def build_node_returns(
    panel: Panel,
    nodes: list[TreeNode],
    min_node_stocks: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Form value-weighted node returns using signal-month medians."""
    periods, assets = panel.future_returns.shape
    node_returns = np.full((periods, len(nodes)), np.nan, dtype=float)
    stock_counts = np.zeros((periods, len(nodes)), dtype=np.int32)
    market_value_shares = np.full((periods, len(nodes)), np.nan, dtype=float)
    for period_index in range(periods):
        lme = panel.lme[period_index]
        future_returns = panel.future_returns[period_index]
        base = np.isfinite(lme) & (lme > 0) & np.isfinite(future_returns)
        if int(base.sum()) == 0:
            continue
        masks = np.zeros((len(nodes), assets), dtype=bool)
        masks[0] = base
        for node in nodes[1:]:
            parent = masks[node.parent_index]  # type: ignore[index]
            split_values = panel.characteristics[period_index, :, node.sequence[-1]]
            eligible = parent & np.isfinite(split_values)
            if int(eligible.sum()) == 0:
                continue
            median = float(np.nanmedian(split_values[eligible]))
            if node.path[-1] == 0:
                masks[node.index] = eligible & (split_values <= median)
            else:
                masks[node.index] = eligible & (split_values > median)
        stock_counts[period_index] = masks.sum(axis=1)
        weighted_returns = np.nan_to_num(lme * future_returns, nan=0.0)
        numerators = masks @ weighted_returns
        denominators = masks @ np.nan_to_num(lme, nan=0.0)
        valid = (stock_counts[period_index] >= min_node_stocks) & (denominators > 0)
        node_returns[period_index, valid] = numerators[valid] / denominators[valid]
        node_returns[period_index] *= np.asarray([node.scale for node in nodes])
        market_value_shares[period_index, valid] = denominators[valid] / denominators[0]
    return node_returns, stock_counts, market_value_shares


def annualized_sharpe(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return float("nan")
    standard_deviation = float(np.std(values, ddof=1))
    if standard_deviation <= 0:
        return float("nan")
    return float(np.mean(values) / standard_deviation * math.sqrt(12.0))


def fill_from_training(
    returns: np.ndarray,
    train_rows: np.ndarray,
    candidate_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Use training-only column means for sparse node availability."""
    train = returns[train_rows][:, candidate_indices]
    means = np.nanmean(train, axis=0)
    means = np.nan_to_num(means, nan=0.0)
    filled = returns[:, candidate_indices].copy()
    missing = ~np.isfinite(filled)
    filled = np.where(missing, means[None, :], filled)
    return filled, means, missing


def covariance_from_training(train_returns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    means = np.mean(train_returns, axis=0)
    centered = train_returns - means[None, :]
    denominator = max(len(train_returns) - 1, 1)
    covariance = centered.T @ centered / denominator
    covariance = np.nan_to_num(covariance, nan=0.0, posinf=0.0, neginf=0.0)
    covariance = (covariance + covariance.T) / 2.0
    diagonal = np.maximum(np.diag(covariance), 0.0)
    covariance[np.diag_indices_from(covariance)] = diagonal
    return means, covariance


def lasso_for_target_k(
    covariance: np.ndarray,
    robust_mean: np.ndarray,
    target_k: int,
    lambda1_grid_points: int = 40,
) -> tuple[np.ndarray, float, float, int]:
    """Solve the AP-Pruning LASSO after whitening the robust pricing-error loss."""
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    floor = max(float(np.max(eigenvalues)) * 1e-10, 1e-12)
    eigenvalues = np.maximum(eigenvalues, floor)
    square_root = np.sqrt(eigenvalues)
    inverse_square_root = 1.0 / square_root
    # X = Sigma^(1/2), y = Sigma^(-1/2) mu.  sklearn's alpha is scaled by
    # the number of rows; lambda1 below is the paper-objective coefficient.
    design = (eigenvectors * square_root[None, :]) @ eigenvectors.T
    response = (eigenvectors * inverse_square_root[None, :]) @ (eigenvectors.T @ robust_mean)
    observation_count = len(response)
    alpha_max = float(np.max(np.abs(design.T @ response)) / max(observation_count, 1))
    if not math.isfinite(alpha_max) or alpha_max <= 0:
        return np.zeros_like(robust_mean), 0.0, 0.0, 0
    alphas = alpha_max * np.geomspace(1.0, 1e-6, lambda1_grid_points)
    best: tuple[tuple[int, int, float], np.ndarray, float, int] | None = None
    for alpha in alphas:
        model = Lasso(
            alpha=float(alpha),
            fit_intercept=False,
            max_iter=8_000,
            tol=1e-6,
            selection="cyclic",
        )
        # The near-zero ridge grid points can be numerically ill-conditioned
        # because the training covariance has rank at most T-1.  Those path
        # points are only used to locate a sparse support, so keep the fit
        # deterministic without flooding the research log with warnings.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            model.fit(design, response)
        coefficients = np.asarray(model.coef_, dtype=float)
        active = np.flatnonzero(np.abs(coefficients) > max(1e-9, np.max(np.abs(coefficients), initial=0.0) * 1e-7))
        active_count = int(len(active))
        # Prefer exactly K; otherwise prefer the closest count and the stronger
        # penalty (larger alpha) as a conservative tie-breaker.
        score = (abs(active_count - target_k), 0 if active_count <= target_k else 1, -float(alpha))
        if best is None or score < best[0]:
            best = (score, coefficients, float(alpha), active_count)
    if best is None:
        return np.zeros_like(robust_mean), 0.0, 0.0, 0
    _, coefficients, alpha, active_count = best
    return coefficients, alpha * observation_count, alpha, active_count


def run_pruning(
    node_returns: np.ndarray,
    nodes: list[TreeNode],
    train_rows: np.ndarray,
    validation_rows: np.ndarray,
    test_rows: np.ndarray,
    target_k: int,
    min_train_valid_fraction: float,
    lambda0_grid: Iterable[float] = DEFAULT_LAMBDA0_GRID,
    ridge_grid: Iterable[float] = DEFAULT_RIDGE_GRID,
) -> tuple[PruningResult, np.ndarray, dict[str, object]]:
    train_valid_fraction = np.isfinite(node_returns[train_rows]).mean(axis=0)
    candidates = np.flatnonzero(train_valid_fraction >= min_train_valid_fraction)
    if len(candidates) < target_k:
        raise RuntimeError(
            f"Only {len(candidates)} AP Tree nodes have >= {min_train_valid_fraction:.0%} "
            f"training availability; cannot target K={target_k}"
        )
    filled, train_means_all, missing = fill_from_training(node_returns, train_rows, candidates)
    train = filled[train_rows]
    validation = filled[validation_rows]
    test = filled[test_rows]
    train_mean, covariance = covariance_from_training(train)
    diagonal_scale = float(np.median(np.diag(covariance)))
    diagonal_scale = diagonal_scale if math.isfinite(diagonal_scale) and diagonal_scale > 0 else 1e-4
    best_validation: tuple[float, tuple[float, float, float, float, int], np.ndarray, int, float, float] | None = None
    grid_records: list[dict[str, object]] = []
    for lambda0 in lambda0_grid:
        robust_mean = train_mean + float(lambda0) * float(np.mean(train_mean))
        for ridge_relative in ridge_grid:
            lambda2 = float(ridge_relative) * diagonal_scale
            robust_covariance = covariance + lambda2 * np.eye(len(candidates))
            weights, lambda1, alpha, active_count = lasso_for_target_k(robust_covariance, robust_mean, target_k)
            validation_sdf = validation @ weights
            validation_sharpe = annualized_sharpe(validation_sdf)
            score = validation_sharpe if math.isfinite(validation_sharpe) else -float("inf")
            record = {
                "lambda0": float(lambda0),
                "lambda2_relative": float(ridge_relative),
                "lambda2_absolute": lambda2,
                "lambda1": lambda1,
                "alpha": alpha,
                "active_count": active_count,
                "validation_sharpe": validation_sharpe,
            }
            grid_records.append(record)
            tie_key = (score, -abs(active_count - target_k), -lambda2)
            if best_validation is None or tie_key > (best_validation[0], -best_validation[1][4], -best_validation[1][1]):
                best_validation = (
                    score,
                    (float(lambda0), lambda2, lambda1, alpha, active_count),
                    weights,
                    active_count,
                    lambda2,
                    float(lambda0),
                )
    if best_validation is None:
        raise RuntimeError("AP-Pruning hyperparameter grid produced no candidate")
    _, tuning, candidate_weights, active_count, lambda2, lambda0 = best_validation
    lambda1, alpha = tuning[2], tuning[3]
    selected = np.flatnonzero(np.abs(candidate_weights) > max(1e-9, np.max(np.abs(candidate_weights), initial=0.0) * 1e-7))
    full_weights = np.zeros(node_returns.shape[1], dtype=float)
    full_weights[candidates] = candidate_weights
    train_sdf = train @ candidate_weights
    validation_sdf = validation @ candidate_weights
    test_sdf = test @ candidate_weights
    result = PruningResult(
        k_target=int(target_k),
        candidate_count=int(len(candidates)),
        selected_count=int(len(selected)),
        lambda0=float(lambda0),
        lambda2_relative=float(lambda2 / diagonal_scale),
        lambda2_absolute=float(lambda2),
        lambda1=float(lambda1),
        alpha=float(alpha),
        train_sharpe=annualized_sharpe(train_sdf),
        validation_sharpe=annualized_sharpe(validation_sdf),
        test_sharpe=annualized_sharpe(test_sdf),
        train_mean_monthly=float(np.mean(train_sdf)),
        validation_mean_monthly=float(np.mean(validation_sdf)),
        test_mean_monthly=float(np.mean(test_sdf)),
        test_observations=int(len(test_sdf)),
        test_start="",
        test_end="",
        selected_node_indices=[int(candidates[index]) for index in selected],
        selected_node_labels=[nodes[int(candidates[index])].label for index in selected],
    )
    details = {
        "candidate_indices": candidates.tolist(),
        "candidate_train_valid_fraction": train_valid_fraction[candidates].tolist(),
        "selected_candidate_positions": selected.tolist(),
        "full_weights": full_weights.tolist(),
        "training_fill_means": train_means_all.tolist(),
        "imputed_cells_by_period": missing.sum(axis=1).tolist(),
        "hyperparameter_grid": grid_records,
    }
    return result, full_weights, details


def node_catalog_frame(nodes: list[TreeNode]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "index": node.index,
                "depth": node.depth,
                "sequence": ">".join(node.sequence_names) if node.sequence else "",
                "path": ">".join("L" if side == 0 else "H" for side in node.path) if node.path else "ROOT",
                "parent_index": node.parent_index,
                "scale": node.scale,
                "label": node.label,
            }
            for node in nodes
        ]
    )


def summarize_periods(
    months: pd.PeriodIndex,
    train_end: pd.Period,
    validation_end: pd.Period,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    train = np.flatnonzero(months <= train_end)
    validation = np.flatnonzero((months > train_end) & (months <= validation_end))
    test = np.flatnonzero(months > validation_end)
    if len(train) < 24 or len(validation) < 12 or len(test) < 12:
        raise RuntimeError(
            f"Insufficient local split: train={len(train)}, validation={len(validation)}, test={len(test)}"
        )
    return train, validation, test


def parse_k_values(text: str) -> list[int]:
    values = [int(value.strip()) for value in text.split(",") if value.strip()]
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("--k must contain positive integers, e.g. 10,40")
    return values


def write_report(
    output_dir: Path,
    panel: Panel,
    nodes: list[TreeNode],
    node_returns: np.ndarray,
    stock_counts: np.ndarray,
    market_value_shares: np.ndarray,
    train_rows: np.ndarray,
    validation_rows: np.ndarray,
    test_rows: np.ndarray,
    results: list[PruningResult],
    weights_by_k: dict[int, np.ndarray],
    details_by_k: dict[int, dict[str, object]],
    train_end: pd.Period,
    validation_end: pd.Period,
    min_train_valid_fraction: float,
    min_node_stocks: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    node_catalog = node_catalog_frame(nodes)
    node_catalog.to_csv(output_dir / "node_catalog.csv", index=False)
    selected_rows: list[dict[str, object]] = []
    for result in results:
        weights = weights_by_k[result.k_target]
        for node_index in result.selected_node_indices:
            node = nodes[node_index]
            finite_test = np.isfinite(node_returns[test_rows, node_index])
            selected_rows.append(
                {
                    "k_target": result.k_target,
                    "node_index": node_index,
                    "node_label": node.label,
                    "depth": node.depth,
                    "sequence": ">".join(node.sequence_names) if node.sequence else "",
                    "path": ">".join("L" if side == 0 else "H" for side in node.path) if node.path else "ROOT",
                    "scale": node.scale,
                    "sdf_weight": weights[node_index],
                    "mean_test_stock_count": float(np.nanmean(stock_counts[test_rows, node_index])),
                    "mean_test_market_value_share": float(np.nanmean(market_value_shares[test_rows, node_index])),
                    "test_node_return_coverage": float(np.mean(finite_test)),
                }
            )
    pd.DataFrame(selected_rows).to_csv(output_dir / "selected_nodes.csv", index=False)

    monthly = pd.DataFrame({"signal_month": panel.months.astype(str)})
    for result in results:
        details = details_by_k[str(result.k_target)]
        candidate_indices = np.asarray(details["candidate_indices"], dtype=int)
        training_fill_means = np.asarray(details["training_fill_means"], dtype=float)
        candidate_returns = node_returns[:, candidate_indices]
        candidate_returns = np.where(
            np.isfinite(candidate_returns),
            candidate_returns,
            training_fill_means[None, :],
        )
        sdf = candidate_returns @ weights_by_k[result.k_target][candidate_indices]
        monthly[f"sdf_k{result.k_target}"] = sdf
        monthly[f"sample_k{result.k_target}"] = np.where(
            np.arange(len(panel.months)) <= train_rows[-1], "train",
            np.where(np.arange(len(panel.months)) <= validation_rows[-1], "validation", "test"),
        )
    monthly.to_csv(output_dir / "monthly_sdf.csv", index=False)

    summary = {
        "paper": {
            "title": "Forest through the Trees: Building Cross-Sections of Stock Returns",
            "doi": "10.1111/jofi.13477",
            "authors": ["Svetlana Bryzgalova", "Markus Pelger", "Jason Zhu"],
        },
        "data": {
            "requested_path": "/data/games/quanlab",
            "actual_cache_root": str(DEFAULT_CACHE_ROOT),
            "market": "China A shares",
            "source": "quantlab cached Tushare parquet",
            "signal_month_first": str(panel.months[0]),
            "signal_month_last": str(panel.months[-1]),
            "months": int(len(panel.months)),
            "instruments": int(len(panel.instruments)),
            "accounting_instruments": panel.accounting_instruments,
            "raw_daily_rows_scanned": panel.price_rows,
            "raw_daily_basic_rows_scanned": panel.basic_rows,
            "accounting_rows_loaded": panel.accounting_rows,
        },
        "definitions": {
            "LME": "log(total_mv) for median ordering; total_mv weights value-weighted portfolios",
            "OP": "operate_profit / total_hldr_eqy_exc_min_int (proxy; exact REVT-COGS-TIE-XSGA unavailable)",
            "Investment": "annual total_assets(t-1) / total_assets(t-2) - 1",
            "return": "unadjusted monthly close-to-close return; cash distributions are not added",
            "point_in_time": "income/balance rows require ann_date <= signal month-end",
            "portfolio_weight": "market-cap weighted within each node, multiplied by 2^(-depth/2)",
            "risk_free_rate": "0 because no local Treasury-bill series was supplied",
        },
        "tree": {
            "max_depth": DEFAULT_MAX_DEPTH,
            "all_nodes_before_filter": len(nodes),
            "excluded_depth4_single_characteristic_leaves": 3 * (2**DEFAULT_MAX_DEPTH),
            "split": "node-conditional unweighted median; low <= median, high > median",
            "min_node_stocks": min_node_stocks,
        },
        "split": {
            "train": {"start": str(panel.months[train_rows[0]]), "end": str(panel.months[train_rows[-1]]), "months": int(len(train_rows))},
            "validation": {"start": str(panel.months[validation_rows[0]]), "end": str(panel.months[validation_rows[-1]]), "months": int(len(validation_rows))},
            "test": {"start": str(panel.months[test_rows[0]]), "end": str(panel.months[test_rows[-1]]), "months": int(len(test_rows))},
            "requested_train_end": str(train_end),
            "requested_validation_end": str(validation_end),
            "note": "Local data are too short for the paper's 20/10/23-year timeline; 60/24/remainder months are used.",
        },
        "ap_pruning": {
            "objective": "0.5*(mu_robust-Sigma_robust*w)'*inv(Sigma_robust)*(mu_robust-Sigma_robust*w) + lambda1*||w||1",
            "mu_robust": "sample_mean + lambda0 * cross_section_mean",
            "Sigma_robust": "sample_covariance + lambda2 * I",
            "selection": "weights are fixed from training; lambda0/lambda2 and target-K LASSO are selected by validation Sharpe",
            "min_train_valid_fraction": min_train_valid_fraction,
            "results": [asdict(result) for result in results],
            "grid_details": details_by_k,
        },
        "interpretation": "SDF weights may be signed; selected AP Tree nodes are long-only managed portfolios, but their SDF combination is not a long-only trading strategy.",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    lines = [
        "# Local AP Tree Reproduction",
        "",
        "This is a China A-share method reproduction of Bryzgalova, Pelger and Zhu (2025), not a cell-by-cell replication of the U.S. CRSP/Compustat sample.",
        "",
        "## Result",
        "",
        "| K | train Sharpe | validation Sharpe | test Sharpe | selected nodes | lambda0 | lambda2 / median diagonal |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result.k_target} | {result.train_sharpe:.4f} | {result.validation_sharpe:.4f} | {result.test_sharpe:.4f} | {result.selected_count} | {result.lambda0:.4g} | {result.lambda2_relative:.4g} |"
        )
    lines.extend(
        [
            "",
            "## Reproduction Boundary",
            "",
            "- `OP` is an explicit proxy because the cache exposes `operate_profit`, not all four components `REVT`, `COGS`, `TIE`, and `XSGA`.",
            "- Returns use unadjusted close-to-close prices; dividends and a risk-free series are not available in this local cache.",
            "- The paper has 53 years and uses 20 years of training, 10 years of validation, and 23 years of testing. This cache provides roughly 11 years, so the run uses 60 months, 24 months, and the remaining months.",
            "- The output reports annualized monthly Sharpe ratios with `sqrt(12)`. They are SDF diagnostics, not the long-only PandaAI competition score.",
            "",
            "## Files",
            "",
            "- `summary.json`: exact settings, definitions, split dates, grid, and metrics.",
            "- `selected_nodes.csv`: selected node descriptions and signed SDF weights.",
            "- `node_catalog.csv`: all recursive nodes used by the pruning candidate set.",
            "- `monthly_sdf.csv`: monthly SDF diagnostics by K.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def self_test() -> None:
    nodes = build_tree_nodes()
    expected = 1 + 6 + 36 + 216 + (81 * 16 - 3 * 16)
    assert len(nodes) == expected, (len(nodes), expected)
    assert nodes[0].label == "market"
    assert all(node.parent_index is not None for node in nodes[1:])
    assert all(node.depth < 4 or len(set(node.sequence)) > 1 for node in nodes)
    print(f"self-test ok: {len(nodes)} nodes; depth4 single-character leaves excluded")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-month", default="2015-03")
    parser.add_argument("--end-month", default="2026-08")
    parser.add_argument("--train-end", default=DEFAULT_TRAIN_END)
    parser.add_argument("--validation-end", default=DEFAULT_VALIDATION_END)
    parser.add_argument("--k", type=parse_k_values, default=[10])
    parser.add_argument("--min-node-stocks", type=int, default=DEFAULT_MIN_NODE_STOCKS)
    parser.add_argument("--min-train-valid-fraction", type=float, default=DEFAULT_MIN_TRAIN_VALID_FRACTION)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not 0 < args.min_train_valid_fraction <= 1:
        parser.error("--min-train-valid-fraction must be in (0, 1]")
    if args.min_node_stocks < 1:
        parser.error("--min-node-stocks must be positive")

    start_month = parse_period(args.start_month)
    end_month = parse_period(args.end_month)
    train_end = parse_period(args.train_end)
    validation_end = parse_period(args.validation_end)
    print(f"loading local panel from {args.cache_root}", flush=True)
    panel = build_monthly_panel(args.cache_root, start_month, end_month)
    train_rows, validation_rows, test_rows = summarize_periods(panel.months, train_end, validation_end)
    print(
        f"panel: {len(panel.months)} signal months, {len(panel.instruments)} instruments; "
        f"split train={len(train_rows)}, validation={len(validation_rows)}, test={len(test_rows)}",
        flush=True,
    )
    nodes = build_tree_nodes()
    print(f"building {len(nodes)} recursive AP Tree nodes", flush=True)
    node_returns, stock_counts, market_value_shares = build_node_returns(panel, nodes, args.min_node_stocks)
    print(
        f"node returns built; median root stock count={np.nanmedian(stock_counts[:, 0]):.0f}; "
        f"median depth4 count={np.nanmedian(stock_counts[:, [node.index for node in nodes if node.depth == 4]]):.0f}",
        flush=True,
    )
    results: list[PruningResult] = []
    weights_by_k: dict[int, np.ndarray] = {}
    details_by_k: dict[int, dict[str, object]] = {}
    for target_k in args.k:
        print(f"AP-Pruning K={target_k}: training robust LASSO grid", flush=True)
        result, weights, details = run_pruning(
            node_returns,
            nodes,
            train_rows,
            validation_rows,
            test_rows,
            target_k,
            args.min_train_valid_fraction,
        )
        result.test_start = str(panel.months[test_rows[0]])
        result.test_end = str(panel.months[test_rows[-1]])
        results.append(result)
        weights_by_k[target_k] = weights
        details_by_k[str(target_k)] = details
        print(
            f"K={target_k}: selected={result.selected_count}, "
            f"validation SR={result.validation_sharpe:.4f}, test SR={result.test_sharpe:.4f}",
            flush=True,
        )
    write_report(
        args.output_dir,
        panel,
        nodes,
        node_returns,
        stock_counts,
        market_value_shares,
        train_rows,
        validation_rows,
        test_rows,
        results,
        weights_by_k,
        details_by_k,
        train_end,
        validation_end,
        args.min_train_valid_fraction,
        args.min_node_stocks,
    )
    print(f"wrote {args.output_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
