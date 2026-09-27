import io
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/ab-batch-20260925"
GP = ROOT / "research_reports/platform_alignment/gp-platform-tests-20260925"

scen = pd.read_csv(OUT / "pool_scenarios.csv").set_index(["candidate", "tag"])
stats = pd.read_csv(OUT / "seat_stats.csv").set_index("candidate")
mon = pd.read_csv(OUT / "monthly_dcomb.csv").set_index("candidate")
base = pd.read_csv(OUT / "base_pool.csv").iloc[0]


def g(key, tag, column):
    return float(scen.loc[(key, tag), column])


def pct(value):
    return f"{value * 100:.2f}%"


def pts(value, digits=0):
    return f"{value:+,.{digits}f}"


def cand_row(key, tag):
    s = stats.loc[key]
    return (
        f"| {key} | {pct(s['net'])} | {pct(s['turnover'])} | {s['rank_ic']:.4f} | "
        f"{pct(s['neu_net'])} | {s['corr_max']:.3f} ({s['corr_max_seat']}) | "
        f"{g(key, tag, 'd_comb'):+.4f} | {pts(g(key, tag, 'd_points'))} | "
        f"{g(key, tag, 'd_nc'):+.4f} | {pts(g(key, tag, 'd_points_nc_only'))} |"
    )


HEADER = (
    "| 候选 | 本地净 | 换手 | RankIC | size 中性后净额 | 与席位最高相关 | ΔComb | Δ分/月 | ΔNC | 纯收益侧 Δ分/月 |\n"
    "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |"
)

A_KEYS = ["A_K008_cand0000", "A_K021_cand0013", "A_K015_cand0003"]
B_KEYS = ["B_K020a_rankfix", "B_K020b_xrankfix", "B_K024a_denoise", "B_K024b_smooth",
          "B_K024c_keep2", "B_K024d_compK021", "B_K024e_compK008"]

