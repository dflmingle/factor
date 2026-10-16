# 精选研报库

这里存放后续因子研究会反复使用的精选研报，不限定于超跌反弹。

## 目录

- [本周总览：2026-10-10至10-16](./weekly-20261010-20261016.md)：策略库覆盖、平台候选、对手复刻、论文实验、账本修正及换机边界；以修正后的证据等级为准。
- [`literature/advances-fml-meta-label-20261016-ledger-v2/report.md`](./literature/advances-fml-meta-label-20261016-ledger-v2/report.md)：Meta-label 账本审计修正；完整买卖成本、连续漂移持仓、共同支持集与 qfq 标签重算后，五席算术净年超额 16.03%→16.09%，原约 +3.40pp 改善未保留；独立现金/份额账本复核，零平台算力。
- [`selected/huatai-multifactor-series13/`](./selected/huatai-multifactor-series13/)：华泰证券 2016--2019 年多因子系列 13 篇的完整副本，包含 PDF 和可检索 TXT。
- [`short_reversal/`](./short_reversal/)：从上述资料中筛出的短期反转专题资料，并附有外部论文索引。
- [`market_behavior/`](./market_behavior/)：洗盘、出货、主力资金、大单和高频订单行为研究。
- [`platform_alignment/ALIGNMENT_RULES.md`](./platform_alignment/ALIGNMENT_RULES.md)：PandaAI 平台结果与本地 Tushare 重建的固定对齐口径和变更纪律。
- [`platform_alignment/quant-corpus-coverage-audit-20261015/summary.md`](./platform_alignment/quant-corpus-coverage-audit-20261015/summary.md)：策略库覆盖与成果核查；补齐此前未入总表的1126行既有三控制结果索引，保留215来源障碍复核队列；未发现新强入池因子，不宣称全策略复现完成。
- [`platform_alignment/strategy-factor-mining-supplement-20261014/summary.md`](./platform_alignment/strategy-factor-mining-supplement-20261014/summary.md)：策略库补测14条财务与价量交互规格；保留季节收入惊喜的弱增量，记录双窗口、相关簇、旧五席组合和证伪结果。
- [`platform_alignment/revenue-seasonal-pool-20261014/summary.md`](./platform_alignment/revenue-seasonal-pool-20261014/summary.md)：平台已验证季节收入惊喜三项控制版的本地池级加席及全五席替换；加席净超额20.33%→20.23%，两条BM换席小幅提收益但五年积分代理均负，候选s_i仅0.00154；零算力，不推进正式池。
- [`platform_alignment/revenue-seasonal-platform-20261014/budget14-summary.md`](./platform_alignment/revenue-seasonal-platform-20261014/budget14-summary.md)：季节收入惊喜通过官方上传 Tushare PIT 信号跑通，原始/三控制/六控制五年净超额1.13%/5.88%/4.80%；追加授权实际10点，累计26点；原生历史字段仍未修复，不作纳池或新簇结论。
- [`wu-factor-timing-v2-20261014/summary.md`](./wu-factor-timing-v2-20261014/summary.md)：Wu（2024）中国股票因子择时的本地代理复现；24 个因子、月度回归与聚类择时、成本和延迟执行诊断。
- [`literature/wu-china-factor-timing-20261014/method_mapping.md`](./literature/wu-china-factor-timing-20261014/method_mapping.md)：上述论文出版全文、方法映射，以及不能声称原文数值完整复现的差异清单。

## 主题导航

- [策略分红层补全研究（2026-10-15）](./platform_alignment/quant-corpus-dividend-completion-20261015/summary.md)：补下载历史实施分红，6条适配＋3条同支持消融，双窗口、三风格剥离、旧簇相关与全部6条本地加席诊断；最佳五年净超额2.72%，均未达入池门槛，零平台算力。

| 主题 | 重点报告 | 可研究方向 |
|---|---|---|
| 估值 | 系列二、十三 | 价值、相对估值、估值历史分位数 |
| 成长 | 系列三 | 收入、利润、现金流增长 |
| 财务质量 | 系列八、十三 | 盈利能力、收益质量、现金流、周转率 |
| 动量与反转 | 系列四 | 价格反转、换手率加权、衰减加权 |
| 换手率与流动性 | 系列五 | 换手率水平、乖离率、波动和低拥挤 |
| 波动率 | 系列六 | 波动率、风险暴露和波动反转 |
| 资金流向 | 系列七 | 资金流、价量关系和流动性冲击 |
| 一致预期 | 系列九 | 盈利预测、分析师修订和关注度 |
| 因子合成 | 系列十 | 等权、IC/ICIR 加权、半衰和 PCA |
| 技术因子 | 系列十一 | 价量背离、技术指标和反转确认 |
| 风险模型 | 系列十二 | 风险暴露、中性化和组合约束 |

原始下载/转换资料继续保留在 `sources/huatai-multifactor/series13/`，这里的文件用于研究归档和检索。研报结论只作为候选假设，实际使用前仍需在统一的 5 年窗口、固定调仓周期和交易成本假设下验证。
