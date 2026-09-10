# Report-backed untested directions: retrospective

- Window: 2021-09-07 to 2026-09-07
- Rebalance: 5 trading days
- Groups: 10
- One-way cost assumption: 0.30%
- Candidates tested in this batch: 3
- Study-wide hypothesis count: 88; rough reference threshold: `p < 0.0006`
- Billing: 8 credits deducted; balance after settlement: 718.523142

## Results

| Candidate | Formula | Rank IC | IC p | Mono | Long excess | Turnover | Annual cost | Net excess | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `HT13-NEW-ALPHA40` | `-1 * RANK(STDDEV(HIGH,10)) * CORR(HIGH,VOLUME,10)` | 0.0690 | 0.0000 | 0.87 | 4.87% | 72.39% | 21.89% | -17.02% | abandon for current pool |
| `HT13-NEW-HIST-OPPROFIT-6Q` | `TS_RANK(oper_oper_profit_to_tp_ttm,756)` | 0.0021 | 0.1564 | 0.67 | 0.14% | 12.91% | 3.90% | -3.76% | abandon |
| `HT13-NEW-HIST-GPM-6Q` | `TS_RANK(oper_gross_margin_ttm,756)` | -0.0002 | 0.5509 | 0.34 | -3.42% | 11.21% | 3.39% | -6.81% | abandon |

## Attribution

- `HT13-NEW-ALPHA40`: the report-backed price-volume interaction produced a strong raw Rank IC and acceptable monotonicity, but its 72.39% held-decile turnover implies an annual cost larger than the gross long-side excess. It is not competitive under the current cost assumption.
- `HT13-NEW-HIST-OPPROFIT-6Q`: the TTM proxy for the report's quarterly operating-profit quality percentile has low turnover, but its IC p-value and Rank IC are weak and the gross long-side excess does not cover cost.
- `HT13-NEW-HIST-GPM-6Q`: the TTM proxy for the report's quarterly gross-margin percentile has low turnover, but it is effectively null or adverse in this window. The quarterly-to-daily TTM proxy remains a possible data-mismatch explanation, not evidence for retuning it in sample.

## Research decision

All three candidates are in-sample five-year results and none is retained for the current pool. No second-round lookback, direction, or threshold tuning is justified after the cost-adjusted failure. Cross-sectional correlation and independent holdout checks were not run because there is no survivor to escalate; the raw results and ranked report remain available for audit.

Records:

- Candidate file: `report-backed-untested-candidates.txt`
- Ranked report: `report-backed-untested-candidates.report.md` and `.csv`
- Raw responses: `report-backed-untested-candidates.results/`