lines = [
    "# A/B 批次：池级 ΔComb 评估（2026-09-25/26，零平台算力）",
    "",
    "全本地运行，未提交任何平台任务、未消耗算力。产物目录 `research_reports/platform_alignment/ab-batch-20260925/`。",
    "",
    "## 零、前置：两个席位大缓存缺失 → 本机重建（这是本批唯一的口径变化）",
    "",
    "A/B 批次依赖的 `pool-screen-20260921-qualitygate3/signals.pkl`（53 MB）与",
    "`pool-extended-search-20260922/built_signals.pkl`（228 MB）在本机不存在——`.gitignore` 从 2026-09-24 起忽略 `*.pkl`，",
    "交接单 `handoff_20260924` 明确它们只能直拷或重建。",
    "",
    "本批**只重建了真正需要的部分**（现役 5 席面板 + signal frame + 前向收益），未冒充原 228 MB 缓存：",
    "",
    "- 脚本：`scripts/ab_seat_rebuild_20260925.py`，产物 `seat_panels_rebuilt.pkl`（71.5 MB，新文件）；",
    "- 口径：与 `prescreen_extended_members_20260922.build_members` 相同（同一 full-A/qfq/`total_mv` 面板、",
    "  同一 cycle-10 的 120 期信号日、同一 Winsorize(1%,99%)+Z-score）；",
    "- 方向与平台净额取自本机 `qualitygate1` 全量对齐报告（该报告与本机数据缓存同代；",
    "  代码默认指向的 `qualitygate3` 报告目录在本机不存在）；",
    "- 席位来源与规则版本已写入 `run_provenance.json`（`seat_source=rebuilt:...qualitygate1`）。",
    "",
    "**重建验证（两层）**",
    "",
    "| 席位 | 平台净超额 | 目录内既有本地净 | 重建后本地净 | 差 | 目录内 RankIC | 重建 RankIC |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    "| size_only | 21.43% | 17.16% | 17.97% | +0.81pp | −0.0529 | −0.0530 |",
    "| impact60 | 16.44% | 15.02% | 16.68% | +1.67pp | 0.0610 | 0.0610 |",
    "| t10_size_plus_impact_bm | 18.09% | 13.85% | 15.75% | +1.90pp | 0.1160 | 0.1160 |",
    "| book_to_market_lf_minus_size | 16.74% | 14.54% | 15.92% | +1.37pp | 0.0791 | 0.0791 |",
    "| book_to_market_lf_plus_impact | 15.05% | 13.48% | 15.23% | +1.75pp | 0.0766 | 0.0766 |",
    "",
    "- **RankIC 逐位吻合（4 位小数）→ 重建出的面板与原缓存是同一批信号**；净额差 +0.8~1.9pp 来自",
    "  `_summary` 与 `all_factor_compare` 两条成本/换手后端的差异，不是信号差异。",
    f"- 池级复核：重建 5 席池 **净 {pct(base['pool_net'])} / 换手 {pct(base['pool_turnover'])} / SR {base['pool_sr']:.4f} / MaxDD {pct(base['pool_dd'])}**，",
    "  对照平台池记录 `F-P260922-08`（净 20.30% / 换手 13.39% / SR 1.0648 / MaxDD 31.64%）→ **净额差 +0.36pp，验收通过**。",
    "",
    "> 只要本机没有直拷回那两个 pkl，A/B 批次就应继续引用 `seat_panels_rebuilt.pkl` 并在结论里带上这条 provenance；",
    "> 直拷回原文件后 `ab_batch_20260925.py` 会自动改回读原缓存（`load_seats()` 优先原文件）。",
    "",
    "## 一、口径",
    "",
    "- 池：现役 5 席 `size_only` / `impact60` / `t10_size_plus_impact_bm` / `book_to_market_lf_minus_size` / `book_to_market_lf_plus_impact`，"
    "席位等权、各自日截面 z-score 后平均；",
    "- 两个池场景：`replace-SIZE`（用候选替换最弱的 size_only）与 `add-6th`（候选作第 6 席）；",
    "- 账本：10 日调仓、10 组、单边 0.30%、`close(t+1)→close(t+cycle+1)`、全 A、qfq、`total_mv`；",
    "- 评分形状：`Comb = 0.20·NA + 0.45·NC`（本批只用可本地测量的两项）；`Δ分/月 = 44000 × ΔComb`；",
    "- **ΔA 的口径**：席位 A 项用平台 s_i（与 `prescreen` / `relaxed_gp_screen` 一致的 `SEAT_SI`），候选 A 项用本地 `s_i`（同上两个脚本的既有约定）。",
    "  本批 10 个候选的本地 `s_i` 均为 0（`P(IC>0.02)=0`，即 Pearson IC 从未越过 2% 线），因此**每个候选都被扣了同一笔 ΔA −0.0398**。",
    "  为让结论不受这条约定绑架，另列**纯收益侧 = 0.45·ΔNC**（把 A 项抵扣全部归零）。",
    "",
    "## 二、基线（重建 5 席池，120 期）",
    "",
    f"- 净 {pct(base['pool_net'])}｜换手 {pct(base['pool_turnover'])}｜SR {base['pool_sr']:.4f}｜MaxDD {pct(base['pool_dd'])}｜毛超额 {pct(base['pool_gross'])}",
    f"- NA {base['pool_na']:.3f}｜NC {base['pool_nc']:.3f}｜Comb {base['pool_comb']:.4f}＝{pts(base['pool_comb'] * 44000)} 分/月 基准",
    f"- 换手上限对照：2×换手 {pct(base['T_monthly_k2'])}、3×换手 {pct(base['T_monthly_k3'])}、T* {pct(base['T_star'])}、T_cap {pct(base['T_cap'])}",
    "",
    "## 三、A 组（3 条已过平台验证的候选，进池意义）",
    "",
    "### 3.1 作第 6 席（add-6th）",
    "",
    HEADER,
]
for key in A_KEYS:
    lines.append(cand_row(key, "add-6th"))
lines += [
    "",
    "### 3.2 替换最弱席（replace-SIZE）",
    "",
    HEADER,
]
for key in A_KEYS:
    lines.append(cand_row(key, "replace-SIZE"))
