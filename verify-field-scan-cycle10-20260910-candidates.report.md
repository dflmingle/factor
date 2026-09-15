# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VERIFY10-E260910-04 | 1 | 0.0823 | 0.3162 | 18.23% | 9.85% | 1.49% | 16.74% | 0.9567 | 29.62% | 65.00% |
| VERIFY10-F260910-12 | 1 | 0.0804 | 0.3148 | 16.41% | 9.02% | 1.36% | 15.05% | 0.9458 | 25.85% | 66.67% |
| VERIFY10-G260910-13 | 1 | 0.0559 | 0.3041 | 15.37% | 9.43% | 1.43% | 13.94% | 0.8357 | 32.54% | 61.67% |
