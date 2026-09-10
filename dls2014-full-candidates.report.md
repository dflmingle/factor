# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DLS14-NCF-PROXY-20D | 1 | 0.0434 | 0.1663 | 2.71% | 34.73% | 10.50% | -7.79% | 0.4715 | 37.02% | 55.00% |
| DLS14-STREV-20D | 1 | 0.0624 | 0.3192 | 7.21% | 52.46% | 15.86% | -8.65% | 0.5697 | 40.64% | 56.67% |
