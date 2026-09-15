# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0003
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10-SIZE-PLUS-IMPACT | 1 | 0.1113 | 0.4524 | 22.79% | 30.64% | 4.63% | 18.16% | 1.0453 | 29.97% | 61.67% |
| T10-SIZE-PLUS-IMPACT-WC | 1 | 0.1052 | 0.4421 | 21.58% | 27.36% | 4.14% | 17.44% | 1.0260 | 28.76% | 65.00% |
| T10-SIZE-PLUS-WC-MCAP | 1 | 0.1032 | 0.4395 | 19.43% | 32.07% | 4.85% | 14.58% | 0.9569 | 28.72% | 61.67% |
