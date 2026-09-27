from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/GOAL.md")
text = p.read_text(encoding="utf-8")

# 1) credit ledger rows
anchor = "| 2026-09-25 | round7：单字段探针 ×2（RATIO_BM_LYR 2.0 / CAL_30D_PRICE_VOL_CORR 2.0；含一次卡死未计费） | 4 | 1676.12 |"
rows = anchor + "\n".join([
    "",
    "| 2026-09-25/26 | 第八轮全跑 5 条 + K021/K024 补强 + A/B 池级模拟（22 + 0 本地） | 22 | 1654.12 |",
    "| 2026-09-26 | 放宽换手档 T2/T4 六席池实测：T2 成功 4.0；T4 三次平台故障（status=8 零节点 ×2 未计费、一次白付 6.0） | 10 | 1654.12 |",
    "| 2026-09-26 | （收到 10 算力礼包，余额 1654.12 起算；T2+T4 实付 10.0 后仍为 1654.12） | — | 1654.12 |",
])
assert anchor in text
text = text.replace(anchor, rows, 1)

# 2) new structure constraint item 25
item24_tail = "   - 结论：**该池子当前的改进空间在\"换席\"而非\"加席\"**；且按 09-24 决议，换池应等 10 月首份官方月度快照后再执行。\n"
item25 = item24_tail + """
25. **放宽换手假设被平台证伪（2026-09-26，10 算力）——T2 作第 6 席在平台端为负，本地逐月机器连符号都错**：
   - 本地逐月官方口径重算给 T2 加席 **+482（local）/ +655（uplifted）分/月**（A 项 +489/+662、C 项 −7），
     两条候选 T2/T4 由用户批准上平台 6 席实测（8 算力）。
   - **平台实测（run `6ab75e8f…`）**：毛超额 22.32%→**20.58%**、净 20.30%→**17.93%（−2.37pp）**、
     每次调仓换手 13.39%→**17.50%**；Sharpe 1.0648→1.1509、全期 MaxDD 31.64%→26.28% 是仅有的改善。
   - **A 侧反号**：池级 `RankIC×IC_IR×P(IC>0.02)` 0.02392→0.02147（RankIC 0.0919→0.0893、
     胜率 70.83%→63.87%）→ **ΔNA = −0.031（−269 分/月）**。本地 A 项假设"池 rawA 上移 (s6−rawA)/6"是错的：
     候选自己的 `s_i_rank` 高 ≠ 池级 IC 改善。
   - **C 侧为负**：换手从 13.39% 抬到 17.50% 使 2 调仓月 T 由 0.268（地板下）升到 0.35（地板上），
     rawC 分母惩罚 ×0.857；全期 DD 代理桥 ΔNC = −0.104（−2,060 分/月）。
     月度口径复核（平台每期净值→自然月）：月均超额 1.24%→1.16%、中位 1.37%→1.23%、负月同为 15/60、
     T2 占优 28/60 —— **本地"逐月 T\\* 抬得动"没有平台证据**。
   - 合计（不含 NB）≈ **−2,330 分/月** vs 本地 +482 → 失败登记表第 13 条
     `platform_pool_tests_20260926:pool6-t2t4-v2:POOL6-T2V2-20260926`；与 09-24 AGG 对靶同向
     （本地 +666 vs 平台可归因 A+C ≈ −254），**本地逐月机器仍系统性高估候选边际**。
   - **T4 未取得可用结果**（status=8 零节点 ×2 未计费 + 一次「获取运行详情失败」白付 6.0）。
     本地预估 A +254/+381、C −106，机制与 T2 同构 → 建议不再花算力。
   - **新规则**：候选边际评估必须同时给「池级 IC 代理」与「加席后是否跨过 0.30 换手地板」，
     单看候选自身 `s_i_rank` + 逐月 C 会给出反号结论；`换手放宽到 30-40%` 档按证伪处理。
"""
assert item24_tail in text
text = text.replace(item24_tail, item25, 1)

# 3) lever table wording
old_lever = "| NA 0.239 → 0.70 | +4,048 分/月 | 需要**新信号族**：高 IC（换手放宽到 ≤30%/次，见 §6.2） |"
new_lever = ("| NA 0.239 → 0.70 | +4,048 分/月 | 需要**新信号族**：高 IC（换手须 **≤30%/次**；"
             "30–40% 档已于 2026-09-26 被平台证伪，见第 25 条） |")
assert old_lever in text
text = text.replace(old_lever, new_lever, 1)

p.write_text(text, encoding="utf-8")
print("GOAL.md updated")