# -*- coding: utf-8 -*-
"""平台公式仿真校验（2026-10-03，行为金融 2 条，零算力）。

把 candidates.txt 里的平台公式用 pandas 语义仿真，与本地腿/复合（behavioral_legs_20261003）
逐期截面秩相关对照，确认转写无误（承袭 _alphagen_formula_verify_20261002 的流程）。

用法：
  python scripts/_behavioral_formula_verify_20261003.py <candidates.txt>
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from behavioral_legs_20261003 import build_behavioral_legs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"

SIGNED = {
    "BHV-LIMITUP20-20261003": {"limitup20": 1.0},
    "BHV-LU-CGO-ONID-20261003": {"limitup20": 1.0, "cgo500": -1.0, "on_minus_id": 1.0},
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
    close = panels["close"].astype("float64")
    open_ = panels["open"].astype("float64")
    volume = panels["volume"].astype("float64")
    amount = panels["amount"].astype("float64")
    turnover = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float64")

    def RANK(x):
        return x.rank(axis=1, pct=True)

    def MA(x, n):
        return x.rolling(int(n)).mean()

    def RETURNS(x, n):
        return x / x.shift(int(n)) - 1.0

    def COUNT(x, n):
        return x.astype("float64").rolling(int(n)).sum()

    def SUM(x, n):
        return x.rolling(int(n)).sum()

    def DELAY(x, n):
        return x.shift(int(n))

    return dict(CLOSE=close, OPEN=open_, VOLUME=volume, AMOUNT=amount, TURNOVER=turnover,
                RANK=RANK, MA=MA, RETURNS=RETURNS, COUNT=COUNT, SUM=SUM, DELAY=DELAY, ABS=abs)


def local_composite(raw_legs: dict, signed: dict) -> pd.DataFrame:
    comp = None
    for name, sign in signed.items():
        part = (float(sign) * raw_legs[name]).rank(axis=1, pct=True)
        comp = part if comp is None else comp + part
    return (comp / float(len(signed)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    args = ap.parse_args()

    panels = pickle.load(PANELS.open("rb"))
    raw_legs = build_behavioral_legs(panels)
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