import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
GP = ROOT / "research_reports/platform_alignment/gp-platform-tests-20260925/summary.md"
GOAL = ROOT / "GOAL.md"
AB = ROOT / "research_reports/platform_alignment/ab-batch-20260925/summary.md"
DESK = Path(r"C:\Users\58302\Desktop\池级进池评估-20260926.md")

SECTION16 = """

## 十六、A/B 批次：池级 ΔComb 全跑（2026-09-25/26，零平台算力）——A 组三条均不进池，B 组仅 K024c 转正

用户批准「全跑」A/B 两批。完整报告：`research_reports/platform_alignment/ab-batch-20260925/summary.md`。
批次定义：**A 组**=3 条已过平台验证的候选（K008 / K021 / K015）跑池级 ΔComb；**B 组**=K020 消解版与 K024 补强轮，
允许与已验证因子复合。

**前置（本批唯一口径变化）**：`pool-screen-20260921-qualitygate3/signals.pkl` 与
`pool-extended-search-20260922/built_signals.pkl` 本机缺失（`.gitignore` 忽略 `*.pkl`，交接单列为需直拷）。
只重建了需要的部分（现役 5 席面板 + signal frame + 前向收益，`scripts/ab_seat_rebuild_20260925.py`），
产物是新文件 `seat_panels_rebuilt.pkl`，provenance 记在 `run_provenance.json`。
**验证**：5 席 RankIC 与对齐报告里的既有本地值逐位吻合（4 位小数）；重建池净 20.70% / 换手 13.93% / SR 1.0427，
对照平台池记录 `F-P260922-08`（20.30% / 13.39% / 1.0648）净额差 **+0.36pp**，验收通过。

| 候选 | 场景 | ΔComb | Δ分/月 | 纯收益侧 Δ分/月 | 与席位最高相关 | 判定 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| K008/cand0000 | add-6th | −0.0813 | −3,575 | −3,225 | 0.333 (size_only) | ❌ 不进池 |
| K021/cand0013 | add-6th | −0.1509 | −6,640 | −6,289 | 0.322 (impact60) | ❌ 不进池 |
| K015/cand0003 | add-6th | −0.0133 | −586 | −236 | 0.509 (impact60) | ❌ 不进池（最接近） |
| K024c_keep2 | add-6th | **+0.0040** | **+177** | +528 | 0.831 (size_only) | ⚠️ 唯一转正，但靠 size 暴露 |
| K020b_xrankfix | add-6th | −0.0068 | −301 | +49 | 0.861 (impact60) | ⚠️ 收益侧打平，impact60 变体 |
| K024d_compK021 | add-6th | −0.2050 | −9,022 | −8,803 | 0.310 | ❌ 最差 |
| K024e_compK008 | add-6th | −0.2022 | −8,896 | −8,623 | 0.278 | ❌ 最差 |

（三个 A 组候选的 `replace-SIZE` 场景同样全负：−0.1060 / −0.1696 / −0.0182。）

**要点**

- **A 组三条进池无意义**：两个场景、两种 A 项口径、逐段账本全部为负；把 A 项抵扣归零后纯收益侧仍为负
  → 不是代理口径造成的假阴性。共同原因是换手 43~45%（池基线 13.9%）。
- **复合消解不掉换手膨胀**：把 K024 与 K021/K008 做 `Rank()` 复合后换手涨到 58.8%/62.4%、ΔComb −0.20 级别
  → 「复合」不再是补强手段。
- **K024c_keep2 是唯一正 ΔComb（+177 分/月）**，但与 `size_only` 相关 0.831、size 中性后净额只剩 1.70%，
  本质是「换 size 暴露」而非新信息；只在明确要加第 6 席时启用。
- **口径发现**：cycle=10 下每月只有 2 期信号日，「逐月实测 ΔComb 月均 > 0」这条门槛**不可评估**
  （月度 ΔComb 全落在 ±176 分/月内、正向月占比 ≤3.8%）。改用连续 6 期分块后只有 K020b 为正（+0.0035）。
  已提请用户确认是否把规则文本改成「逐 6 期分块 ΔComb 均值 > 0 且正向块占比 ≥ 50%」。
- **零算力**：本批未提交任何平台任务，余额仍 1654.12。

**产物**：`ab-batch-20260925/{summary.md, pool_scenarios.csv, decision_table.csv, ab_batch_final_table.csv,
monthly_dcomb.csv, seat_stats.csv, base_pool.csv, seat_panels_rebuilt.pkl, seat_rebuild_validation.csv, run_provenance.json}`。
"""

