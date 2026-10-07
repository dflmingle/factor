#!/usr/bin/env python3
"""Local probe: can a gradient-boosting combo of our factor legs beat the best single leg?

Zero platform credit. Convention aligned with the project rules:
- full-A .SH/.SZ universe with the loader's ST/listing filter (qualitygate)
- qfq prices, daily_basic.total_mv
- label close(t+1) -> close(t+cycle+1), cross-sectionally demeaned (excess)
- cycle=10, decile long side, 0.30% one-way cost

Training uses every trading day; evaluation only uses the 10-day grid
(signal dates). The learner is sklearn HistGradientBoosting, a histogram GBDT
in the same family as LightGBM; swap in lightgbm later if a cross-check is
wanted. A memory watchdog aborts the run before this 15 GB box starts swapping.

Outputs go to research_reports/platform_alignment/ml-combo-probe-20261001/.
"""
import gc
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from full_a_local_data import load_full_a_data  # noqa: E402

PRICE_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
CAP_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
OUT_DIR = ROOT / "research_reports/platform_alignment/ml-combo-probe-20261001"

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-09-07")
CYCLE = 10
ONE_WAY = 0.003
MEM_LIMIT_GB = 9.5
FOLDS = [
    ("2023-08-31", "2024-08-31"),
    ("2024-08-31", "2025-08-31"),
    ("2025-08-31", "2026-09-07"),
]


def _watchdog(stop: threading.Event) -> None:
    proc = psutil.Process()
    while not stop.wait(10):
        rss = proc.memory_info().rss / 1e9
        if rss > MEM_LIMIT_GB:
            print(f"!! watchdog: RSS {rss:.1f} GB > {MEM_LIMIT_GB} GB, aborting", flush=True)
            import os

            os._exit(3)


