import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
P4 = ROOT / "research_reports/platform_alignment/pending4-eval-20260926/summary.md"
GOAL = ROOT / "GOAL.md"
AB = ROOT / "research_reports/platform_alignment/ab-batch-20260925/summary.md"

CORRECTION = """
## 〇、重要更正（2026-09-26 提交前核对发现）

**这 4 条候选在 2026-09-24 就已经上过平台，不是"待批"。** 本目录在开工时把交接单
`HANDOFF_20260924` §4 的"未决事项"读成了"从未验证"——那一条实际问的是"**怎么处置这组已测结果**"，
不是"要不要测"。证据：

- `platform_pool_tests_20260924/summary.md`：四个 6 席池全部实测成功，run ID
  `6ab4d772…`/`6ab4d7f1…`/`6ab4d866…`/`6ab4d8e4…`，各扣 4 算力，共 **16 算力**，余额 1752.12；
- `platform_pool_tests_20260924/{agg,g13,downside,wc}.run.json`（2026-09-24 20:55 落盘）含完整指标；
- `GOAL.md` 预算表第 12 行与 §四 第 145–147 行均已登记。

**平台实测结果（加第 6 席口径，5 席 + 候选）**：

| 候选 | 6 席净额 | Δ净额 | 池换手/次 | ΔNA | ΔNB | ΔNC | Δ积分/月 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AGG | 22.57% | +2.27pp | 16.26% | +1.96% | +2.62% | −2.16% | **+148.8** |
| G13 | 22.61% | +2.31pp | 16.26% | +1.77% | +2.36% | −1.88% | +148.3 |
| DOWNSIDE | 22.60% | +2.30pp | 16.36% | +2.03% | +2.71% | −2.46% | +108.7 |
| WC | 21.99% | +1.69pp | 16.80% | +2.31% | +3.09% | −7.39% | −783.3 |

→ **再提交一次就是纯重复花费。本目录不构成任何新的算力申请。**

## 〇之二、真正的产出：本地 ΔComb 有两个系统性偏负（重要）

把本目录的本地结果与上面的平台实测对照，暴露出本地模拟的两处口径缺口——这解释了为什么
本地说"加席四条全负"而平台说"三条为正"：

1. **本地少了 NB 项**。平台 `Comb = 0.20·NA + 0.35·NB + 0.45·NC`（用平台基线
   `NA 0.2390 / NB 0.3187 / NC 0.7449 / Comb 0.4945` 反解验证）。AGG 转正的主因正是
   **ΔNB +2.62% × 0.35 = +0.0092**，而本目录与 A/B 批次都只算 `0.20·NA + 0.45·NC`。
2. **本地 NC 用了全期 MaxDD**，平台 C 分项用的是**当月日频 MaxDD**（283 池中位 4.15%，
   本池月度中位 4.59%）。`seat-rescreen-20260924` 已记录：把全期 DD 当成月度 DD 会把
   t10 族的边际从 +291~+476 分/月压成 −1,400~−2,600 分/月。

**影响范围**：本目录与 `ab-batch-20260925`（A 组/B 组）的所有 ΔComb 数值**只能用于排序，
不能当作与平台桥可比的绝对分**。凡是"加席"类结论都应带上这条折扣；
`ab-batch-20260925/summary.md` 的 A 组"全负"尤其不能被理解为"平台实测也为负"。

## 〇之三、仍然真正未测过的：换席版本

2026-09-24 测的是**加第 6 席**（5 席 + 候选）。本目录 §二 的 **`swap-T10-ADD-BM`**
（5 席 − T10-ADD-BM + 候选）是**另一个池组合，从未上过平台**。若以后要花算力，
这是唯一非重复的实验；但 09-24 的既有决议是"等 10 月首份官方月度快照核对月度 MaxDD/NC 后再执行换池"，
本目录不建议现在提交。

"""

text = P4.read_text(encoding="utf-8")
if "重要更正" not in text:
    head, sep, rest = text.partition("## 一、单因子对比")
    text = head + CORRECTION.lstrip("\n") + sep + rest
    P4.write_text(text, encoding="utf-8")
    print("pending4 summary corrected")
else:
    print("pending4 summary already corrected")

old_title = '24. **待批 4 条候选（AGG/G13/DOWNSIDE/WC）池级复核（2026-09-26，零算力）——唯一正场景是"换掉 T10-ADD-BM"**：'
new_title = '24. **AGG/G13/DOWNSIDE/WC 池级复核（2026-09-26，零算力）+【更正】它们 09-24 已测过 + 本地 ΔComb 有系统性偏负**：'
assert old_title in GOAL.read_text(encoding="utf-8")
goal = GOAL.read_text(encoding="utf-8")
goal = goal.replace(old_title, new_title, 1)

old_tail = """   - 结论：**该池子当前的改进空间在"换席"而非"加席"**；待用户批准 AGG（4 算力）是否上平台做 6 席池实测。
"""
new_tail = """   - **【更正】这 4 条 09-24 就已上过平台（16 算力，run `6ab4d772…` 等），不是"待批"**——交接单 §4 问的是"怎么处置已测结果"，
     被读成了"从未验证"。已有实测（加第 6 席）：AGG +148.8 / G13 +148.3 / DOWNSIDE +108.7 / WC −783.3 分/月。
     **不得重复提交**。真的未测过的只有"换席"版本（5 席 − T10-ADD-BM + 候选）。
   - **【新规则】本地 ΔComb 两处系统性偏负，只能排序不能当绝对分**：①缺 NB 项（平台权重 0.35，
     AGG 转正主因就是 ΔNB +2.62%）；②本地 NC 用**全期 MaxDD**，平台 C 用**当月日频 MaxDD**。
     影响 `ab-batch-20260925` 与本批的全部 ΔComb 数字；"加席类全负"不能读成"平台实测也为负"。
   - 结论：**该池子当前的改进空间在"换席"而非"加席"**；且按 09-24 决议，换池应等 10 月首份官方月度快照后再执行。
"""
assert old_tail in goal
goal = goal.replace(old_tail, new_tail, 1)
GOAL.write_text(goal, encoding="utf-8")
print("GOAL item 24 amended")

ab = AB.read_text(encoding="utf-8")
old_note = "- 评分形状：`Comb = 0.20·NA + 0.45·NC`（本批只用可本地测量的两项）；`Δ分/月 = 44000 × ΔComb`；"
new_note = (old_note + "\n"
            "  > ⚠️ **本批 ΔComb 只可用于排序，不是可与平台桥比较的绝对分**（2026-09-26 补充）："
            "平台 `Comb = 0.20·NA + 0.35·NB + 0.45·NC`，本批**缺 NB 项**；且本批 NC 用**全期 MaxDD**，"
            "平台 C 分项用**当月日频 MaxDD**。两处都让本批ΔComb系统性偏负。"
            "证据：AGG 加第 6 席本地 −3,193 分/月，平台实测 09-24 为 **+148.8 分/月**（符号相反）。")
assert old_note in ab
ab = ab.replace(old_note, new_note, 1)
AB.write_text(ab, encoding="utf-8")
print("ab-batch summary caveat added")