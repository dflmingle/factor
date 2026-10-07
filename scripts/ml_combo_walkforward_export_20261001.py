#!/usr/bin/env python3
"""Train the walk-forward HistGBM (sklearn) combo and export it as a platform Python factor.

Windows (strictly out of sample, one frozen model per window):
  w3: train <= 2023-08-31 -> apply 2023-09-01..2024-08-31
  w4: train <= 2024-08-31 -> apply 2024-09-01..2025-08-31
  w5: train <= 2025-08-31 -> apply 2025-09-01..2026-09-07
Dates before 2023-09-01 carry no model and return NaN.

Deliverables under research_reports/platform_alignment/ml-combo-platform-20261001/:
  ml_gbdt_wf_factor.py  platform Python factor, embedded trees, numpy-only inference
  models_wf.npz         same payload for inspection
  local_wf_eval.csv     local OOS metrics per window
  candidates.txt        batch.py input (python mode)
Validation: the generated factor is exec'd with a mocked environment; its output is
checked against the sklearn model's own predict on identical feature rows.
"""
import base64
import gc
import io
import json
import os
import sys
import threading
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from full_a_local_data import load_full_a_data  # noqa: E402
import ml_combo_probe_20261001 as probe  # noqa: E402

PRICE_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
CAP_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
OUT_DIR = ROOT / "research_reports/platform_alignment/ml-combo-platform-20261001"
FACTOR_PATH = OUT_DIR / "ml_gbdt_wf_factor.py"

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-09-07")
MEM_LIMIT_GB = 9.5
WINDOWS = [
    ("2023-08-31", "2024-08-31"),
    ("2024-08-31", "2025-08-31"),
    ("2025-08-31", "2026-09-07"),
]
HGB_PARAMS = dict(max_iter=150, learning_rate=0.06, max_leaf_nodes=31,
                  min_samples_leaf=200, l2_regularization=1.0, random_state=7)
FEATURES = ["vv6_500", "turn_stab", "rev5", "mom20", "mom60", "vol20",
            "turn_rel20", "size", "hl20", "amihud20", "maxret20", "turn_lvl"]


def _watchdog(stop: threading.Event) -> None:
    proc = psutil.Process()
    while not stop.wait(10):
        rss = proc.memory_info().rss / 1e9
        if rss > MEM_LIMIT_GB:
            print(f"!! watchdog: RSS {rss:.1f} GB, aborting", flush=True)
            os._exit(3)


