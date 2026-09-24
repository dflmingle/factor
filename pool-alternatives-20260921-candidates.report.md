# PandaAI Factor Research Report

- Candidates: 3; completed: 1; failed: 2
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0001
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-P260921-02 | 1 | 0.0946 | 0.3609 | 21.31% | 19.32% | 2.92% | 18.39% | 1.0526 | 33.00% | 66.67% |

## Failures

- `F-P260921-03`: run: 因子分析执行失败（无详细错误信息）
- `F-P260921-04`: run: 因子分析执行失败（无详细错误信息）
