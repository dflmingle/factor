#!/usr/bin/env python3
"""苦日子复刻第五轮：全 191 编号 × turn/vol 模板的 5 日口径基底全扫描。

背景：第四轮参数网格在 {010,042,120,140} 四个基底上找到新模板
  T1 = turn k=5 N=750 w=0.1 -> icir .7623（此前上限 .679）。
本脚本把四个模板套到全部 191 个 alpha191 编号基底上，cycle=5 口径
（2021-09-07..2026-09-07，241 期，全 A qfq），寻找 icir > .76 的新基底。

模板（混权 = w*rank(base) + (1-w)*rank(leg)）：
  T1 turn k=5  N=750 w=0.1   （网格最优）
  T2 turn k=6  N=504 w=0.2   （次优，win 最高 .751）
  T3 turn k=6  N=504 w=0.1
  V1 vol  k=6  N=504 w=0.2   （vol 源最优）
评价：每 5 交易日一期，RankIC 序列 -> ic/icir/win/s_i；前/后半段 icir 作稳定性诊断。
输出 repro_a191turn_stats.csv（长表，逐 alpha 追加写盘）。
"""
from __future__ import annotations

import io
import sys
import time
import traceback
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
    assert len(funcs) == 191, len(funcs)

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
    log("panels ready")

    data_dict = {"close": C, "open": O, "high": H, "low": L,
                 "volume": V, "amount": None, "vwap": vwap, "turn": T}
    data_dict["amount"] = pv("amount")
    log("amount panel ready")

    schedule = [cal[i] for i in range(0, len(cal), CYCLE) if ALIGN_START <= cal[i] <= ALIGN_END]
    rows_idx = []
    for d in schedule:
        i = pos[d]
        if i + 1 + CYCLE < len(cal):
            rows_idx.append(i)
    rets = []
    for i in rows_idx:
        j0, j1 = i + 1, i + 1 + CYCLE
        rets.append(C.iloc[j1].to_numpy(dtype="float64") / C.iloc[j0].to_numpy(dtype="float64") - 1.0)
    log(f"signal rows {len(rows_idx)}")

    def rank_rows(Xr: np.ndarray) -> np.ndarray:
        out = np.empty_like(Xr)
        for k in range(Xr.shape[0]):
            out[k] = pd.Series(Xr[k]).rank().to_numpy()
        return out

    def ic_series(Xr: np.ndarray) -> np.ndarray:
        ics = []
        for k in range(Xr.shape[0]):
            x = Xr[k]; y = rets[k]
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 100:
                ics.append(np.nan); continue
            xr = pd.Series(x[m]).rank().to_numpy(); yr = pd.Series(y[m]).rank().to_numpy()
            ics.append(float(np.corrcoef(xr, yr)[0, 1]))
        return np.asarray(ics)

    def half_stats(Xr: np.ndarray) -> tuple:
        ics = ic_series(Xr)
        h = len(ics) // 2
        a = ic_stats(ics[:h]); b = ic_stats(ics[h:])
        return a["icir"], b["icir"]

    templates = {
        "T1_turn_k5N750w10": ("turn", 5, 750, 0.1),
        "T2_turn_k6N504w20": ("turn", 6, 504, 0.2),
        "T3_turn_k6N504w10": ("turn", 6, 504, 0.1),
        "V1_vol_k6N504w20": ("vol", 6, 504, 0.2),
    }
    src_panels = {"vol": V, "turn": T}
    leg_rows = {}
    for tname, (src, k, n, w) in templates.items():
        S = src_panels[src]
        ratio = S.rolling(k).std() / S.rolling(n, min_periods=int(n * 0.32)).std()
        leg = 1.0 - ratio.rank(axis=1, pct=True)
        leg_rows[tname] = (leg.iloc[rows_idx].to_numpy(dtype="float32"), w)
        del ratio, leg
        log(f"leg {tname} ready")

    out_csv = OUT / "repro_a191turn_stats.csv"
    rows = []
    fails = []
    for i in range(1, 192):
        name = f"alpha191_{i:03d}"
        fn = funcs.get(name)
        if fn is None:
            fails.append((name, "missing")); continue
        try:
            res = fn(data_dict)
            if not isinstance(res, pd.DataFrame):
                fails.append((name, f"type={type(res).__name__}")); continue
            sig = res.reindex(index=C.index, columns=C.columns).astype("float32")
            if not np.isfinite(sig.to_numpy()).any():
                fails.append((name, "all-nan")); continue
            base_rank = sig.rank(axis=1, pct=True).iloc[rows_idx].to_numpy(dtype="float32")
        except Exception as exc:  # noqa: BLE001
            fails.append((name, f"{type(exc).__name__}: {exc}"))
            continue
        st = ic_stats(ic_series(base_rank))
        rows.append(dict(alpha=name, variant="bare", **st))
        for tname, (lr, w) in leg_rows.items():
            mixed = (w * base_rank + (1.0 - w) * lr).astype("float32")
            st = ic_stats(ic_series(mixed))
            h1, h2 = half_stats(mixed)
            rows.append(dict(alpha=name, variant=tname, half1_icir=h1, half2_icir=h2, **st))
        if i % 10 == 0 or i == 191:
            log(f"alpha {i:3d}/191 done, elapsed {time.time()-T0:.0f}s")
        del sig, base_rank

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    wide = df.pivot(index="alpha", columns="variant", values="icir").sort_values(
        "T1_turn_k5N750w10", ascending=False)
    pd.set_option("display.width", 240)
    print("\n== T1 模板 top25 ==")
    cols = ["bare", "T1_turn_k5N750w10", "T2_turn_k6N504w20", "V1_vol_k6N504w20"]
    print(wide[cols].head(25).round(4).to_string())
    print("\n== T1 显著优于 042 模板（.7623）的编号 ==")
    top = wide[wide["T1_turn_k5N750w10"] > 0.7623]
    print(top.round(4).to_string())
    full = df[df.variant == "T1_turn_k5N750w10"].set_index("alpha")
    print("\n== top10 前后半段稳定性（T1）==")
    sel = wide.head(10).index
    print(full.loc[sel, ["ic", "icir", "win", "half1_icir", "half2_icir"]].round(4).to_string())
    print(f"\n== 失败 {len(fails)} 个 ==")
    for nm, why in fails[:20]:
        print(" ", nm, why)
    print("== 苦日子目标（cycle=5, n=240）==")
    print("R03 .0962/.9436 | C260912-B01 .0936/.8691 | R01-0847 .0914/.8658 | "
          "R01-0790 .0744/.8379 | R01-0812 .0675/.7303")
    log(f"done, csv -> {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
