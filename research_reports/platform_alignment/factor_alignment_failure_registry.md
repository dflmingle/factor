# 因子对齐失败登记表

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate3`
硬失败标准：`abs(delta) > 5.00pp`
来源：`quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate3/all_factor_local_compare.json`

## 摘要

| 指标 | 数值 |
|---|---:|
| 平台记录 | 196 |
| 本地复现记录 | 164 |
| 有效净超额 | 164 |
| 净超额可接受（<=5pp） | 160 |
| 净超额不可接受（>5pp） | 4 |
| 暂无法判断 | 0 |
| 默认拉黑字段 | 无；当前证据不足以全局拉黑已验证字段 |

## 不可接受记录

| 记录 | handler | 净超额差(pp) | 毛超额差(pp) | 原因 | 公式字段 | 字段归因 |
|---|---|---:|---:|---|---|---|
| alphaprobe-net1-platform-20260914-candidates.report:F-NET01-PLAT-20260914 | wma_low_volume40 | 5.537728525730216 | 5.235088224658288 | gross_return_path_mismatch, factor_ranking_path_mismatch, unexplained_net_excess_gap | low, volume | low(low); volume(low) |
|  |  |  |  | 说明 | `WMA((((1/LOW)/LOW)/VOLUME),40)` | 毛超额差异为 +5.24pp，优先检查字段值、复权、停牌处理、标签和算子路径。 Top20 仅重合 5/20，说明因子值或排序路径仍不一致。 净超额绝对差为 5.54pp，超过不可接受阈值 5.00pp。 |
| dls2014-candidates.report:DLS14-NCF-PROXY-20D | reversal20_growth_net | 7.35730718703989 | 8.537249430147531 | gross_return_path_mismatch, factor_ranking_path_mismatch, unexplained_net_excess_gap | close, gr_net_profit_ttm | close(low); gr_net_profit_ttm(medium) |
|  |  |  |  | 说明 | `RANK(1 - RETURNS(CLOSE,20)) + RANK(gr_net_profit_ttm)` | 毛超额差异为 +8.54pp，优先检查字段值、复权、停牌处理、标签和算子路径。 Top20 仅重合 5/20，说明因子值或排序路径仍不一致。 净超额绝对差为 7.36pp，超过不可接受阈值 5.00pp。 |
| dls2014-candidates.report:DLS14-STREV-20D | reversal20 | 5.784520342088754 | 5.582278741373443 | gross_return_path_mismatch, unexplained_net_excess_gap | close | close(low) |
|  |  |  |  | 说明 | `1 - RETURNS(CLOSE,20)` | 毛超额差异为 +5.58pp，优先检查字段值、复权、停牌处理、标签和算子路径。 净超额绝对差为 5.78pp，超过不可接受阈值 5.00pp。 |
| huatai-momentum-weighted-20260909.report:HT13-EXPWRET-6M | exp_weighted_reversal126 | 29.33497439442103 | 3.4538928913745384 | unexplained_net_excess_gap | close, turnover | close(low); turnover(low) |
|  |  |  |  | 说明 | `-(TURNOVER * RETURNS(CLOSE,1) + 0.959189457109 * DELAY(TURNOVER * RETURNS(CLOSE,1),1) + 0.920044414629 * DELAY(TURNOVER * RETURNS(CLOSE,1),2) + 0.882496902585 * DELAY(TURNOVER *...` | 净超额绝对差为 29.33pp，超过不可接受阈值 5.00pp。 |

## 字段风险

决策只依据净超额 >5pp 的重复证据；字段出现在失败公式中不等于字段已经被证明错误。

| 字段 | 公式数 | >5pp | <=5pp | 换手主导 | 平均绝对差(pp) | 最大绝对差(pp) | 决策 |
|---|---:|---:|---:|---:|---:|---:|---|
| `close` | 113 | 3 | 110 | 0 | 1.60 | 29.33 | suspect |
| `gr_net_profit_ttm` | 5 | 1 | 4 | 0 | 2.39 | 7.36 | suspect |
| `low` | 15 | 1 | 14 | 0 | 2.39 | 5.54 | suspect |
| `turnover` | 33 | 1 | 32 | 0 | 2.52 | 29.33 | suspect |
| `volume` | 30 | 1 | 29 | 0 | 1.88 | 5.54 | suspect |
| `amount` | 15 | 0 | 15 | 0 | 2.28 | 3.12 | retain |
| `beta` | 1 | 0 | 1 | 0 | 4.54 | 4.54 | retain |
| `book_to_market_ratio_lf` | 7 | 0 | 7 | 0 | 1.36 | 2.42 | retain |
| `book_to_market_ratio_lyr` | 8 | 0 | 8 | 0 | 0.65 | 2.40 | retain |
| `cfd_ocf_to_debt_ttm` | 4 | 0 | 4 | 0 | 1.05 | 2.31 | retain |
| `cfd_surplus_cash_multi_ttm` | 4 | 0 | 4 | 0 | 0.79 | 2.31 | retain |
| `current_assets` | 2 | 0 | 2 | 0 | 2.08 | 2.33 | retain |
| `current_liabilities` | 2 | 0 | 2 | 0 | 2.08 | 2.33 | retain |
| `fin_current_ratio_lyr` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `fin_current_ratio_ttm` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `fin_debt_to_asset_lyr` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `fin_debt_to_asset_ttm` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `gr_ocf_ttm` | 3 | 0 | 3 | 0 | 0.74 | 0.95 | retain |
| `gr_oper_profit_ttm` | 2 | 0 | 2 | 0 | 0.93 | 0.95 | retain |
| `gr_revenue_ttm` | 2 | 0 | 2 | 0 | 0.64 | 0.95 | retain |
| `gr_roe_ttm` | 1 | 0 | 1 | 0 | 0.14 | 0.14 | retain |
| `gr_total_asset_lyr` | 10 | 0 | 10 | 0 | 1.07 | 2.82 | retain |
| `high` | 18 | 0 | 18 | 0 | 1.67 | 3.12 | retain |
| `inventory` | 2 | 0 | 2 | 0 | 2.08 | 2.33 | retain |
| `market_cap` | 19 | 0 | 19 | 0 | 1.54 | 4.72 | retain |
| `open` | 19 | 0 | 19 | 0 | 1.94 | 4.72 | retain |
| `oper_gross_margin_lyr` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `oper_gross_margin_ttm` | 4 | 0 | 4 | 0 | 1.81 | 4.36 | retain |
| `oper_main_profit_ttm` | 2 | 0 | 2 | 0 | 1.10 | 1.38 | retain |
| `oper_net_margin_ttm` | 1 | 0 | 1 | 0 | 2.90 | 2.90 | retain |
| `oper_oper_profit_to_tp_ttm` | 1 | 0 | 1 | 0 | 0.53 | 0.53 | retain |
| `oper_roa_net_lyr` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `oper_roa_net_ttm` | 4 | 0 | 4 | 0 | 0.99 | 2.31 | retain |
| `oper_roe_lyr` | 9 | 0 | 9 | 0 | 0.88 | 2.69 | retain |
| `oper_roe_ttm` | 5 | 0 | 5 | 0 | 1.60 | 4.70 | retain |
| `oper_roic_ttm` | 1 | 0 | 1 | 0 | 0.18 | 0.18 | retain |
| `oper_total_asset_turnover_lyr` | 3 | 0 | 3 | 0 | 0.96 | 2.31 | retain |
| `oper_total_asset_turnover_ttm` | 4 | 0 | 4 | 0 | 1.00 | 2.31 | retain |
| `profitability` | 1 | 0 | 1 | 0 | 2.26 | 2.26 | retain |
| `ratio_bm_ttm` | 23 | 0 | 23 | 0 | 0.60 | 1.44 | retain |
| `ratio_cfp_ttm` | 10 | 0 | 10 | 0 | 0.60 | 1.44 | retain |
| `ratio_ep_ttm` | 7 | 0 | 7 | 0 | 0.79 | 1.08 | retain |
| `ratio_ev_ebitda_ttm` | 1 | 0 | 1 | 0 | 4.52 | 4.52 | retain |
| `ratio_pcf_ocf_ttm` | 3 | 0 | 3 | 0 | 0.65 | 1.02 | retain |
| `ratio_sp_ttm` | 3 | 0 | 3 | 0 | 0.56 | 1.02 | retain |
| `residual_volatility` | 2 | 0 | 2 | 0 | 2.46 | 4.15 | retain |

## 使用规则

- 默认 GP/GFN 不使用登记表中 `blocked` 字段。
- `suspect` 字段只记录风险，不自动排除，避免把 HIGH、AMOUNT、VOLUME 等已通过单字段隔离的字段误拉黑。
- 需要复查被拉黑字段时，显式使用 `--allow-blocked-fields`，结果仍标记为诊断模式。
- 每次正式全量复现后重新运行 `python scripts/build_alignment_failure_registry.py`，再开始下一轮本地挖掘。
