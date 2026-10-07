# PandaAI Factor Research Report

- Candidates: 1; completed: 0; failed: 1
- Settings: 3-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0500
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - | - | - |

## Failures

- `POOL5-LIVE-CYCLE3-20261007`: run: HTTP 409, code=None: 工作流已在运行中 (run_id: 6ac6337b9e9d797cfb2d25f9)，请勿重复启动
