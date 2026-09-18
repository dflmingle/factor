# 换手对齐诊断

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`；规则文档：`research_reports/platform_alignment/ALIGNMENT_RULES.md`。
输入：`/data/games/factor_/quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1/all_factor_local_compare.json`。完整逐条表：`/data/games/factor_/research_reports/platform_alignment/turnover_alignment_diagnosis_20260917_qualitygate1.csv`。

## 摘要

| 指标 | 数值 |
|---|---:|
| 已保存平台记录 | 173 |
| 本地已计算 | 160 |
| 当前不支持 | 13 |
| 本地净超额有效记录 | 159 |
| 换手可比 | 158 |
| 质量状态 | `aligned`=76, `field_or_path_mismatch`=82, `turnover_dominant`=1, `unsupported`=1 |
| 可进入本地净超额挖掘 | 76 |
| 正式净超额平均绝对差 | +2.29pp |
| 平台换手敏感性平均绝对差 | +2.24pp |
| 正式净超额绝对差 >=5pp | 9 |
| 敏感性净超额绝对差 >=5pp | 11 |
| 换手敏感性使绝对差变小 | 49 |

换手状态： `comparable`=158, `platform_turnover_over_100`=1, `unavailable`=1

质量状态： `aligned`=76, `field_or_path_mismatch`=82, `turnover_dominant`=1, `unsupported`=1

## 换手主导差异

这里的“主导”是诊断启发式：正式净超额绝对差至少 5pp，且替换平台换手计成本后绝对差不超过 2pp。它不是对平台隐藏持仓的证明。

| 记录 | 平台净超额 | 本地净超额 | 正式差 | 敏感性净超额 | 敏感性差 | 平台/本地换手 |
|---|---:|---:|---:|---:|---:|---:|
| huatai-momentum-weighted-20260909.report:HT13-EXPWRET-6M | -26.28% | 0.32% | +26.60pp | -25.57% | +0.71pp | 216.73% / 45.50% |

## 不可直接比较的换手

| 记录 | 状态 | 换手差 | 正式差 | 敏感性差 | 诊断标记 |
|---|---|---:|---:|---:|---|
| huatai-momentum-weighted-20260909.report:HT13-EXPWRET-6M | `platform_turnover_over_100` | +171.23pp | +26.60pp | +0.71pp | platform_turnover_over_100;platform_high_local_low;large_turnover_gap |
| report-backed-untested-candidates.report:HT13-NEW-HIST-OPPROFIT-6Q | `unavailable` | n/a | n/a | n/a | missing:local_turnover |

## 正式净超额差最大的记录

| 记录 | handler | 正式差 | 敏感性差 | 平台/本地换手 | Top20 |
|---|---|---:|---:|---:|---:|
| huatai-momentum-weighted-20260909.report:HT13-EXPWRET-6M | `exp_weighted_reversal126` | +26.60pp | +0.71pp | 216.73% / 45.50% | 19/20 |
| combo-direct-4factor-size-2026-ytd-candidates.report:COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | `reversal_chip_turn_size_eq` | -6.93pp | -8.32pp | 42.15% / 32.92% | 2/20 |
| dls2014-candidates.report:DLS14-NCF-PROXY-20D | `reversal20_growth_net` | +6.21pp | +7.47pp | 32.41% / 36.57% | 5/20 |
| t10-additions-20260911-candidates.report:T10-ADD-G13-20260911 | `t10_size_plus_impact_g13` | -6.01pp | -5.99pp | 26.57% / 26.64% | 19/20 |
| t10-more-additions-20260911-candidates.report:T10-ADD-AGG-IMPACT-20260911 | `t10_size_plus_impact_aggregate` | -5.53pp | -5.52pp | 26.59% / 26.68% | 19/20 |
| t10-more-additions-20260911-candidates.report:T10-ADD-DOWNSIDE-IMPACT-20260911 | `t10_size_plus_impact_downside` | -5.24pp | -5.24pp | 27.05% / 27.07% | 19/20 |
| combo-direct-4factor-size-20260909-candidates.report:COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | `reversal_chip_turn_size_eq` | -5.22pp | -5.36pp | 36.68% / 35.75% | 19/20 |
| oversold-rebound-candidates.report:OSR-DD20-20D | `drawdown20` | -5.02pp | -5.19pp | 44.78% / 44.22% | 19/20 |
| t10-newdirections-20260911-candidates.report:T10-SIZE-PLUS-IMPACT | `t10_size_plus_impact` | -5.01pp | -5.06pp | 30.64% / 30.32% | 19/20 |
| verify-field-scan-20260910-candidates.report:VERIFY-G260910-13 | `impact_abs_return60` | -4.97pp | -5.04pp | 5.62% / 5.38% | 15/20 |
| oversold-rebound-candidates.report:OSR-MA20-20D | `ma_drawdown20` | -4.75pp | -4.90pp | 55.17% / 54.65% | 19/20 |
| nonhuatai-factor-6-20260909.report:NONHT-LOW-BETA | `beta_low` | +4.62pp | +3.57pp | 13.60% / 6.64% | 7/20 |
| alphaprobe-final-20260914-candidates.report:F-A18 | `ma_reversion40` | -4.61pp | -4.77pp | 39.54% / 38.98% | 19/20 |
| oversold-rebound-candidates.report:OSR-RET10-20D | `reversal10` | -4.59pp | -4.82pp | 67.84% / 67.06% | 19/20 |
| report-backed-untested-candidates.report:HT13-NEW-HIST-GPM-6Q | `quality_gross_margin_tsrank756` | +4.56pp | +3.07pp | 11.21% / 6.29% | 0/20 |

## 结论

- 正式本地净超额仍使用本地相邻信号期实际成员交集计算的换手；平台换手只进入敏感性结果。
- 只有 `alignment_quality=aligned` 且换手可比的记录标记为 `local_mining_eligible=true`；`turnover_dominant` 和 `field_or_path_mismatch` 不进入净超额挖掘候选池。
- `HT13-EXPWRET-6M` 的 RankIC 和 Top20 已接近，平台换手超过 100%，按平台换手计成本后敏感性差约为 0.71pp，主要差异可归因于平台换手摘要与本地成员换手不一致。
- `F-NET-D02` 虽然也触发平台高、本地低换手，但平台换手敏感性差仍约 -16.17pp，说明它还有毛超额/因子字段差异，不能只改成本口径。
- 其他记录即使敏感性变小，也不能据此声称逐期平台持仓已恢复；需要平台提供逐期持仓或逐股票换手明细才能进一步验证。

## 当前不支持

| 记录 | 公式 | 原因 |
|---|---|---|
| alphaprobe-gfn-new-20260916-candidates.report:F-GFN-N01-20260916 | `AMOUNT / VOLUME / HIGH` | HIGH/AMOUNT/VOLUME field semantics do not match the saved platform ranking; qfq high proxy is rejected |
| alphaprobe-gfn-platform-20260916-candidates.report:F-A19 | `ps_ratio_ttm - TS_MAX(ps_ratio_ttm,40)` | no local handler for this formula |
| alphaprobe-gfn-platform-20260916-candidates.report:F-A20 | `TS_SKEW(book_to_market_ratio_lf * book_to_market_ratio_lf,30)` | book_to_market_ratio_lf is not mapped in the local financial cache |
| alphaprobe-untested-20260916-candidates.report:GFN-UNT-20260916-EVPRICE | `1 / EV_TTM / CLOSE` | EV/EBITDA fields are not mapped in the local financial cache |
| base-fields-3-20260910-candidates.report:BASE-DIV-YIELD-TTM | `RANK(dividend_yield_ttm)` | local snapshot has no complete point-in-time dividend history for dividend_yield_ttm |
| distribution-risk-core-10d-candidate.report:DISTRIBUTION-RISK-CORE-10D | `(RANK(cal_close_30min_vol_ratio) + RANK(-cal_close_30min_return) + RANK(-cal_close_15min_vol_price_corr) + RANK(MA(TURNOVER,21) / MA(TURNOVER,252))) / 4` | platform intraday cal_* fields are not present in the local daily cache |
| distribution-risk-intraday-3signal-10d-candidate.report:DISTRIBUTION-INTRADAY-3SIGNAL-10D | `(RANK(cal_close_30min_vol_ratio) + RANK(-cal_close_30min_return) + RANK(-cal_close_15min_vol_price_corr))` | platform intraday cal_* fields are not present in the local daily cache |
| high-potential-5-20260910-candidates.report:NEW-HIST-ADJPROFIT-6Q | `TS_RANK(oper_adj_profit_ratio_ttm,756)` | local financial cache has no adjusted-profit/non-recurring-income fields |
| market-behavior-washout-distribution-cycle10-candidates.report:DISTRIBUTION-RISK-10D | `(RANK(RETURNS(CLOSE,60)) + RANK(cal_close_30min_vol_ratio) + RANK(-cal_close_30min_return) + RANK(-cal_close_15min_vol_price_corr) + RANK(MA(TURNOVER,21) / MA(TURNOVER,252))) / 5` | platform intraday cal_* fields are not present in the local daily cache |
| net-dd-multiobjective-20260916-diversified-candidates.report:F-NET-D02 | `(BOOK_TO_MARKET_RATIO_LYR*MA(INSURANCE_COMMISSION_EXPENSE_MRQ_9,10))` | insurance_commission_expense_mrq_9 needs a verified MRQ field mapping; no local equivalent |
| net-dd-multiobjective-20260916-diversified-candidates.report:F-NET-D03 | `COV(MIN(TOTAL_ASSETS_MRQ_1,CASH_RECEIVED_FROM_ISSUING_SECURITY_MRQ_10),INTEREST_PAYABLE_MRQ_4,30)` | no local handler for this formula |
| pandaai-net15-20260915-candidates.report:F-NET01-PLAT-20260915 | `TS_MIN(INTEREST_EXPENSE_MRQ_10,50)` | no local handler for this formula |
| pandaai-orthogonal-net-20260916-candidates.report:F-NET03-PLAT-20260916 | `(1/(REF(EV_NO_CASH_TTM,10)))` | EV/EBITDA fields are not mapped in the local financial cache |
