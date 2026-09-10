# Paper-derived composite without small-cap sleeve retrospective

Date: 2026-09-09  
Parent comparison window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10CMP-NOMCAP-20260909-`

## Ablation

The only change from `paper-derived-composite` is removing the explicit inverse-market-cap term.
The remaining value, profitability, and conservative-investment sleeves are unchanged.

```text
ZSCORE(RANK(book_to_market_ratio_lyr))
+ ZSCORE(RANK(oper_roe_lyr))
- ZSCORE(RANK(gr_total_asset_lyr))
```

## Result

| Metric | Parent with small-cap sleeve | No small-cap sleeve | Change |
| --- | ---: | ---: | ---: |
| Rank IC | 0.0717 | 0.0478 | -0.0239 |
| IC mean | 0.0416 | 0.0171 | -0.0245 |
| IC IR | 0.2696 | 0.1156 | -0.1540 |
| IC p-value | 0.0038 | 0.2080 | weaker |
| Monotonicity | 0.99 | 0.84 | -0.15 |
| Long-side excess | 12.61% | 0.83% | -11.78 pp |
| Turnover | 9.31% | 6.25% | -3.06 pp |
| Annual cost | 1.41% | 0.95% | -0.46 pp |
| Net excess | **11.20%** | **-0.11%** | **-11.31 pp** |
| Long Sharpe | 0.8284 | 0.4863 | -0.3421 |
| Max drawdown | 26.39% | 18.51% | -7.88 pp |
| Monthly win rate | 65.00% | 61.67% | -3.33 pp |

## Decision

**Abandon this ablation for the current pool; retain the original composite.** Removing the
small-cap sleeve lowers turnover and annual cost, but the reduction is only 3.06 and 0.46
percentage points, respectively. It removes 11.78 points of gross long-side excess, leaving the
net result slightly negative. The displayed IC p-value of 0.2080 also fails the rough study-wide
reference of `p < 0.0005` for 100 hypotheses.

The result shows that the small-cap sleeve is important to this particular five-year signal, but
does not establish that its return is pure alpha rather than size exposure. This remains an
in-sample result with no industry or market-cap neutralization and no out-of-sample validation.

## Records

- Candidate manifest: `paper-derived-nomcap-cycle10-candidates.txt`
- Checkpoint: `paper-derived-nomcap-cycle10-candidates.txt.state.json`
- Ranked report: `paper-derived-nomcap-cycle10-candidates.report.md`
- Filterable table: `paper-derived-nomcap-cycle10-candidates.report.csv`
- Factor id: `6aa0c28251cdfe29b2e0b6ea`
- Run id: `6aa0c2836df2a192a47e77c5`
- Actual billing: 4.0 credits deducted; settled balance 674.120152