def wide(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return frame.pivot(index="date", columns="instrument", values=column).astype("float32")


def rank_pct(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True).astype("float32")


def stack_features(feats: dict[str, pd.DataFrame], mask: np.ndarray, y: pd.DataFrame):
    names = list(feats)
    ys = y.loc[mask].to_numpy(dtype="float32").ravel()
    xs = np.stack([v.loc[mask].to_numpy(dtype="float32").ravel() for v in feats.values()], axis=1)
    ok = np.isfinite(ys)
    for j in range(xs.shape[1]):
        ok &= np.isfinite(xs[:, j])
    return names, xs[ok], ys[ok]


def evaluate(pred: pd.DataFrame, excess: pd.DataFrame, grid_dates: pd.DatetimeIndex) -> dict:
    ics, longs, turns, decile_means = [], [], [], []
    prev_top: pd.Index | None = None
    for d in grid_dates:
        if d not in pred.index:
            continue
        p, y = pred.loc[d], excess.loc[d]
        ok = p.notna() & y.notna()
        if ok.sum() < 200:
            continue
        p, y = p[ok], y[ok]
        ics.append(p.corr(y, method="spearman"))
        thr = p.quantile(0.90)
        top = p[p >= thr].index
        longs.append(float(y[top].mean()))
        dec = pd.qcut(p.rank(method="first"), 10, labels=False)
        decile_means.append(y.groupby(dec).mean())
        if prev_top is not None and len(top):
            turns.append(1.0 - len(top.intersection(prev_top)) / len(top))
        prev_top = top
    if not ics:
        return {}
    mono = float("nan")
    if decile_means:
        dm = pd.concat(decile_means, axis=1).mean(axis=1)
        mono = float(pd.Series(dm.index).corr(pd.Series(dm.to_numpy()), method="spearman"))
    ic_mean = float(np.mean(ics))
    gross = float(np.mean(longs)) * 252.0 / CYCLE * 100.0
    turn = float(np.mean(turns)) if turns else float("nan")
    cost = turn * 2.0 * ONE_WAY * 252.0 / CYCLE * 100.0
    return {
        "ic_mean": ic_mean,
        "n_dates": len(ics),
        "gross_pct": gross,
        "turnover": turn,
        "cost_pct": cost,
        "net_pct": gross - cost,
        "mono": mono,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    stop = threading.Event()
    threading.Thread(target=_watchdog, args=(stop,), daemon=True).start()
    proc = psutil.Process()

    print(f"[1/5] loading full-A frame {DATA_START.date()}..{DATA_END.date()} ...", flush=True)
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, DATA_START, DATA_END, market_cap_field="total_mv")
    print(f"    rows={len(frame):,} stocks={frame['instrument'].nunique():,} "
          f"rss={proc.memory_info().rss/1e9:.1f}GB t=+{time.time()-t0:.0f}s", flush=True)

    print("[2/5] pivoting wide matrices ...", flush=True)
    close = wide(frame, "close_qfq")
    volume = wide(frame, "volume")
    turnover = wide(frame, "turnover")
    total_mv = wide(frame, "total_mv")
    high = wide(frame, "high_qfq")
    low = wide(frame, "low_qfq")
    amount = wide(frame, "amount")
    del frame
    gc.collect()
    dates = close.index
    print(f"    shape={close.shape} rss={proc.memory_info().rss/1e9:.1f}GB", flush=True)

    print("[3/5] building features ...", flush=True)
    ret1 = close / close.shift(1) - 1.0
    raw = {
        "vv6_500": -(volume.rolling(6).std() / volume.rolling(500, min_periods=250).std()),
        "turn_stab": -(turnover.rolling(10).std() / turnover.rolling(750, min_periods=240).std()),
        "rev5": -(close / close.shift(5) - 1.0),
        "mom20": close / close.shift(20) - 1.0,
        "mom60": close / close.shift(60) - 1.0,
        "vol20": ret1.rolling(20).std(),
        "turn_rel20": turnover / turnover.rolling(20).mean(),
        "size": np.log(total_mv),
        "hl20": ((high - low) / close).rolling(20).mean(),
        "amihud20": (ret1.abs() / amount * 1e8).rolling(20).mean(),
        "maxret20": ret1.rolling(20).max(),
        "turn_lvl": turnover,
    }
    feats = {k: rank_pct(v) for k, v in raw.items()}
    del raw
    gc.collect()
    print(f"    {len(feats)} features rss={proc.memory_info().rss/1e9:.1f}GB", flush=True)

    fwd = close.shift(-11) / close.shift(-1) - 1.0
    excess = fwd.sub(fwd.mean(axis=1), axis=0)
    del fwd
    gc.collect()

    grid = np.zeros(len(dates), dtype=bool)
    grid[::CYCLE] = True
    dvals = dates.to_numpy()

    results: list[dict] = []
    pred_store: dict[str, pd.Series] = {}

    for fi, (tr_end, te_end) in enumerate(FOLDS, 1):
        tr_mask = dvals <= np.datetime64(pd.Timestamp(tr_end))
        te_mask = (dvals > np.datetime64(pd.Timestamp(tr_end))) & (dvals <= np.datetime64(pd.Timestamp(te_end)))
        print(f"[4/5] fold {fi}: train<= {tr_end} test<= {te_end} "
              f"(train days {int(tr_mask.sum())}, test days {int(te_mask.sum())})", flush=True)
        names, xs, ys = stack_features(feats, tr_mask, excess)
        print(f"    train rows={len(ys):,} rss={proc.memory_info().rss/1e9:.1f}GB", flush=True)
        model = HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=200, l2_regularization=1.0, random_state=7,
        )
        model.fit(xs, ys)
        del xs, ys
        gc.collect()

        test_dates = dates[te_mask & grid]
        te_idx = np.where(te_mask)[0]
        pred = pd.DataFrame(index=dates[te_idx], columns=close.columns, dtype="float32")
        xs_te = np.stack([v.iloc[te_idx].to_numpy(dtype="float32").ravel() for v in feats.values()], axis=1)
        ok = np.isfinite(xs_te).all(axis=1)
        out = np.full(len(xs_te), np.nan, dtype="float32")
        out[ok] = model.predict(xs_te[ok])
        pred.iloc[:, :] = out.reshape(len(te_idx), -1)
        metrics = evaluate(pred, excess, test_dates)
        metrics.update({"model": "gbm", "fold": fi})
        results.append(metrics)
        print(f"    gbm: {json.dumps(metrics, ensure_ascii=False)}", flush=True)
        for d, row in pred.iterrows():
            if d in test_dates:
                pred_store[f"gbm|{d.date()}"] = row
        del xs_te, pred, out
        gc.collect()

        # baselines on the same fold
        ew = None
        for k, v in feats.items():
            m = evaluate(v.iloc[te_idx].set_axis(dates[te_idx], axis=0), excess, test_dates)
            if m:
                m.update({"model": f"single:{k}", "fold": fi})
                results.append(m)
            sign = np.sign(pd.Series(v.loc[tr_mask].to_numpy(dtype="float32").ravel()).corr(
                pd.Series(excess.loc[tr_mask].to_numpy(dtype="float32").ravel()), method="spearman"))
            part = (v.iloc[te_idx] - 0.5) * float(sign if np.isfinite(sign) else 0.0)
            ew = part if ew is None else ew + part
        m = evaluate(ew.set_axis(dates[te_idx], axis=0), excess, test_dates)
        if m:
            m.update({"model": "equal_weight", "fold": fi})
            results.append(m)
            print(f"    equal_weight: {json.dumps(m, ensure_ascii=False)}", flush=True)
        del ew
        gc.collect()

    print("[5/5] writing outputs ...", flush=True)
    res = pd.DataFrame(results)
    res = res[["model", "fold", "ic_mean", "n_dates", "gross_pct", "turnover", "cost_pct", "net_pct", "mono"]]
    res.to_csv(OUT_DIR / "fold_results.csv", index=False, float_format="%.4f")
    pooled = (res.groupby("model")[["ic_mean", "gross_pct", "turnover", "cost_pct", "net_pct", "mono"]]
              .mean().sort_values("net_pct", ascending=False))
    pooled.to_csv(OUT_DIR / "pooled_results.csv", float_format="%.4f")
    print(pooled.to_string(), flush=True)
    peak = proc.memory_info().rss / 1e9
    (OUT_DIR / "run_meta.json").write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "data_window": [str(DATA_START.date()), str(DATA_END.date())],
        "folds": FOLDS, "cycle": CYCLE, "one_way": ONE_WAY,
        "model": "sklearn.HistGradientBoostingRegressor(max_iter=150, lr=0.06, leaves=31)",
        "features": list(feats), "elapsed_s": round(time.time() - t0, 1),
        "final_rss_gb": round(peak, 2),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    stop.set()
    print(f"done in {time.time()-t0:.0f}s, rss={peak:.1f}GB, out={OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