def build_features(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    close = probe.wide(frame, "close_qfq")
    volume = probe.wide(frame, "volume")
    turnover = probe.wide(frame, "turnover")
    total_mv = probe.wide(frame, "total_mv")
    high = probe.wide(frame, "high_qfq")
    low = probe.wide(frame, "low_qfq")
    amount = probe.wide(frame, "amount")
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
    return {k: probe.rank_pct(v) for k, v in raw.items()}


def export_arrays(model: HistGradientBoostingRegressor) -> dict:
    feat, thr, left, right, mleft, leaf = [], [], [], [], [], []
    baseline = float(np.ravel(model._baseline_prediction)[0])
    offsets = [0]
    for it in model._predictors:
        for tp in it:
            nd = tp.nodes
            base = len(feat)
            for i in range(len(nd)):
                if nd["is_leaf"][i]:
                    feat.append(-1)
                    thr.append(0.0)
                    mleft.append(0)
                    left.append(-1)
                    right.append(-1)
                    leaf.append(float(nd["value"][i]))
                else:
                    feat.append(int(nd["feature_idx"][i]))
                    thr.append(float(nd["num_threshold"][i]))
                    mleft.append(int(nd["missing_go_to_left"][i]))
                    left.append(base + int(nd["left"][i]))
                    right.append(base + int(nd["right"][i]))
                    leaf.append(0.0)
            offsets.append(len(feat))
    return dict(feat=np.asarray(feat, dtype=np.int16),
                threshold=np.asarray(thr, dtype=np.float64),
                left=np.asarray(left, dtype=np.int32), right=np.asarray(right, dtype=np.int32),
                missing_left=np.asarray(mleft, dtype=np.uint8),
                leaf_value=np.asarray(leaf, dtype=np.float64),
                offsets=np.asarray(offsets, dtype=np.int32),
                baseline=np.asarray([baseline], dtype=np.float64))


def predict_trees(X: np.ndarray, p: dict) -> np.ndarray:
    feat, thr, left, right = p["feat"], p["threshold"], p["left"], p["right"]
    mleft, leaf, offsets = p["missing_left"], p["leaf_value"], p["offsets"]
    rows = np.arange(X.shape[0])
    out = np.full(X.shape[0], float(p["baseline"][0]), dtype=np.float64)
    for t in range(len(offsets) - 1):
        node = np.full(X.shape[0], int(offsets[t]), dtype=np.int64)
        for _ in range(64):
            fidx = feat[node].astype(np.int64)
            v = X[rows, fidx]
            nan = np.isnan(v)
            go_left = np.where(nan, mleft[node].astype(bool), v <= thr[node])
            is_leaf = feat[node] < 0
            nxt = np.where(go_left, left[node], right[node])
            node = np.where(is_leaf, node, nxt)
            if is_leaf.all():
                break
        out += leaf[node]
    return out


FACTOR_TEMPLATE = '''"""ML-GBDT walk-forward combo (embedded trees, numpy-only inference).

Generated by scripts/ml_combo_walkforward_export_20261001.py -- do not edit by hand.
Each model is trained strictly before its application window.  Dates before
2023-09-01, or rows with an incomplete feature vector, return NaN.
"""
import numpy as np

{payload_block}
_FEATURES = {features!r}
_CUTS = {cuts!r}


def _models():
    out = []
    for m in _MODELS:
        out.append({{"feat": np.asarray(m["feat"], dtype=np.int16),
                     "threshold": np.asarray(m["threshold"], dtype=np.float64),
                     "left": np.asarray(m["left"], dtype=np.int32),
                     "right": np.asarray(m["right"], dtype=np.int32),
                     "missing_left": np.asarray(m["missing_left"], dtype=np.uint8),
                     "leaf_value": np.asarray(m["leaf_value"], dtype=np.float64),
                     "offsets": np.asarray(m["offsets"], dtype=np.int32),
                     "baseline": np.asarray([m["baseline"]], dtype=np.float64)}})
    return out


def _field(factors, names):
    for name in names:
        try:
            return factors[name]
        except Exception:
            continue
    return None


def _predict(X, p):
    n = X.shape[0]
    rows = np.arange(n)
    feat, thr, left, right = p["feat"], p["threshold"], p["left"], p["right"]
    mleft, leaf, offsets = p["missing_left"], p["leaf_value"], p["offsets"]
    out = np.full(n, float(p["baseline"][0]), dtype=np.float64)
    for t in range(len(offsets) - 1):
        node = np.full(n, int(offsets[t]), dtype=np.int64)
        for _ in range(64):
            fidx = feat[node].astype(np.int64)
            v = X[rows, fidx]
            nan = np.isnan(v)
            go_left = np.where(nan, mleft[node].astype(bool), v <= thr[node])
            is_leaf = feat[node] < 0
            nxt = np.where(go_left, left[node], right[node])
            node = np.where(is_leaf, node, nxt)
            if is_leaf.all():
                break
        out += leaf[node]
    return out


class MlGbdtWf(Factor):
    def calculate(self, factors):
        close = factors["close"]
        idx = close.index

        def wide(series):
            # platform python pane is fixed [date, symbol]: level 1 = symbol
            return series.unstack(level=1)

        close_w = wide(close)
        volume = _field(factors, ("volume",))
        amount = _field(factors, ("amount",))
        turnover = _field(factors, ("turnover",))
        cap = _field(factors, ("market_cap", "total_mv"))
        high = _field(factors, ("high",))
        low = _field(factors, ("low",))

        missing = close_w * np.nan
        volume_w = wide(volume) if volume is not None else missing
        high_w = wide(high) if high is not None else close_w
        low_w = wide(low) if low is not None else close_w
        amount_w = wide(amount) if amount is not None else volume_w * close_w
        turnover_w = wide(turnover) if turnover is not None else missing
        cap_w = wide(cap) if cap is not None else missing

        ret1 = close_w / close_w.shift(1) - 1.0
        raw = {{
            "vv6_500": -(volume_w.rolling(6).std() / volume_w.rolling(500, min_periods=250).std()),
            "turn_stab": -(turnover_w.rolling(10).std() / turnover_w.rolling(750, min_periods=240).std()),
            "rev5": -(close_w / close_w.shift(5) - 1.0),
            "mom20": close_w / close_w.shift(20) - 1.0,
            "mom60": close_w / close_w.shift(60) - 1.0,
            "vol20": ret1.rolling(20).std(),
            "turn_rel20": turnover_w / turnover_w.rolling(20).mean(),
            "size": np.log(cap_w),
            "hl20": ((high_w - low_w) / close_w).rolling(20).mean(),
            "amihud20": (ret1.abs() / amount_w * 1e8).rolling(20).mean(),
            "maxret20": ret1.rolling(20).max(),
            "turn_lvl": turnover_w,
        }}
        feats = {{k: v.rank(axis=1, pct=True) for k, v in raw.items()}}

        days = np.asarray([np.datetime64(str(d)[:10]) for d in close_w.index])
        X = np.stack([feats[name].to_numpy(dtype="float32").ravel() for name in _FEATURES], axis=1)
        pred = np.full(X.shape[0], np.nan, dtype="float64")
        complete = np.isfinite(X).all(axis=1)
        cuts = [np.datetime64(c) for c in _CUTS]
        day_grid = np.repeat(days, len(close_w.columns))
        models = _models()
        for k, cut in enumerate(cuts):
            lower = np.datetime64("1900-01-01") if k == 0 else cuts[k - 1]
            mask = complete & (day_grid > lower) & (day_grid <= cut)
            if mask.any():
                pred[mask] = _predict(X[mask], models[k])
        pred_w = close_w.astype("float64") * np.nan
        pred_w.iloc[:, :] = pred.reshape(close_w.shape)
        return pred_w.stack().reindex(idx).rename("value")
'''


def emit_payload_block(payloads: dict, cut_strings: list) -> str:
    def tuple_text(values, cast):
        rows, cur = [], []
        for value in values:
            cur.append(repr(cast(value)))
            if len(cur) >= 20:
                rows.append(", ".join(cur))
                cur = []
        if cur:
            rows.append(", ".join(cur))
        if not rows:
            return "()"
        return "(\n    " + ",\n    ".join(rows) + ",\n)"

    blocks = []
    for wi in range(len(cut_strings)):
        m = {k: payloads[f"m{wi}_{k}"] for k in
             ("feat", "threshold", "left", "right", "missing_left", "leaf_value", "offsets", "baseline")}
        blocks.append(
            f"_M{wi} = {{\n"
            f'    "baseline": {repr(float(m["baseline"][0]))},\n'
            f'    "feat": {tuple_text(m["feat"], int)},\n'
            f'    "threshold": {tuple_text(m["threshold"], float)},\n'
            f'    "left": {tuple_text(m["left"], int)},\n'
            f'    "right": {tuple_text(m["right"], int)},\n'
            f'    "missing_left": {tuple_text(m["missing_left"], int)},\n'
            f'    "leaf_value": {tuple_text(m["leaf_value"], float)},\n'
            f'    "offsets": {tuple_text(m["offsets"], int)},\n'
            f"}}")
    blocks.append("_MODELS = (" + ", ".join(f"_M{wi}" for wi in range(len(cut_strings))) + ")")
    return "\n\n".join(blocks)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    stop = threading.Event()
    threading.Thread(target=_watchdog, args=(stop,), daemon=True).start()
    proc = psutil.Process()

    print("[1/4] loading data + features ...", flush=True)
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, DATA_START, DATA_END, market_cap_field="total_mv")
    feats = build_features(frame)
    close = probe.wide(frame, "close_qfq")
    dvals = close.index.to_numpy()
    print(f"    shape={close.shape} rss={proc.memory_info().rss/1e9:.1f}GB t=+{time.time()-t0:.0f}s", flush=True)

    fwd = close.shift(-11) / close.shift(-1) - 1.0
    excess = fwd.sub(fwd.mean(axis=1), axis=0)
    del fwd
    gc.collect()

    grid = np.zeros(len(dvals), dtype=bool)
    grid[::probe.CYCLE] = True

    models, payloads, results, cut_strings = [], {}, [], []
    for wi, (tr_end, te_end) in enumerate(WINDOWS):
        tr_mask = dvals <= np.datetime64(pd.Timestamp(tr_end))
        te_mask = (dvals > np.datetime64(pd.Timestamp(tr_end))) & (dvals <= np.datetime64(pd.Timestamp(te_end)))
        names, xs, ys = probe.stack_features(feats, tr_mask, excess)
        print(f"[2/4] window {wi}: train rows={len(ys):,} -> apply {tr_end}..{te_end}", flush=True)
        model = HistGradientBoostingRegressor(**HGB_PARAMS)
        model.fit(xs, ys)
        te_idx = np.where(te_mask)[0]
        xs_te = np.stack([v.iloc[te_idx].to_numpy(dtype="float32").ravel() for v in feats.values()], axis=1)
        ok = np.isfinite(xs_te).all(axis=1)
        pred = np.full(xs_te.shape[0], np.nan)
        pred[ok] = model.predict(xs_te[ok])
        pred_df = pd.DataFrame(index=close.index[te_idx], columns=close.columns, dtype="float64")
        pred_df.iloc[:, :] = pred.reshape(len(te_idx), -1)
        metrics = probe.evaluate(pred_df, excess, close.index[te_mask & grid])
        metrics.update({"window": wi, "train_end": tr_end, "apply_end": te_end, "train_rows": len(ys)})
        results.append(metrics)
        print(f"    hgb: {json.dumps(metrics, ensure_ascii=False)}", flush=True)
        pay = export_arrays(model)
        check = predict_trees(xs_te[ok][:20000], pay)
        direct = model.predict(xs_te[ok][:20000])
        print(f"    tree check max|diff| = {np.max(np.abs(check - direct)):.2e}", flush=True)
        payloads.update({f"m{wi}_{k}": v for k, v in pay.items()})
        models.append(model)
        cut_strings.append(str(pd.Timestamp(te_end).date()))
        del xs, ys, xs_te, pred, pred_df
        gc.collect()

    print("[3/4] writing npz + factor file ...", flush=True)
    buf = io.BytesIO()
    np.savez_compressed(buf, **payloads)
    blob = buf.getvalue()
    (OUT_DIR / "models_wf.npz").write_bytes(blob)
    (OUT_DIR / "candidates.txt").write_text("ML-GBDT-WF ~ ml_gbdt_wf_factor.py ~ 1\n",
                                            encoding="utf-8", newline="\n")
    FACTOR_PATH.write_text(
        FACTOR_TEMPLATE.format(payload_block=emit_payload_block(payloads, cut_strings),
                               features=FEATURES, cuts=cut_strings),
        encoding="utf-8", newline="\n")
    pd.DataFrame(results).to_csv(OUT_DIR / "local_wf_eval.csv", index=False, float_format="%.4f")
    print(f"    {FACTOR_PATH.stat().st_size/1024:.0f} KB (payload literals)", flush=True)

    print("[4/4] end-to-end factor check against sklearn ...", flush=True)
    slice_dates = close.index[-950:]
    cmp_dates = close.index[-40:]
    mock = {}
    for name, key in (("close", "close_qfq"), ("volume", "volume"), ("amount", "amount"),
                      ("turnover", "turnover"), ("market_cap", "total_mv"),
                      ("high", "high_qfq"), ("low", "low_qfq")):
        mock[name] = probe.wide(frame, key).loc[slice_dates].stack(dropna=False)
    ns = {"Factor": object, "__name__": "factor_mod"}
    exec(compile(FACTOR_PATH.read_text(encoding="utf-8"), str(FACTOR_PATH), "exec"), ns)
    got = ns["MlGbdtWf"]().calculate(mock)
    got_w = got.unstack(level=1).loc[cmp_dates]
    xs_cmp = np.stack([v.loc[cmp_dates].to_numpy(dtype="float32").ravel() for v in feats.values()], axis=1)
    ok = np.isfinite(xs_cmp).all(axis=1)
    cuts_np = np.array([np.datetime64(c) for c in cut_strings])
    win = int(np.searchsorted(cuts_np, np.datetime64(str(cmp_dates[-1])[:10])))
    expected = models[win].predict(xs_cmp[ok])
    got_values = got_w.to_numpy(dtype="float64").ravel()[ok]
    both = np.isfinite(expected) & np.isfinite(got_values)
    diff = np.abs(got_values[both] - expected[both])
    missing = int(np.sum(np.isfinite(expected) & ~np.isfinite(got_values)))
    dmax = float(np.max(diff)) if diff.size else float("inf")
    print(f"    rows={ok.sum():,} window={win} finite_missing={missing} max|diff|={dmax:.2e}", flush=True)
    finite = int(np.isfinite(got.to_numpy()).sum())
    print(f"    factor output finite={finite:,} / {len(got):,}", flush=True)
    (OUT_DIR / "run_meta.json").write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(), "windows": WINDOWS, "features": FEATURES,
        "hgb_params": HGB_PARAMS, "elapsed_s": round(time.time() - t0, 1),
        "rss_gb": round(proc.memory_info().rss / 1e9, 2), "factor_kb": round(FACTOR_PATH.stat().st_size / 1024, 1),
        "e2e_max_abs_diff": dmax if np.isfinite(dmax) else None,
        "e2e_finite_missing": missing, "e2e_rows": int(ok.sum()),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    stop.set()
    if missing == 0 and dmax < 1e-6:
        print(f"    e2e PASS (rows={int(ok.sum()):,})", flush=True)
    else:
        print("    e2e FAILED -- do not submit this factor", flush=True)
        return 1
    print(f"done in {time.time()-t0:.0f}s -> {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
