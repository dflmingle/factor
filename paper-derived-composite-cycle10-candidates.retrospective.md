# Paper-derived composite: 10-day rebalance retrospective

Date: 2026-09-08  
Source window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10CMP-20260908-`

## Decision

Retain `paper-derived-composite` as a leading low-turnover research candidate. At 10 days it
keeps nearly the same cost-adjusted long-side result as the existing 5-day version, while annual
turnover cost falls. This is a stronger cycle choice for further validation, but not a submission
decision or an official pool score.

## Results

| Metric | 5-day | 10-day |
| --- | ---: | ---: |
| Rank IC | 0.0597 | 0.0717 |
| IC IR | 0.2221 | 0.2696 |
| IC p-value | 0.0007 | 0.0038 |
| Monotonicity | 0.99 | 0.99 |
| Long-side excess | 13.32% | 12.61% |
| Turnover | 6.32% | 9.31% |
| Annual cost | 1.91% | 1.41% |
| Net excess | **11.41%** | **11.20%** |
| Long Sharpe | 0.8395 | 0.8284 |
| Max drawdown | 35.74% | 26.39% |
| Monthly win rate | 63.33% | 65.00% |

The 10-day result is almost unchanged after costs: net excess declines by only 0.21 percentage
points. The per-rebalance turnover is higher because fewer, larger portfolio changes occur each
time; the annual cost is lower because the rebalance frequency is halved.

With 96 study-wide hypotheses, the rough multiple-testing reference is p < 0.0005. The displayed
IC p-value is for the IC-mean t-statistic, not Rank IC, and 0.0038 does not pass that study-wide
reference. The exact 10-day version has not yet had a non-overlapping out-of-sample validation.

## Mechanism and records

The composite combines value (book-to-market), profitability (ROE), conservative investment
(inverse asset growth), and a small-cap tilt (inverse market capitalization), after cross-sectional
rank and z-score standardization.

- Candidate manifest: `paper-derived-composite-cycle10-candidates.txt`
- Checkpoint: `paper-derived-composite-cycle10-candidates.txt.state.json`
- Ranked report: `paper-derived-composite-cycle10-candidates.report.md`
- Filterable table: `paper-derived-composite-cycle10-candidates.report.csv`
- New platform object uses the `T10CMP-20260908-` prefix.
