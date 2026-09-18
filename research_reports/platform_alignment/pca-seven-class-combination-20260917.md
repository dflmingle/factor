# PCA seven-direction local combination test

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1`；规则文档：`research_reports/platform_alignment/ALIGNMENT_RULES.md`。

这是本地 proxy 组合测试，不是 PandaAI 官方组合回测。组合方法为：每个代表因子先按信号日做截面百分位秩，再按保存的平台方向统一为高分持有，最后等权平均。组合净超额使用组合自身有效股票截面的 `factor_valid` 基准和本地实际成员换手。

## 代表因子

| 统计方向 | handler | 平台方向 | 平台净超额 | 说明 |
|---|---|---:|---:|---|
| 反转/筹码/换手/基本面 | `reversal_chip_turn_paper` | 1 | 12.77% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ；combo-direct-4factor-paper-20260909-candidates.report.csv |
| 冲击/流动性 | `impact_abs_return60` | 1 | 13.94% | VERIFY10-G260910-13；verify-field-scan-cycle10-20260910-candidates.report.csv |
| 价值/账面价值/冲击 | `book_to_market_lf_plus_impact` | 1 | 15.05% | VERIFY10-F260910-12；verify-field-scan-cycle10-20260910-candidates.report.csv |
| 换手方向 | `turn_signal` | 1 | 6.40% | HT13-TURN-BIAS-1M-POS；huatai-turn-bias-positive.report.csv |
| 资产成长 | `asset_growth` | 0 | 0.76% | paper-derived-asset-growth；paper-derived-full.report.csv |
| 质量/财务健康 | `fscore_interact` | 1 | 1.84% | NONHT-FSCORELIKE-REV40-INTERACT；literature-rankic-optimization-20260909-formula.report.csv |
| 残差波动风险 | `residual_volatility` | 1 | 0.37% | NONHT-RESVOL-LOW；nonhuatai-factor-6-20260909.report.csv |
| 动量/波动替代 | `momentum120` | 0 | 2.29% | HT13-MOMENTUM-120D-D0；ht13-momentum-120d-d0.report.csv |

`momentum120` 是 PC7 的替代代表，单独作为敏感性组合测试；它没有替换主组合中的 `residual_volatility`。平台方向为 0 的 `asset_growth`（以及替代的 `momentum120`）在合成前已反向。

## 结果

净超额为算术年化毛超额减本地实际换手成本；Sharpe 和最大回撤是组合持有端、扣除逐期换手成本后的本地风险 proxy。月度胜率统计月度毛超额大于 0 的月份。

| 调仓 | 组合 | 因子数 | 期数 | RankIC | IC | 毛超额 | 换手 | 年化成本 | 净超额 | Sharpe | 最大回撤 | 月胜率 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | single_book_to_market_lf_plus_impact | 1 | 241 | 0.0615 | 0.0341 | 14.60% | 5.75% | 1.74% | 12.86% | 0.8827 | 33.18% | 66.67% |
| 5 | seven_without_fscore_interact | 6 | 241 | 0.0886 | 0.0450 | 16.29% | 12.49% | 3.78% | 12.51% | 0.9267 | 31.38% | 76.67% |
| 5 | seven_without_residual_volatility | 6 | 241 | 0.0910 | 0.0473 | 17.18% | 17.59% | 5.32% | 11.86% | 0.8719 | 34.00% | 75.00% |
| 5 | seven_without_reversal_chip_turn_paper | 6 | 241 | 0.0894 | 0.0442 | 15.92% | 13.42% | 4.06% | 11.86% | 0.9221 | 31.57% | 73.33% |
| 5 | seven_without_asset_growth | 6 | 241 | 0.0991 | 0.0489 | 16.31% | 16.68% | 5.04% | 11.27% | 0.8949 | 31.59% | 71.67% |
| 5 | seven_without_turn_signal | 6 | 241 | 0.0901 | 0.0451 | 15.92% | 16.06% | 4.86% | 11.06% | 0.8639 | 32.77% | 71.67% |
| 5 | seven_equal_residual | 7 | 241 | 0.0953 | 0.0471 | 15.75% | 16.18% | 4.89% | 10.86% | 0.8702 | 31.90% | 68.33% |
| 5 | seven_equal_momentum | 7 | 241 | 0.0919 | 0.0474 | 16.21% | 18.82% | 5.69% | 10.52% | 0.8118 | 34.01% | 66.67% |
| 5 | single_impact_abs_return60 | 1 | 241 | 0.0402 | 0.0310 | 11.36% | 5.38% | 1.63% | 9.73% | 0.7371 | 36.76% | 75.00% |
| 5 | seven_without_book_to_market_lf_plus_impact | 6 | 241 | 0.0954 | 0.0462 | 15.18% | 18.08% | 5.47% | 9.71% | 0.8362 | 32.02% | 73.33% |
| 5 | seven_without_impact_abs_return60 | 6 | 241 | 0.0952 | 0.0441 | 12.99% | 17.74% | 5.37% | 7.62% | 0.7834 | 30.24% | 66.67% |
| 5 | single_reversal_chip_turn_paper | 1 | 241 | 0.0897 | 0.0438 | 14.81% | 24.24% | 7.33% | 7.48% | 0.6940 | 36.17% | 63.33% |
| 5 | single_turn_signal | 1 | 241 | 0.0672 | 0.0305 | 9.86% | 15.13% | 4.57% | 5.29% | 0.7029 | 30.53% | 68.33% |
| 5 | single_residual_volatility | 1 | 241 | 0.0584 | 0.0197 | 4.65% | 3.99% | 1.21% | 3.45% | 0.8091 | 19.95% | 53.33% |
| 5 | single_momentum120 | 1 | 241 | 0.0535 | 0.0256 | 6.03% | 25.31% | 7.65% | -1.62% | 0.3393 | 42.28% | 50.00% |
| 5 | single_fscore_interact | 1 | 241 | 0.0568 | 0.0244 | 7.21% | 29.52% | 8.93% | -1.71% | 0.3871 | 36.77% | 63.33% |
| 5 | single_asset_growth | 1 | 241 | 0.0097 | 0.0071 | -1.79% | 1.86% | 0.56% | -2.35% | 0.3150 | 39.67% | 43.33% |
| 10 | single_book_to_market_lf_plus_impact | 1 | 120 | 0.0759 | 0.0453 | 14.22% | 8.96% | 1.35% | 12.86% | 0.8917 | 27.96% | 66.67% |
| 10 | seven_without_residual_volatility | 6 | 120 | 0.1094 | 0.0615 | 16.65% | 27.22% | 4.12% | 12.53% | 0.9092 | 26.84% | 73.33% |
| 10 | seven_without_fscore_interact | 6 | 120 | 0.1065 | 0.0589 | 15.25% | 20.68% | 3.13% | 12.12% | 0.9237 | 27.18% | 70.00% |
| 10 | seven_without_turn_signal | 6 | 120 | 0.1090 | 0.0595 | 15.32% | 23.51% | 3.56% | 11.76% | 0.9031 | 26.59% | 66.67% |
| 10 | seven_equal_momentum | 7 | 120 | 0.1110 | 0.0621 | 16.08% | 28.63% | 4.33% | 11.75% | 0.8637 | 26.99% | 66.67% |
| 10 | seven_without_reversal_chip_turn_paper | 6 | 120 | 0.1074 | 0.0582 | 14.93% | 21.26% | 3.21% | 11.71% | 0.9326 | 26.69% | 71.67% |
| 10 | seven_without_asset_growth | 6 | 120 | 0.1186 | 0.0644 | 15.38% | 25.93% | 3.92% | 11.46% | 0.9218 | 24.42% | 68.33% |
| 10 | seven_equal_residual | 7 | 120 | 0.1142 | 0.0617 | 14.79% | 25.12% | 3.80% | 11.00% | 0.8900 | 26.31% | 66.67% |
| 10 | single_impact_abs_return60 | 1 | 120 | 0.0507 | 0.0392 | 11.77% | 9.15% | 1.38% | 10.39% | 0.7629 | 34.50% | 70.00% |
| 10 | seven_without_book_to_market_lf_plus_impact | 6 | 120 | 0.1137 | 0.0605 | 14.14% | 27.93% | 4.22% | 9.92% | 0.8532 | 25.66% | 70.00% |
| 10 | single_reversal_chip_turn_paper | 1 | 120 | 0.1078 | 0.0572 | 14.13% | 36.02% | 5.45% | 8.68% | 0.7388 | 28.48% | 68.33% |
| 10 | seven_without_impact_abs_return60 | 6 | 120 | 0.1132 | 0.0580 | 12.41% | 27.42% | 4.15% | 8.26% | 0.8154 | 24.10% | 60.00% |
| 10 | single_turn_signal | 1 | 120 | 0.0773 | 0.0390 | 8.83% | 26.17% | 3.96% | 4.87% | 0.6832 | 25.98% | 68.33% |
| 10 | single_residual_volatility | 1 | 120 | 0.0702 | 0.0295 | 4.36% | 7.01% | 1.06% | 3.31% | 0.7902 | 15.82% | 55.00% |
| 10 | single_fscore_interact | 1 | 120 | 0.0693 | 0.0333 | 7.50% | 42.33% | 6.40% | 1.10% | 0.4721 | 29.76% | 60.00% |
| 10 | single_momentum120 | 1 | 120 | 0.0679 | 0.0353 | 5.77% | 35.14% | 5.31% | 0.46% | 0.3839 | 38.81% | 50.00% |
| 10 | single_asset_growth | 1 | 120 | 0.0127 | 0.0088 | -2.14% | 3.43% | 0.52% | -2.66% | 0.2816 | 39.20% | 46.67% |

## 解释边界

- 7 个方向来自相关矩阵 PCA 的统计方向，不是严格互斥的经济类别；等权秩组合是可解释的基准，不是针对本区间优化出的最优权重。
- 逐一剔除行仅用于判断单个方向对组合的边际影响，不能把最高的一行当作无条件样本外结论。
- 本地财务字段、残差波动率和冲击字段含规则文档中说明的 proxy；结果不能宣称与平台内部字段字节等价。
- 信号日来自保存的平台结果；为使 5 日、10 日组合可比较，所有代表因子都在同一公共调仓日集合上重建。因子尚未形成有效值的早期日期会被组合 complete-case 排除，实际期数已在表中列出。

详细逐期持仓端统计见：
`/data/games/factor_/research_reports/platform_alignment/pca-seven-class-combination-20260917.periods.csv`

机器可读汇总见：
`/data/games/factor_/research_reports/platform_alignment/pca-seven-class-combination-20260917.json` 和 `/data/games/factor_/research_reports/platform_alignment/pca-seven-class-combination-20260917.csv`
