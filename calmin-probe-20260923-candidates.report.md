# PandaAI Factor Research Report

- Candidates: 3; completed: 2; failed: 1
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CALMIN-20260923-CLOSE15-VPC | 1 | -0.0085 | -0.1414 | -1.15% | 89.15% | 13.48% | -14.63% | 0.3042 | 30.28% | 53.33% |
| CALMIN-20260923-MIN5-SKEW | 1 | -0.0346 | -0.2296 | -10.41% | 85.37% | 12.91% | -23.32% | -0.0673 | 49.26% | 45.00% |

## Failures

- `CALMIN-20260923-OPEN30-RET`: run: 因子分析执行失败（无详细错误信息）
