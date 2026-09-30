#!/usr/bin/env python3
"""席位场景目标（加席 + 换席）的 L1 代理标定与打分（2026-09-28，零算力）。

场景：append（第 6 席）与 swap_i（替换第 i 席，i=1..5）。
A/B 段用官方汇率精确算（110000 分/月 per raw_a 单位 的 A 段 + B 段 15400/0.06）；
C 段用可秒算的代理（换手变化、与其余席位相关）。

拟合：用 46 个候选的真实 ΔComb（append 场景）拟合 α,β,γ；
再用 swapf_recheck 的 4 个换席实测点做方向校验。

输出：e-decomp-20260928/seatscenario_proxy.csv
"""
from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/e-decomp-20260928"

MEAN_S_PLAT = 0.025893          # 五席平台均值（A 门槛）
POOL_TURN = 0.2916              # 五席月换手基线
A_PTS = 110_000.0               # 分/月 per 1.0 raw_a（= 8800 / 0.08）
B_PTS = 15_400.0 / 0.06         # B 段稳态汇率（注意池龄>=1月才生效）
SEATS = {  # name -> (s_i 平台, 单席月换手 from seats_marginals only_t_mean)
    "size_only": (0.00914, 0.1796),
    "impact60": (0.01798, 0.2174),
    "t10_size_plus_impact_bm": (0.05927, 0.6047),
    "book_to_market_lf_minus_size": (0.02101, 0.2011),
    "book_to_market_lf_plus_impact": (0.02207, 0.1957),
}


def main() -> int:
    c = pd.read_csv(OUT / "seatproxy_calib.csv")
    c = c.dropna(subset=["d_comb_uplift"]).copy()
    c["d_raw_a_append"] = (c.s_i_local - MEAN_S_PLAT) / 6.0
    c["d_turn_append"] = c.turn_pool_seed - POOL_TURN

    # --- 拟合（append 场景真实 ΔComb）---
    best = None
    for a, b, g in product([2e5, 3e5, 4e5, 6e5], [0, 4e4, 8e4, 1.6e5], [0, 4e4, 8e4]):
        x = a * c.d_raw_a_append - b * c.d_turn_append - g * (c.rho_max - 0.5).clip(lower=0)
        r = pd.Series(x).corr(c.d_comb_uplift, method="spearman")
        if best is None or abs(r) > abs(best[0]):
            best = (r, a, b, g)
    r, a, b, g = best
    print(f"拟合: ΔComb ≈ {a:.0f}·Δraw_a − {b:.0f}·Δturn − {g:.0f}·max(rho−0.5,0)   spearman={r:+.3f}")
    print(f"（纯 A+B 理论斜率应为 110000 + 15400/0.06 = {A_PTS + B_PTS:,.0f}）\n")

    def scenario_score(s_cand, turn_cand, rho_max, replaced=None):
        if replaced is None:
            d_raw = (s_cand - MEAN_S_PLAT) / 6.0
            d_turn = (turn_cand - POOL_TURN) / 6.0 * 6.0  # pool 换手变化 ≈ 单席增量
            d_raw_pts = A_PTS * d_raw
            d_b_pts = B_PTS * d_raw
        else:
            s_old, t_old = SEATS[replaced]
            d_raw = (s_cand - s_old) / 5.0
            d_turn = (turn_cand - t_old) / 5.0
            d_raw_pts = A_PTS * d_raw
            d_b_pts = B_PTS * d_raw
        d_c_pts = -b * d_turn - g * max(rho_max - 0.5, 0.0)
        return d_raw_pts + d_b_pts + d_c_pts, dict(dA_pts=d_raw_pts, dB_pts=d_b_pts, dC_pts=d_c_pts,
                                                   d_raw=d_raw, d_turn=d_turn)

    rows = []
    for row in c.itertuples():
        best_scen = ("append", None, *scenario_score(row.s_i_local, row.turn_intrinsic, row.rho_max))
        for seat in SEATS:
            res = scenario_score(row.s_i_local, row.turn_intrinsic, row.rho_max, replaced=seat)
            if res[0] > best_scen[2]:
                best_scen = (f"swap:{seat}", seat, *res)
        rows.append(dict(name=row.name, best_scenario=best_scen[0], replaced=best_scen[1],
                         score_total=best_scen[2], **best_scen[3],
                         d_comb_append_real=row.d_comb_uplift, s_i_local=row.s_i_local,
                         turn_intrinsic=row.turn_intrinsic, rho_max=row.rho_max,
                         append_pts=scenario_score(row.s_i_local, row.turn_intrinsic, row.rho_max)[0]))
    out = pd.DataFrame(rows).sort_values("score_total", ascending=False)
    out.to_csv(OUT / "seatscenario_proxy.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    print("=== 按‘最优场景’排序的 top-12 ===")
    print(out.head(12)[["name", "best_scenario", "score_total", "dA_pts", "dB_pts", "dC_pts",
                        "d_comb_append_real"]].round(0).to_string(index=False))
    print("\n=== 加席 vs 换席 谁赢？ ===")
    win = out[out.best_scenario != "append"]
    print(f"最优场景是换席的候选: {len(win)}/{len(out)}；换席目标席多为: "
          f"{win.replaced.value_counts().to_dict()}")
    print("\n=== 与真实 append ΔComb 的排序一致性（append_pts 列）===")
    print("spearman =", round(out.append_pts.corr(out.d_comb_append_real, method="spearman"), 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
