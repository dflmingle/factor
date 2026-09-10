# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0125
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DLS14-DR-OPCF-20D | 1 | 0.0510 | 0.2008 | 3.69% | 37.30% | 11.28% | -7.59% | 0.5112 | 36.75% | 60.00% |
| DLS14-DR-BROAD-20D | 1 | 0.0515 | 0.2039 | 2.86% | 37.56% | 11.36% | -8.50% | 0.4714 | 38.22% | 55.00% |
