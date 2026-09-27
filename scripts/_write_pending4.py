import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/pending4-eval-20260926"
GOAL = ROOT / "GOAL.md"

scen = pd.read_csv(OUT / "pool_scenarios.csv")
stats = pd.read_csv(OUT / "candidate_stats.csv").set_index("tag")
mon = pd.read_csv(OUT / "monthly_dcomb.csv").set_index("candidate")
base = pd.read_csv(OUT / "base_pool.csv").iloc[0]
POINTS = 44000.0

SWAP = "swap-t10_size_plus_impact_bm"
TAGS = ["AGG", "DOWNSIDE", "G13", "WC"]


def g(tag, scenario, a_term, col):
    return float(scen[(scen.candidate == tag) & (scen.scenario == scenario) & (scen.a_term == a_term)][col].iloc[0])


lines = [
    "# 待批 4 条候选池级复核：AGG / G13 / DOWNSIDE / WC（2026-09-26，零平台算力）",
    "",
    "复核对象：交接单 `HANDOFF_20260924` §4 列出的 4 条「已报批、从未验证」的候选。",
    "旧口径 6 席池 ΔComb 为 +148.8 / +148.3 / +108.7 / −783.3 分/月。",
    "",
    "本次用今天重建的现役 5 席面板（`ab-batch-20260925/seat_panels_rebuilt.pkl`）+ 与 A/B 批次",
    "完全相同的账本（10 日调仓 / 10 组 / 0.30% 单边 / 全 A / qfq / `total_mv`）重算，",
    "并首次把换席对象从「最弱的 SIZE」扩到**全部 5 席**。",
    "",
    "脚本 `scripts/pending4_seat_eval_20260926.py`。基线复现与 A/B 批次逐位一致",
    f"（Comb {base['pool_comb']:.4f} / 净 {base['pool_net'] * 100:.2f}% / 换手 {base['pool_turnover'] * 100:.2f}%）。",
    "",
    "## 一、单因子对比（与现役 T10-ADD-BM 同族）",
    "",
    "| 候选 | 平台净 | 平台 S_i | 本地净 | 本地换手 | RankIC | 与现役 `t10_size_plus_impact_bm` 相关 | 面板覆盖 | 对齐质量 |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    "| **现役 T10-ADD-BM** | 18.09% | 0.0373 | 15.75% | 29.63% | 0.1160 | 1.000 | 0.886 | aligned |",
    "| **AGG** | **19.76%** | 0.0320 | **16.86%** | **26.85%** | 0.1063 | 0.934 | 0.811 | aligned |",
    "| DOWNSIDE | 19.39% | n/a | 16.33% | 27.23% | 0.1070 | 0.939 | 0.811 | aligned |",
    "| G13 | 19.62% | n/a | 15.95% | 26.81% | 0.1050 | 0.931 | 0.811 | ❌ field_or_path_mismatch |",
    "| WC | 17.44% | n/a | 15.85% | 29.80% | 0.1158 | **0.9987** | 0.810 | ❌ field_or_path_mismatch |",
    "",
    "四条方向都是 `direction=1`，本地净 15.9~16.9% 与平台 17.4~19.8% 同号同量级；",
    "反向（把方向取反）本地净为 −29~−32%，**方向无疑**。",
    "",
    "## 二、池级 ΔComb：唯一为正的场景是「换掉 T10-ADD-BM」",
    "",
    "| 候选 | 场景 | A 项=local Pearson | A 项=`s_i_rank` | 纯收益侧 | 月均 ΔComb | 6 期分块 |",
    "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
]
for tag in TAGS:
    for scenario, label in ((SWAP, "swap-T10-ADD-BM"), ("add-6th", "add-6th"), ("replace-SIZE", "replace-SIZE")):
        lines.append(
            f"| {tag} | {label} | {POINTS * g(tag, scenario, 'local_pearson', 'd_comb'):+,.0f} | "
            f"{POINTS * g(tag, scenario, 'rank_ic', 'd_comb'):+,.0f} | "
            f"{POINTS * g(tag, scenario, 'rank_ic', 'd_comb_nc_only'):+,.0f} | "
            f"{mon.loc[tag, 'dcomb_month_mean']:+.4f} | {mon.loc[tag, 'dcomb_block6_mean']:+.4f} |"
        )
