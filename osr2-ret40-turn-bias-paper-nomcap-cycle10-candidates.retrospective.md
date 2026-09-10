# No-market-cap sleeve ablation retrospective

Date: 2026-09-09  
Parent comparison window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10OSRTURNPAPER-NOMCAP-20260909-`

## Ablation

The only change from `OSR2-RET40-TURN-BIAS-PAPER-EQ` is removing the explicit market-cap sleeve
from the fundamental sub-composite. The denominator remains `/ 3` so this is a literal deletion,
not a reweighting experiment.

```text
(
  RANK(1 - RETURNS(CLOSE,40))
  + RANK(1 - MA(TURNOVER,21) / MA(TURNOVER,504))
  + RANK(
      ZSCORE(RANK(book_to_market_ratio_lyr))
      + ZSCORE(RANK(oper_roe_lyr))
      - ZSCORE(RANK(gr_total_asset_lyr))
    )
) / 3
```

## Result

| Metric | Parent with market-cap sleeve | No market-cap sleeve | Change |
| --- | ---: | ---: | ---: |
| Rank IC | 0.1148 | 0.1015 | -0.0133 |
| IC mean | 0.0669 | 0.0531 | -0.0138 |
| IC IR | 0.4456 | 0.3612 | -0.0844 |
| IC p-value | 0.0000 | 0.0001 | weaker |
| Monotonicity | 0.98 | 0.95 | -0.03 |
| Long-side excess | 17.61% | 11.12% | -6.49 pp |
| Turnover | 39.46% | 38.99% | -0.47 pp |
| Annual cost | 5.97% | 5.90% | -0.07 pp |
| Net excess | **11.64%** | **5.22%** | **-6.42 pp** |
| Long Sharpe | 0.9960 | 0.8338 | -0.1622 |
| Max drawdown | 24.66% | 24.00% | -0.66 pp |
| Monthly win rate | 63.33% | 60.00% | -3.33 pp |

## Decision

**Abandon this ablation for the current pool; retain the parent factor.** Removing the market-cap
term barely changes turnover and annual cost, so it does not solve the low-liquidity or small-cap
exposure concern through trading-cost reduction. In this five-year sample it removes a material
part of the signal and reduces the cost-adjusted result by 6.42 percentage points.

This is evidence about the exact composite and window, not proof that market-cap exposure is an
independent source of alpha. The variant remains an in-sample five-year result with no separate
industry or market-cap neutralization and no out-of-sample validation.

## Records

- Candidate manifest: `osr2-ret40-turn-bias-paper-nomcap-cycle10-candidates.txt`
- Checkpoint: `osr2-ret40-turn-bias-paper-nomcap-cycle10-candidates.txt.state.json`
- Ranked report: `osr2-ret40-turn-bias-paper-nomcap-cycle10-candidates.report.md`
- Filterable table: `osr2-ret40-turn-bias-paper-nomcap-cycle10-candidates.report.csv`
- Factor id: `6aa0c0435d52c44d2f55c0b9`
- Run id: `6aa0c0433e7967143f8fabf6`
- Actual billing: 4.0 credits deducted; settled balance 678.120152
