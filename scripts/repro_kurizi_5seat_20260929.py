#!/usr/bin/env python3
""""苦日子"（rank 3 池）5 席的同口径复算（2026-09-29，零平台算力）。

目标（平台 cycle=5，n=240）：R03 / C260912-B01 / R01-0.0847 / R01-0.0790 / R01-0.0812
本地候选（签名最近邻，来自 board-details-20260929）：
  10xvolV5y_w0.1 / stdvol20_rel5y / 120xvolT5y_w0.2 / 140xvolV5y_w0.5 / 140xrel_T5_T252_w0.3
复算口径：全 A .SH/.SZ、qfq、2018 暖机、cycle=5（240 期，20210929~20260814 近似）与
          cycle=10（120 期）双口径；RankIC 序列 mean/std/win(>0.02)。
混权定义（与 side-line p0b_blend 一致）：LW = w*rank(base) + (1-w)*rank(leg)；rank=逐日截面 pct。
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
        return dict(periods=len(s), ic=None, icir=None, win=None, s_i=None)
    mean = float(s.mean())
    std = float(s.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    win = float((s > 0.02).mean()) if mean >= 0 else float((s < -0.02).mean())
    return dict(periods=len(s), ic=mean, icir=ir, win=win, s_i=abs(mean) * abs(ir) * win)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    install_shim()
    ns: dict = {}
    ref = ROOT / ".cache/third_party/alpha191_reference.py"
    exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
    funcs = {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}
    log(f"reference loaded, factors={len(funcs)}")

    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, DATA_START, END)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    log(f"frame {frame.shape} {frame['date'].min().date()}..{frame['date'].max().date()}")
    pv = lambda c: frame.pivot(index="date", columns="instrument", values=c).astype("float32")
    C = pv("close_qfq"); O = pv("open_qfq"); H = pv("high_qfq"); L = pv("low_qfq")
    V = pv("volume"); A = pv("amount"); T = pv("turnover")
    cal = [pd.Timestamp(d) for d in C.index]
    pos = {d: i for i, d in enumerate(cal)}
    log(f"panels close {C.shape}")

    vwap = (A / V * 10.0).astype("float32")
    R = lambda X: X.rank(axis=1, pct=True)
    V5y = (V.rolling(10).std() / V.rolling(1250, min_periods=400).std())
    T5y = (T.rolling(20).std() / T.rolling(1250, min_periods=400).std())
    R25 = (T.rolling(5).mean() / T.rolling(252, min_periods=100).mean())
    stdrel = (V.rolling(20).std() / V.rolling(1250, min_periods=400).std())
    log("legs rolling done")
    leg_volV5y = 1.0 - R(V5y)
    leg_volT5y = 1.0 - R(T5y)
    leg_relT = 1.0 - R(R25)
    s010 = (-funcs["alpha191_010"]({"close": C})).astype("float32")
    s120 = funcs["alpha191_120"]({"open": O, "high": H, "low": L, "close": C,
                                  "volume": V, "vwap": vwap}).astype("float32")
    s140 = funcs["alpha191_140"]({"open": O, "high": H, "low": L, "close": C,
                                  "volume": V, "vwap": vwap}).astype("float32")
    log("A191 signals done")

    cands = {
        "10xvolV5y_w0.1": 0.1 * R(s010) + 0.9 * R(leg_volV5y),
        "stdvol20_rel5y": stdrel,
        "120xvolT5y_w0.2": 0.2 * R(s120) + 0.8 * R(leg_volT5y),
        "140xvolV5y_w0.5": 0.5 * R(s140) + 0.5 * R(leg_volV5y),
        "140xrel_T5_T252_w0.3": 0.3 * R(s140) + 0.7 * R(leg_relT),
    }

    rows = []
    for cycle in (5, 10):
        schedule = [cal[i] for i in range(0, len(cal), cycle)
                    if ALIGN_START <= cal[i] <= ALIGN_END]
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
            rows.append(dict(cycle=cycle, name=name, **st))
            log(f"cycle={cycle} {name:22s} n={st['periods']} ic={st['ic']:+.4f} "
                f"icir={st['icir']:+.4f} win={st['win']:.4f} s_i={st['s_i']:.5f}")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "repro_5seat_stats.csv", index=False, encoding="utf-8-sig")

    target = {
        "10xvolV5y_w0.1": ("R03-0.0727-0.8019", 0.096234, 0.943611, 0.8125),
        "stdvol20_rel5y": ("C260912-B01", 0.093552, 0.869099, 0.775),
        "120xvolT5y_w0.2": ("R01-0.0847-0.7915", 0.091362, 0.865800, 0.754167),
        "140xvolV5y_w0.5": ("R01-0.0790-0.9569", 0.074442, 0.837932, 0.741667),
        "140xrel_T5_T252_w0.3": ("R01-0.0812-0.9306", 0.067516, 0.730259, 0.716667),
    }
    print("\n=== cycle=5（240 期）对比苦日子席位 ===")
    for name, (opp, oic, oir, owin) in target.items():
        r = df[(df.cycle == 5) & (df.name == name)].iloc[0]
        print(f"{name:22s} -> {opp:20s} mine ic={r.ic:+.4f} icir={r.icir:+.4f} win={r.win:.4f} n={r.periods} "
              f"| opp ic={oic:+.4f} icir={oir:+.4f} win={owin:.4f} "
              f"| d_ic={r.ic-oic:+.4f} d_icir={r.icir-oir:+.4f} d_win={r.win-owin:+.4f}")
    print(f"\nwritten {OUT/'repro_5seat_stats.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