lines += [
    "",
    "（单位：分/月。另外两个换席场景 `swap-impact60` / `swap-book_to_market_lf_*` 四条全部 ≤ −3,790，已略。）",
    "",
    "**要点**",
    "",
    "1. **加第 6 席（add-6th）四条全负**（−2,358 ~ −2,700），与旧口径「4 条候选」的定位一致——",
    "   它们本来就是**换席候选**，不是加席候选。",
    "2. **换掉 T10-ADD-BM 才是它们的位置**：`s_i_rank` 口径下 AGG **+507**、WC +407、DOWNSIDE +339、G13 +198 分/月。",
    f"   AGG 的分解：Δna {g('AGG', SWAP, 'rank_ic', 'd_na'):+.4f} + ΔNC {g('AGG', SWAP, 'rank_ic', 'd_nc'):+.4f}",
    f"   → 换手反而**下降** {abs(g('AGG', SWAP, 'rank_ic', 'd_turn')) * 100:.2f}pp。",
    "3. **符号对 A 项口径敏感，但 AGG 两种口径都为正**：",
    "   - 用本地 `s_i_rank`（AGG 0.0447 > 现役本地 0.0359）→ **+507 分/月**；",
    "   - 换成平台 S_i（AGG 0.0320 < 现役 0.0373）→ Δna 转负，但仍 **+227 分/月**（收益项撑住）。",
    "4. **G13 / WC 不可信**：两条在 catalog 里都是 `field_or_path_mismatch`（本地复现未对齐），",
    "   WC 与现役席相关 **0.9987** —— 它基本就是同一个因子，+407 分/月是噪声级的重复度差。",
    "5. **这是同族优化，不是新信息**：四条与现役 T10-ADD-BM 的相关都在 0.93 以上，",
    "   换席只是把同一族里平台净额更高的那条放到池子里。对 NA 的贡献只来自成员 S_i，量级 +227~+507 分/月。",
    "6. 逐段账本（6 期分块）四条仍为负（−0.002 ~ −0.004），说明这条增益**不是全期均匀**的；",
    "   与 A/B 批次同一现象（cycle=10 下逐段账本噪声大），不单独作为否决依据。",
    "",
    "## 三、建议",
    "",
    "1. **AGG（T10-ADD-AGG-IMPACT）是本批唯一值得上平台的候选**：平台净额 19.76%（比现役高 1.67pp）、",
    "   `aligned`、换手更低、两种 A 项口径下换席都为正。",
    "2. **DOWNSIDE 次之**（+339 分/月），同族、`aligned`；可作为 AGG 的备选或并行验证。",
    "3. **G13 / WC 不建议花算力**：一条本地未对齐、一条与现役重复度 0.9987。",
    "4. 花费：若只做 AGG 的 6 席池实测，1 条 × 4 算力；做 AGG+DOWNSIDE 两条 8 算力。",
    "   9-30 23:16 到期的 46.0 GIFT 余额足够，且**到期前不用就作废**。",
    "5. 上平台前按纪律仍需用户明确批准（本批复核零算力）。",
    "",
    "## 四、与 A/B 批次的合并看法",
    "",
    "| 路线 | 最好 ΔComb | 结论 |",
    "| --- | ---: | --- |",
    "| 加第 6 席（A/B 批次 10 条） | +177 分/月（K024c，且 corr_size 0.831 过不了防作弊线） | ❌ 挖空 |",
    "| 加第 6 席（本次 4 条） | −2,358 分/月 | ❌ 定位错 |",
    "| **换席：T10-ADD-BM → AGG** | **+507 分/月**（保守口径 +227） | ⏳ 待平台验证 |",
    "",
    "即：**这个池子现在的改进空间在「换席」而不是「加席」**，而换席的天花板是 +200~+500 分/月，",
    "对比 NA（+4,048）与 NB（+15,400）仍然是零头。真正的上限仍卡在缺新信号族。",
    "",
    "## 五、产物",
    "",
    "| 文件 | 内容 |",
    "| --- | --- |",
    "| `candidate_stats.csv` | 4 条的单因子统计（含 `s_i_rank`、逐席相关、方向反事实） |",
    "| `pool_scenarios.csv` | 4 候选 × 7 场景 × 2 种 A 项口径，含 Δna/ΔNC 分解 |",
    "| `monthly_dcomb.csv` | 月度 + 6 期分块逐段账本 |",
    "| `base_pool.csv` / `run_provenance.json` | 基线复现值与运行出处 |",
    "",
]
report = OUT / "summary.md"
report.write_text("\n".join(lines), encoding="utf-8")
print("written:", report, report.stat().st_size)

ITEM24 = """24. **待批 4 条候选（AGG/G13/DOWNSIDE/WC）池级复核（2026-09-26，零算力）——唯一正场景是"换掉 T10-ADD-BM"**：
   - 用重建 5 席面板 + A/B 同口径重算，并把换席对象从"最弱的 SIZE"扩到全部 5 席。
   - **加第 6 席四条全负**（−2,358 ~ −2,700 分/月）→ 它们本来就是换席候选，不是加席候选。
   - **换掉 T10-ADD-BM 是正贡献**：`s_i_rank` 口径下 AGG **+507**、WC +407、DOWNSIDE +339、G13 +198 分/月；
     AGG 换手反而下降 0.49pp；换成平台 S_i 口径后 AGG 仍 **+227 分/月**（两种口径同号）。
   - **AGG = 本批唯一值得花算力的**：平台净额 19.76%（比现役高 1.67pp）、`aligned`；
     DOWNSIDE 次之（+339）；G13/WC 不建议——一条 `field_or_path_mismatch`，一条与现役相关 **0.9987**（重复因子）。
   - **性质提醒**：四条与现役 T10-ADD-BM 相关均 ≥0.93，这是**同族优化**不是新信息，量级 +227~+507 分/月，
     相比 NA(+4,048)/NB(+15,400) 仍是零头。
   - 结论：**该池子当前的改进空间在"换席"而非"加席"**；待用户批准 AGG（4 算力）是否上平台做 6 席池实测。

"""
goal = GOAL.read_text(encoding="utf-8")
if "待批 4 条候选（AGG/G13/DOWNSIDE/WC）池级复核" not in goal:
    anchor = "## 五、唯一可主动改变的杠杆"
    assert anchor in goal
    goal = goal.replace(anchor, ITEM24 + anchor, 1)
    GOAL.write_text(goal, encoding="utf-8")
    print("inserted GOAL item 24")
else:
    print("GOAL item already present")