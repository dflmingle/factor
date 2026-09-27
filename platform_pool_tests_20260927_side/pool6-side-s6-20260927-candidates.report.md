# PandaAI Factor Research Report

- Candidates: 2; completed: 1; failed: 1
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL6-SIDE-S6B-20260927 | 1 | 0.2282 | 0.6881 | 63.31% | 13.39% | 2.02% | 61.29% | 3.3625 | 0.00% | 100.00% |

## Failures

- `POOL6-SIDE-S6A-20260927`: run: 轮询超时 (600s)
