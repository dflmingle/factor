#!/usr/bin/env python3
"""轻量候选屏 v2：cycle=10 口径的 s_i / 独立换手 / corr_size / 池合成 Δturnover 预测。

- s_i：RankIC 序列口径（120 期）
- turnover：候选自身 top-decile 换手/次
- corr_size：与 total_mv 的秩相关
- pred_dT：把候选 z-score 作为第 6 席并入现役 5 席池（等权），逐期算
  top-decile 组合换手差（= 池合成换手增量，直接预测账本的 dT）
输出 light191_cycle10.csv（或 --tag 指定）。
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import pickle
import sys
import types
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha191_ops_local as ops  # noqa: E402
import alphaprobe_gp_tushare as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/e-decomp-20260929"
PANELS = OUT / "panels_cache.pkl"
REBUILD = ROOT / "research_reports/platform_alignment/e-decomp-20260928/seat_panels_rebuilt.pkl"
CYCLE, GROUPS = 10, 10
T0 = time.time()


def log(m: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)


def install_shim() -> None:
    def factor_attr(*_a, **_k):
        def deco(fn):
            return fn
        return deco

    lib = types.ModuleType("lib"); lib.__path__ = []
    sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object
    sys.modules["lib.base"] = base
    pkg = types.ModuleType("lib.ops"); pkg.__path__ = []
    sys.modules["lib.ops"] = pkg
    fo = types.ModuleType("lib.ops.factor_ops")
    for name, fn in ops.OPS.items():
        setattr(fo, name, fn)
    sys.modules["lib.ops.factor_ops"] = fo
    ut = types.ModuleType("lib.utils"); ut.__path__ = []
    sys.modules["lib.utils"] = ut
    ma = types.ModuleType("lib.utils.method_attrs"); ma.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = ma
    ql = types.ModuleType("qlib"); ql.__path__ = []
    sys.modules["qlib"] = ql
    qd = types.ModuleType("qlib.data"); qd.__path__ = []
    sys.modules["qlib.data"] = qd
    qo = types.ModuleType("qlib.data.ops")
    for name in ("rolling_slope", "rolling_rsquare", "rolling_resi",
                 "expanding_slope", "expanding_rsquare", "expanding_resi"):
        setattr(qo, name, getattr(ops, name))
    sys.modules["qlib.data.ops"] = qo


def make_leg(panels, src_name, k, n, ratio_smooth=1):
    src = panels["volume" if src_name == "vol" else src_name]
    ratio = src.rolling(k).std() / src.rolling(n, min_periods=int(n * 0.32)).std()
    if int(ratio_smooth) > 1:
        ratio = ratio.rolling(int(ratio_smooth)).mean()
    return 1.0 - ratio.rank(axis=1, pct=True)


def top_decile_held(values: np.ndarray) -> set:
    finite = np.isfinite(values)
    idx = np.flatnonzero(finite)
    if len(idx) < GROUPS * 10:
        return set()
    q = (len(idx) * (GROUPS - 1)) // GROUPS
    part = np.argpartition(values[idx], q)[q:]
    return set(idx[part].tolist())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", default="all")
    ap.add_argument("--templates", default="turn6x504w20,turn10x750w20")
    ap.add_argument("--tag", default="light191_cycle10")
    ap.add_argument("--specs", type=Path, default=None,
                    help="optional JSON spec list {name, base, src, k, n, w, smooth, smooth_mode}")
    args = ap.parse_args()
    templates = []
    for t in args.templates.split(","):
        if t.startswith("turn"):
            tail = t[4:]
        elif t.startswith("vol"):
            tail = t[3:]
        else:
            raise SystemExit(f"bad template {t}")
        k, rest = tail.split("x")
        n, w = rest.split("w")
        templates.append(dict(src=t[:4] if t.startswith("turn") else "vol",
                              k=int(k), n=int(n), w=int(w) / 100.0, name=t))

    install_shim()
    ns: dict = {}
    ref = ROOT / ".cache/third_party/alpha191_reference.py"
    exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
    funcs = {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}

    failed = {5, 30, 103, 133, 143, 177}
    if args.bases == "all":
        bases = [f"{i:03d}" for i in range(1, 192) if i not in failed]
    else:
        bases = args.bases.split(",")

    specs_mode = args.specs is not None
    if specs_mode:
        raw = json.loads(args.specs.read_text(encoding="utf-8"))
        templates = [dict(src=x["src"], k=x["k"], n=x["n"], w=x["w"],
                          name=x["name"], smooth=x.get("smooth", 1),
                          smooth_mode=x.get("smooth_mode", "mix"),
                          ratio_smooth=x.get("ratio_smooth", 1), base=str(x["base"]))
                     for x in raw]
        bases = sorted({t["base"] for t in templates if t["base"] != "leg_only"})
        log(f"specs mode: {len(templates)} specs, bases={bases}")
    log("loading panels cache")
    panels = pickle.load(PANELS.open("rb"))
    payload = pickle.load(REBUILD.open("rb"))
    dates = [pd.Timestamp(d) for d in payload["dates"]]
    seats = payload["scores"].reset_index(drop=True)
    signal_frame = payload["signal_frame"]
    seat_sum = seats.sum(axis=1).to_numpy(dtype="float64")
    date_mask = {pd.Timestamp(d): (signal_frame["date"] == d).to_numpy()
                 for d in dates}
    log(f"panels+payload ready, bases={len(bases)} templates={len(templates)}")

    cal = list(panels["close"].index)
    pos = {d: i for i, d in enumerate(cal)}
    C = panels["close"]
    rets = [C.iloc[pos[d] + 1 + CYCLE].to_numpy(dtype="float64") /
            C.iloc[pos[d] + 1].to_numpy(dtype="float64") - 1.0 for d in dates]
    cap = panels["mcap"].reindex(index=dates)
    log("returns ready")

    data_keys = ("close", "open", "high", "low", "volume", "amount", "vwap", "turn")
    leg_cache = {}
    leg_base = {}
    for t in templates:
        key = (t["src"], t["k"], t["n"], int(t.get("ratio_smooth", 1)))
        if key not in leg_base:
            leg_base[key] = make_leg(panels, key[0], key[1], key[2], ratio_smooth=key[3])
        lg = leg_base[key]
        if int(t.get("smooth", 1)) > 1 and t.get("smooth_mode", "mix") == "leg":
            lg = lg.rolling(int(t["smooth"])).mean()
        leg_cache[t["name"]] = lg
    log("legs ready")

    # baseline pool composite turnover (5 seats) - instrument-name space
    prev_pool = None
    pool_turn = []
    for k, d in enumerate(dates):
        m = date_mask[d]
        inst_d = signal_frame.loc[m, "instrument"].astype(str).to_numpy()
        held = {inst_d[i] for i in top_decile_held(seat_sum[m])}
        if prev_pool is not None and held:
            pool_turn.append(1.0 - len(held & prev_pool) / len(held))
        prev_pool = held
    log(f"pool baseline turnover/rebal = {np.mean(pool_turn):.4f} (n={len(pool_turn)})")

    seat_finite = np.isfinite(seats.to_numpy(dtype="float64")).all(axis=1)
    stock_pos = {c: j for j, c in enumerate(C.columns.astype(str))}
    date_take = {}
    for d in dates:
        mrow = date_mask[d]
        inst = signal_frame.loc[mrow, "instrument"].astype(str).to_numpy()
        take = np.array([stock_pos.get(s2, -1) for s2 in inst], dtype=np.int64)
        date_take[d] = (mrow, take)

    rows = []
    loop_bases = bases if not specs_mode else bases + (["leg_only"] if any(t["base"]=="leg_only" for t in templates) else [])
    for bi, base in enumerate(loop_bases):
        if base == "leg_only":
            base_rank = None
        else:
            try:
                fn = funcs[f"alpha191_{base}"]
                res = fn({k: panels[k] for k in data_keys})
                base_rank = res.rank(axis=1, pct=True)
            except Exception as exc:  # noqa: BLE001
                log(f"[{base}] FAIL {type(exc).__name__}: {exc}"[:120])
                continue
        for t in templates:
            if specs_mode and t["base"] != base:
                continue
            leg = leg_cache[t["name"]]
            if base == "leg_only":
                mixed = leg
            else:
                mixed = t["w"] * base_rank + (1.0 - t["w"]) * leg
            sm = int(t.get("smooth", 1)); sm_mode = t.get("smooth_mode", "mix")
            if sm > 1 and sm_mode == "leg":
                leg2 = leg.rolling(sm).mean()
                mixed = t["w"] * base_rank + (1.0 - t["w"]) * leg2
                del leg2
            if sm > 1 and sm_mode == "mix":
                mixed = mixed.rolling(sm).mean()
            sig = mixed.reindex(index=dates)
            ics, turns, corrs, dturns = [], [], [], []
            prev = None
            prev_pool = None
            prev_oldmap = None
            for k, d in enumerate(dates):
                x = sig.iloc[k].to_numpy(dtype="float64")
                y = rets[k]
                m = np.isfinite(x) & np.isfinite(y)
                if m.sum() >= 100:
                    ics.append(float(np.corrcoef(pd.Series(x[m]).rank(),
                                                 pd.Series(y[m]).rank())[0, 1]))
                held = top_decile_held(x)
                if prev is not None and held:
                    turns.append(1.0 - len(held & prev) / len(held))
                prev = held
                b = cap.iloc[k].to_numpy(dtype="float64")
                m2 = np.isfinite(x) & np.isfinite(b)
                if m2.sum() >= 200:
                    corrs.append(float(np.corrcoef(pd.Series(x[m2]).rank(),
                                                   pd.Series(b[m2]).rank())[0, 1]))
                # pool composite simulation
                mrow, take = date_take[d]
                cvals = np.full(len(take), np.nan)
                ok = take >= 0
                cvals[ok] = x[take[ok]]
                finite = np.isfinite(cvals)
                seats_ok = seat_finite[mrow]
                ok = seats_ok & np.isfinite(cvals)
                idx = np.flatnonzero(ok)
                if len(idx) >= 100:
                    v = cvals[idx]
                    lo, hi = np.quantile(v, [0.01, 0.99])
                    clipped = np.clip(v, lo, hi)
                    std = clipped.std(ddof=0)
                    z = (clipped - clipped.mean()) / std if std > 1e-12 else np.zeros(len(v))
                    ssum = seat_sum[mrow][idx]
                    new_sum = ssum + z
                    inst_d = signal_frame.loc[mrow, "instrument"].astype(str).to_numpy()
                    q = (len(idx) * (GROUPS - 1)) // GROUPS
                    hn = set(inst_d[idx[np.argpartition(new_sum, q)[q:]]])
                    ho = set(inst_d[idx[np.argpartition(ssum, q)[q:]]])
                    if prev_pool is not None and hn and ho:
                        t_new = 1.0 - len(hn & prev_pool) / len(hn)
                        t_old = 1.0 - len(ho & prev_oldmap) / len(ho)
                        dturns.append(t_new - t_old)
                    prev_pool = hn
                    prev_oldmap = ho
            ics = np.asarray(ics)
            mean = float(ics.mean()); std = float(ics.std(ddof=1))
            ir = mean / std if std > 0 else 0.0
            win = float((ics > 0.02).mean()) if mean >= 0 else float((ics < -0.02).mean())
            rows.append(dict(alpha=base, template=t["name"], periods=int(np.isfinite(ics).sum()),
                             rank_ic=mean, ic_ir=ir, win=win,
                             s_i=abs(mean) * abs(ir) * win,
                             turnover=float(np.mean(turns)) if turns else np.nan,
                             corr_size=float(np.mean(corrs)) if corrs else np.nan,
                             pred_dturn=float(np.mean(dturns)) if dturns else np.nan))
        if (bi + 1) % 20 == 0:
            log(f"base {bi+1}/{len(bases)} done")
        if base_rank is not None:
            del base_rank
        gc.collect()

    df = pd.DataFrame(rows)
    path = OUT / f"{args.tag}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    df = df.sort_values("s_i", ascending=False)
    pd.set_option("display.width", 250)
    print(df.head(40).round(4).to_string(index=False))
    log(f"written {path} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
