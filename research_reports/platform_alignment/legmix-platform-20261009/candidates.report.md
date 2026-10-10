# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL6-CAND-C-20261009 | 1 | 0.1199 | 0.4667 | 18.34% | 37.57% | 5.68% | 12.66% | 1.0256 | 26.76% | 63.33% |
| POOL6-CAND-B-20261009 | 1 | 0.1019 | 0.3345 | 12.61% | 24.74% | 3.74% | 8.87% | 0.9407 | 20.42% | 65.00% |
| POOL6-CAND-A-20261009 | 1 | 0.1194 | 0.4463 | 14.45% | 42.26% | 6.39% | 8.06% | 0.9302 | 24.65% | 65.00% |
