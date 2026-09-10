# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0005
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OSR2-RET40 | 1 | 0.0908 | 0.3602 | 13.35% | 55.02% | 8.32% | 5.03% | 0.7380 | 30.05% | 60.00% |
| HT13-TURN-BIAS-1M | 0 | -0.0737 | -0.3612 | 9.04% | 26.97% | 4.08% | 4.96% | 0.9491 | 22.94% | 58.97% |
| OSR2-DD120 | 1 | 0.0405 | 0.2085 | 8.69% | 29.39% | 4.44% | 4.25% | 0.5506 | 28.55% | 55.00% |
