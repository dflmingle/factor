# 侧线工作包 2026-09-25 .. 09-27（对手复现 → 换手闸筛 → 方法论检验）

本目录是侧线（非主研究线）在 09-25 ~ 09-27 的工作归档：对手因子复现、换手闸筛查、
算子/窗口口径踩坑、以及两条"可借鉴方法论"（正交化、条件反转）的本地检验与证伪。
**除标注的平台实测外，全部为零平台算力的本地研究。**

- 本地口径：沪深全 A、qfq、`total_mv`、平台保存信号日（2021-09-07..2026-08-10，120 期，10 日步长）、
  label-1（t+1 → t+11）；池级账本复用 `ab-batch-20260925`，基线自检
  `pool_net .20703 / turnover .13933 / comb .39743`（与平台实测 20.30% / 13.39% 同口径）。
- 平台实名：`platform_pool_tests_20260927_side/`（S6 两条 4 算力）+ `summary-pool6-side-20260927.md`（4 条 16 算力）。
- 环境：Windows PowerShell；分析用 `D:\anaconda3\python.exe`，平台提交用 `easyrl4rec` 环境 + `pandaai-cli`；
  跑批需 `PYTHONUTF8=1`；脚本均带内存看门狗（本机空闲内存常年 2.5~4.8GB，峰值控制在 <1GB）。

## 一、对手因子复现（`opp_factor_reproduction.md`）

- 逐位对上（Δic ≤ 0.005）：sx 的 bias/反转族、LavineX 的 maxret20/pvcorr20/amt60/illiq/size、
  forests 的 volume-vol-10d/ema26/reversal20/小市值、神人队的 intradayma40/60/90/120_low、dfkai 的 Amihud/小市值。
- 第二轮新解出：`std(volume,20)/std(volume,1250)`（波动稳定性族）、`rank(−bias20)×(1−rank(turnover))`、
  A191 #120/#140/#124 的低换手改造（IC 对上、ICIR 差 .32）。
- **仍未对上**：`F-I01_Alpha191_010_LW`（IC .1253 / ICIR .980，全场最高）、forests 的 #042 改造版
  （.0957/.975/.773，官方复刻只有 .0639/.486/.646）、MATRIX 条件反转三条、W12/Y04 双正交、QF-*、tuc/tud。
- 计分链复算 20/20 池逐位一致（`sept_score_check.md`）；feed 日更榜单**不能**当逐日指纹用（股票池不同）。

## 二、换手闸筛查（`换手闸筛查报告_20260927.md`）

- 校准：Δ换手偏差 ≤0.5pp；**Δ净额本地系统性偏乐观 0.5~2.3pp**（换手越高越乐观）。
- 原始族 12 条全灭；慢化变体 3 条在"2018 全窗"过闸（MIXsms/T60/T20sm63），
  但按**平台部分窗口口径**（起点截断 2021-05-07 + min_periods=1）复算后全部转负 ⇒ VOLSTAB 整线关闭。

## 三、平台口径踩坑（`summary-pool6-s6-20260927.md`）

- S6A：`STDDEV(x,1250)` 全样本无值（首值晚于样本末端）→ 秒失败、未扣费。
- S6B：假象"净 +61.29%、DD=0"，实为**只覆盖最后 4 期**。
- 根因：平台滚动窗口可用历史起点 ≈ **2021-05-07**（回测起点前仅 ~86 交易日）；
  严格型算子（STDDEV/STD/VAR）需满窗，`MA/SUM` 类可部分窗口启动。
- **流程修正**：此后任何长回看（>60 交易日）候选，本地必须用"平台部分窗口"仿真，不能用 2018 全窗。

## 四、P0/P1：变换破解与家族扫描（`P0P1_报告_20260927.md`）

- 参照组 120/140 的核心成分 = **量/换手波动稳定性**（10~20 日波动 ÷ 5 年波动，反向），非低换手、非平滑。
- 产出三条候选；其中 F2-nb60_x_T5 / F1-im40 平台实测（`summary-pool6-side-20260927.md`）：
  加席 −1.66pp / −0.08pp、换席 −3.61pp / −1.07pp，**换手死区（席位换手 ≈0.49/0.72）**，全部退役。

## 五、P3 系列：正交化与条件反转（`P3_双正交_条件反转_20260927.md`、`P3b-G_...md`）

