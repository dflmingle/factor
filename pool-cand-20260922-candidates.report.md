# PandaAI Factor Research Report

- Candidates: 3; completed: 2; failed: 1
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0000
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-P260922-01 | 1 | 0.0863 | 0.3371 | 24.21% | 15.12% | 2.29% | 21.92% | 1.0829 | 32.69% | 65.00% |
| F-P260922-02 | 1 | 0.0912 | 0.3527 | 22.87% | 14.05% | 2.12% | 20.75% | 1.0738 | 31.60% | 66.67% |

## Failures

- `F-P260922-03`: run: 因子分析执行失败（无详细错误信息）
