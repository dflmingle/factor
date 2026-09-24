# PandaAI Factor Research Report

- Candidates: 3; completed: 2; failed: 1
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-P260921-07 | 1 | 0.1027 | 0.4005 | 22.27% | 26.25% | 3.97% | 18.30% | 1.0118 | 33.68% | 63.33% |
| F-P260921-08 | 1 | 0.1134 | 0.4106 | 22.29% | 29.78% | 4.50% | 17.79% | 1.0577 | 29.45% | 65.00% |

## Failures

- `F-P260921-06`: run: 因子分析执行失败（无详细错误信息）
