#!/usr/bin/env python3
"""慢变量腿探针：找单腿 ICIR >= 0.88 且 IC >= 0.09 的信号。

榜单头部 010_LW/R03/042 的平台 ICIR 0.94~0.98（本地等价 ~0.90~0.93），
2 腿混权与多腿集成都封顶 ~0.857。假设：需要"慢变量"腿（长窗稳定性/自相关）。
输出：opp-halfcenter-20260928/slowleg_probe.csv
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
    grid = [cal[i] for i in range(int(cal.searchsorted(pd.Timestamp("2021-09-29"), side="left")),
                                 int(cal.searchsorted(pd.Timestamp("2021-09-29"), side="left")) + 10 * 119, 10)]
    grid = [d for d in grid if d in pos][:119]

    C = close
    O, H, L, V, A, T = (panels[k] for k in ("open", "high", "low", "volume", "amount", "turnover"))
    ret1 = C.pct_change(fill_method=None)
    std5y_V = V.rolling(1250, min_periods=400).std()
    std5y_T = T.rolling(1250, min_periods=400).std()

    legs: dict[str, pd.DataFrame] = {}
    for k in (5, 10, 20, 40, 60, 120):
        legs[f"volV{k}"] = -(V.rolling(k).std() / std5y_V)
    for k in (20, 60, 120):
        legs[f"volT{k}"] = -(T.rolling(k).std() / std5y_T)
    for k in (5, 20, 60):
        legs[f"volret{k}"] = -ret1.rolling(k).std()
    for a, b in ((5, 252), (5, 504), (21, 504), (60, 504), (120, 504)):
        legs[f"relT{a}_{b}"] = -(T.rolling(a).mean() / T.rolling(b, min_periods=b // 2).mean())
    for k in (20, 60, 120):
        legs[f"amihud{k}"] = (ret1.abs() / A).rolling(k).mean()
    for k in (20, 60, 120):
        legs[f"intr{k}"] = -((C - O) / O).rolling(k).mean()
    # 半方差比：下跌波动 / 上涨波动
    dn = ret1.clip(upper=0).rolling(20).std()
    up = ret1.clip(lower=0).rolling(20).std()
    legs["semivar20"] = -(dn / up)
    # 收益自相关代理（acf-3y 家族）
    p1 = ret1 * ret1.shift(1)
    legs["acf_ret_756"] = -(p1.rolling(756, min_periods=400).mean() / ret1.rolling(756, min_periods=400).var())
    legs["acf_T_756"] = -((T * T.shift(1)).rolling(756, min_periods=400).mean()
                          / T.rolling(756, min_periods=400).var())
    # 上涨天数占比（胜率动量）
    legs["winrate60"] = (ret1 > 0).rolling(60).mean()
    legs["winrate250"] = (ret1 > 0).rolling(250, min_periods=100).mean()

    rows = []
    for name, df in legs.items():
        st = ic_stats(rank_ic_series(df, cal, grid, CYCLE, pos, close))
        rows.append(dict(name=name, ic=st["ic"], icir=st["icir"], win=st["win"], s_i=st["s_i"]))
        flag = " <<<" if (st["ic"] >= 0.09 and st["icir"] >= 0.88) else ""
        print(f"{name:<16} ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} s_i={st['s_i']:.4f}{flag}",
              flush=True)
    df = pd.DataFrame(rows).sort_values("icir", ascending=False)
    df.to_csv(OUT / "slowleg_probe.csv", index=False, encoding="utf-8-sig")
    print(f"\nwritten {OUT/'slowleg_probe.csv'}")
    top = df[(df.ic >= 0.09)].nlargest(5, "icir")
    print("\nIC>=0.09 top-5 ICIR:")
    print(top.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
