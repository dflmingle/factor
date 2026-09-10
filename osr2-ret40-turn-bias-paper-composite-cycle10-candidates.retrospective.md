# Three-sleeve composite retrospective

Date: 2026-09-08  
Source window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10OSRTURNPAPER-20260908-`

## Definition

```text
(
  RANK(1 - RETURNS(CLOSE,40))
  + RANK(1 - MA(TURNOVER,21) / MA(TURNOVER,504))
  + RANK(
      ZSCORE(RANK(book_to_market_ratio_lyr))
      + ZSCORE(RANK(oper_roe_lyr))
      - ZSCORE(RANK(gr_total_asset_lyr))
      - ZSCORE(RANK(MARKET_CAP))
    )
) / 3
```

The three sleeves are 40-day price reversal, a direction-aligned recent-versus-long-run
turnover bias, and the previously tested paper-derived value, profitability, investment, and
size composite. The factor direction is `1`, so the highest-ranked decile is the long side.

## Result

| Metric | Value |
| --- | ---: |
| Rank IC | 0.1148 |
| IC mean | 0.0669 |
| IC IR | 0.4456 |
| IC p-value | 0.0000 |
| Monotonicity | 0.98 |
| Long-side excess | 17.61% |
| Turnover | 39.46% |
| Annual cost | 5.97% |
| Net excess | **11.64%** |
| Long Sharpe | 0.9960 |
| Max drawdown | 24.66% |
| Monthly win rate | 63.33% |

The platform displays the IC p-value rounded to four decimals; it is the p-value of the
IC-mean t-statistic, not a p-value for Rank IC. With 98 study-wide hypotheses, the rough
multiple-testing reference is p < 0.0005. The displayed value passes that reference, subject to
the rounding caveat.

## Comparison with existing 10-day composites

| Candidate | Rank IC | IC IR | Long excess | Turnover | Annual cost | Net excess | Long Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `OSR2-RET40-TURN-BIAS-EQ` | 0.0987 | 0.4228 | 14.77% | 48.77% | 7.37% | 7.40% | 0.8345 | 30.05% |
| `paper-derived-composite` | 0.0717 | 0.2696 | 12.61% | 9.31% | 1.41% | 11.20% | 0.8284 | 26.39% |
| `OSR2-RET40-TURN-BIAS-PAPER-EQ` | **0.1148** | **0.4456** | **17.61%** | 39.46% | 5.97% | **11.64%** | **0.9960** | **24.66%** |

Relative to the prior two-sleeve composite, this version adds 2.84 percentage points of gross
long-side excess, reduces turnover by 9.31 points, lowers annual cost by 1.40 points, and raises
net excess by 4.24 points. Relative to the low-turnover paper-derived composite, it raises net
excess by only 0.44 points while adding 30.15 points of turnover and 4.56 points of annual cost.

## Research decision

Retain as a leading research candidate and **orthogonalize before any pool decision**. Its result
is attractive after costs, but the formula contains both sleeves of the prior two-factor
composite and the prior paper-derived composite, so structural redundancy is expected. A factor
value download and local Spearman correlation against those existing objects were not performed
in this batch; no correlation estimate is asserted here.

No additional cycle, size exclusion, calendar split, or non-overlapping out-of-sample run was
started automatically. Those are the next falsification and validation checks if this candidate
is selected for a later research round. This is an in-sample five-year result, not an official
competition pool score.

## Records

- Candidate manifest: `osr2-ret40-turn-bias-paper-composite-cycle10-candidates.txt`
- Checkpoint: `osr2-ret40-turn-bias-paper-composite-cycle10-candidates.txt.state.json`
- Ranked report: `osr2-ret40-turn-bias-paper-composite-cycle10-candidates.report.md`
- Filterable table: `osr2-ret40-turn-bias-paper-composite-cycle10-candidates.report.csv`
- Factor id: `6a9fe1363e7967143f8fab47`
- Run id: `6a9fe1366df2a192a47e76a5`
- Actual billing: 4.0 credits deducted; result payload balance 672.523142
