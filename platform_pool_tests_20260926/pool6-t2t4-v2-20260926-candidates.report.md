# PandaAI Factor Research Report

- Candidates: 2; completed: 1; failed: 1
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL6-T2V2-20260926 | 1 | 0.0893 | 0.3764 | 20.58% | 17.50% | 2.65% | 17.93% | 1.1509 | 26.28% | 68.33% |

## Failures

- `POOL6-T4V2-20260926`: run: 轮询超时 (600s)
