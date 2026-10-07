# -*- coding: utf-8 -*-
"""B 钟表账：换席打断样本外时钟的一次性分数成本 vs A/C 月增益（2026-10-05，零平台算力）。

模型（GOAL 第 57 条，零算力反解）：
  * nb 点亮门槛 den_b >= 4；den_b = 已进入样本外的席位数；每席需 N 个调仓周期。
  * 换掉 k 席后：保留席按原入池日到点，新席按换席日到点。
      k <= 1  -> den_b = 4  >= 4 -> 点亮时点不变，B 无损失
      k >= 2  -> den_b = 5-k < 4 -> 点亮推迟，延迟天数 = 换席日 - 入池日（与 N 无关）
  * 我方入池 2026-09-24，换席窗口 2026-11-01 => 延迟 38 天。
  * 延迟期内的损失 = nb_inf * 15400 分/月 * 延迟天数/30.4，一次性。

ΔA/ΔC 全部来自本地整池账（platform-measured s_i 的 A 段 + e_decomp 官方月度账本的 C 段），
见 pool-family-20261004 / pool-variants-20261005 / bclock-ledger-20261005 的 pool_summary.csv。
"""
from __future__ import annotations

import pandas as pd

POOL_START, SWAP_DATE = "2026-09-24", "2026-11-01"
A_UNIT, NB_UNIT, MONTH_DAYS, SEASON_MONTHS = 8800.0, 15400.0, 30.4, 10  # 2026-11..2027-08
DELAY = (pd.Timestamp(SWAP_DATE) - pd.Timestamp(POOL_START)).days

# name: (席数, 保留的现役席位数, ΔA 分/月, ΔC 分/月, 备注)
SCEN = [
    ("hold 不动",                    5, 5,     0.0,     0.0, "基准"),
    ("swap1 -F +K10",                5, 4,   995.1,  -218.8, "第 45/48 条平台确认；den_b 5->4 仍在门槛"),
    ("swap4 = L6",                   5, 1,  3311.8, -1340.2, "第 53 条主候选；den_b 5->1"),
    ("add1 keep5 +K10",              6, 5,   759.1,  +281.2, "第 43 条平台确认 ΔA +759；B 无损失"),
    ("add4 keep5 +K10K20STD20AMT",   9, 5,  1498.8,  -382.0, "B 无损失，size 检查变好"),
    ("S1 keep4(-size) +4席",         8, 4,  1916.6,  -616.9, "B 安全边界解"),
    ("S3 keep4(-impact) +5席",       9, 4,  2024.6,  -626.9, "B 安全边界最优"),
    ("S2 keep4(-size) +5席",         9, 4,  2132.7,  -997.4, "A 更高但 C 更贵"),
]


def main():
    rows = []
    for nb in (0.0, 0.27, 0.43, 0.67, 1.00):
        for name, nseat, kept, dA, dC, note in SCEN:
            delay = 0.0 if kept >= 4 else DELAY
            dB = -nb * NB_UNIT * delay / MONTH_DAYS
            rows.append(dict(nb_inf=nb, scen=name, seats=nseat, kept_old=kept, dA=dA, dC=dC,
                             dAC_per_month=dA + dC, delay_days=delay, dB_oneoff=round(dB, 1),
                             season_total=round(SEASON_MONTHS * (dA + dC) + dB, 1), note=note))
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(df.to_string(index=False))
    out = "research_reports/platform_alignment/bclock-ledger-20261005/bclock_ledger.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print("\nsaved", out)

    print("\n[盈亏平衡 nb_inf]  L6 要优于各 B 安全方案所需的最大 nb_inf")
    l6_season = SEASON_MONTHS * (3311.8 - 1340.2)
    for name, nseat, kept, dA, dC, note in SCEN:
        if name.startswith(("swap1", "hold")):
            continue
        other = SEASON_MONTHS * (dA + dC)
        be = (l6_season - other) / (NB_UNIT * DELAY / MONTH_DAYS)
        print("  vs %-30s season=%7.0f  平衡点 nb_inf = %+.2f" % (name, other, be))
    print("\n  参考：点亮池 raw_b 分布 -> nb_inf：p25 %.2f / 中位 %.2f / p75 %.2f / p90 %.2f" % (
        0.0072 / 0.06, 0.0161 / 0.06, 0.0334 / 0.06, 0.0498 / 0.06))


if __name__ == "__main__":
    main()