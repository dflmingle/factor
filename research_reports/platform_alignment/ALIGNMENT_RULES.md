# 平台/本地对齐规则

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1`<br>
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
  --output quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1 \
  --platform-net-filter all \
  --label-offset 1
```

CFP 代理诊断：

```bash
python scripts/diagnose_financial_field_proxies.py
```

两条命令都只读取本地缓存和已保存平台结果，不读取 PandaAI token，也不消耗平台算力。

## 当前基线

`full-a-qfq-label1-v1` 的旧基线和新规则输出必须分目录保存。`pythonindex1` 全量结果目录为
`all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1/`；旧基线详细结果仍见
[`positive_factor_alignment_20260914.md`](./positive_factor_alignment_20260914.md)。

本次全量结果：保存平台记录 `163` 条，本地有 handler `158` 条，当前缓存仍不支持 `5` 条；
其中 `157` 条能产出有效净超额。与旧 `parserfix1` 结果相比，`MAX5` 的绝对净超额差从
`6.16pp` 降到 `0.45pp`；全量有效记录的平均绝对差从 `2.36pp` 降到 `2.32pp`，绝对差
达到 `5pp` 及以上的记录从 `10` 条降到 `9` 条。

剩余最大差异中，`HT13-EXPWRET-6M` 的 RankIC 为 `0.0991/0.1004`、Top20 为 `19/20`，
但平台/本地换手为 `216.73%/45.50%`，属于平台换手字段异常，不能反向修改因子；T10
冲击/规模组合的 RankIC 和 Top20 已接近，但毛超额仍差约 `4~6pp`，更可能是平台内部
high/low/amount、停牌处理或收益路径口径差异，当前没有证据支持切换 `total_mv` 或 qfq。

剩余大差异主要来自市场冲击/行情字段、复权与停牌处理，以及平台内部财务和 Barra 字段的语义差异；不能仅靠继续替换 CFP 代理声称已经抹平。

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
- 不得将不同规则版本放在同一输出目录或混合计算均值。正式脚本发现目录已有不同版本 metadata 时会停止，而不是覆盖旧结果。

## 新因子接入约定

新增因子接入本地 handler 时必须同时记录：平台公式、方向、调仓周期、保存的平台信号日期来源、所需基础字段、是否使用财务/Barra/盘中字段、每个 proxy 的具体映射、缺失值处理、时间序列暖机长度和 fidelity 说明。时间序列算子先沿每只股票的日度序列计算，再在信号日做横截面排序；只有已经有证据的 Python index 异常或并列值异常才能使用对应的兼容代理。

新因子的比较流程固定为：先读取本契约 -> 使用相同 qfq/full-A/`total_mv`/label-1/10 组/`factor_valid`/成本口径 -> 复现全部保存结果中的该因子 -> 同时报告 RankIC、IC、方向对应组的毛超额、净超额、换手、Top20 和有效期数 -> 标记 proxy 与不可复现原因。短样本（尤其只有少量调仓期的 2026 YTD）只能作为诊断，不能单独证明对齐。

如果发现新的、可重复验证的公共语义差异，先保存最小诊断和对照结果，再修改配置；修改后递增 `ALIGNMENT_RULE_VERSION`，建立带新版本的输出目录，并重新生成受影响的全量报告。没有完成这一步时，旧结果仍按旧版本解释。
