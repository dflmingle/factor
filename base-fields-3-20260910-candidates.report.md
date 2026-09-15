# PandaAI Factor Research Report

- Candidates: 3; completed: 1; failed: 2
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0003
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE-DIV-YIELD-TTM | 1 | 0.0294 | 0.0415 | 0.79% | 5.69% | 0.86% | -0.07% | 0.5093 | 17.69% | 61.67% |

## Failures

- `BASE-GROSSPROFIT-ASSET-TTM`: run: 因子分析执行失败（无详细错误信息）
- `BASE-ACCRUAL-CASH-TTM`: run: 因子分析执行失败（无详细错误信息）
