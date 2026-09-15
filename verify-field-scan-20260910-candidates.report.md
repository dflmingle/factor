# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VERIFY-E260910-04 | 1 | 0.0681 | 0.2692 | 19.89% | 7.05% | 2.13% | 17.76% | 1.0014 | 39.04% | 63.33% |
| VERIFY-F260910-12 | 1 | 0.0656 | 0.2602 | 17.37% | 5.89% | 1.78% | 15.59% | 0.9630 | 35.67% | 63.33% |
| VERIFY-G260910-13 | 1 | 0.0450 | 0.2731 | 16.40% | 5.62% | 1.70% | 14.70% | 0.8539 | 42.66% | 65.00% |
