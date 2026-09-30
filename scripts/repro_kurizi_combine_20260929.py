#!/usr/bin/env python3
""""苦日子"复算第三轮：多腿贪心复合能否把 5 日口径 ICIR 抬到 .85+。

流程：构造 ~14 条混权腿（cycle=5、241 期口径），逐条算 ICIR；
贪心从最高 ICIR 腿出发，每次加入"使复合 ICIR 增益最大"的腿（信号日截面 rank 平均），
输出完整链条。产物 repro_combine_stats.csv + 控制台链。
"""
from __future__ import annotations

import io
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import exhaustive_representative_combination as e  # noqa: E402
import alpha191_ops_local as ops  # noqa: E402
from independent_information_combination import DATA_START, END  # noqa: E402

OUT = ROOT / "research_reports/platform_alignment/repro-kurizi-20260929"
ALIGN_START = pd.Timestamp("2021-09-07")
ALIGN_END = pd.Timestamp("2026-09-07")
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


def ic_stats(ics: np.ndarray) -> dict:
    s = ics[np.isfinite(ics)]
    if len(s) < 3:
        return dict(periods=len(s), ic=np.nan, icir=np.nan, win=np.nan)
    mean = float(s.mean())
    std = float(s.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    win = float((s > 0.02).mean()) if mean >= 0 else float((s < -0.02).mean())
    return dict(periods=len(s), ic=mean, icir=ir, win=win)


def main() -> int:
    install_shim()
    ns: dict = {}
    ref = ROOT / ".cache/third_party/alpha191_reference.py"
    exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
    funcs = {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}

    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, DATA_START, END)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    log(f"frame {frame.shape}")
    pv = lambda c: frame.pivot(index="date", columns="instrument", values=c).astype("float32")
    C = pv("close_qfq"); O = pv("open_qfq"); H = pv("high_qfq"); L = pv("low_qfq")
    V = pv("volume"); A = pv("amount"); T = pv("turnover")
    cal = [pd.Timestamp(d) for d in C.index]
    pos = {d: i for i, d in enumerate(cal)}
    vwap = (A / V * 10.0).astype("float32")
    R = lambda X: X.rank(axis=1, pct=True)
    log("panels ready, legs ...")

    V5y = V.rolling(10).std() / V.rolling(1250, min_periods=400).std()
    T5y = T.rolling(20).std() / T.rolling(1250, min_periods=400).std()
    stdrel = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()
    R252 = T.rolling(5).mean() / T.rolling(252, min_periods=100).mean()
    R21504 = T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()
    lv5 = 1.0 - R(V5y); lt5 = 1.0 - R(T5y); rt = 1.0 - R(R252); rt21504 = 1.0 - R(R21504)
    lvlT = 1.0 - R(T)
    volret = 1.0 - C.pct_change(fill_method=None).rolling(20).std().rank(axis=1, pct=True)
    s010 = (-funcs["alpha191_010"]({"close": C})).astype("float32")
    s120 = funcs["alpha191_120"]({"open": O, "high": H, "low": L, "close": C, "volume": V, "vwap": vwap}).astype("float32")
    s140 = funcs["alpha191_140"]({"open": O, "high": H, "low": L, "close": C, "volume": V, "vwap": vwap}).astype("float32")
    ra, rb, rc = R(s010), R(s120), R(s140)
    log("legs done")

    legs = {
        "010xvolV5y_w0.1": 0.1 * ra + 0.9 * lv5,
        "010xvolV5y_w0.2": 0.2 * ra + 0.8 * lv5,
        "010xvolT5y_w0.2": 0.2 * ra + 0.8 * lt5,
        "010xrelT21504_w0.2": 0.2 * ra + 0.8 * rt21504,
        "010xlvlT_w0.2": 0.2 * ra + 0.8 * lvlT,
        "010xvolret_w0.2": 0.2 * ra + 0.8 * volret,
        "120xvolT5y_w0.2": 0.2 * rb + 0.8 * lt5,
        "120xvolT5y_w0.3": 0.3 * rb + 0.7 * lt5,
        "120xrelT21504_w0.2": 0.2 * rb + 0.8 * rt21504,
        "140xvolV5y_w0.5": 0.5 * rc + 0.5 * lv5,
        "140xvolT5y_w0.3": 0.3 * rc + 0.7 * lt5,
        "140xrelT_w0.3": 0.3 * rc + 0.7 * rt,
        "140xrelT21504_w0.3": 0.3 * rc + 0.7 * rt21504,
        "stdvol20_rel5y": stdrel,
    }
    cycle = 5
    schedule = [cal[i] for i in range(0, len(cal), cycle) if ALIGN_START <= cal[i] <= ALIGN_END]
    idxs = [pos[d] for d in schedule]
    rets = []
    keep_rows = []
    for i in idxs:
        j0, j1 = i + 1, i + 1 + cycle
        if j1 >= len(cal):
            continue
        keep_rows.append(i)
        rets.append(C.iloc[j1].to_numpy(dtype="float64") / C.iloc[j0].to_numpy(dtype="float64") - 1.0)
    log(f"schedule {len(keep_rows)} periods")

    def rank_panel(X: pd.DataFrame) -> np.ndarray:
        return np.stack([X.iloc[i].rank().to_numpy(dtype="float64") for i in keep_rows])

    def ir_of(sig_rank: np.ndarray) -> dict:
        ics = []
        for k in range(sig_rank.shape[0]):
            x = sig_rank[k]; y = rets[k]
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 100:
                continue
            xr = pd.Series(x[m]).rank().to_numpy(); yr = pd.Series(y[m]).rank().to_numpy()
            ics.append(float(np.corrcoef(xr, yr)[0, 1]))
        return ic_stats(np.asarray(ics))

    ranks = {}
    single = []
    for name, X in legs.items():
        ranks[name] = rank_panel(X)
        st = ir_of(ranks[name])
        single.append(dict(item=name, stage="single", **st))
        log(f"single {name:24s} ic={st['ic']:+.4f} icir={st['icir']:+.4f} win={st['win']:.4f}")

    order = sorted(legs, key=lambda n: -(ir_of(ranks[n])["icir"] if np.isfinite(ir_of(ranks[n])["icir"]) else -9))
    chosen = [order[0]]
    combo = ranks[order[0]].copy()
    chain = [{"step": 1, "add": order[0], "icir": ir_of(combo)["icir"]}]
    pool = [n for n in order[1:]]
    while pool:
        best = None
        for n in pool:
            c = (combo * len(chosen) + ranks[n]) / (len(chosen) + 1)
            st = ir_of(c)
            if best is None or st["icir"] > best[1]["icir"]:
                best = (n, st, c)
        n, st, c = best
        if st["icir"] <= chain[-1]["icir"] + 1e-6:
            break
        chosen.append(n); combo = c; pool.remove(n)
        chain.append({"step": len(chosen), "add": n, "icir": st["icir"],
                      "ic": st["ic"], "win": st["win"]})
        log(f"combo step{len(chosen)} +{n:24s} ic={st['ic']:+.4f} icir={st['icir']:+.4f} win={st['win']:.4f}")
    pd.DataFrame(single + [dict(item=c["add"], stage=f"combo{c['step']}", ic=c.get("ic"), icir=c["icir"], win=c.get("win")) for c in chain]).to_csv(
        OUT / "repro_combine_stats.csv", index=False, encoding="utf-8-sig")
    print("\nchain:", " -> ".join(c["add"] for c in chain))
    print("final icir:", round(chain[-1]["icir"], 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
