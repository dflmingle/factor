# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL9-BSAFE-ADD4-KEEP5-20261005 | 1 | 0.1073 | 0.4184 | 21.13% | 21.30% | 3.22% | 17.91% | 1.0458 | 31.11% | 65.00% |
| POOL8-BSAFE-S1-KEEP4-DROP-SIZE-20261005 | 1 | 0.1105 | 0.4262 | 20.18% | 22.56% | 3.41% | 16.77% | 1.0371 | 29.58% | 65.00% |
| POOL9-BSAFE-S3-KEEP4-DROP-IMPACT-20261005 | 1 | 0.1146 | 0.4586 | 20.33% | 26.47% | 4.00% | 16.33% | 1.0496 | 40.36% | 63.79% |
