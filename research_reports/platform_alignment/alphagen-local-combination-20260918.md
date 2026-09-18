# AlphaGen local constrained combination

Alignment rules: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.

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
| AlphaPROBE_expanding_simple | full | dynamic_top5 | signed_equal_1/N_per_period | 11.88% | 36.30% | 0.9079 | 30.90% | 0.1144 |
| AlphaPROBE_expanding_simple | train | dynamic_top5 | signed_equal_1/N_per_period | 10.40% | 36.31% | 0.1389 | 30.90% | 0.1175 |
| AlphaPROBE_expanding_simple | validation | dynamic_top5 | signed_equal_1/N_per_period | 13.55% | 36.29% | 1.8096 | 19.65% | 0.1109 |
| MseAlphaPool_simple | full | value_component,impact60,reversal40,weighted_reversal_lowturn,size_component | value_component:0.200000;impact60:0.200000;reversal40:0.200000;weighted_reversal_lowturn:0.200000;size_component:0.200000 | 13.89% | 35.05% | 0.8962 | 30.38% | 0.1188 |
| MseAlphaPool_simple | train | value_component,impact60,reversal40,weighted_reversal_lowturn,size_component | value_component:0.200000;impact60:0.200000;reversal40:0.200000;weighted_reversal_lowturn:0.200000;size_component:0.200000 | 13.90% | 34.85% | 0.3122 | 30.38% | 0.1232 |
| MseAlphaPool_simple | validation | value_component,impact60,reversal40,weighted_reversal_lowturn,size_component | value_component:0.200000;impact60:0.200000;reversal40:0.200000;weighted_reversal_lowturn:0.200000;size_component:0.200000 | 13.89% | 35.36% | 1.8214 | 19.65% | 0.1119 |
| baseline_atomic_equal | full | size_component,impact60,value_component,roe_component,low_asset_growth_component,reversal40,drawdown120,weighted_reversal_lowturn | size_component:0.125000;impact60:0.125000;value_component:0.125000;roe_component:0.125000;low_asset_growth_component:0.125000;reversal40:0.125000;drawdown120:0.125000;weighted_reversal_lowturn:0.125000 | 11.82% | 36.38% | 0.8328 | 28.08% | 0.1117 |
| baseline_atomic_equal | train | size_component,impact60,value_component,roe_component,low_asset_growth_component,reversal40,drawdown120,weighted_reversal_lowturn | size_component:0.125000;impact60:0.125000;value_component:0.125000;roe_component:0.125000;low_asset_growth_component:0.125000;reversal40:0.125000;drawdown120:0.125000;weighted_reversal_lowturn:0.125000 | 12.09% | 35.76% | 0.2511 | 28.08% | 0.1154 |
| baseline_atomic_equal | validation | size_component,impact60,value_component,roe_component,low_asset_growth_component,reversal40,drawdown120,weighted_reversal_lowturn | size_component:0.125000;impact60:0.125000;value_component:0.125000;roe_component:0.125000;low_asset_growth_component:0.125000;reversal40:0.125000;drawdown120:0.125000;weighted_reversal_lowturn:0.125000 | 11.40% | 37.32% | 1.7602 | 20.72% | 0.1059 |
| baseline_paper_composite | full | paper_composite_baseline | paper_composite_baseline:1.000000 | 9.52% | 9.29% | 0.7837 | 24.96% | 0.0690 |
| baseline_paper_composite | train | paper_composite_baseline | paper_composite_baseline:1.000000 | 13.85% | 9.51% | 0.2954 | 24.96% | 0.0810 |
| baseline_paper_composite | validation | paper_composite_baseline | paper_composite_baseline:1.000000 | 2.78% | 8.95% | 1.5002 | 19.92% | 0.0504 |
| baseline_size_impact | full | size_component,impact60 | size_component:0.500000;impact60:0.500000 | 18.54% | 7.89% | 0.9855 | 31.22% | 0.0619 |
| baseline_size_impact | train | size_component,impact60 | size_component:0.500000;impact60:0.500000 | 18.15% | 8.09% | 0.3913 | 31.22% | 0.0593 |
| baseline_size_impact | validation | size_component,impact60 | size_component:0.500000;impact60:0.500000 | 19.15% | 7.58% | 1.9825 | 21.47% | 0.0660 |

## Limits

- Component terms without an individual saved positive platform run are labeled `local_component_proxy`; they are not presented as independent platform factors.
- AlphaPROBE uses expanding historical selection only. Its original continuous least-squares coefficients are not used in the reported combination, so the result tests adaptive membership rather than a rolling coefficient search.
- The validation period is a holdout for the static MSE fit and for each expanding selection decision; factor-set choice still comes from the existing research catalog.

Detailed periods: `/data/games/factor_/research_reports/platform_alignment/alphagen-local-combination-20260918.periods.csv`; rolling selections: `/data/games/factor_/research_reports/platform_alignment/alphagen-local-combination-20260918.selections.csv`.
