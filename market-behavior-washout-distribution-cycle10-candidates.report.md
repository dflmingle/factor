# PandaAI Factor Research Report

- Candidates: 3; completed: 1; failed: 2
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0005
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DISTRIBUTION-RISK-10D | 0 | -0.0375 | -0.2708 | 6.03% | 78.01% | 11.80% | -5.77% | 0.5500 | 28.78% | 53.33% |

## Failures

- `WASHOUT-RECOVERY-10D`: run: 因子分析执行失败（无详细错误信息）
- `INTRADAY-ABSORPTION-10D`: run: 因子分析执行失败（无详细错误信息）
