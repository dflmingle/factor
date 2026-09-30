# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL5-CTRL-20260929 | 1 | 0.1678 | 0.9748 | 50.36% | 24.10% | 3.64% | 46.72% | 2.0611 | 20.73% | 75.00% |
| POOL6-LAMD10K5V2-20260929 | 1 | 0.1709 | 0.9540 | 47.62% | 28.45% | 4.30% | 43.32% | 1.9921 | 21.22% | 75.00% |
