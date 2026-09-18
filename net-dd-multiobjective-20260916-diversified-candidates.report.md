# PandaAI Factor Research Report

- Candidates: 3; completed: 2; failed: 1
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0003
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-NET-D03 | 1 | 0.0176 | 0.0800 | 7.76% | 68.37% | 20.68% | -12.92% | 0.2301 | 25.23% | 36.00% |
| F-NET-D02 | 1 | -0.0036 | -0.1583 | 2.59% | 90.35% | 27.32% | -24.73% | 1.1271 | 21.41% | 50.00% |

## Failures

- `F-NET-D01`: result: fewer than two group rows returned
