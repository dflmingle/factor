# PandaAI Factor Research Report

- Candidates: 3; completed: 1; failed: 2
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0003
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GFN-UNT-20260916-EVPRICE | 1 | 0.0044 | 0.1733 | 1.68% | 89.85% | 27.17% | -25.49% | 0.4357 | 35.07% | 60.00% |

## Failures

- `GFN-UNT-20260916-BMQUALITY`: run: 因子分析执行失败（无详细错误信息）
- `GP-UNT-20260916-CONTRACT-RET30`: run: 因子分析执行失败（无详细错误信息）
