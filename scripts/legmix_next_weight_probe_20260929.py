#!/usr/bin/env python3
"""慢腿加权探测：对候选复合，把自身低换手腿的权重提到 2 倍，测 s_i/turn10。"""
from __future__ import annotations
import json, pickle, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legmix_next_legs_20260929 import build_raw_legs
from legmix_next_mine_20260929 import ic_series, stats, turnover_top, sched_of, W5

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/legmix-next-20260929"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"

CAND = [("lam000", 6), ("lam000", 7), ("lam000", 8), ("lam010", 5),
        ("lam020", 5), ("lam020", 6), ("lam040", 6), ("lam010_seed7", 9), ("legmix7cal", 7)]

def main() -> int:
    panels = pickle.load(PANELS.open("rb"))
    C = panels["close"]; cal = C.index
    idx = {d: i for i, d in enumerate(cal)}
    w5s = sched_of(cal, W5)
    signs = json.loads((OUT / "leg_signs.json").read_text())
    raw = build_raw_legs(panels)
    legs, turn_of = {}, {}
    for name, df in raw.items():
        r = df.rank(axis=1, pct=True).astype("float32") * float(signs[name])
        legs[name] = r
        turn_of[name] = turnover_top(r, w5s, idx)
    rows = []
    for tag, k in CAND:
        d = json.loads((OUT / f"{tag}_specs.json").read_text())
        step = next(s for s in d["steps"] if s["k"] == k)
        names = step["legs"]
        for mode, thr in [("w1", None), ("w2_lt25", 0.25), ("w2_lt35", 0.35), ("w3_lt25", 0.25)]:
            comp, wsum = None, 0.0
            for n in names:
                w = 1.0
                if thr and turn_of[n] < thr:
                    w = float(mode.split("_")[0][1:])
                wsum += w
                v = legs[n] * w
                comp = v if comp is None else comp + v
            comp = (comp / wsum).astype("float32")
            st = stats(ic_series(comp, C, cal, w5s, idx))
            rows.append(dict(cand=f"{tag}K{k}", mode=mode, s_i=st["s_i"], icir=st["icir"],
                             ic=st["ic"], win=st["win"], turn10=turnover_top(comp, w5s, idx)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "weight_probe.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print(df.round(4).to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
