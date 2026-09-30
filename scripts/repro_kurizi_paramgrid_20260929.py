#!/usr/bin/env python3
""""苦日子"复刻第四轮：5 日口径参数网格（k x N x 基底 x w x 源）。

假设：对手的高 ICIR 来自"短快窗/短慢窗 + 不同基底"的参数化（此前只扫过 10 日口径的 k）。
网格：源 {volume, turnover} × 快窗 k {5,6,10,20} × 慢窗 N {252,504,750,1250}
      × 基底 {010,042,120,140} × w {0.1,0.2,0.3,0.5}
评估：cycle=5、2021-09-07..2026-09-07、全 A qfq、RankIC 序列 -> ic/icir/win/s_i。
输出 repro_paramgrid_stats.csv（按 icir 降序）+ 控制台 top30 与苦日子席位并排。
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
CYCLE = 5
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
    del A
    R = lambda X: X.rank(axis=1, pct=True)
    log("panels ready")

    schedule = [cal[i] for i in range(0, len(cal), CYCLE) if ALIGN_START <= cal[i] <= ALIGN_END]
    rows_idx = []
    for d in schedule:
        i = pos[d]
        if i + 1 + CYCLE < len(cal):
            rows_idx.append(i)
    log(f"signal rows {len(rows_idx)}")
    rets = []
    for i in rows_idx:
        j0, j1 = i + 1, i + 1 + CYCLE
        rets.append(C.iloc[j1].to_numpy(dtype="float64") / C.iloc[j0].to_numpy(dtype="float64") - 1.0)

    def signal_rows(X: pd.DataFrame) -> np.ndarray:
        return X.iloc[rows_idx].to_numpy(dtype="float64")

    def rank_rows(Xr: np.ndarray) -> np.ndarray:
        out = np.empty_like(Xr)
        for k in range(Xr.shape[0]):
            out[k] = pd.Series(Xr[k]).rank().to_numpy()
        return out

    def ir_of(Xr: np.ndarray) -> dict:
        ics = []
        for k in range(Xr.shape[0]):
            x = Xr[k]; y = rets[k]
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 100:
                continue
            xr = pd.Series(x[m]).rank().to_numpy(); yr = pd.Series(y[m]).rank().to_numpy()
            ics.append(float(np.corrcoef(xr, yr)[0, 1]))
        return ic_stats(np.asarray(ics))

    bases = {
        "010": R((-funcs["alpha191_010"]({"close": C})).astype("float32")),
        "042": R(funcs["alpha191_042"]({"close": C, "open": O, "high": H, "low": L, "volume": V})),
        "120": R(funcs["alpha191_120"]({"open": O, "high": H, "low": L, "close": C, "volume": V, "vwap": vwap})),
        "140": R(funcs["alpha191_140"]({"open": O, "high": H, "low": L, "close": C, "volume": V, "vwap": vwap})),
    }
    base_rows = {name: signal_rows(df) for name, df in bases.items()}
    del bases
    log("bases done")

    Ks = [5, 6, 10, 20]
    Ns = [252, 504, 750, 1250]
    Ws = [0.1, 0.2, 0.3, 0.5]
    rows = []
    for src_name, S in (("vol", V), ("turn", T)):
        stdk = {k: S.rolling(k).std() for k in Ks}
        stdN = {n: S.rolling(n, min_periods=int(n * 0.32)).std() for n in Ns}
        log(f"rolling done for {src_name}")
        leg_rows = {}
        for k in Ks:
            for n in Ns:
                ratio = stdk[k] / stdN[n]
                leg = 1.0 - ratio.rank(axis=1, pct=True)
                leg_rows[(k, n)] = signal_rows(leg)
                del ratio, leg
            log(f"legs {src_name} k={k} done")
        del stdk, stdN
        for name, br in base_rows.items():
            rb = br  # already rank rows? base_rows are raw rank positions -> re-rank fine
            for (k, n), lr in leg_rows.items():
                for w in Ws:
                    mixed = w * rb + (1.0 - w) * lr
                    st = ir_of(mixed)
                    rows.append(dict(src=src_name, base=name, k=k, n=n, w=w, **st))
        log(f"grid done for {src_name}")

    df = pd.DataFrame(rows).sort_values("icir", ascending=False)
    df.to_csv(OUT / "repro_paramgrid_stats.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print("\n== 5 日口径参数网格 top30 ==")
    print(df.head(30).round(4).to_string(index=False))
    print("\n== 苦日子目标（cycle=5, n=240）==")
    print("R03 .0962/.9436/.8125 | C260912-B01 .0936/.8691/.775 | R01-0847 .0914/.8658/.7542 | "
          "R01-0790 .0744/.8379/.7417 | R01-0812 .0675/.7303/.7167")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
