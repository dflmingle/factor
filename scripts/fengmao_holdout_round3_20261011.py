"""Causal holdout test for the Fengmao public-score reproduction.

The first 95 target periods are the only labels used for fitting.  The final
24 periods are a one-shot validation block; no tree count, blend weight, or
formula is selected from it.  This is intentionally local-only.
"""
from __future__ import annotations

import gc
import json
import os
import time
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import lightgbm as lgb
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

import fengmao_rankboost_round2_20261011 as task
from platform_score_rules import seat_stats


ROOT = task.ROOT
OUT = ROOT / "research_reports/platform_alignment/fengmao-holdout-round3-20261011"
OUT.mkdir(parents=True, exist_ok=True)
TREES = 1200
TRAIN_PERIODS = 95
HOLDOUT_PERIODS = 24
CYCLE = 10.0
COST = 0.003


def save_json(name: str, value: object) -> None:
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def rank_panel(panel: np.ndarray) -> np.ndarray:
    out = np.full(panel.shape, np.nan, dtype=np.float32)
    for i in range(panel.shape[0]):
        row = panel[i]
        ok = np.isfinite(row)
        if ok.sum():
            vals = row[ok]
            order = np.argsort(vals, kind="stable")
            ranks = np.empty(len(vals), dtype=np.float32)
            ranks[order] = np.arange(len(vals), dtype=np.float32)
            out[i, ok] = ranks / max(len(vals) - 1, 1)
    return out


def fit_regression(x: np.ndarray, y: np.ndarray, cap: np.ndarray, dates: pd.DatetimeIndex,
                   trees: int = TREES) -> lgb.Booster:
    valid = np.isfinite(y[:TRAIN_PERIODS]) & np.isfinite(cap[:TRAIN_PERIODS])
    labels_panel = task.prior.old.rank(np.where(valid, y[:TRAIN_PERIODS], np.nan))
    labels = labels_panel[valid]
    flat_x = x[:TRAIN_PERIODS][valid]
    weights = np.broadcast_to(
        1.0 / np.maximum(valid.sum(axis=1), 1)[:, None], valid.shape
    )[valid]
    weights *= len(weights) / weights.sum()
    params = dict(
        objective="regression",
        metric="None",
        learning_rate=0.03,
        max_bin=63,
        num_threads=1,
        verbosity=-1,
        seed=20261017,
        deterministic=True,
        force_col_wise=True,
        feature_fraction=0.85,
        lambda_l2=20.0,
        min_data_in_leaf=300,
        num_leaves=31,
    )
    dataset = lgb.Dataset(flat_x, label=labels, weight=weights, free_raw_data=True)
    model = lgb.train(params, dataset, num_boost_round=trees)
    del dataset, labels, weights, flat_x, labels_panel
    gc.collect()
    return model


def row_rank_ic(signal: np.ndarray, y: np.ndarray, cap: np.ndarray) -> np.ndarray:
    valid = np.isfinite(signal) & np.isfinite(y) & np.isfinite(cap)
    return task.prior.old.rowcorr(
        task.prior.old.rank(np.where(valid, signal, np.nan)),
        task.prior.old.rank(np.where(valid, y, np.nan)),
    )


