# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VV6-500-platform | 1 | 0.0917 | 0.5595 | 13.22% | 67.02% | 10.13% | 3.09% | 0.9275 | 34.57% | 65.00% |
| VV6-756-platform | 1 | 0.0825 | 0.4362 | 9.28% | 67.12% | 10.15% | -0.87% | 1.4885 | 21.15% | 70.37% |
