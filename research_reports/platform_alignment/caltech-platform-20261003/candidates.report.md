# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CT-COMP-AMTDISP-20261003 | 1 | 0.1049 | 0.4360 | 17.42% | 27.41% | 4.14% | 13.28% | 0.9747 | 28.85% | 65.00% |
| CT-AMT-STD20-20261003 | 1 | 0.1063 | 0.4278 | 16.49% | 34.89% | 5.28% | 11.21% | 0.9441 | 29.33% | 65.00% |
| CT-COMP-TOPMIX-20261003 | 1 | 0.1076 | 0.4101 | 11.44% | 47.26% | 7.15% | 4.29% | 0.8515 | 24.51% | 63.33% |
