# 因子对齐失败登记表

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
硬失败标准：`abs(delta) > 5.00pp`
来源：`D:\factor\quantlab\.quantlab\cache\research\cn_equity\reports\all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1\all_factor_local_compare.json`

## 摘要

| 指标 | 数值 |
|---|---:|
| 平台记录 | 178 |
| 本地复现记录 | 160 |
| 有效净超额 | 158 |
| 净超额可接受（<=5pp） | 152 |
| 净超额不可接受（>5pp） | 6 |
| 暂无法判断 | 2 |
| 默认拉黑字段 | 无；当前证据不足以全局拉黑已验证字段 |

## 不可接受记录

| 记录 | handler | 净超额差(pp) | 毛超额差(pp) | 原因 | 公式字段 | 字段归因 |
|---|---|---:|---:|---|---|---|
| combo-direct-4factor-size-2026-ytd-candidates.report:COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | reversal_chip_turn_size_eq | -6.927464404903839 | -8.323534098436895 | gross_return_path_mismatch, factor_ranking_path_mismatch, unexplained_net_excess_gap | close, market_cap, open, turnover, volume | close(low); market_cap(low); open(low); turnover(low); volume(low) |
|  |  |  |  | 说明 | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP)))) / 4` | 毛超额差异为 -8.32pp，优先检查字段值、复权、停牌处理、标签和算子路径。 Top20 仅重合 2/20，说明因子值或排序路径仍不一致。 净超额绝对差为 6.93pp，超过不可接受阈值 5.00pp。 |
| combo-direct-4factor-size-20260909-candidates.report:COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | reversal_chip_turn_size_eq | -5.217884461719908 | -5.358444268433484 | gross_return_path_mismatch, unexplained_net_excess_gap | close, market_cap, open, turnover, volume | close(low); market_cap(low); open(low); turnover(low); volume(low) |
|  |  |  |  | 说明 | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP)))) / 4` | 毛超额差异为 -5.36pp，优先检查字段值、复权、停牌处理、标签和算子路径。 净超额绝对差为 5.22pp，超过不可接受阈值 5.00pp。 |
| dls2014-candidates.report:DLS14-NCF-PROXY-20D | reversal20_growth_net | 6.212996974735411 | 7.469549710508566 | gross_return_path_mismatch, factor_ranking_path_mismatch, unexplained_net_excess_gap | close, gr_net_profit_ttm | close(low); gr_net_profit_ttm(medium) |
|  |  |  |  | 说明 | `RANK(1 - RETURNS(CLOSE,20)) + RANK(gr_net_profit_ttm)` | 毛超额差异为 +7.47pp，优先检查字段值、复权、停牌处理、标签和算子路径。 Top20 仅重合 5/20，说明因子值或排序路径仍不一致。 净超额绝对差为 6.21pp，超过不可接受阈值 5.00pp。 |
| huatai-momentum-weighted-20260909.report:HT13-EXPWRET-6M | exp_weighted_reversal126 | 26.595098661690088 | 0.7052211821175254 | platform_turnover_summary_mismatch | close, turnover | close(low); turnover(high) |
|  |  |  |  | 说明 | `-(TURNOVER * RETURNS(CLOSE,1) + 0.959189457109 * DELAY(TURNOVER * RETURNS(CLOSE,1),1) + 0.920044414629 * DELAY(TURNOVER * RETURNS(CLOSE,1),2) + 0.882496902585 * DELAY(TURNOVER *...` | 正式净超额差异在替换平台汇总换手成本后降至 2pp 以内；平台没有逐期持仓，不能把该差异归因到因子字段。 |
| oversold-rebound-candidates.report:OSR-DD20-20D | drawdown20 | -5.023050174882558 | -5.1921218495033665 | gross_return_path_mismatch, unexplained_net_excess_gap | close | close(low) |
|  |  |  |  | 说明 | `RANK(1 - CLOSE / TS_MAX(CLOSE,20))` | 毛超额差异为 -5.19pp，优先检查字段值、复权、停牌处理、标签和算子路径。 净超额绝对差为 5.02pp，超过不可接受阈值 5.00pp。 |
| t10-additions-20260911-candidates.report:T10-ADD-G13-20260911 | t10_size_plus_impact_g13 | -5.292664223796464 | -5.257627561011308 | gross_return_path_mismatch, unexplained_net_excess_gap | amount, close, high, low, market_cap, open, turnover, volume | amount(low); close(low); high(low); low(low); market_cap(low); open(low); turnover(low); volume(low) |
|  |  |  |  | 说明 | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP))) + RANK(S...` | 毛超额差异为 -5.26pp，优先检查字段值、复权、停牌处理、标签和算子路径。 净超额绝对差为 5.29pp，超过不可接受阈值 5.00pp。 |

## 字段风险

决策只依据净超额 >5pp 的重复证据；字段出现在失败公式中不等于字段已经被证明错误。

| 字段 | 公式数 | >5pp | <=5pp | 换手主导 | 平均绝对差(pp) | 最大绝对差(pp) | 决策 |
|---|---:|---:|---:|---:|---:|---:|---|
| `close` | 113 | 5 | 107 | 1 | 2.35 | 6.93 | suspect |
| `market_cap` | 19 | 3 | 16 | 0 | 3.71 | 6.93 | suspect |
| `open` | 19 | 3 | 16 | 0 | 3.89 | 6.93 | suspect |
| `turnover` | 33 | 3 | 29 | 1 | 2.81 | 6.93 | suspect |
| `volume` | 29 | 3 | 26 | 0 | 2.78 | 6.93 | suspect |
| `amount` | 15 | 1 | 14 | 0 | 3.64 | 5.29 | suspect |
| `gr_net_profit_ttm` | 5 | 1 | 4 | 0 | 2.19 | 6.21 | suspect |
| `high` | 18 | 1 | 17 | 0 | 2.51 | 5.29 | suspect |
| `low` | 14 | 1 | 13 | 0 | 3.20 | 5.29 | suspect |
| `beta` | 1 | 0 | 1 | 0 | 4.62 | 4.62 | retain |
| `book_to_market_ratio_lf` | 6 | 0 | 5 | 0 | 2.53 | 4.24 | retain |
| `book_to_market_ratio_lyr` | 8 | 0 | 8 | 0 | 2.12 | 4.08 | retain |
| `cfd_ocf_to_debt_ttm` | 4 | 0 | 4 | 0 | 1.45 | 3.76 | retain |
| `cfd_surplus_cash_multi_ttm` | 4 | 0 | 4 | 0 | 1.45 | 3.76 | retain |
| `current_assets` | 2 | 0 | 2 | 0 | 3.43 | 3.56 | retain |
| `current_liabilities` | 2 | 0 | 2 | 0 | 3.43 | 3.56 | retain |
| `fin_current_ratio_lyr` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `fin_current_ratio_ttm` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `fin_debt_to_asset_lyr` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `fin_debt_to_asset_ttm` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `gr_ocf_ttm` | 3 | 0 | 3 | 0 | 0.47 | 0.73 | retain |
| `gr_oper_profit_ttm` | 2 | 0 | 2 | 0 | 0.34 | 0.48 | retain |
| `gr_revenue_ttm` | 2 | 0 | 2 | 0 | 0.75 | 1.02 | retain |
| `gr_roe_ttm` | 1 | 0 | 1 | 0 | 0.32 | 0.32 | retain |
| `gr_total_asset_lyr` | 9 | 0 | 9 | 0 | 2.23 | 4.08 | retain |
| `inventory` | 2 | 0 | 2 | 0 | 3.43 | 3.56 | retain |
| `oper_gross_margin_lyr` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `oper_gross_margin_ttm` | 4 | 0 | 4 | 0 | 2.57 | 4.56 | retain |
| `oper_main_profit_ttm` | 1 | 0 | 0 | 0 | n/a | n/a | retain |
| `oper_net_margin_ttm` | 1 | 0 | 1 | 0 | 2.77 | 2.77 | retain |
| `oper_oper_profit_to_tp_ttm` | 1 | 0 | 0 | 0 | n/a | n/a | retain |
| `oper_roa_net_lyr` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `oper_roa_net_ttm` | 4 | 0 | 4 | 0 | 1.65 | 3.76 | retain |
| `oper_roe_lyr` | 9 | 0 | 9 | 0 | 2.00 | 4.08 | retain |
| `oper_roe_ttm` | 5 | 0 | 5 | 0 | 1.23 | 3.88 | retain |
| `oper_roic_ttm` | 1 | 0 | 1 | 0 | 0.41 | 0.41 | retain |
| `oper_total_asset_turnover_lyr` | 3 | 0 | 3 | 0 | 1.91 | 3.76 | retain |
| `oper_total_asset_turnover_ttm` | 4 | 0 | 4 | 0 | 1.64 | 3.76 | retain |
| `profitability` | 1 | 0 | 1 | 0 | 2.27 | 2.27 | retain |
| `ratio_bm_ttm` | 22 | 0 | 22 | 0 | 1.57 | 4.42 | retain |
| `ratio_cfp_ttm` | 10 | 0 | 10 | 0 | 1.15 | 2.11 | retain |
| `ratio_ep_ttm` | 7 | 0 | 7 | 0 | 0.60 | 1.50 | retain |
| `ratio_ev_ebitda_ttm` | 1 | 0 | 1 | 0 | 0.14 | 0.14 | retain |
| `ratio_pcf_ocf_ttm` | 3 | 0 | 3 | 0 | 0.66 | 1.33 | retain |
| `ratio_sp_ttm` | 3 | 0 | 3 | 0 | 0.59 | 0.97 | retain |
| `residual_volatility` | 2 | 0 | 2 | 0 | 1.90 | 3.25 | retain |

## 使用规则

- 默认 GP/GFN 不使用登记表中 `blocked` 字段。
- `suspect` 字段只记录风险，不自动排除，避免把 HIGH、AMOUNT、VOLUME 等已通过单字段隔离的字段误拉黑。
- 需要复查被拉黑字段时，显式使用 `--allow-blocked-fields`，结果仍标记为诊断模式。
- 每次正式全量复现后重新运行 `python scripts/build_alignment_failure_registry.py`，再开始下一轮本地挖掘。
