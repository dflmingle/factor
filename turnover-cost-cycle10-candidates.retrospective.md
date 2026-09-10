# Turnover-cost candidates: 10-day rebalance retrospective

Date: 2026-09-08  
Source window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10-20260908-`

## Decision

`HT-WREV-LOWTURN-21D` is the only candidate with positive cost-adjusted long-side excess
return. It is the current survivor for a later robustness check, not a submission decision.
`OSR2-RET20` and `HT13-REVERSAL-20D` are near break-even and remain watch-list candidates.
The remaining four do not pass the current cost-adjusted screen.

## Results

| Candidate | Rank IC | IC IR | IC p | Monotonicity | Long excess | Turnover | Annual cost | Net excess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HT-WREV-LOWTURN-21D` | 0.0998 | 0.4790 | 0.0000 | 0.90 | 11.94% | 61.03% | 9.23% | **2.71%** |
| `OSR2-RET20` | 0.0881 | 0.4036 | 0.0000 | 0.85 | 10.61% | 70.85% | 10.71% | -0.10% |
| `HT13-REVERSAL-20D` | 0.0867 | 0.4653 | 0.0000 | 0.85 | 10.48% | 70.89% | 10.72% | -0.24% |
| `HT-WREV-21D` | 0.0927 | 0.4575 | 0.0000 | 0.88 | 9.90% | 70.81% | 10.71% | -0.81% |
| `OSR-RSI14-20D` | 0.0664 | 0.2778 | 0.0029 | 0.81 | 5.31% | 66.05% | 9.99% | -4.68% |
| `HT13-ALPHA13` | 0.0457 | 0.2466 | 0.0079 | 0.74 | 3.92% | 85.52% | 12.93% | -9.01% |
| `HT13-ALPHA44` | 0.0396 | 0.2485 | 0.0075 | 0.94 | 3.57% | 87.26% | 13.19% | -9.62% |

## Comparison with the earlier 5-day run

The first four reversal-related candidates improved their net excess by roughly 4.8 to 8.4
percentage points. `HT-WREV-LOWTURN-21D` moved from -2.05% to +2.71%. The two basic reversal
proxies moved close to break-even. Alpha13 and Alpha44 still failed despite the lower annual
cost because their gross long-side excess weakened and their per-rebalance turnover remained
very high.

The displayed IC p-value is for the IC-mean t-statistic, not Rank IC. With 92 study-wide
hypotheses, the rough multiple-testing reference is p < 0.0005. These are in-sample five-year
results; no out-of-sample or cycle-robustness run was performed in this batch.

## Records

- Candidate manifest: `turnover-cost-cycle10-candidates.txt`
- Checkpoint: `turnover-cost-cycle10-candidates.txt.state.json`
- Ranked report: `turnover-cost-cycle10-candidates.report.md`
- Filterable table: `turnover-cost-cycle10-candidates.report.csv`
- New platform objects use the `T10-20260908-` prefix.
