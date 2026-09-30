#!/usr/bin/env python3
""""苦日子"复算补洞实验：平滑/换腿能否把 5 日口径 ICIR 从 .55-.68 抬到 .85+。

候选族（cycle=5，241 期）：
  base5   = 上一轮 5 条混权腿
  ema3/5/10      = 对候选做 EMA(span) 平滑
  roll3/5        = 对候选做滚动均值平滑
  swap 腿        = 010×rel_T21_T504 / 010×volret / 010×lvl1mT21 / 120×relT / 140×rel_T21_T504
  w 扫描         = 010 基底 w=0.2/0.3/0.4 × volV5y
输出 repro_smooth_stats.csv（按 cycle=5 ICIR 降序）。
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
        return dict(periods=len(s), ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan)
    mean = float(s.mean())
    std = float(s.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    win = float((s > 0.02).mean()) if mean >= 0 else float((s < -0.02).mean())
    return dict(periods=len(s), ic=mean, icir=ir, win=win, s_i=abs(mean) * abs(ir) * win)


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
    log("panels ready, rolling legs ...")

    V5y = V.rolling(10).std() / V.rolling(1250, min_periods=400).std()
    T5y = T.rolling(20).std() / T.rolling(1250, min_periods=400).std()
    stdrel = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()
    R25 = T.rolling(5).mean() / T.rolling(252, min_periods=100).mean()
    R21504 = T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()
    leg_volV5y = 1.0 - R(V5y)
    leg_volT5y = 1.0 - R(T5y)
    leg_relT = 1.0 - R(R25)
    leg_relT21504 = 1.0 - R(R21504)
    leg_lvlT = 1.0 - R(T)
    volret = (1.0 - (C.pct_change(fill_method=None).rolling(20).std()).rank(axis=1, pct=True))
    s010 = (-funcs["alpha191_010"]({"close": C})).astype("float32")
    s120 = funcs["alpha191_120"]({"open": O, "high": H, "low": L, "close": C,
                                  "volume": V, "vwap": vwap}).astype("float32")
    s140 = funcs["alpha191_140"]({"open": O, "high": H, "low": L, "close": C,
                                  "volume": V, "vwap": vwap}).astype("float32")
    log("legs done")

    ra010, ra120, ra140 = R(s010), R(s120), R(s140)
    base_cands = {
        "010xvolV5y_w0.1": 0.1 * ra010 + 0.9 * leg_volV5y,
        "010xvolV5y_w0.2": 0.2 * ra010 + 0.8 * leg_volV5y,
        "010xvolV5y_w0.3": 0.3 * ra010 + 0.7 * leg_volV5y,
        "010xvolV5y_w0.4": 0.4 * ra010 + 0.6 * leg_volV5y,
        "010xrelT21504_w0.2": 0.2 * ra010 + 0.8 * leg_relT21504,
        "010xvolret_w0.2": 0.2 * ra010 + 0.8 * volret,
        "010xlvlT_w0.2": 0.2 * ra010 + 0.8 * leg_lvlT,
        "120xvolT5y_w0.2": 0.2 * ra120 + 0.8 * leg_volT5y,
        "120xrelT21504_w0.2": 0.2 * ra120 + 0.8 * leg_relT21504,
        "140xrelT21504_w0.3": 0.3 * ra140 + 0.7 * leg_relT21504,
        "stdvol20_rel5y": stdrel,
    }
    cands: dict[str, pd.DataFrame] = dict(base_cands)
    for name, X in base_cands.items():
        for span in (3, 5, 10):
            cands[f"{name}__ema{span}"] = X.ewm(span=span, adjust=False).mean()
        for win in (3, 5):
            cands[f"{name}__roll{win}"] = X.rolling(win).mean()
    log(f"candidates {len(cands)}")

    cycle = 5
    schedule = [cal[i] for i in range(0, len(cal), cycle) if ALIGN_START <= cal[i] <= ALIGN_END]
    rows = []
    for name, cand in cands.items():
        ics = []
        for d in schedule:
            i = pos[d]
            j0, j1 = i + 1, i + 1 + cycle
            if j1 >= len(cal):
                continue
            x = cand.iloc[i].to_numpy(dtype="float64")
            y = (C.iloc[j1].to_numpy(dtype="float64") / C.iloc[j0].to_numpy(dtype="float64") - 1.0)
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 100:
                continue
            xr = pd.Series(x[m]).rank().to_numpy()
            yr = pd.Series(y[m]).rank().to_numpy()
            ics.append(float(np.corrcoef(xr, yr)[0, 1]))
        st = ic_stats(np.asarray(ics))
        rows.append(dict(name=name, **st))
    df = pd.DataFrame(rows).sort_values("icir", ascending=False)
    df.to_csv(OUT / "repro_smooth_stats.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(df.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