text = GP.read_text(encoding="utf-8")
if "## 十六、A/B 批次" not in text:
    if not text.endswith("\n"):
        text += "\n"
    text += SECTION16
    GP.write_text(text, encoding="utf-8")
    print("appended section 16 to", GP.name)
else:
    print("section 16 already present")

ITEM23 = """23. **A/B 批次池级 ΔComb（2026-09-25/26，零算力）+「逐月账本不可评估」的口径发现**：
   - 前置：两个席位大缓存本机缺失，只重建了现役 5 席（新文件 `seat_panels_rebuilt.pkl`）。验证：5 席 RankIC 与既有本地值
     逐位吻合，重建池净 20.70% / 换手 13.93% / SR 1.0427 vs 平台池记录 `F-P260922-08`（20.30% / 13.39% / 1.0648），净额差 +0.36pp。
   - **A 组（K008 / K021 / K015）进池全负**：add-6th ΔComb −0.0813 / −0.1509 / −0.0133；replace-SIZE 同样全负；
     把 A 项抵扣归零后纯收益侧仍是 −3,225 / −6,289 / −236 分/月 → **已过平台验证 ≠ 能进现役池**（换手 43~45% vs 池基线 13.9%）。
   - **B 组只有 K024c_keep2 转正**（add-6th +177 分/月，纯收益侧 +528），但与 `size_only` 相关 0.831、size 中性后净额 1.70%
     → 属"换 size 暴露"而非新信息；K020b_xrankfix 收益侧打平（+49）但属 impact60 变体。
   - **复合变体 K024d/K024e 是本批最差**（−9,022 / −8,896 分/月，换手 58.8%/62.4%）→ 复合消解不掉换手膨胀。
   - **口径规则待改**：cycle=10 下每月仅 2 期信号日，「逐月实测 ΔComb 月均 > 0」在本口径下**不可评估**
     （月度值全在 ±176 分/月内、正向月占比 ≤3.8%）；建议改为「逐 6 期分块 ΔComb 均值 > 0 且正向块占比 ≥ 50%」，**需用户确认**。
   - 独立信息的门槛仍是"换手 ≤30%/次 且 与现役 5 席相关 <0.3"：本批 10 条里只有 4 条满足相关门槛，而这 4 条恰好收益侧最差或换手最高。

"""

goal = GOAL.read_text(encoding="utf-8")
if "A/B 批次池级 ΔComb" not in goal:
    anchor = "## 五、唯一可主动改变的杠杆"
    assert anchor in goal
    goal = goal.replace(anchor, ITEM23 + anchor, 1)
    GOAL.write_text(goal, encoding="utf-8")
    print("inserted GOAL item 23")
else:
    print("GOAL item already present")

header = (
    "# 池级进池评估：A/B 批次（2026-09-26）\n\n"
    "> 桌面副本。仓库正式版：`D:\\factor\\research_reports\\platform_alignment\\ab-batch-20260925\\summary.md`；\n"
    "> 批次总报告：`gp-platform-tests-20260925/summary.md` 第十六节。本批零平台算力，余额仍 1654.12。\n\n"
    "---\n\n"
)
body = AB.read_text(encoding="utf-8")
body = body.split("\n", 1)[1].lstrip("\n")
DESK.write_text(header + body, encoding="utf-8")
print("written desktop copy:", DESK, DESK.stat().st_size)