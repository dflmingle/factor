"""换席/加席的池级边际（月度 T* 口径，2026-09-26 夜，零平台算力）。

口径来源：competition_rules.md（Rex_ann 用**扣费后**日收益；rawC 的三个输入都是**当月**量）
+ nc-turn-20260924（T* = Rex·SR·(1-1.2DD)/0.6；地板 0.30；调仓次数 46/7/7 个月）。

与 09-24 桥表的差别（两处都会翻转结论）：
  1. Rex 用**净超额**（扣 0.30% 单边、买卖各一次），不是 run 详情里的毛值 excessAnnualized；
  2. DD 用**月度**尺度（基线 4.59%），全期 DD 只用来做**相对**缩放。
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
OUT = ROOT / "research_reports/platform_alignment/swap-size-20260926"
COST = 0.003 * 2 * 252 / 10          # 单边 0.30%、买卖各一次、年化
DD_MONTH_BASE = 0.0459               # 五席池月度日频 MaxDD 中位（GOAL 第 10 条）
KS = {1: 7, 2: 46, 3: 7}             # 2021-09~2026-08 的 60 个月调仓次数分布
SI = {"size_only": 0.009136, "impact60": 0.017983, "t10_size_plus_impact_bm": 0.059267,
      "book_to_market_lf_minus_size": 0.021011, "book_to_market_lf_plus_impact": 0.022068}
CAND = {"AGG": 0.045278, "G13": 0.043116, "DOWNSIDE": 0.046256, "WC": 0.048009}

BASE = dict(name="base5", gross=0.2232, turn=0.1339, sr=1.0648, dd5=0.3164,
            seats=dict(SI))
RUNS = [
    dict(name="AGG-add6 (09-24)", gross=0.2257, turn=0.1626, sr=1.0626, dd5=0.3184,
         seats=dict(SI, **{"AGG": CAND["AGG"]})),
    dict(name="AGG-swapSIZE (09-26)", gross=0.2207, turn=0.1754, sr=1.0710, dd5=0.2997,
         seats={k: v for k, v in SI.items() if k != "size_only"} | {"AGG": CAND["AGG"]}),
    dict(name="DOWNSIDE-swapSIZE (09-26)", gross=0.2195, turn=0.1768, sr=1.0675, dd5=0.2996,
         seats={k: v for k, v in SI.items() if k != "size_only"} | {"DOWNSIDE": CAND["DOWNSIDE"]}),
]


def pool_cfg(spec):
    net = spec["gross"] - spec["turn"] * COST
    dd_m = DD_MONTH_BASE * (spec["dd5"] / BASE["dd5"])
    t_star = max(net, 0.0) * spec["sr"] * (1 - 1.2 * dd_m) / 0.6
    nc = {k: min(1.0, t_star / max(k * spec["turn"], 0.30)) for k in KS}
    exp_nc = sum(KS[k] * nc[k] for k in KS) / sum(KS.values())
    raw_a = float(np.mean(list(spec["seats"].values())))
    return dict(name=spec["name"], net=net, turn=spec["turn"], sr=spec["sr"], dd_month=dd_m,
                t_star=t_star, nc1=nc[1], nc2=nc[2], nc3=nc[3], nc_exp=exp_nc,
                raw_a=raw_a, na=min(raw_a / 0.08, 0.70), n_seats=len(spec["seats"]))


base = pool_cfg(BASE)
rows = [base]
for spec in RUNS:
    rows.append(pool_cfg(spec))
df = pd.DataFrame(rows)

print(f"{'配置':<28}{'净额':>8}{'换手/次':>9}{'T*':>7}{'NC2':>7}{'NC3':>7}{'E[NC]':>7}{'na':>8}")
for _, r in df.iterrows():
    print(f"{r['name']:<28}{r['net']:>8.2%}{r['turn']:>9.2%}{r['t_star']:>7.3f}"
          f"{r['nc2']:>7.3f}{r['nc3']:>7.3f}{r['nc_exp']:>7.3f}{r['na']:>8.4f}")
print()

out = []
for i in range(1, len(df)):
    r = df.iloc[i]
    d_raw_a = r["raw_a"] - base["raw_a"]
    d_na = (r["na"] - base["na"]) if base["na"] < 0.70 else 0.0
    d_nc = r["nc_exp"] - base["nc_exp"]
    pts_a = 44000 * 0.20 * d_na
    pts_b = 44000 * 0.35 * (d_raw_a / 0.06)
    pts_c = 44000 * 0.45 * d_nc
    out.append(dict(scenario=r["name"], d_raw_a=d_raw_a, d_na=d_na, d_nc=d_nc,
                    points_A=pts_a, points_B=pts_b, points_C=pts_c,
                    points_total_no_B=pts_a + pts_c, points_total=pts_a + pts_b + pts_c))
    print(f"{r['name']:<28} Δraw_a {d_raw_a:+.5f} | Δna {d_na:+.4f} | ΔE[NC] {d_nc:+.4f} "
          f"| A {pts_a:+7.0f} | B {pts_b:+8.0f} | C {pts_c:+7.0f} | 合计 {pts_a+pts_b+pts_c:+8.0f}")

OUT.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT / "pool_cfg.csv", index=False)
pd.DataFrame(out).to_csv(OUT / "marginals.csv", index=False)
print("\nwritten:", OUT)
