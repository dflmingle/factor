# 技术目录族（cal-date/MA/oscillators/volume-indicators）本地挖掘（2026-10-03，全本地零平台算力）

用户指令"先挖别的"后的新信号族搜索。全部本地完成，未消耗平台算力；平台测试提案见第六节（**待批准**）。

## 一、覆盖侦察（`../field-recon-20261003/`）

- 新脚本 `scripts/_field_coverage_probe_20261003.py`：用 stub frame + stub data 调 `PandaAIFieldStore.status()`，
  30 秒盘清 **1396 个声明字段**（catalog 1048 + 基础 348），交叉历史公式登记表（51,783 签名）标注"从未进过任何公式"的新货。
- 本地可物化 **318/1396**（local_direct 17 / local_proxy 288 / local_derived 13）；**新货 41 个**：
  ma-indicators 16、oscillators 9、cal-date 5、volume-indicators 4、valuation 2、cashflow/growth/operating 1~2。
- **财务/估值 57 字段预屏（`fundamental_prelim.csv`，判否）**：除 B/M 族（ratio_bm_lyr s_i .0129 / ttm .0124，已在池内轴）
  与两个价值组合（comp_qv .0095 / comp_value .0083）外，其余全部 s_i ≤ .005（EP/SP/CFP .002~.005）；
  质量/成长/现金流/应计族 ≤ .0014 ⇒ 财务线关闭。
- **技术目录 194 字段预屏（`technical_prelim.csv`，重大发现）**：过线 5 条——
  `cal_20d_amt_std` s_i **.0529**（recent_ic +.098）、`cal_20d_amt_ma` .0406、`davol5` .0261、
  `cal_10d_vol_std` .0257、`cal_10d_120d_turnover_ratio` .0254；tier2（.015~.024）另有 vol3/amp10/vol5/dpo/macd_diff/ar 等 30 余条。
  （跳过 6 个 O(T×N) 双循环实现：mdd20/60、aroon_up/down、cal_5d_max/min_*_idx。）
- 命名去重：cal_10d_120d_turnover_ratio≡davol10、vol5≡cal_5d_turnover_sum、vol10≡cal_10d_avg_turnover、davol20≡cal_20d_120d_turnover_ratio。

## 二、池级全账 · 加第 6 席（`caltech-20261003/`，25 条，零算力）

腿库 `scripts/caltech_legs_20261003.py`（19 单腿 + 4 组合，字段实现复用 `pandaai_fields_local._catalog_technical_panel`），
筛选器 `scripts/_caltech_screen_20261003.py`（e_decomp_direct 管线，seed=现役 5 席，120 期，60 月账）。
口径：ΔComb_up = ΔA_uplift + ΔC（含 K5 口径平滑；本地口径只用于相对排序）。

| 候选 | 形态 | s_i | corr_size | ΔT/月 | ΔNC | ΔC | ΔComb_up | 正 C 月 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ct_comp_topmix（8 腿） | 加席 | **.0593** | -.32 | +.136 | -.0171 | -339 | **+659** | 2/60 |
| ct_comp_activity_swapF | 换 F | .0477 | -.53 | +.087 | -.0064 | -126 | +638 | 2/60 |
| ct_amt_std20（单腿） | 加席 | .0550 | -.56 | +.060 | -.0134 | -266 | +625 | 0/60 |
| ct_comp_amtdisp（2 腿） | 加席 | .0481 | -.62 | +.037 | -.0126 | -250 | +469 | 1/60 |
| ct_comp_activity_swapE | 换 E | .0477 | -.53 | +.080 | -.0183 | -362 | +434 | 1/60 |
| ct_amt_ma20（单腿） | 加席 | .0407 | -.66 | +.017 | -.0102 | -202 | +335 | 1/60 |

## 三、池级全账 · 换席形态（`caltech-swap-20261003/`，5 条，零算力）

| 候选 | 换出 | s_i | ΔT/月 | ΔNC | ΔC | ΔComb_up |
|---|---|---:|---:|---:|---:|---:|
| ct_amt_std20_swapF | VERIFY10-F | .0550 | +.101 | -.0118 | -234 | **+747** |
| ct_comp_amtdisp_swapF | VERIFY10-F | .0481 | +.073 | -.0031 | **-61** | **+715** |
| ct_comp_topmix_swapF | VERIFY10-F | .0593 | +.189 | -.0333 | -660 | +450 |
| ct_comp_topmix_swapE | VERIFY10-E | .0593 | +.182 | -.0383 | -759 | +382 |
| ct_amt_ma20_swapF | VERIFY10-F | .0407 | +.050 | -.0105 | -207 | +349 |

## 四、与既有候选对照（同管线同口径）

