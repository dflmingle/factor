# 疯猫单因子复现：新增文献、开源与博客检索

2026-10-11。只检索公共资料，只在本地研究；没有创建/运行平台因子，没有动现役池。检索原始返回保存在 `sources.json`、`followup_sources.json`、`alpha101_sources.json`（包含失败请求），只保存读取第三方源码文本，没有执行第三方代码。

## 有证据的新方向

| 来源 | 实际读取范围 | 可转化的本地结构与限制 |
|---|---|---|
| [A tug of war: Overnight versus intraday expected returns](https://doi.org/10.1016/j.jfineco.2019.03.011) (2019) | OpenAlex 书目；摘要未返回，未取得全文 | 日内/隔夜分解是待验证假设，不宣称已读懂全文的全部结果 |
| [Intraday momentum and reversal in Chinese stock market](https://doi.org/10.1016/j.frl.2019.04.002) (2019) | OpenAlex 书目；未取得全文 | 提示中国市场相关性；日频 OHLC 分解不能精确复现该论文的盘中策略 |
| [Text-Based Industry Momentum](https://doi.org/10.1017/s0022109018000479) (2018) | 书目与摘要 | 摘要强调低可见性产品文本同伴冲击；本地只有量/波动分桶同伴，不等价于文本网络同伴 |
| [Does Investor Attention Affect Stock Trading and Returns? Evidence from Publicly Listed Firms in China](https://doi.org/10.1080/15427560.2020.1785469) (2020) | 书目 | 注意力/异常量方向候选；成交量不能宣称等价于注意力数据 |
| [AlphaCFG](https://github.com/HanYang544/AlphaCFG) | README、仓库元信息、`alphacfg/mcts_core.py` | Grammar + PUCT；适配为固定低复杂度语法与 3 种子预算。不是原版神经策略网络训练/论文成绩复现 |
| [FaVOR](https://github.com/damilab/FaVOR) | README、仓库元信息 | 假设→可观测条件→公式；先做截断、语义和反证。没有运行其收费 LLM/API 管线 |
| [AlphaGen](https://github.com/RL-MLDM/alphagen) / [Qlib](https://github.com/microsoft/qlib) | README 与元信息 | 项目内已有 PPO/GFN/pool 路线结果；本轮不重复旧特征空间，不切 raw 数据或默认标签 |
| [Alphalens](https://quantopian.github.io/alphalens/alphalens.html) | 文档 HTML | IC、分组、换手作为独立诊断；不搬用默认 label/成本配置 |
| [QuantConnect: Overnight Anomaly](https://www.quantconnect.com/research/15296/overnight-anomaly/) | 博客正文 | SPY 收盘买、次日开盘卖；正文明确提示高频换仓对成本敏感。它不是 A 股横截面因子、不能将其收益迁移到本比赛 |
| [101 Formulaic Alphas](https://arxiv.org/abs/1601.00991)；[公开示例代码](https://github.com/yli188/WorldQuant_alpha101_code) | OpenAlex 书目与示例源码 | `alpha002` 是先 rank 再 6 日量价相关。但该仓库 `rank(df)` 实际 `df.rank(pct=True)` 默认 axis=0，与其“cross sectional”注释矛盾；不可照搬，必须显式每日 axis=1。文章未取得全文，公式锚点来自代码 |

网页质量核对：两个 Quantpedia 拟定文章链接返回通用首页，未读到目标文章，不作为论据；其 WP 搜索接口与 QuantStart 请求失败，亦不当作已读来源。网络资料只提供结构灵感，不提供对手公式证据。

## 已执行与正在执行

- `fengmao-paper-hypotheses-20261011`：246 个结构候选完成，6 个家庭冻结；独立复核 18 组指标通过。日内反转 × 下跌成交量状态、日内反转 × MACD 状态有诊断价值，但全部未匹配公开目标。
- `fengmao-information-shock-20261011`：730 个候选预声明，原始日频 volume surprise、量价相关、日内/隔夜拆分、组内 leave-one-out 过去收益差；正式 120 期与对手推定 119 期严格分开。
- `fengmao-grammar-mcts-20261011`：AlphaCFG 启发的本地 PUCT，3 个固定随机种子 × 160 轨迹，不用最终留出标签选型；仅组合因果新原子与已有上下文，不重新训练一批低量低波动复制品。
- `fengmao-information-models-20261011`：新增原子增量验证，14 个正则线性/树检查点；留出表现与旧模型近似，不支持新信息带来显著稳定性增量。
- `fengmao-daily-rankcorr-20261011`：补查 `d3c/r6` 的“每日横截面 Rank → 6 日时序相关”读法，含 Alpha101#2 结构近邻。独立目录，不将 `TS_RANK` 与每日 `RANK` 混同。

## 不变的验收与防止虚假发现

公开 RankIC `0.1722791715`、IR `1.661320605`、111/119 胜必须联合比较；`S_i` 是这三者派生乘积，不是第四条独立证据。缺少对手逐期 IC、持仓和 2026-10 六席池日账，因此本地单席 C 只能代理，不能拿月均 NC 直接和对手池某个月相减。

最后历史段早已被先前研究查看，虽本轮不用于选型，也不能称全新盲测。跨轮搜索数累计增加，内部赢家存在多重选择偏差。本轮同时登记失败候选、分年、去最小市值 20% 反证、既有信号相关和成本；不因为 IC 好看就认为满足 `GOAL.md` 的池级 A+B+C 准入。

副产品只进入研究登记，不提交、不入池。目标未达成时不能宣称找对公式；下一条搜索必须有新信息/新假设而非只扩大相同特征空间。