def c_proxy(signal: np.ndarray, y: np.ndarray, cap: np.ndarray) -> dict[str, float]:
    """Single-factor pool proxy using period returns and monthly turnover.

    The official C ledger is daily and pool-level.  Here each 10-day label is
    used as a period return, with the same rawC/NC formula and a 21/10 monthly
    turnover conversion.  It is a diagnostic, not a platform score.
    """
    periods, previous = [], set()
    for i in range(len(signal)):
        valid = np.isfinite(signal[i]) & np.isfinite(y[i]) & np.isfinite(cap[i])
        ids = np.flatnonzero(valid)
        if len(ids) < 100:
            continue
        n = max(1, int(len(ids) * 0.10))
        chosen = ids[np.argsort(-signal[i, ids], kind="stable")[:n]]
        members = set(chosen.tolist())
        turn = np.nan if not previous else 1.0 - len(members & previous) / len(members)
        previous = members
        port = float(np.mean(y[i, chosen]))
        bench = float(np.mean(y[i, ids]))
        periods.append((port, bench, turn))
    if len(periods) < 3:
        return {"periods": len(periods), "nc": 0.0, "raw_c": 0.0}
    p = np.asarray([v[0] for v in periods], dtype=float)
    b = np.asarray([v[1] for v in periods], dtype=float)
    t = np.nan_to_num(np.asarray([v[2] for v in periods], dtype=float), nan=0.0)
    after = p - t * COST
    years = len(after) * CYCLE / 252.0
    if np.any(1.0 + after <= 0) or np.any(1.0 + b <= 0):
        return {"periods": len(periods), "nc": 0.0, "raw_c": 0.0}
    rex = float((np.prod(1.0 + after) ** (1.0 / years) - 1.0)
                - (np.prod(1.0 + b) ** (1.0 / years) - 1.0))
    std = float(after.std(ddof=1))
    sr = float(after.mean() / std * np.sqrt(252.0 / CYCLE)) if std > 0 else 0.0
    equity = np.cumprod(1.0 + after)
    dd = float(-(equity / np.maximum.accumulate(equity) - 1.0).min())
    turn_period = float(np.mean(t[1:])) if len(t) > 1 else 0.0
    turn_month = turn_period * 21.0 / CYCLE
    raw_c = max(rex, 0.0) / max(turn_month, 0.30) * sr * (1.0 - 1.2 * dd)
    nc = float(np.clip(raw_c / 0.60, 0.0, 1.0))
    return {
        "periods": len(periods),
        "annual_excess": rex,
        "annual_sr": sr,
        "max_dd": dd,
        "turnover_period": turn_period,
        "turnover_month_proxy": turn_month,
        "raw_c": float(raw_c),
        "nc": nc,
        "c_contribution": 0.45 * nc,
    }


def metrics(name: str, window: str, signal: np.ndarray, y: np.ndarray, cap: np.ndarray,
            dates: pd.DatetimeIndex, mask: np.ndarray) -> dict[str, object]:
    rho = row_rank_ic(signal[mask], y[mask], cap[mask])
    stats = seat_stats(rho)
    c = c_proxy(signal[mask], y[mask], cap[mask])
    return {
        "candidate": name,
        "window": window,
        "start": str(dates[mask][0].date()),
        "end": str(dates[mask][-1].date()),
        "periods": int(mask.sum()),
        "rank_ic": float(stats.ic_mean),
        "rank_ir": float(stats.icir),
        "wins": int((rho > 0.02).sum()),
        "win_rate": float(stats.win_rate),
        "s_i": float(stats.s_i_a),
        "c_proxy": c,
    }


