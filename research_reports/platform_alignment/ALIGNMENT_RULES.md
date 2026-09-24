# 平台/本地对齐规则

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate4`<br>
适用范围：保存的 PandaAI 因子结果与本地 Tushare 重建结果的离线对比。<br>
性质：研究复现规则，不是 PandaAI 内部实现的声明，也不会创建因子或发起平台回测。

脚本侧的单一配置源是 [`scripts/platform_alignment_rules.py`](../../scripts/platform_alignment_rules.py)。正式复现和 CFP 代理诊断都必须读取它；改变已验证规则时，应递增规则版本并生成新的结果目录。

## 固定口径

| 项目 | 固定规则 |
|---|---|
| 股票池 | `沪深全A`；本地使用 Tushare qfq 行情与 `daily_basic` 连接后的 `.SH/.SZ` 行，最终默认 `total_mv` |
| 平台窗口 | `20210907..20260907`；本地数据从 `20180101` 加载，用于时间序列暖机 |
| 复权 | qfq；不能用 raw 价格结果替代 |
| 调仓日期 | 优先使用保存的平台 RankIC/收益图表日期，不自行按自然日生成；本地日期来自交易日历 |
| 分组 | 10 组，横截面升序分位；方向 `1` 持有第 10 组，方向 `0` 持有第 1 组 |
| Top20 | 单独比较原始因子值最高的 20 个标的；不根据方向改成底部 20 个 |
| 标签 | `close(t+1) -> close(t+cycle+1)`；当前价和未来价同时向后取 1 个交易日 |
| 基准 | `factor_valid`：当期因子值和未来收益都有效的同一批股票的等权平均收益 |
| 成本 | 单边 `0.30%`，代码中的 round-trip cost 为 `0.006`；年化成本 = 换手率 × `252/cycle` × `0.006` |
| 净超额 | 算术累计的年化毛超额减年化换手成本；与平台 headline 长短收益分开报告 |
| 相关性 | 每个交易日对两因子有效股票截面计算 Spearman（平均秩处理并列值），再对每日相关系数取算术平均；不使用 pooled stock-day correlation 作为主结果 |
| 缺失值 | 计算前删除因子或收益无效行；价格面板按本地交易日历前向填充，这是本地代理规则，不等同于平台内部停牌处理 |

## 计算顺序

1. 读取保存结果中的平台信号日期、周期、方向和分组设置。
2. 从本地交易日历定位信号日；用信号日后第 1 个交易日作为当前价，用当前价后 `cycle` 个交易日作为未来价。
3. 在每个信号日删除因子值或收益无效的股票，再做横截面排序和 10 分组。
4. 计算方向对应极端组的等权收益、同一有效截面的基准收益、毛超额和组成员换手。
5. 第一个信号日不计换手；后续换手为 `1 - 新旧持仓交集数 / 新持仓数`。
6. 对所有有效信号期做算术累计，再按 `252 / (有效期数 × cycle)` 年化。
7. 单独计算 RankIC、IC、Top20 重合度，并保留平台对应值用于审计。

平台的 `excessAnnualized`、RankIC 和换手字段直接来自保存的结果；本地字段只作为同口径代理。任何单条结果的接近都不能证明字段或执行规则完全等价。

## 相关性计算规则

平台相关性工作流已用历史任务 `CORR-20260911-T10-SIZE-H03-T10` 验证。固定主口径为：

1. 对每个交易日取两因子同时有效的股票截面。
2. 在该截面上计算 Spearman 相关，使用平均秩处理并列值。
3. 对所有有效交易日的横截面相关系数取算术平均。

中心配置为 `ALIGNMENT_CORRELATION_METHOD = "daily_cross_sectional_spearman_mean"`。合并所有股票日观测后计算的 Pearson 或 Spearman 只作为诊断项，不得替代主结果。当前本地复现值为 `0.4162929759`，平台值为 `0.4151352929`，差值 `0.0011576830`。

## 财务数据规则

- 使用公告日点时连接：只使用 `ann_date <= signal_date` 的最近记录。
- 财务表优先合并口径 `comp_type=1`；相同标的、公告日和报告期按最新 `update_flag` 去重。
- 季度累计报表先还原季度值，再组合最近四个季度构造 TTM。
- 年报字段使用 `end_type=4`；`book_to_market_ratio_lf` 使用最新已公告资产负债表权益，不把它误写成年报字段。
- 平台字段没有可验证的字节级等价物时，必须标记为 proxy；不能把 Tushare 字段名当成平台字段定义的证明。

## 财务代理修正（financialfix1）

- `GR_ROE_TTM` 使用 TTM 归母净利润除以平均公告股东权益，再与同一标的约 252 个交易日前的 PIT 比值计算同比增长；这是对平台 `gr_roe_ttm` 的可复现代理，不再把 ROE 水平误当成增长率。
- `OPER_ROA_NET_TTM` 使用 TTM 净利润除以公告总资产，并在日度 PIT 比值上执行严格 `TS_RANK(...,756)`；不再直接把 `fina_indicator.roa` 当作 TTM ROA。
- `OPER_OPER_PROFIT_TO_TP_TTM` 使用 TTM 营业利润 / TTM 净利润作为可用的分母代理，并在日度 PIT 比值上执行严格 `TS_RANK(...,756)`；当前缓存没有 `total_profit`，因此该项仍标记为 proxy。
- 以上两项先做时间序列变换，再做信号日横截面排名；旧版本报告保留在原输出目录，不覆盖。

## 指数移动平均修正（financialfix2）

- `EMA(X,N)` 使用标准递归 EMA，平滑系数为 `2/(N+1)`，并要求每只股票先积累 `N` 个有效观测；它不等同于手工展开的有限 `exp(-k/tau)` 权重和。
- 因此 `EMA(TURNOVER * RETURNS(CLOSE,1),63) / EMA(TURNOVER,63)` 与 HT13 的手工 63 日权重公式使用不同 handler；不能再共用同一组 `tau=12` 的有限窗代理。

## 并列值换手代理（tieproxy1）

`CROSS` 和保存的 Python OBV 结果会生成大量完全相同的因子值。平台保存的结果只提供汇总换手和最后一期 Top20，没有逐期持仓或隐藏的并列排序键；从平台换手接近 90% 可以确认平台没有按股票代码稳定保留这些并列值。本地因此对以下三个 handler 在完全相等的因子值内部使用固定种子的逐日伪随机顺序：`rsi_cross30`、`ma20_cross5`、`python_obv`。

- 因子值、RankIC 和毛收益计算仍使用原始值；只有分组成员和换手使用该 tie-break 代理。
- 种子为 `918273`，实现和配置见 `scripts/platform_alignment_rules.py`。
- 这是对平台隐藏排序的可复现代理，不声称恢复平台真实逐期持仓；未观察到并列值证据的 handler 不使用该规则。

## Python 索引语义兼容（pythonindex1）

保存的 `NONHT-MAX5-LOW-21D` Python 因子在平台运行时返回的 MultiIndex 实际排列为
`[date, symbol]`。代码中的 `groupby(level=0)` 因而按交易日分组，而不是按股票分组；
`DELAY` 先按股票生成收益后，`MAX(5)` 的滚动窗口才在同一交易日的股票序列上运行。

本地仅对 `max5_low21` 复现这一已从保存结果验证的运行时行为，其他 Python 因子继续使用各自
的显式 handler。该规则不是对平台 Python API 的普遍推断，配置见
`ALIGNMENT_PYTHON_INDEX_HANDLERS`，并在结果 `fidelity` 中标记。

## 换手可比性诊断（turnoverdiag1）

平台保存结果只有分组汇总换手，没有逐期持仓或逐股票换手明细；本地则根据相邻信号期的实际分组成员交集计算换手。因此，平台和本地换手即使使用相同的年化成本公式，也不必然是同一语义。规则保留两套数值：

- `local_turnover` 和由它计算的 `local_net_excess` 是正式本地复现值；不能用平台摘要换手替换它。
- `platform_turnover` 只作为平台审计字段。`turnover_alignment` 按固定阈值标记 `comparable`、`large_turnover_gap`、`platform_high_local_low` 或 `platform_turnover_over_100`，并保留有符号差值 `turnover_gap_pp = platform_turnover - local_turnover`。
- `platform_turnover_cost_sensitivity` 固定为“本地毛超额减去平台摘要换手年化成本”，只回答“如果本地收益路径不变、仅采用平台换手计成本，净超额会落在哪里”；它是诊断值，不是平台持仓复现值。

当前阈值为：平台换手 `>=85%`、本地换手 `<=50%` 时触发 `platform_high_local_low`；绝对差 `>=25` 个百分点时触发 `large_turnover_gap`；平台换手超过 `100%` 时触发 `platform_turnover_over_100`。平台没有逐期持仓文件时，不得为了抹平净超额差异反向修改因子值、标签、复权或股票池。

## 大差异质量门槛（qualitygate1）

本地因子挖掘只使用已经证明与平台结果足够接近的记录。质量门槛同时检查净超额、毛超额、RankIC、最新 Top20 和有效信号期覆盖；不能只因为把平台换手代入成本后净超额接近，就把字段或收益路径不一致的因子当成已对齐。

| 字段 | 阈值 |
|---|---:|
| 净超额绝对差告警 | `5pp` |
| 毛超额绝对差告警 | `5pp` |
| RankIC 绝对差告警 | `0.02` |
| Top20 最低重合 | `15/20` |
| 有效期覆盖率最低 | `95%` |
| 换手主导的敏感性残差 | `2pp` |

每条本地结果写入 `alignment_quality`：

- `aligned`：上述路径指标在阈值内；只有换手也 `comparable` 时才写入 `local_mining_eligible=true`。
- `turnover_dominant`：净超额差较大，但毛超额、RankIC、Top20、有效期都对得上，且差异可由平台汇总换手敏感性解释；只能做收益路径诊断，不进入净超额挖掘。
- `field_or_path_mismatch`：字段语义、复权/停牌/标签路径或排序结果仍有明显差异；禁止进入本地挖掘候选池。
- `unsupported`：本地没有有效计算结果；禁止进入本地挖掘候选池。

`AMOUNT/VOLUME/HIGH` 的当前 qfq 高价代理已被保存结果证明排名不一致，因此暂时回到 `unsupported`，直到拿到可验证的字段语义映射。旧版本结果目录保留作诊断，不能和新质量门槛版本混合。

## 逐期 IC 一致性门槛（qualitygate2）

qualitygate1 把"最新一期 Top20 重合度 ≥ 15/20"当作硬门槛。诊断显示这条才是大部分
`field_or_path_mismatch` 的真正原因：最新一期的最高因子值恰好落在字段语义差异最大的极端尾部
（换手率的分母口径、账面权益的入账口径），而净超额、毛超额、RankIC、换手水平和有效期覆盖
其实都对得上。对组合预筛来说，这些因子是有用的；被挡住只是尾部一期的敏感性。

qualitygate2 因此改为用**平台已保存的逐期 RankIC 图表序列**与本地逐期 RankIC 比较：

| 指标 | 阈值 |
|---|---:|
| 逐期 RankIC 相关系数 | `>= 0.50` |
| 逐期 RankIC 平均绝对差 | `<= 0.06` |
| 可比期数 | `>= 20` |

- Top20 重合度降级为诊断标记 `low_top20_overlap` / `missing_top20_overlap`，写入结果但不再单独否决记录。
- 其余门槛不变：净超额 5pp、毛超额 5pp、RankIC 差 0.02、有效期覆盖 95%、换手可比性。
- 标定证据（`calib_qualitygate2` 目录）：已知对齐记录的逐期相关系数为 0.906–0.997、平均绝对差 ≤ 0.039；本次被 Top20 拦下的 TURN-BIAS-1M、VALUE-BP、VALUE-SP 分别为 0.998/0.997/0.999 与 0.006/0.015/0.008，恢复为 `aligned`；真正不一致的 NONHT-RESVOL-LOW（0.887 / 0.070）与 NEW-VALUE-EVEBITDA（−0.322 / 0.103）仍然被拦下。
- 平台图表期数少到无法计算逐期一致性时（< 20 期），回退到旧的 Top20 硬门槛，并写入 `ic_series_unavailable_top20_fallback` 诊断标记；不会因为"没有证据"而放进挖掘池。
- 恢复的记录仍然带 `low_top20_overlap` 诊断标记，用于组合预筛时必须显式说明尾部一期选股不可复现。
- 旧 `qualitygate1` 结果目录保留，不与本版本混合统计。

全量重算结果：`qualitygate1` 可挖掘 76/160 条，`qualitygate2` 为 143/164 条；仍有 21 条被拦，原因是真实的净额/毛额偏差（如 T10-ADD-G13 −6.0pp）、逐期 IC 序列不一致（RESVOL、LOW-BETA、VWAP 组合等）、平台图表缺失（动量 120D-D0）或换手不可比（HT13-EXPWRET-6M）。

### 净超额一致性分级（net_close / net_proxy）

5pp 的拦截线只回答"能不能用"，不回答"绝对收益可不可信"。因此对可挖掘记录再分两级：

| 分级 | 条件 | 用途 |
|---|---|---|
| `net_close` | \|本地 − 平台净超额\| ≤ `2pp` | 可直接按其净超额排名与比较水平 |
| `net_proxy` | `2pp` < \|差\| < `5pp` | 保留在候选集中，但绝对收益带已知偏移；只用于相对排名与结构（相关、换手、方向）判断 |
| 拦截 | \|差\| ≥ `5pp` | 不进入挖掘池 |

- `net_proxy` 记录带 `net_proxy_offset` 标记；结果表另列 `net_tier` 字段。
- 组合预筛必须输出每条候选里 `net_close` / `net_proxy` 的成员数，以及 proxy 中偏移最大的成员和偏移值。
- 本地组合预筛的绝对净超额一律按"下限"阅读：已验证的两个五成员池（F-P260921-01、F-P260921-06）平台结果比本地高 `+6.5pp` / `+5.1pp`，所以预筛只用于排序，最终结论必须由平台实测确认。

## 股票池过滤与复利年化（qualitygate3）

qualitygate2 之后仍有 2–6pp 的系统性缺口：本地净超额一致低于平台。逐条排查后定位到两处口径差，
两处都与因子信号无关，属于组合构造层面。

**一、股票池过滤。** 平台的组合不持有 ST 与次新股，本地面板此前两者都保留。以 SIZE 单因子的最小市值
十分组为例（2021-09-07–2026-09-07，复利年化）：

| 口径 | 分组年化 |
|---|---:|
| 全样本（旧） | 28.49% |
| 剔除 ST | 31.13% |
| 剔除 ST + 上市未满一年 | 31.75% |
| 平台保存的分组1 | 34.02% |

本地因此按逐日 ST 状态（`stock_basic/namechange.parquet`，由 `scripts/fetch_tushare_namechange.py`
从 Tushare 拉取，token 只从环境变量读取、不入库）与 `stock_basic.list_date` 过滤股票池；
`FACTOR_LOCAL_UNIVERSE_FILTER=off` 可关闭该过滤用于诊断。

**证据强度提示。** 这条过滤是**由收益水平拟合推断**的，不是平台侧的直接证据：平台保存的
`query_last_date_top_factor` 里确实出现 ST 名称（例如 2026-09-04 的 `*ST瑞茂`、`*ST卓然`，
经 PIT 更名记录核实当天就是 ST），但该列表是"因子值最高端"，对方向 0 的因子并不是持仓端
（SIZE 的列表全是工商银行/建设银行等最大市值股，而组合持有的是最小市值端），因此它只说明
平台**展示截面**包含 ST，不能证明平台**组合**包含 ST。判别实验：VALUE-BP（方向 1，高端即持仓端）
开过滤净额差 +0.49pp、关过滤 −0.35pp；SIZE 最小市值分组开过滤 31.75%、关过滤 28.49%（平台 34.02%）。
两个实验都不反驳该过滤，但都不足以定论；若平台页面给出分组口径说明，应以其为准并重跑。

**二、复利年化。** 旧口径把每期超额直接求和再除以年数，平台则是把持有组和基准两条腿分别复利、
分别年化后相减。对高波动组合，求和口径会系统性低估年化收益（SIZE 分组低估约 5pp）。

两处修正后抽样对照：

| 因子 | 旧净额差 | 新净额差 |
|---|---:|---:|
| SIZE-ONLY | −4.27pp | **+0.27pp** |
| H03-T10-SINGLE | −2.18pp | +1.66pp |
| HT13-TURN-BIAS-1M | −1.27pp | +1.93pp |
| NONHT-CHIP-COST-250 | −1.65pp | +1.79pp |

系统性低估消失，残差转为约 +1.5pp 的轻微高估（可能来自仍缺失的停牌/一字板处理）。规则版本因此
递增为 `qualitygate3`，旧 `qualitygate1/2` 目录保留，不混合统计。

## 逐期 IC 幅度归一化门槛（qualitygate4）

`qualitygate2/3` 用本地逐期 RankIC 与平台保存图表的**平均绝对差 ≤ 0.06** 判定字段/路径是否一致。
`F-NET01`（`WMA((((1/LOW)/LOW)/VOLUME),40)`）暴露了这条门槛的一个盲点：平台自己保存的两条 RankIC 序列
**幅度不一致**——图表序列 std 为 `0.149`（cycle5）/`0.163`（cycle10），而同一结果里的 `Rank_IC / IC_IR`
隐含 std 为 `0.190 / 0.195`。本地逐期 IC std 是 `0.193 / 0.212`，匹配的是**指标隐含幅度**。
于是即使逐期排序一致（Spearman 秩相关 `0.894 / 0.888`），原始平均绝对差仍被振幅差顶到 `0.065–0.081`。

qualitygate4 因此把这一步拆成"形状 + 幅度归一化残差"：

| 指标 | 阈值 |
|---|---:|
| 逐期 RankIC 相关系数（Pearson） | `>= 0.50` |
| 逐期 RankIC 秩相关（Spearman） | `>= 0.50` |
| 幅度归一化残差 `mean(abs(beta*local - platform))`，`beta` 为 platform 对 local 的 OLS 斜率 | `<= 0.06` |

- 原始平均绝对差继续记录；当它超过 `0.06` 而幅度比 `|std_local/std_platform - 1|` 超过 `0.20` 时，
  只写诊断标记 `ic_chart_scale_gap`，不再单独否决记录。
- 归一化只剥掉**振幅**：水平偏移、形状不一致仍然会顶高归一化残差。
  `beta = rho*sigma_p/sigma_l` 时残差 std 的闭式解为 `sigma_p*sqrt(1-rho^2)`，因此该判据实际要求
  "形状相关 + 平台图表幅度可控"两个条件同时成立。
- 旧记录若缺少新字段，自动回退到 qualitygate2/3 的原始比较，行为与旧版本一致；不会因为"没有新字段"而放宽。
- 标定预览（`qualitygate4_preview_20260924.py`，解析估计）：164 条记录中 149 条本来就是 `aligned`，
  规则变化只影响 2 条：`F-B06-260921-T10` 转 `aligned`（带 `ic_chart_scale_gap`），
  `F-NET01-PLAT-20260914` 的 IC 侧通过但仍被自身净额差（5 日口径 `+5.5pp`）挡住；
  被拦的 `VWAP10-VOL20-MOM20-RAW`（相关 `0.506`）与 `HT13-NEW-HIST-OPPROFIT-6Q`（相关 `0.339`）保持被拦。
- 只重跑了 `F-NET01` 家族两条记录到目录
  `all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate4/`；
  这是**局部**质量门槛回归，不是全量重算，不能和 qualitygate3 的全量统计混合。
  完整诊断见 [`fnet01-alignment-20260924/summary.md`](./fnet01-alignment-20260924/summary.md)。
- 该版本同时确认：平台保存的"最新一期 Top20"可能是**退化尾部**（20 条因子值完全相同，且多为 ST 名），
  此时 `low_top20_overlap` 不具判别力——它本来就是诊断标记，不能单独否决记录。

### 平台不支持的因子族

平台已明确表示不支持 Barra 类风险字段。这类记录不再计入"本地/平台差异"：本地代理永远没有可对标的
平台定义，所以单列为 `platform_unsupported`，不进入候选池，也不在失败登记中占位。当前名单见
`ALIGNMENT_PLATFORM_UNSUPPORTED_HANDLERS`：`residual_volatility`、`residual_volatility_max_interact`、
`beta_low`（对应 NONHT-RESVOL-LOW、NONHT-RESVOL-MAX-INTERACT-21D、NONHT-LOW-BETA 三条）。
此前为对齐 RESVOL 试过的 252/126 日、等权/市值加权市场四个变体因此作废：
`FACTOR_LOCAL_RESVOL_VARIANT` 保留仅为诊断开关，默认 `ew252` 不变。

### 字段投影与载荷解析修复（qualitygate3 补充）

两轮排查发现"缺数据"多数其实是本地读取路径的问题，修复后不必重拉 Tushare：

- **财务列投影**：`load_financial_cache` 只读取 `_FINANCIAL_VALUE_COLUMNS` 列出的字段，导致
  资产负债表的 `st_borr/lt_borr/bond_payable/non_cur_liab_due_1y/lease_liab`、利润表的
  `total_profit`、现金流的折旧摊销三项虽然已在缓存里（资产负债表共 158 列）却没有进入本地信号。
  现已补齐：EV 改用有息负债而非总负债；EBITDA 缺失时用 `EBIT + 折旧摊销` 重建。
- **分母取错表**：`TS_RANK(oper_oper_profit_to_tp_ttm,756)` 的分母此前从资产负债表取（该表没有此字段），
  永远算不出值；`_ttm_ratio_history` 增加 `denominator_source` 参数后改为从利润表取 TTM 利润总额，
  该记录本地净额差从"无法计算"变为 −0.53pp。
- **载荷结构**：`factor_result` 返回的分析 JSON 位于顶层 `factor_analysis`，旧解析器只认
  `results.factor_analysis`，导致部分记录被误判为"平台无图表"。解析器现同时支持两种结构；
  两份被截断的本地保存（HT13-MOMENTUM-120D-D0、WF6AA4-D0-OPEN20-MOM-20260912）已用只读的
  `factor_result` 重新拉取，`scripts/refresh_saved_platform_runs.py` 可复现该修复。
- **逐期 IC 最少期数**：从 20 期降到 10 期。平台部分保存只有 10–16 期图表，要求 20 期会把它们退回
  单期 Top20 门槛；现在这类记录仍须同时通过相关系数 ≥0.5 与平均绝对差 ≤0.06。

本轮结束后：可挖掘 147 条，`field_or_path_mismatch` 14 条，`platform_unsupported` 3 条；
`|净额差|` 中位 0.95pp、均值 1.18pp，其中 118 条属于 `net_close`。剩余 14 条均为真实的收益路径差
（>5pp）、信号定义差或平台换手口径不同，不再是本地读取问题。

### EV / CFP / Barra 字段的后续修复

- **EV 单位越界（重要）**：`daily_basic.total_mv` 的单位是万元，资产负债表的有息负债与货币资金是元。
  二者直接相加减使 `ratio_ev_ebitda_ttm` 的本地代理在 51% 的截面上变成负值、排序近乎随机。
  统一到万元后，`NEW-VALUE-EVEBITDA` 的逐期 IC 相关从 **−0.53 提升到 +0.96**、RankIC 差 −0.005，
  直接进入 `aligned`。任何"市值与报表项相加/相减"的新因子都必须先统一单位。
- **CFP 代理改选**：`ratio_cfp_ttm`（现金收益率ttm）此前用自建 `ocf_ttm_mv`（逐期 IC 相关 0.837、
  平均差 0.063，超 0.06 门槛）；改用厂商 CFPS/现价口径 `cfps_cur_price` 后为 0.906 / 0.049，
  `OSR4-RET40-BP-CFP-TSRANK756` 进入 `aligned`。覆盖开关为 `FACTOR_LOCAL_CFP_PROXY`。
- **`profitability` 属于 Barra 因子表**（`references/fields-barra.md`，与 beta、residual_volatility 同表），
  因此 `paper-derived-profitability` 从 `field_or_path_mismatch` 改判为 `platform_unsupported`，
  不再计入"可修差异"。

本轮后：可挖掘 **149** 条，`field_or_path_mismatch` 11 条，`platform_unsupported` 4 条。

## 本地挖掘字段边界

`local_mining_eligible=true` 的 76 条记录是当前本地净超额挖掘的验证样本。GP/GFN 默认只从 `scripts/platform_alignment_rules.py` 中的 `ALIGNMENT_VERIFIED_SEARCH_FIELDS` 取命名字段；未验证的 PandaAI 声明字段仍可在字段覆盖报告中查看，但不能悄悄进入对齐搜索。需要研究未验证字段时必须显式开启诊断模式，并把结果标记为未验证代理。

AlphaPROBE GFlowNet 的 `VWAP` 是本地 `AMOUNT/VOLUME` 计算得到的特征，不属于已验证的 PandaAI 命名字段。它只能作为本地搜索特征，提交平台前必须改写为平台可接受的公式（例如 `AMOUNT/VOLUME`），且改写后的公式仍需单独在线验证。

## 不可接受差异的字段归因

净超额绝对差 `>5pp` 才记为硬失败；`<=5pp` 记录可以继续作为净超额口径的可接受样本，但 Top20、RankIC、毛超额和换手差异仍保留为诊断信息。

每次正式复现后运行：

```bash
python scripts/build_alignment_failure_registry.py
```

脚本生成 [`factor_alignment_failure_registry.json`](./factor_alignment_failure_registry.json) 和对应 Markdown 报告。每条硬失败记录至少保存：公式字段、算子、净/毛超额差、换手敏感性、Top20、RankIC、有效期覆盖、原因代码和字段归因置信度。字段只因出现在失败公式中不会自动拉黑；至少两条 `>5pp` 失败且没有任何 `<=5pp` 通过证据时，才进入 `blocked_fields`。

GP/GFN 默认不使用登记表中的 `blocked_fields`。需要复查被拉黑字段时，必须显式使用 `--allow-blocked-fields`，并将该轮标记为诊断模式。当前登记表没有足够证据全局拉黑已验证的 `CLOSE`、`HIGH`、`AMOUNT`、`VOLUME`、`TURNOVER` 或 `MARKET_CAP`；已有单字段隔离结果显示不能把组合失败错误归因给这些单个字段。

CFP 组合使用经过同一评估器诊断的公式级代理：

| handler | 代理 |
|---|---|
| `reversal_bm_cfp` | `cfps_lyr_price` |
| `reversal_bm_cfp_rev2` / `reversal_bm_cfp_rev3` | `ocfps_cur_price` |
| `reversal_bm_cfp_val2` | `cfps_lyr_price` |
| `reversal_bm_cfp_val3` | `cfps_cur_price` |
| `reversal_bm_cfp_sp` / `reversal_bm_cfp_pcf` | `cfps_lyr_price` |
| `reversal_bm_cfp_ma63` | `cfps_cur_price` |
| `reversal_bm_cfp_tsrank756` | `ocf_ttm_mv` |

MA63 和 TS_RANK756 先在每只股票的日度点时序列上做时间序列运算，再进行信号日横截面排序。代理诊断必须使用与正式复现相同的 `factor_valid` 基准，不能用全 A 基准挑选代理后再直接套入正式结果。

## 市场字段规则

- `MARKET_CAP` 默认映射到 `daily_basic.total_mv`。离线敏感性显示 `circ_mv` 明显更差，因此除非另有证据，不切换到 `circ_mv`。
- 冲击类公式优先使用缓存中的 `high_qfq`、`low_qfq`、`amount`；缺失时才使用明确标记的开收盘区间或 `volume × 平均价` 代理。
- `residual_volatility` 是市场模型残差波动率代理，不宣称等价于平台 Barra 字段。
- working-capital、EV/EBITDA 等没有完整平台字段的实现必须在结果 `fidelity` 中保留 proxy 说明。

## 变更纪律

以下任一项改变都必须新建规则版本和输出目录，不能覆盖不同口径的旧结果：

- 标签偏移、交易日历或平台信号日期来源；
- qfq/raw、股票池、`total_mv/circ_mv` 或停牌前向填充处理；
- 组数、方向对应持仓组、基准有效截面或换手成本；
- 公告日、合并报表、TTM 和 CFP 代理映射；
- 平台结果解析方式或年化公式。
- 相关性聚合方法、并列值处理或有效日期筛选规则。

代理字段的选择流程固定为：列出候选代理 -> 使用同一评估器比较全部候选 -> 保存诊断表 -> 更新脚本配置 -> 重新跑完整正收益目录 -> 重新生成总报告。禁止只凭单个因子的 RankIC 或旧口径的净超额选择代理。

## 算子和 handler 层规则

公共回测口径相同，并不意味着同名算子可以随意复用实现。当前已经验证或明确记录的实现边界如下：

- RSI 使用 Wilder 指数平滑（`alpha=1/N`，首个完整窗口后递推），不能用简单滚动均值替代。
- 标准 `EMA(X,N)` 使用递归 EMA，`alpha=2/(N+1)`，每只股票先达到 `N` 个有效观测；平台公式中明确展开的有限指数权重则使用独立的有限窗口 handler，不能和递归 EMA 共用实现。
- `WMA` 的最近观测权重最高；滚动统计、相关、协方差、Beta 和 TS_RANK 都按股票分组并沿日序列计算，不能把横截面和时间序列轴混用。
- 交叉信号（例如 `RSI_CROSS30`、`MA20_CROSS5`）按平台状态信号生成，不把布尔值重新解释成连续强度；完全相同的信号值只在分组成员和换手计算中使用 `tieproxy1` 的固定种子顺序。
- 保存的 Python OBV 结果按每只股票保留原始输出并明确标注解释边界；不能为了提高 Top20 重合而擅自加截面排名。`MAX5` 只对已经验证的 `max5_low21` 使用 `pythonindex1` 的 `[date, symbol]` level-0 兼容语义。
- 需要完整高低价、成交额的冲击因子优先读取缓存的 `high_qfq`、`low_qfq`、`amount`；缺失时使用 open/close 区间或 `volume * average(open, close)`，并在 `fidelity` 中保留代理说明。
- Beta 使用等权全 A 日收益作为本地市场收益代理；`residual_volatility` 使用市场模型残差波动率代理；两者都不宣称等价于平台内部 Barra 字段。
- 每个 handler 的时间序列运算必须先按 `instrument` 完整排序、暖机，再抽取平台信号日做横截面排序；不能先抽取调仓日再做 63/252/756 日滚动。

如果平台结果只保存了汇总指标而没有逐期图表，日期来源必须在结果的 `date_source` 中标记：优先使用该因子的保存图表日期；缺失时使用同周期且有图表的参考模板；最后才允许按交易日历生成同周期日期。不能把这种回退结果和完整平台图表结果假定为同等证据。

本地横截面只有在有效因子值和未来收益都存在时才进入排序；少于 `10 * groups` 个有效标的的信号期跳过，并在结果中保留有效期数。无效期不能用零收益补齐，也不能为了增加样本把全 A 基准重新引入。

## 标准命令

正式全量复现：

```bash
python scripts/positive_factor_local_compare.py \
  --universe full_a \
  --market-cap-field total_mv \
  --data-start 20180101 \
  --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches \
  --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a \
  --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a \
  --output quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1 \
  --platform-net-filter all \
  --label-offset 1
