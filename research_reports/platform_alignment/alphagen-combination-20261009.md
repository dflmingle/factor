# AlphaGen local constrained combination

Alignment rules: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate4`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.

The saved paper composite is removed from the pool and represented by four atomic terms. All factors are direction-aligned and cross-sectionally ranked before combination.
MseAlphaPool is used for static IC/mutual-IC selection. AlphaPROBE-style expanding selection uses historical RankIC/RankICIR. Final weights are simple signed equal weights; the continuous optimizer weights are audit diagnostics only.

## Factor pool

| name | source | handler | status | formula |
|---|---|---|---|---|
| size_component | size | `paper_size_component` | local_component_proxy | `-ZSCORE(RANK(MARKET_CAP))` |
| impact60 | impact_liquidity | `impact60` | saved_aligned_factor | `RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))` |
| value_component | value | `paper_bm_component` | local_component_proxy | `ZSCORE(RANK(book_to_market_ratio_lyr))` |
| roe_component | profitability | `paper_roe_component` | local_component_proxy | `ZSCORE(RANK(oper_roe_lyr))` |
| low_asset_growth_component | asset_growth | `paper_asset_growth_component` | local_component_proxy | `-ZSCORE(RANK(gr_total_asset_lyr))` |
| reversal40 | price_reversal | `reversal40` | saved_aligned_factor | `RANK(1-RETURNS(CLOSE,40))` |
| drawdown120 | drawdown_risk | `drawdown120` | saved_aligned_factor | `RANK(1-CLOSE/TS_MAX(CLOSE,120))` |
| weighted_reversal_lowturn | turnover_reversal | `weighted_reversal_lowturn` | saved_aligned_factor | `(RANK(-SUM(TURNOVER*RETURNS(CLOSE,1),21)/SUM(TURNOVER,21))+RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)))/2` |

## Results

Net excess is arithmetic annualized gross excess minus local turnover cost under the alignment contract.

| model | period | factors | weights | net excess | turnover | Sharpe | max drawdown | RankIC |
|---|---|---|---|---:|---:|---:|---:|---:|
| AlphaPROBE_expanding_simple | full | dynamic_top5 | signed_equal_1/N_per_period | 13.86% | 36.53% | 1.0019 | 25.47% | 0.1140 |
| AlphaPROBE_expanding_simple | train | dynamic_top5 | signed_equal_1/N_per_period | 11.95% | 37.48% | 0.2341 | 25.47% | 0.1155 |
| AlphaPROBE_expanding_simple | validation | dynamic_top5 | signed_equal_1/N_per_period | 16.01% | 35.48% | 1.8788 | 19.17% | 0.1124 |
| MseAlphaPool_simple | full | impact60,reversal40,value_component,weighted_reversal_lowturn,size_component | impact60:0.200000;reversal40:0.200000;value_component:0.200000;weighted_reversal_lowturn:0.200000;size_component:0.200000 | 16.77% | 35.25% | 1.0300 | 25.47% | 0.1233 |
| MseAlphaPool_simple | train | impact60,reversal40,value_component,weighted_reversal_lowturn,size_component | impact60:0.200000;reversal40:0.200000;value_component:0.200000;weighted_reversal_lowturn:0.200000;size_component:0.200000 | 17.26% | 35.11% | 0.4814 | 25.47% | 0.1303 |
| MseAlphaPool_simple | validation | impact60,reversal40,value_component,weighted_reversal_lowturn,size_component | impact60:0.200000;reversal40:0.200000;value_component:0.200000;weighted_reversal_lowturn:0.200000;size_component:0.200000 | 16.01% | 35.48% | 1.8788 | 19.17% | 0.1124 |
| baseline_atomic_equal | full | size_component,impact60,value_component,roe_component,low_asset_growth_component,reversal40,drawdown120,weighted_reversal_lowturn | size_component:0.125000;impact60:0.125000;value_component:0.125000;roe_component:0.125000;low_asset_growth_component:0.125000;reversal40:0.125000;drawdown120:0.125000;weighted_reversal_lowturn:0.125000 | 14.42% | 36.61% | 0.9504 | 22.99% | 0.1156 |
| baseline_atomic_equal | train | size_component,impact60,value_component,roe_component,low_asset_growth_component,reversal40,drawdown120,weighted_reversal_lowturn | size_component:0.125000;impact60:0.125000;value_component:0.125000;roe_component:0.125000;low_asset_growth_component:0.125000;reversal40:0.125000;drawdown120:0.125000;weighted_reversal_lowturn:0.125000 | 15.57% | 36.16% | 0.4198 | 22.99% | 0.1213 |
| baseline_atomic_equal | validation | size_component,impact60,value_component,roe_component,low_asset_growth_component,reversal40,drawdown120,weighted_reversal_lowturn | size_component:0.125000;impact60:0.125000;value_component:0.125000;roe_component:0.125000;low_asset_growth_component:0.125000;reversal40:0.125000;drawdown120:0.125000;weighted_reversal_lowturn:0.125000 | 12.62% | 37.30% | 1.7850 | 19.06% | 0.1068 |
| baseline_impact_only | full | impact60 | impact60:1.000000 | 16.08% | 10.54% | 0.9913 | 28.17% | 0.0663 |
| baseline_impact_only | train | impact60 | impact60:1.000000 | 16.08% | 10.42% | 0.3945 | 28.17% | 0.0680 |
| baseline_impact_only | validation | impact60 | impact60:1.000000 | 16.07% | 10.72% | 1.9628 | 19.90% | 0.0635 |
| baseline_paper_composite | full | paper_composite_baseline | paper_composite_baseline:1.000000 | 10.19% | 9.42% | 0.8563 | 24.08% | 0.0694 |
| baseline_paper_composite | train | paper_composite_baseline | paper_composite_baseline:1.000000 | 14.65% | 9.71% | 0.3948 | 24.08% | 0.0822 |
| baseline_paper_composite | validation | paper_composite_baseline | paper_composite_baseline:1.000000 | 3.27% | 8.97% | 1.5205 | 19.64% | 0.0496 |
| baseline_size_impact | full | size_component,impact60 | size_component:0.500000;impact60:0.500000 | 20.96% | 8.70% | 1.0738 | 31.96% | 0.0660 |
| baseline_size_impact | train | size_component,impact60 | size_component:0.500000;impact60:0.500000 | 21.78% | 8.74% | 0.5440 | 31.96% | 0.0659 |
| baseline_size_impact | validation | size_component,impact60 | size_component:0.500000;impact60:0.500000 | 19.68% | 8.65% | 1.9527 | 21.91% | 0.0660 |
| baseline_size_impact_value | full | size_component,impact60,value_component | size_component:0.500000;impact60:0.250000;value_component:0.250000 | 19.80% | 9.25% | 1.0628 | 30.53% | 0.0769 |
| baseline_size_impact_value | train | size_component,impact60,value_component | size_component:0.500000;impact60:0.250000;value_component:0.250000 | 22.24% | 9.58% | 0.5809 | 30.53% | 0.0807 |
| baseline_size_impact_value | validation | size_component,impact60,value_component | size_component:0.500000;impact60:0.250000;value_component:0.250000 | 16.01% | 8.75% | 1.8295 | 19.63% | 0.0709 |
| baseline_size_only | full | size_component | size_component:1.000000 | 20.12% | 8.64% | 1.0055 | 33.21% | 0.0560 |
| baseline_size_only | train | size_component | size_component:1.000000 | 22.01% | 8.61% | 0.5314 | 33.21% | 0.0528 |
| baseline_size_only | validation | size_component | size_component:1.000000 | 17.17% | 8.67% | 1.7795 | 23.02% | 0.0609 |

## Limits

- Component terms without an individual saved positive platform run are labeled `local_component_proxy`; they are not presented as independent platform factors.
- AlphaPROBE uses expanding historical selection only. Its original continuous least-squares coefficients are not used in the reported combination, so the result tests adaptive membership rather than a rolling coefficient search.
- The validation period is a holdout for the static MSE fit and for each expanding selection decision; factor-set choice still comes from the existing research catalog.

Detailed periods: `research_reports/platform_alignment/alphagen-combination-20261009.periods.csv`; rolling selections: `research_reports/platform_alignment/alphagen-combination-20261009.selections.csv`.
