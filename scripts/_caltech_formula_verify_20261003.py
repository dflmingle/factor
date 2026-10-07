# -*- coding: utf-8 -*-
"""平台公式仿真校验（2026-10-03，技术目录族 2 条，零算力）。

把 candidates.txt 里的平台公式用 pandas 语义仿真，与本地腿库（caltech_legs_20261003）
的腿/复合逐期截面秩相关对照，确认转写无误（照抄 _behavioral_formula_verify_20261003 流程）。

用法:
  python scripts/_caltech_formula_verify_20261003.py <candidates.txt>
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from caltech_legs_20261003 import build_caltech_legs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"

SIGNED = {
    "CT-AMT-STD20-20261003": {"ct_amt_std20": 1.0},
    "CT-COMP-AMTDISP-20261003": {"ct_amt_std20": 1.0, "ct_amt_ma20": 1.0},
    "CT-COMP-TOPMIX-20261003": {
        "ct_amt_std20": 1.0, "ct_amt_ma20": 1.0, "ct_vol_std10": 1.0, "ct_vol_std20": 1.0,
        "ct_tor_ratio10_120": 1.0, "ct_vol5": 1.0, "ct_davol5": 1.0, "ct_amp10": 1.0,
    },
}


def parse_candidates(path: Path):
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("~")]
        if len(parts) != 3:
            raise ValueError(f"bad candidate line: {raw!r}")
        out.append((parts[0], parts[1], parts[2]))
    return out


def build_ns(panels: dict) -> dict:
    """与 caltech_legs_20261003 完全同源的原始序列（store 口径），再按平台语义组装。"""
    import caltech_legs_20261003 as ct

    store = ct._store_for(panels)
    index = panels["close"].index
    columns = panels["close"].columns

    def P(arr):
        return pd.DataFrame(np.asarray(arr, dtype="float64"), index=index, columns=columns)

    open_ = P(store._daily_panel(("open_qfq", "open"), fill="ffill"))
    close = P(store._daily_panel(("close_qfq", "close"), fill="ffill"))
    high = P(store._daily_panel(("high_qfq", "high"), fill="ffill"))
    low = P(store._daily_panel(("low_qfq", "low"), fill="ffill"))
    volume = P(store._daily_panel("volume", fill="zero"))
    turnover = P(store._daily_panel("turnover"))
    amount = P(store._daily_panel("amount"))
    fallback = volume * (open_ + close) / 2.0
    amount = amount.where(np.isfinite(amount) & (amount > 0.0), fallback)

    def RANK(x):
        return x.rank(axis=1, pct=True)

    def MA(x, n):
        return x.rolling(int(n), min_periods=int(n)).mean()

    def TS_MAX(x, n):
        return x.rolling(int(n), min_periods=int(n)).max()

    def TS_MIN(x, n):
        return x.rolling(int(n), min_periods=int(n)).min()

    def DELAY(x, n):
        return x.shift(int(n))

    def DIV(a, b):
        return a / b

    def ADD(a, b):
        return a + b

    def SUB(a, b):
        return a - b

    ns = dict(
        CLOSE=close, HIGH=high, LOW=low, VOLUME=volume, AMOUNT=amount, TURNOVER=turnover,
        RANK=RANK, MA=MA, TS_MAX=TS_MAX, TS_MIN=TS_MIN, DELAY=DELAY,
        DIV=DIV, ADD=ADD, SUB=SUB,
    )
    # CAL_* 目录字段：直接取腿库同源数组（消除 fill 口径差）
    ns["CAL_20D_AMT_STD"] = P(store._named_array("cal_20d_amt_std"))
    ns["CAL_20D_AMT_MA"] = P(store._named_array("cal_20d_amt_ma"))
    ns["CAL_10D_VOL_STD"] = P(store._named_array("cal_10d_vol_std"))
    ns["CAL_20D_VOL_STD"] = P(store._named_array("cal_20d_vol_std"))
    ns["CAL_10D_120D_TURNOVER_RATIO"] = P(store._named_array("cal_10d_120d_turnover_ratio"))
    return ns


def local_composite(raw_legs: dict, signed: dict) -> pd.DataFrame:
    comp = None
    for name, sign in signed.items():
        part = (float(sign) * raw_legs[name]).rank(axis=1, pct=True)
        comp = part if comp is None else comp + part
    return comp / float(len(signed))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    args = ap.parse_args()

    panels = pickle.load(PANELS.open("rb"))
    raw_legs = build_caltech_legs(panels)
    ns = build_ns(panels)

    ok = True
    for name, formula, direction in parse_candidates(Path(args.candidates)):
        signed = SIGNED[name]
        local = local_composite(raw_legs, signed)
        emu = eval(formula, {"__builtins__": {}}, ns)
        if not isinstance(emu, pd.DataFrame):
            emu = pd.DataFrame(emu)
        idx = local.index.intersection(emu.index)
        cols = local.columns.intersection(emu.columns)
        a = local.loc[idx, cols].to_numpy(dtype="float64")
        b = np.asarray(emu.loc[idx, cols], dtype="float64")
        corrs = []
        for i in range(a.shape[0]):
            x, y = a[i], b[i]
            m = np.isfinite(x) & np.isfinite(y)
            if int(m.sum()) < 50:
                continue
            xr = pd.Series(x[m]).rank().to_numpy()
            yr = pd.Series(y[m]).rank().to_numpy()
            corrs.append(float(np.corrcoef(xr, yr)[0, 1]))
        arr = np.asarray(corrs)
        verdict = "PASS" if arr.min() > 0.999 else "FAIL"
        if verdict == "FAIL":
            ok = False
        print(f"[{verdict}] {name}: rank-corr mean {arr.mean():.6f} min {arr.min():.6f} "
              f"(days {arr.size}, dir {direction})")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())