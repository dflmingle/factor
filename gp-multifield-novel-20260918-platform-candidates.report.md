# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-GP-NOVEL-20260918-02 | 1 | -0.0063 | -0.0989 | 9.51% | 2.44% | 0.74% | 8.77% | 0.5998 | 43.92% | 60.00% |
| F-GP-NOVEL-20260918-01 | 1 | -0.0284 | -0.0790 | 8.97% | 2.83% | 0.86% | 8.11% | 0.6214 | 39.31% | 61.67% |
| F-GP-NOVEL-20260918-03 | 1 | 0.0174 | 0.0164 | 8.78% | 4.07% | 1.23% | 7.55% | 0.6493 | 38.60% | 61.67% |
