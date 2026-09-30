#!/usr/bin/env python3
"""volV5 精细化：k×基准窗口网格 + 与 relT5_504 / volV10 的混权。
输出：opp-halfcenter-20260928/volv5_probe.csv
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from opp_halfcenter_search_20260928 import ic_stats, rank_ic_series  # noqa: E402

OUT = ROOT / "research_reports/platform_alignment/opp-halfcenter-20260928"
PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
CYCLE = 10


def main() -> int:
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    close = panels["close"]
    cal = close.index
    pos = {d: i for i, d in enumerate(cal)}
    p0 = int(cal.searchsorted(pd.Timestamp("2021-09-29"), side="left"))
    grid = [cal[i] for i in range(p0, min(p0 + 10 * 119, len(cal)), 10)]

    V, T = panels["volume"], panels["turnover"]
    rows = []
    best = {}
    for k in (3, 4, 5, 6, 8):
        for den in (504, 756, 1250):
            leg = -(V.rolling(k).std() / V.rolling(den, min_periods=den // 2).std())
            st = ic_stats(rank_ic_series(leg, cal, grid, CYCLE, pos, close))
            name = f"volV{k}_{den}"
            best[name] = leg
            rows.append(dict(kind="single", name=name, ic=st["ic"], icir=st["icir"], win=st["win"], s_i=st["s_i"]))
            print(f"{name:<14} ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} s_i={st['s_i']:.4f}",
                  flush=True)

    relT = -(T.rolling(5).mean() / T.rolling(504, min_periods=252).mean())
    rk = {n: v.rank(axis=1, pct=True) for n, v in best.items()}
    relT_r = relT.rank(axis=1, pct=True)
    sign = {}
    for n, v in best.items():
        st = ic_stats(rank_ic_series(v, cal, grid, CYCLE, pos, close))
        sign[n] = 1.0 if st["mean"] >= 0 else -1.0
    v5 = rk["volV5_1250"] * sign["volV5_1250"]
    r5 = relT_r * (1.0 if True else 1.0)
    for w in (0.3, 0.4, 0.5, 0.6, 0.7):
        mix = w * v5 + (1 - w) * r5
        st = ic_stats(rank_ic_series(mix, cal, grid, CYCLE, pos, close))
        rows.append(dict(kind="mix_relT", name=f"volV5xrelT5_504@{w:.1f}", ic=st["ic"], icir=st["icir"],
                         win=st["win"], s_i=st["s_i"]))
        print(f"volV5 x relT5_504 w={w:.1f}  ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} "
              f"s_i={st['s_i']:.4f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "volv5_probe.csv", index=False, encoding="utf-8-sig")
    print(f"\nwritten {OUT/'volv5_probe.csv'}")
    print(df.sort_values("icir", ascending=False).head(8).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
