# Full-catalog seven-factor combination

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1`；规则文档：`research_reports/platform_alignment/ALIGNMENT_RULES.md`。

这是离线本地 proxy 测试，不创建因子、不调用 PandaAI。候选池先取保存记录中平台净超额大于 0 的因子，再按完全相同公式去重；在同一调仓周期内，按平台净超额从高到低贪心选择，要求新代表与已选代表的方向对齐截面相关绝对值小于 0.80。
这种选择会把所有正净超额候选纳入筛选，而不是先固定 PCA 载荷代表。每类代表优先由净超额决定，相关候选仍保留在候选明细中。

## Selected representatives

| 类别 | handler | 因子 | 方向 | 平台净超额 | 与前面代表最大绝对相关 |
|---:|---|---|---:|---:|---:|
| 1 | `size_only` | SIZE-ONLY-20260911 | 0 | 21.43% | 0.0000 |
| 2 | `t10_size_plus_impact_aggregate` | T10-ADD-AGG-IMPACT-20260911 | 1 | 19.76% | 0.7105 |
| 3 | `book_to_market_lf_minus_size` | VERIFY10-E260910-04 | 1 | 16.74% | 0.7142 |
| 4 | `impact60` | H03-T10-SINGLE | 1 | 16.44% | 0.7927 |
| 5 | `reversal_chip_turn_paper` | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | 1 | 12.77% | 0.7744 |
| 6 | `reversal40` | OSR2-RET40 | 1 | 5.03% | 0.7360 |
| 7 | `turn_bias` | HT13-TURN-BIAS-1M | 0 | 4.96% | 0.6799 |

## Candidate coverage

| 候选 | handler | 平台净超额 | 最近代表 | 相关系数 |
|---|---|---:|---|---:|
| SIZE-ONLY-20260911 | `size_only` | 21.43% | SIZE-ONLY-20260911 | +1.0000 |
| NEW-VALUE-EVEBITDA | `ev_ebitda_proxy` | 3.32% | SIZE-ONLY-20260911 | +0.1726 |
| T10-ADD-AGG-IMPACT-20260911 | `t10_size_plus_impact_aggregate` | 19.76% | T10-ADD-AGG-IMPACT-20260911 | +1.0000 |
| T10-ADD-G13-20260911 | `t10_size_plus_impact_g13` | 19.62% | T10-ADD-AGG-IMPACT-20260911 | +0.9987 |
| T10-ADD-DOWNSIDE-IMPACT-20260911 | `t10_size_plus_impact_downside` | 19.39% | T10-ADD-AGG-IMPACT-20260911 | +0.9994 |
| T10-SIZE-PLUS-IMPACT | `t10_size_plus_impact` | 18.16% | T10-ADD-AGG-IMPACT-20260911 | +0.9786 |
| T10-ADD-BM-20260911 | `t10_size_plus_impact_bm` | 18.09% | T10-ADD-AGG-IMPACT-20260911 | +0.9364 |
| T10-ADD-FSCORE-20260911 | `t10_size_plus_impact_fscore` | 17.48% | T10-ADD-AGG-IMPACT-20260911 | +0.9293 |
| T10-SIZE-PLUS-IMPACT-WC | `t10_size_plus_impact_wc` | 17.44% | T10-ADD-AGG-IMPACT-20260911 | +0.9393 |
| T10-ADD-DD120-20260911 | `t10_size_plus_impact_dd120` | 16.83% | T10-ADD-AGG-IMPACT-20260911 | +0.9220 |
| VERIFY10-E260910-04 | `book_to_market_lf_minus_size` | 16.74% | VERIFY10-E260910-04 | +1.0000 |
| VERIFY10-F260910-12 | `book_to_market_lf_plus_impact` | 15.05% | VERIFY10-E260910-04 | +0.9008 |
| paper-derived-composite | `paper_composite` | 11.20% | VERIFY10-E260910-04 | +0.8167 |
| NONHT-RESVOL-LOW | `residual_volatility` | 0.37% | VERIFY10-E260910-04 | +0.3239 |
| H03-T10-SINGLE | `impact60` | 16.44% | H03-T10-SINGLE | +1.0000 |
| VERIFY10-G260910-13 | `impact_abs_return60` | 13.94% | H03-T10-SINGLE | +0.9656 |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | `reversal_chip_turn_size_eq` | 16.38% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9350 |
| T10-SIZE-PLUS-WC-MCAP | `t10_size_plus_wc_mcap` | 14.58% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8944 |
| T10-NOMCAP-PLUS-IMPACT | `t10_nomcap_plus_impact` | 14.23% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9286 |
| COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | `reversal_chip_turn_paper` | 12.77% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +1.0000 |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | `reversal_turn_paper` | 11.64% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9465 |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | `reversal_chip_turn_eq` | 8.66% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9281 |
| OSR2-RET40-TURN-BIAS-EQ | `reversal_turn_eq` | 7.40% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8565 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | `reversal_turn_paper_nomcap` | 5.22% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8975 |
| NONHT-CHIP-COST-250 | `chip250` | 4.28% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.7955 |
| HT13-MOMENTUM-120D-D0 | `momentum120` | 2.29% | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.6733 |
| COMBO-DIRECT-OSR2-CHIP-EQ | `reversal_chip_eq` | 7.88% | OSR2-RET40 | +0.8859 |
| OSR2-RET40 | `reversal40` | 5.03% | OSR2-RET40 | +1.0000 |
| OSR2-DD120 | `drawdown120` | 4.25% | OSR2-RET40 | +0.6025 |
| NONHT-FSCORELIKE-REV40-INTERACT | `fscore_interact` | 1.84% | OSR2-RET40 | +0.6506 |
| NONHT-FSCORELIKE-REV40 | `fscore_eq` | 1.82% | OSR2-RET40 | +0.6887 |
| HT13-TURN-BIAS-1M | `turn_bias` | 4.96% | HT13-TURN-BIAS-1M | +1.0000 |
| HT-WREV-LOWTURN-21D | `weighted_reversal_lowturn` | 2.71% | HT13-TURN-BIAS-1M | +0.7996 |

## Local results

净超额为算术年化毛超额减本地实际换手成本；组合和单因子均使用相同信号日期、`factor_valid` 基准、qfq 全 A 和 0.30% 单边成本。

| 调仓 | 组合 | 因子数 | 期数 | RankIC | 毛超额 | 换手 | 年化成本 | 净超额 | Sharpe | 最大回撤 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | single_size_only | 1 | 241 | 0.0437138461706521 | 19.90% | 5.95% | 1.80% | 18.10% | 0.9299380183041945 | 39.75% |
| 5 | single_impact60 | 1 | 241 | 0.050003960760177706 | 17.74% | 4.97% | 1.50% | 16.24% | 0.9586472770594346 | 35.62% |
| 5 | single_book_to_market_lf_minus_size | 1 | 241 | 0.06543712667934017 | 17.16% | 6.77% | 2.05% | 15.11% | 0.9091136579172961 | 35.70% |
| 5 | greedy_seven | 7 | 241 | 0.09263464233388563 | 20.73% | 19.59% | 5.93% | 14.81% | 0.9038715696707122 | 37.88% |
| 5 | single_t10_size_plus_impact_aggregate | 1 | 241 | 0.0859704878465446 | 19.49% | 17.72% | 5.36% | 14.13% | 0.8748961571215498 | 37.98% |
| 5 | single_reversal_chip_turn_paper | 1 | 241 | 0.08971451475669374 | 14.81% | 24.24% | 7.33% | 7.48% | 0.6940145314669859 | 36.17% |
| 5 | single_turn_bias | 1 | 241 | 0.06715229655361811 | 9.86% | 15.13% | 4.57% | 5.29% | 0.7029052183458795 | 30.53% |
| 5 | single_reversal40 | 1 | 241 | 0.06810134339662002 | 8.88% | 39.58% | 11.97% | -3.09% | 0.2813737578959035 | 44.40% |
| 10 | single_size_only | 1 | 120 | 0.052949505168266055 | 18.41% | 8.47% | 1.28% | 17.13% | 0.8989789144739604 | 34.59% |
| 10 | single_impact60 | 1 | 120 | 0.06287593105023079 | 16.70% | 8.99% | 1.36% | 15.34% | 0.9429688816047346 | 28.82% |
| 10 | greedy_seven | 7 | 120 | 0.11261869849009029 | 19.55% | 29.38% | 4.44% | 15.11% | 0.9259965308885749 | 30.74% |
| 10 | single_book_to_market_lf_minus_size | 1 | 120 | 0.07912269589485625 | 15.99% | 9.59% | 1.45% | 14.54% | 0.8979219290237311 | 28.62% |
| 10 | single_t10_size_plus_impact_aggregate | 1 | 120 | 0.10548387490081428 | 18.26% | 26.68% | 4.03% | 14.23% | 0.8844084655061647 | 30.97% |
| 10 | single_reversal_chip_turn_paper | 1 | 120 | 0.1077722413386193 | 14.13% | 36.02% | 5.45% | 8.68% | 0.7388291706301888 | 28.48% |
| 10 | single_turn_bias | 1 | 120 | 0.07727166173675118 | 8.83% | 26.17% | 3.96% | 4.87% | 0.6831519469754999 | 25.98% |
| 10 | single_reversal40 | 1 | 120 | 0.08526468873307808 | 9.95% | 54.49% | 8.24% | 1.71% | 0.4173570704522535 | 37.10% |

## Interpretation

这里的 7 类是去重后的强候选代表，不是保证组合优于单因子的优化结果。若单因子净超额高于组合，说明等权平均稀释了有效暴露；这时应保留单因子作为基准，不能为了让组合看起来更好而改变权重。

完整逐期结果见：
`research_reports/platform_alignment/uncorrelated-seven-factor-combination-20260917.periods.csv`

机器可读结果见：
`research_reports/platform_alignment/uncorrelated-seven-factor-combination-20260917.json` 和 `research_reports/platform_alignment/uncorrelated-seven-factor-combination-20260917.csv`。
