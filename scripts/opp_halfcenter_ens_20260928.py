#!/usr/bin/env python3
"""多腿集成探针：2 腿混权封顶 ICIR 0.856，测 k>2 腿是否能把 ICIR 抬向榜单口径。

复用 opp-halfcenter-20260928/bases.pkl 的 rank 面板缓存。
输出：opp-halfcenter-20260928/ens_probe.csv
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
FIVE_LT = ["volV5y", "volT5y", "rel_T5_T252", "rel_T21_T504", "lvl1mT"]
ALL_LT = FIVE_LT + ["volret", "rel_T21_T252", "lvl1mT21"]


def mean_panel(ranks: dict, names: list) -> pd.DataFrame:
    acc = None
    for n in names:
        v = ranks[n]
        acc = v.copy() if acc is None else acc + v
    return acc / float(len(names))


def main() -> int:
    with (OUT / "bases.pkl").open("rb") as fh:
        cache = pickle.load(fh)
    br, lr, grid = cache["base_rank"], cache["lt_rank"], cache["grid"]
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    close = panels["close"]
    cal = close.index
    pos = {d: i for i, d in enumerate(cal)}

    mixed_lt = {k: mean_panel(lr, v) for k, v in {
        "LT3": ["volV5y", "volT5y", "rel_T5_T252"],
        "LT5": FIVE_LT,
        "LT8": ALL_LT,
        "LT_volpair": ["volV5y", "volT5y"],
    }.items()}
    mixed_base = {k: mean_panel(br, v) for k, v in {
        "BASE_rev": ["retrev5", "retrev20", "pvcorr20"],
        "BASE_intr": ["intr40", "intr60", "amt60", "amihud20"],
        "BASE_042mix": ["042_ref", "retrev5", "amt60"],
        "BASE_r5i20": ["retrev5", "intr20"],
    }.items()}

    cases = []
    for lt in ["LT3", "LT5", "LT8", "LT_volpair"]:
        for w in (0.15, 0.25, 0.35):
            cases.append((f"retrev5|{lt}|{w}", [(br["retrev5"], w), (mixed_lt[lt], 1 - w)]))
    for b in ["BASE_rev", "BASE_intr", "BASE_042mix", "BASE_r5i20"]:
        for lt in ["volV5y", "LT3"]:
            cases.append((f"{b}|{lt}|0.30", [(mixed_base[b], 0.30), (lr[lt] if lt in lr else mixed_lt[lt], 0.70)]))
    combos5 = [("retrev5", "volV5y", 0.20), ("intr40", "rel_T5_T252", 0.60), ("amt60", "rel_T5_T252", 0.30)]
    cases.append(("combo5mean", [(br[b] * w + lr[l] * (1 - w), 1 / 3) for b, l, w in combos5]))

    rows = []
    for name, legs in cases:
        v = None
        for panel, w in legs:
            v = (panel * w) if v is None else (v + panel * w)
        st = ic_stats(rank_ic_series(v, cal, grid, CYCLE, pos, close))
        rows.append(dict(name=name, ic=st["ic"], icir=st["icir"], win=st["win"], s_i=st["s_i"]))
        print(f"{name:<26} ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} s_i={st['s_i']:.4f}",
              flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "ens_probe.csv", index=False, encoding="utf-8-sig")
    print(f"\nwritten {OUT/'ens_probe.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