```

CFP 代理诊断：

```bash
python scripts/diagnose_financial_field_proxies.py
```

两条命令都只读取本地缓存和已保存平台结果，不读取 PandaAI token，也不消耗平台算力。

## 当前基线

`full-a-qfq-label1-v1` 的旧基线和新规则输出必须分目录保存。`qualitygate1` 全量结果目录为
`all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1/`；
`turnoverdiag1` 旧版结果目录仍保留，不再作为当前 handler 结论；
`pythonindex1` 旧版本结果仍保留在 `all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1/`；
旧基线详细结果仍见
[`positive_factor_alignment_20260914.md`](./positive_factor_alignment_20260914.md)。

`pythonindex1` 历史全量结果仍是保存平台记录 `163` 条、本地有 handler `158` 条、当前缓存不支持 `5` 条；
`qualitygate1` 全量结果以当前 handler 逻辑重新生成；报告同时写出质量状态和 `local_mining_eligible`。完整换手/质量诊断见
[`turnover_alignment_diagnosis_20260917_qualitygate1.md`](./turnover_alignment_diagnosis_20260917_qualitygate1.md)。平台换手成本敏感性不能与正式本地净超额混在一起统计。

剩余最大差异中，`HT13-EXPWRET-6M` 的 RankIC 为 `0.0991/0.1004`、Top20 为 `19/20`，
但平台/本地换手为 `216.73%/45.50%`，属于平台换手字段异常，不能反向修改因子；按平台换手计成本的敏感性可以解释其中大部分净超额差，但仍不能证明逐期持仓一致。T10
冲击/规模组合的 RankIC 和 Top20 已接近，但毛超额仍差约 `4~6pp`，更可能是平台内部
high/low/amount、停牌处理或收益路径口径差异，当前没有证据支持切换 `total_mv` 或 qfq。

EV/价格这一类因子的收益路径差异较小，但平台换手 `89.85%`、本地换手约 `3.38%`，按平台换手计成本后本地敏感性净超额约为 `-24.97%`，接近平台 `-25.49%`。这说明该条的主要差距来自成本/换手口径，而不是收益路径；没有逐期持仓数据时，仍标记为换手不可完全等价。

其余大差异主要来自市场冲击/行情字段、复权与停牌处理，以及平台内部财务和 Barra 字段的语义差异；不能仅靠继续替换 CFP 代理声称已经抹平。

## 复现前强制检查

这份文档和 [`scripts/platform_alignment_rules.py`](../../scripts/platform_alignment_rules.py) 是以后所有本地复现的契约，适用于已经保存的平台因子和之后新增的平台因子。新增因子可以增加 handler 或代理，但不能自行改变公共口径；若公式需要新语义，只能在结果中标注 `proxy`，并按变更纪律升级版本。

换电脑或恢复数据后，先在项目根目录执行：

```bash
git lfs install
git lfs pull
python scripts/local_recheck_data.py verify --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py import --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py verify
python scripts/validate_platform_alignment.py --check-snapshot
```

正式复现入口会在读取大盘数据前再次校验核心配置；校验失败时不得通过改参数硬跑。若数据放在独立目录，必须在当前进程设置 `FACTOR_RESEARCH_CACHE_ROOT`，并用同一变量运行校验和复现命令：

```bash
export FACTOR_RESEARCH_CACHE_ROOT=/data/factor/cn_equity
python scripts/validate_platform_alignment.py
```

校验至少应确认：规则文档存在；qfq `daily_batches`、`daily_basic_full_a`、四张 PIT 财务表、交易日历和保存的平台结果都存在；若跨电脑迁移，还要确认 LFS 归档和 SHA-256 manifest 已通过验证。

## 禁止混用的口径

- 正式结果不得使用 raw 价格、`circ_mv`、ST pool、自然日调仓、same-day label 或全 A benchmark 代替当前规则。
- 正式全量目录必须读取保存结果中的全部 `net_excess_pct` 记录，即使用 `--platform-net-filter all`；只看正净超额是子集诊断，不是全量复现。
- 不得把方向为 `0` 的持仓底组当成平台 Top20；Top20 永远按最新平台 Top 列表日期的原始因子值降序比较。
- 不得把平台 headline 长短收益、平台 `excessAnnualized`、本地毛超额、本地净超额和换手成本混成一个指标；报告必须分别保留原始平台值和本地代理值。
- 不得用全 A 基准或另一版标签选择财务/CFP 代理后直接套入当前结果；候选代理必须在同一 `factor_valid`、同一标签和同一规则版本下比较，并保存诊断表。
- 不得把“RankIC 接近”解释为字段字节等价，也不得为了抹平单因子差异擅自切换复权、市场规模字段、停牌处理或平台隐藏排序。
- 正式净超额只能使用本地实际成员换手；平台换手成本敏感性必须单独命名、单独报告，并在 `turnover_alignment` 为非 `comparable` 时提示语义不一致。
- 不得将不同规则版本放在同一输出目录或混合计算均值。正式脚本发现目录已有不同版本 metadata 时会停止，而不是覆盖旧结果。

## 新因子接入约定

新增因子接入本地 handler 时必须同时记录：平台公式、方向、调仓周期、保存的平台信号日期来源、所需基础字段、是否使用财务/Barra/盘中字段、每个 proxy 的具体映射、缺失值处理、时间序列暖机长度和 fidelity 说明。时间序列算子先沿每只股票的日度序列计算，再在信号日做横截面排序；只有已经有证据的 Python index 异常或并列值异常才能使用对应的兼容代理。

新因子的比较流程固定为：先读取本契约 -> 使用相同 qfq/full-A/`total_mv`/label-1/10 组/`factor_valid`/成本口径 -> 复现全部保存结果中的该因子 -> 同时报告 RankIC、IC、方向对应组的毛超额、净超额、换手、Top20 和有效期数 -> 标记 proxy 与不可复现原因。短样本（尤其只有少量调仓期的 2026 YTD）只能作为诊断，不能单独证明对齐。

如果发现新的、可重复验证的公共语义差异，先保存最小诊断和对照结果，再修改配置；修改后递增 `ALIGNMENT_RULE_VERSION`，建立带新版本的输出目录，并重新生成受影响的全量报告。没有完成这一步时，旧结果仍按旧版本解释。