1. **双正交**（对现役池、池+size 取秩残差）：相关性按设计下降，但 s_i 同步下降更多，Δnet 全线未改善；
   λ 扫描（0→1）前沿单调，无中间甜点 ⇒ 关闭。
2. **条件反转**（低换手/深回撤 20/60/双窗口/硬阈值）：s_i 掉 30~80%、换手几乎不动 ⇒ 关闭。
3. **基本面条件席位**：op_yoy/roe/gpm 曾出现 +4pp"过闸"，被三步对照证伪
   （正反方向都赚、中位数填充归零、同覆盖冻结随机倾斜也 +3.5pp）⇒ 是**覆盖率掩码伪影**。
4. **顺藤摸出的真效应**：无财报覆盖的 577 只（= 本地财务池 4879 vs 面板 5456 的差集，近 260 日 46.6% 无收盘价，
   退市/停牌队列）每期比其余持仓低 **1.25pp**，现役池持仓里占 **13.5%**。写成因子值（blocker 席位）
   本地 **+3.81pp net**、SR 1.043→1.141、MaxDD 29.35%→28.50%、换手略降。
   - 分数侧打折：平台 NC 常态月已是 1.0，本地 NC 只有 0.777 ⇒ +4,000 分/月大部分不会兑现，估几百/月；
     若作第 6 席还要被 NA 稀释 ≈−385/月。
   - 未验证风险：平台规则"剔除 ST、当日停牌、当日一字板"，本地重建宇宙可能更宽 ⇒ 必须平台实测才能定。
5. **副产品指纹**：纯噪声候选席位换手锁死 **0.900/0.902**，与平台退化面板 **90.3%** 同型
   ⇒ 本地见到换手 ~0.90 先怀疑量级/并列/NaN，别直接提交。

## 六、文件索引

| 文件 | 内容 |
| --- | --- |
| `opp_factor_reproduction.md` / `opp_by_pool.txt` / `opp_factor_rows.csv` / `top20_factor_details.json` | 对手复现全过程与原始席位数据 |
| `repro_opp_factors.py` / `repro_opp_cycles.py` / `attack_unmatched*.py` / `fingerprint_*.py` | 复现脚本（含未对上项的攻坚） |
| `multi_window.py` / `multi_window_report.md` / `our_si_windows.py` | 三窗口（5y/1y/3m）复核 |
| `sept_score_check.md` / `score_conversion.py` | 计分链复算（20/20 池逐位一致） |
| `换手闸筛查报告_20260927.md` / `gate6_screen.py` / `gate6b_probes.py` / `gate6c_windows.py` / `gate6d_platform_emul.py` | 换手闸 + 平台部分窗口仿真 |
| `P0P1_报告_20260927.md` / `p0_lw_crack.py` / `p0b_blend.py` / `p1_family_scan.py` / `p2b_report.py` / `p2_robust.py` | 变换破解与家族扫描 |
| `P3_双正交_条件反转_20260927.md` / `p3_orth_cond.py` / `p3b_orth_lambda_fund.py` / `p3c_fund_control.py` / `p3d_fund_diag.py` / `p3e_universe_mask.py` / `p3f_nocover_who.py` / `p3g_blocker_seat.py` | 正交化/条件反转/覆盖对照/blocker 全链 |
| `ht_a191_low_variants_report.md` / `lowturn_variants.py` | A191 低换手改造变体 |
| `factor_list_now.json` / `info_nb60t5.json` | 平台因子清单与单因子明细取样 |

## 七、复现须知

- 依赖本地面板 `%TEMP%\side_conv\wide_panels.pkl`（322MB，日频 close/open/volume/amount/turnover/total_mv/circ_mv）
  与 `research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl`（71.5MB，`*.pkl` 按仓库策略不入库）。
- 所有脚本都是"读面板 → 建候选 → 池级账本"结构，直接 `python <script>.py`（需要 `PYTHONUTF8=1`）。
- 平台提交统一走 `scripts/pandaai.py` / `vendor/skill-pandaai-factor-online/scripts/batch.py`，
  提交前必须跑撞名预检与量级归一（见 GOAL.md 第 12、15、17 条）。

## 八、开放项（未决）

1. blocker 席位是否上平台实测（4 算力）—— 这是本侧线唯一过了全部对照的本地增益。
2. `F-I01_A191_010_LW`（全场最高 IC .1253）与 forests #042 改造版仍未破解。
3. 榜首结构的"席位广度"路线（45 席 vs 我们 5 席）尚未做本地实验设计。