- K10 swapF 本地 **+1,264**、K20 swapF **+1,234**（行为批对照逐位复现）⇒ 本族最强 +747 ≈ 60%，**不敌，不改 11-01~03 主候选**。
- 本族定位：**新信号族储备**（NA/NC 长期杠杆 + 未来池重构素材）；`ct_comp_amtdisp_swapF` 的 C 段最轻（ΔC -61、ΔNC -.003）。
- `ct_vol_std10` 是唯一 ΔNC 为正（+.0073）/ΔC +145 的腿（s_i .0250、ΔComb +290）——留作 C 改善素材。

## 五、风险与对照

1. **K021 先例**：`cal_20d_amt_ma` 复杂比率（CORR(ASI,VMA3)/CAL_20D_AMT_MA/QTYR/BS_TOTAL_ASSETS）单因子平台通过（+11.27%），
   但池级加第 6 席平台 ΔComb **-6,289** 否决（本地 -6,640 曾预警）⇒ 单因子通过 ≠ 池级可用；本族本地池账为正（+335~+747），仍需平台池级裁决。
2. **CAL 族平台 s_i 无标定**：LEGMIX 族有本地高估 8~20% 先例；本批必须靠公式实测校准。
3. **C 段预警**：本族 pos_months 全部 1~3/60——高换手代价集中在少数月；`topmix` ΔT +.189/月 已贴高风险线。
4. **量级/结构**：CAL_20D_AMT_STD ~1e8（与平台已验证的 `-MA(amount,60)` 同量级）；组合无"有符号近零分母"结构（DAVOL5 分母为正量 MA(TURNOVER,120)）。
5. **方向**：负向已内嵌 `0-(...)`；依赖代理字段的候选平台方向最终以实测为准。

## 六、平台测试提案（第 1 阶段已执行；结果见下）

**第 1 阶段（2026-10-03 深夜执行，10.0 算力，3/3 通过）**：平台 s_i `CT-COMP-TOPMIX` **.0610**（迄今新候选最高）/ `CT-AMT-STD20` **.0557** / `CT-COMP-AMTDISP` **.0505**（换手 27.4%/次、净 +13.28%，首个「高 IC + 换手≤30%/次」双满足）；本地转移比 **1.01~1.05 倍**（CAL 族本地几乎无偏）。明细与教训见 [`../caltech-platform-20261003/summary.md`](../caltech-platform-20261003/summary.md)。以下为原始提案文本，第 2 阶段仍待批准。

**第 1 阶段 · 公式校准（3 条，预估 10.0 算力）**——`caltech-platform-20261003/candidates.txt`：

| # | 候选 | 公式（平台写法） | 目的 | 预估 |
|---|---|---|---|---|
| 1 | CT-AMT-STD20 | `0 - CAL_20D_AMT_STD` | 单腿 s_i 校准（本地 .0550）+ 大值量级复核 | 2.0 |
| 2 | CT-COMP-AMTDISP | `0.5*RANK(0-CAL_20D_AMT_STD)+0.5*RANK(0-CAL_20D_AMT_MA)` | 2 腿组合校准（本地 .0481），池级最干净形态的先导 | 4.0 |
| 3 | CT-COMP-TOPMIX | 8 腿 RANK 等权（含 VOL5/DAVOL5/AMP10 的 base 字段改写） | 全家幅组合校准（本地 .0593 / RankIC .1038）+ 其余 6 腿字段转写确认 | 4.0 |

提交前本地校验（已全过）：
- `scripts/platform_precheck.py`：无撞名 / 无脆弱结构 / 字段与算子全部在表（组合腿已改写：`VOL5->MA(TURNOVER,5)`、`DAVOL5->MA(TURNOVER,5)/MA(TURNOVER,120)`、`AMP10->(TS_MAX(HIGH,10)-TS_MIN(LOW,10))/DELAY(CLOSE,10)`）。
- `scripts/_caltech_formula_verify_20261003.py`（公式仿真 vs 腿库，逐期截面秩相关）：3/3 **PASS，min 1.000000**。

**第 2 阶段 · 池级（1 条 ≈6.0，待第 1 阶段结果报告后再批）**：pool5-swapf 形态（现役 5 席 − VERIFY10-F + 本族），
首选 `ct_amt_std20_swapF`（本地 +747）或 `ct_comp_amtdisp_swapF`（+715），视第 1 阶段校准结果定。

**算力窗口**：GIFT 72.0 于 **2026-10-07 23:16** 到期（余额 1480.12 含 GIFT）；第 1 阶段预估 10.0。

## 七、产物

- 覆盖侦察：`../field-recon-20261003/`（field_coverage.csv、family_summary.csv、fundamental_prelim.csv、technical_prelim.csv、probe_meta.json）
- 腿库 / 筛选器：`scripts/caltech_legs_20261003.py`、`scripts/_caltech_screen_20261003.py`
- 加席全账：`caltech-20261003/`（25 条 `cand_summary_direct.csv` + 日/月账）
- 换席全账：`caltech-swap-20261003/`（5 条 + `screen.log`）
- 平台候选（待批）：`caltech-platform-20261003/candidates.txt`；校验脚本：`scripts/_caltech_formula_verify_20261003.py`