def main() -> int:
    started = time.monotonic()
    with threadpool_limits(limits=1):
        atoms, y, cap, dates, axes = task.load("target")
        x_flat, feature_names = task.matrix(atoms, dates, axes, augmented=True)
        n_dates, n_stocks = y.shape
        n_features = len(feature_names)
        x = x_flat.reshape(n_dates, n_stocks, n_features)
        base_count = len(task.FEATURES)
        train_mask = np.arange(n_dates) < TRAIN_PERIODS
        holdout_mask = ~train_mask
        masks = {"train": train_mask, "holdout": holdout_mask, "full": np.ones(n_dates, bool)}
        save_json("split.json", {
            "total_periods": n_dates,
            "train_periods": TRAIN_PERIODS,
            "holdout_periods": HOLDOUT_PERIODS,
            "train_start": str(dates[0].date()),
            "train_end": str(dates[TRAIN_PERIODS - 1].date()),
            "holdout_start": str(dates[TRAIN_PERIODS].date()),
            "holdout_end": str(dates[-1].date()),
            "trees": TREES,
            "blend_weight": "fixed 0.5 / 0.5; no holdout tuning",
        })

        base_x = x[:, :, :base_count].reshape(-1, base_count)
        aug_x = x.reshape(-1, n_features)
        models = {}
        raw = {}
        for name, xx in (("CAUSAL_RANKBOOST", base_x), ("CAUSAL_PEERBOOST", aug_x)):
            print(f"training {name} on first {TRAIN_PERIODS} periods", flush=True)
            model = fit_regression(xx.reshape(n_dates, n_stocks, -1), y, cap, dates)
            pred = model.predict(xx, num_threads=1).reshape(n_dates, n_stocks).astype(np.float32)
            pred[~np.isfinite(cap)] = np.nan
            model.save_model(str(OUT / f"{name}.txt"))
            np.save(OUT / f"{name}_target_signals.npy", pred)
            models[name] = model
            raw[name] = pred
            del model, pred
            gc.collect()

        ranked = {name: rank_panel(value) for name, value in raw.items()}
        blend = (ranked["CAUSAL_RANKBOOST"] + ranked["CAUSAL_PEERBOOST"]) / 2.0
        blend[~np.isfinite(cap)] = np.nan
        ranked["CAUSAL_FIXED_BLEND"] = blend.astype(np.float32)
        np.save(OUT / "CAUSAL_FIXED_BLEND_target_signals.npy", ranked["CAUSAL_FIXED_BLEND"])

        result_rows = []
        for name, signal in ranked.items():
            for window, mask in masks.items():
                result_rows.append(metrics(name, window, signal, y, cap, dates, mask))
        pd.DataFrame(result_rows).to_json(OUT / "results.json", orient="records", force_ascii=False, indent=2)
        flat_rows = []
        for row in result_rows:
            c = row.pop("c_proxy")
            flat_rows.append({**row, **{f"c_{k}": v for k, v in c.items()}})
        pd.DataFrame(flat_rows).to_csv(OUT / "results.csv", index=False, encoding="utf-8-sig")

        # Formal five-year diagnostic with the same frozen target-trained models.
        del atoms, x_flat, x, base_x, aug_x, raw, ranked, y, cap
        gc.collect()
        fatoms, fy, fcap, fdates, faxes = task.load("formal")
        fx_flat, f_names = task.matrix(fatoms, fdates, faxes, augmented=True)
        fn_dates, fn_stocks = fy.shape
        fn_features = len(f_names)
        fbase_count = len(task.FEATURES)
        formal_signals = {}
        for name, model in models.items():
            use = fx_flat.reshape(-1, fn_features)[:, :fbase_count] if name == "CAUSAL_RANKBOOST" else fx_flat
            pred = model.predict(use, num_threads=1).reshape(fn_dates, fn_stocks).astype(np.float32)
            pred[~np.isfinite(fcap)] = np.nan
            formal_signals[name] = pred
        formal_signals["CAUSAL_FIXED_BLEND"] = (
            rank_panel(formal_signals["CAUSAL_RANKBOOST"])
            + rank_panel(formal_signals["CAUSAL_PEERBOOST"])
        ) / 2.0
        formal_rows = []
        full_mask = np.ones(fn_dates, bool)
        for name, signal in formal_signals.items():
            row = metrics(name, "formal_5y_frozen", signal, fy, fcap, fdates, full_mask)
            c = row.pop("c_proxy")
            formal_rows.append({**row, **{f"c_{k}": v for k, v in c.items()}})
        pd.DataFrame(formal_rows).to_csv(OUT / "formal_5y_results.csv", index=False, encoding="utf-8-sig")

    metadata = {
        "status": "complete",
        "platform_cost": 0,
        "validation_is_one_shot": True,
        "training_periods": TRAIN_PERIODS,
        "holdout_periods": HOLDOUT_PERIODS,
        "holdout_tuning": False,
        "c_proxy_is_pool_level_diagnostic": True,
        "seconds": time.monotonic() - started,
    }
    save_json("metadata.json", metadata)
    print(f"done in {metadata['seconds']:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
