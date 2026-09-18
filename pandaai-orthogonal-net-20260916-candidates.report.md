# PandaAI Factor Research Report

- Candidates: 3; completed: 1; failed: 2
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-NET03-PLAT-20260916 | 1 | 0.0305 | 0.2449 | 16.00% | 43.67% | 13.21% | 2.79% | 0.8177 | 45.56% | 63.33% |

## Failures

- `F-NET01-PLAT-20260916`: run: 因子分析执行失败（无详细错误信息）
- `F-NET02-PLAT-20260916`: run: 因子分析执行失败（无详细错误信息）
