#!/usr/bin/env python3
"""用"GP 天花板测试"的同一把尺子（原始面板 top-decile 净额 + corr_size）评估 LEGMIX 复合腿。

口径对齐 alphaprobe_gp_tushare.AlignedNetExcessContext.score：
  label = close(t+1) -> close(t+1+cycle)；top decile 等权；基准 = 全 A 有效池等权；
  年化 = sum(excess)/years（years = periods*cycle/252）；往返成本 0.006 × 换手 × (252/cycle)。
零平台算力。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import legmix_next_mine_20260929 as L  # noqa: E402

CYCLE = 10
ROUND_TRIP = 0.006
OUTDIR = ROOT / "research_reports/platform_alignment/legmix-size-20261009"


def net_excess(values: pd.DataFrame, close: pd.DataFrame, cal, sched, idx) -> dict:
    exc, turns, gross_l, bench_l = [], [], [], []
    prev = None
    for date in sched:
        i = idx[date]
        if i + 1 + CYCLE >= len(cal):
            continue
        y = close.iloc[i + 1 + CYCLE].to_numpy("float64") / close.iloc[i + 1].to_numpy("float64") - 1.0
        x = values.iloc[i].to_numpy("float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        xv, yv = x[ok], y[ok]
        k = max(int(ok.sum() * 0.10), 1)
        order = np.argpartition(-xv, k - 1)[:k]
        gross = float(yv[order].mean())
        bench = float(yv.mean())
        exc.append(gross - bench)
        gross_l.append(gross)
        bench_l.append(bench)
        cur = set(np.flatnonzero(ok)[order].tolist())
        if prev is not None:
            turns.append(1.0 - len(cur & prev) / k)
        prev = cur
    periods = len(exc)
    years = periods * CYCLE / 252.0
    gross_ann = float(np.sum(exc)) / years
    turnover = float(np.mean(turns)) if turns else 0.0
    cost = turnover * (252.0 / CYCLE) * ROUND_TRIP
    return {"periods": periods, "gross_excess": gross_ann, "turnover": turnover,
            "annual_cost": cost, "net_excess": gross_ann - cost,
            "mean_per_period": float(np.mean(exc))}


def main() -> int:
    panels = pickle_load(L.PANELS)
    C = panels["close"]
    cap = panels["mcap"].astype("float32")
    cal = C.index
    idx = {d: i for i, d in enumerate(cal)}
    raw = L.build_raw_legs(panels)
    w5s = L.sched_of(cal, L.W5)
    legs, signs = {}, {}
    for name, df in raw.items():
        r = df.rank(axis=1, pct=True).astype("float32")
        s5 = L.ic_series(r, C, cal, w5s, idx)
        m = float(np.nanmean(s5)) if np.isfinite(s5).any() else 0.0
        sign = -1.0 if m < 0 else 1.0
        if sign < 0:
            r = -r
        signs[name] = sign
        legs[name] = r
    rows = []
    for spec_file in sorted(OUTDIR.glob("*_specs.json")):
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        last = spec["steps"][-1]
        names = last["legs"]
        comp = None
        for n in names:
            comp = legs[n] if comp is None else comp + legs[n]
        comp = (comp / len(names)).astype("float32")
        st = net_excess(comp, C, cal, w5s, idx)
        csz = L.corr_size(comp, w5s, idx, cap)
        t10 = L.turnover_top(comp, w5s, idx)
        rows.append(dict(tag=spec["tag"], legs="+".join(names), k=len(names),
                         net_excess=st["net_excess"], gross=st["gross_excess"],
                         gp_turnover=st["turnover"], legmix_turn10=t10, corr_size=csz,
                         periods=st["periods"], lam_size=spec.get("lam_size")))
    df = pd.DataFrame(rows).sort_values("net_excess", ascending=False)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTDIR / "evaluation.csv", index=False, encoding="utf-8-sig")
    print(df.to_string(index=False))
    return 0


def pickle_load(path: Path):
    import pickle
    return pickle.load(path.open("rb"))


if __name__ == "__main__":
    raise SystemExit(main())
