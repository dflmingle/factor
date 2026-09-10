# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0006
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HT-EXPWREV-63D | 1 | 0.0809 | 0.2926 | 6.24% | 23.85% | 7.21% | -0.97% | 0.5694 | 37.74% | 63.33% |
| HT-WREV-LOWTURN-21D | 1 | 0.0817 | 0.3550 | 11.12% | 43.55% | 13.17% | -2.05% | 0.7707 | 34.33% | 63.33% |
| HT-WREV-21D | 1 | 0.0750 | 0.3102 | 6.91% | 52.47% | 15.87% | -8.96% | 0.5917 | 37.33% | 58.33% |
