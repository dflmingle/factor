#!/usr/bin/env python3
"""验证"时间平滑"轴：对 0.5cm 网格 top 混权信号做因果滚动平均（步长=10 交易日网格），
看 IC/ICIR/win 能否从 ICIR~0.85 推到榜单目标 0.94~0.98。

输入：opp-halfcenter-20260928/bases.pkl（rank 面板缓存）+ alpha191-local-20260923/panels.pkl
输出：opp-halfcenter-20260928/smooth_probe.csv
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

COMBOS = [
    ("010LW", "amt60", "volV5y", 0.20),
    ("010LW", "amt60", "volV5y", 0.30),
    ("010LW", "intr40", "volV5y", 0.25),
    ("R03", "retrev5", "volV5y", 0.15),
    ("R03", "retrev5", "volV5y", 0.10),
    ("R03", "stdvol20_rel5y", "volV5y", 0.05),
    ("042", "retrev5", "volV5y", 0.20),
    ("042", "retrev20", "volT5y", 0.20),
    ("042", "intr20", "volT5y", 0.10),
]
TARGETS = {  # ic, icir, win
    "010LW": (0.1253, 0.980, 0.798),
    "R03": (0.0962, 0.944, 0.812),
    "042": (0.0957, 0.975, 0.773),
}
SPANS = [1, 2, 3, 5, 10]


def main() -> int:
    with (OUT / "bases.pkl").open("rb") as fh:
        cache = pickle.load(fh)
    base_rank = cache["base_rank"]
    lt_rank = cache["lt_rank"]
    grid = cache["grid"]
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    close = panels["close"]
    cal = close.index
    pos = {d: i for i, d in enumerate(cal)}

    rows = []
    for tag, bname, lname, w in COMBOS:
        v = w * base_rank[bname] + (1.0 - w) * lt_rank[lname]
        vg = v.reindex(grid)
        tic, tir, twn = TARGETS[tag]
        for k in SPANS:
            vs = vg.rolling(k, min_periods=k).mean() if k > 1 else vg
            panel = pd.DataFrame(np.nan, index=cal, columns=v.columns, dtype="float32")
            panel.loc[vs.index] = vs.astype("float32")
            st = ic_stats(rank_ic_series(panel, cal, grid, CYCLE, pos, close))
            d = abs(st["ic"] - tic) / 0.02 + abs(st["icir"] - tir) / 0.20 + abs(st["win"] - twn) / 0.06
            rows.append(dict(tag=tag, base=bname, lt=lname, w=w, span=k,
                             ic=st["ic"], icir=st["icir"], win=st["win"], s_i=st["s_i"], d=d))
            print(f"{tag:<6} {bname:<15} {lname:<8} w={w:.2f} span={k:<2} -> "
                  f"ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} "
                  f"s_i={st['s_i']:.4f} d={d:.3f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "smooth_probe.csv", index=False, encoding="utf-8-sig")
    print(f"\nwritten {OUT/'smooth_probe.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