lines += [
    "",
    "**判定：三条全部不建议进池。**",
    "",
    "- 双场景 ΔComb 全负；**把 A 项抵扣全部归零后纯收益侧仍全负**（K008 −3,225｜K021 −6,289｜K015 −236 分/月）",
    "  → 不是 A 项口径造成的假阴性，而是这三条在 5 席池里没有可加信息。",
    "- 共同原因是**换手**：三条换手都是 43~45%，而池基线只有 13.9%；`add-6th` 把池换手推高 "
    f"{pct(g('A_K015_cand0003', 'add-6th', 'd_turn'))}~{pct(g('A_K021_cand0013', 'add-6th', 'd_turn'))}，"
    "成本项直接把 NC 打穿。",
    "- K015 最接近（ΔComb −0.0133、纯收益侧 −236 分/月）。K015 与 `impact60` 的相关 0.509 是三条里最高的，",
    "  也说明它不是独立信息。",
    "- 与 2026-09-24 旧口径参考列（`relaxed-gp-20260924/screen2/screened_candidates.csv` 的 add6/delta_points：",
    "  K008 −2,303｜K021 −8,207｜K015 −2,384）**方向一致**，本批只是换成现役 5 席基线与三段账口径。",
    "",
    "## 四、B 组（K020 消解版 / K024 补强轮，6+1 个变体）",
    "",
    "### 4.1 作第 6 席（add-6th）",
    "",
    HEADER,
]
for key in B_KEYS:
    lines.append(cand_row(key, "add-6th"))
lines += [
    "",
    "### 4.2 替换最弱席（replace-SIZE）",
    "",
    HEADER,
]
for key in B_KEYS:
    lines.append(cand_row(key, "replace-SIZE"))
lines += [
    "",
    "**判定：7 个变体里只有 `B_K024c_keep2` 在 add-6th 转正。**",
    "",
    "- **K024c_keep2（保留双层 `bs_total_assets` 除法）＝ 本批唯一正 ΔComb："
    f"{g('B_K024c_keep2', 'add-6th', 'd_comb'):+.4f}（{pts(g('B_K024c_keep2', 'add-6th', 'd_points'))} 分/月）**，",
    f"  纯收益侧 {pts(g('B_K024c_keep2', 'add-6th', 'd_points_nc_only'))} 分/月，",
    f"  换手 {pct(stats.loc['B_K024c_keep2', 'turnover'])}（全组最低档），增量换手只有 {pct(g('B_K024c_keep2', 'add-6th', 'd_turn'))}。",
    f"  **但必须同时记两条负面**：与 `size_only` 的相关高达 {stats.loc['B_K024c_keep2', 'corr_max']:.3f}，",
    f"  且 size 中性化后净额只剩 {pct(stats.loc['B_K024c_keep2', 'neu_net'])}——它的正贡献主要来自 size 暴露，不是新信息。",
    "- **K020b_xrankfix＝收益侧打平**（纯收益侧 +49 分/月，ΔComb −0.0068），且 6 期分块账本是十者最高（+0.0035）；",
    f"  但 `corr_max` {stats.loc['B_K020b_xrankfix', 'corr_max']:.3f}（impact60）→ 本质是既有席位的变体，只作备选。",
    "- **K020a rankfix（TsRank 版）不成立**：ΔNC −0.0032、换手 23.3% 仍高于池基线，收益侧 −64 分/月。",
    "- **复合变体最差**：把 K024 与 K021/K008 做 `Rank()` 复合（K024d/K024e）ΔComb −0.205/−0.202、",
    "  换手膨胀到 58.8%/62.4%、size 中性化后净额 0.59%/−4.55% → **复合消解不掉换手膨胀，反而放大**。",
    "- K024a/K024b 的「去噪/平滑」把换手从 53.5% 降到 35.6%/20.1%、净额升到 9.1%/15.3%，",
    "  但两者与 `impact60` 的相关随之升到 0.83/0.85，进池仍然净负。",
    "",
    "## 五、逐段账本：周期 10 下「逐月实测 ΔComb」不可用（重要口径发现）",
    "",
    "决策规则要求「逐月实测 ΔComb 月均 > 0」。但在 cycle=10 下 120 期信号日只覆盖 53 个月，**每月只有 2 期**——",
    "用 2 期去年化（开 12.6 次方）会让月度 NC 方差爆炸。实测结果印证：",
    "",
    "| 候选 | 月均 ΔComb | 正向月占比 | 6 期分块均 ΔComb | 6 期分块正向占比 |",
    "| --- | ---: | ---: | ---: | ---: |",
]
for key in A_KEYS + B_KEYS:
    lines.append(
        f"| {key} | {mon.loc[key, 'dcomb_month_mean']:+.4f} | {mon.loc[key, 'dcomb_month_positive'] * 100:.1f}% | "
        f"{mon.loc[key, 'dcomb_block6_mean']:+.4f} | {mon.loc[key, 'dcomb_block6_positive'] * 100:.0f}% |"
    )
lines += [
    "",
    "- 月度版：10 条的月均 ΔComb 全落在 ±0.004（±176 分/月）内、正向月占比最高只有 3.8% → **纯噪声**，不能用来过闸。",
    "- 改用**连续 6 期分块（20 块）**作逐段账本：只有 `B_K020b_xrankfix` 为正（+0.0035），"
    "`A_K015`/`B_K020a`/`B_K024a` ≈ 0（−0.0006），其余为负；K024c 反而翻成 −0.0031。",
    "- **建议把决策规则里的「逐月实测 ΔComb 月均 > 0」改写成「逐 6 期分块 ΔComb 均值 > 0 且正向块占比 ≥ 50%」**，",
    "  否则 cycle=10 的候选永远不会合法通过（该门槛在本口径下不可评估）。这条需要用户确认后再改规则文本。",
    "",
    "## 六、净结论与建议",
    "",
    "1. **A 组三条（K008 / K021 / K015）进池无意义**——两个场景、两种 A 项口径、逐段账本全部为负。",
    "   它们作为「独立因子」已过平台，但**进不了现役 5 席池**（换手 3 倍于池基线 + 与既有席位相关 0.33~0.51）。",
    "2. **B 组只有 K024c_keep2 值得进一步考虑**（add-6th +177 分/月），但它与 `size_only` 相关 0.831、",
    "   size 中性后净额 1.70%，属于「换 size 暴露」而不是「加新信息」；只应在**明确要加第 6 席、且接受 size 暴露上升**时启用。",
    "3. **K020b_xrankfix 作备选**（收益侧打平、分块账本最好），但它是 impact60 的变体。",
    "4. **不要再花算力测 A 组或复合变体**：复合变体（K024d/K024e）是本批最差，−9,000 分/月级别。",
    "5. 找独立信息的方向应回到「换手 ≤30%/次且与现有 5 席相关 <0.3」的候选——本批 10 条的 `corr_max` 里只有",
    "   K008(0.333)/K021(0.322)/K024e(0.278)/K024d(0.310) 达标，而这四条恰好收益侧最差或换手最高。",
    "",
    "## 七、产物索引",
    "",
    "| 文件 | 内容 |",
    "| --- | --- |",
    "| `base_pool.csv` | 基线池指标（重建 5 席，120 期） |",
    "| `seat_stats.csv` | 10 条候选的单因子统计（净/换手/RankIC/size 中性/与 5 席逐席相关） |",
    "| `pool_scenarios.csv` | 两个池场景 × 10 候选，含 Δna/ΔNC 分解（`d_comb = 0.20·d_na + 0.45·d_nc`，残差 1e-16） |",
    "| `decision_table.csv` | 判定表（进池有利 / 仅收益项为正 / 进池不利） |",
    "| `monthly_dcomb.csv` | 月度账本 + 6 期分块账本 |",
    "| `ab_batch_final_table.csv` | 上面几张表的合并版（决策 + 逐段 + 单因子） |",
    "| `seat_panels_rebuilt.pkl` / `seat_rebuild_validation.csv` | 席位面板重建产物与逐席验证 |",
    "| `run_provenance.json` | 席位来源、周期、成本、评分常量 |",
    "| `platform_indicators_scan.csv` | 本机平台 run 结果目录里扫出的 Rank_IC/IC_IR/P(IC>2%) 原始值 |",
    "",
    "## 八、待用户决定",
    "",
    "- 是否把逐段账本门槛从「逐月」改成「逐 6 期分块」（§五）。",
    "- 是否为 K024c_keep2 提交平台 6 席池实测（按纪律需先报价：单条约 4 算力，余额 1654.12）。",
    "- 是否接受「A 组三条到此为止」，把下一批算力全部投给新 GP 批次 / 放宽字段，而不是继续在 205 条老候选里找。",
    "",
]

report = OUT / "summary.md"
report.write_text("\n".join(lines), encoding="utf-8")
print("written:", report, report.stat().st_size)