# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a046_t10x750_w20_rsm40 | 1 | 0.0647 | 0.4026 | 8.58% | 61.91% | 9.36% | -0.78% | 0.6157 | 32.91% | 56.67% |
| a046_t10x750_w30_rsm20 | 1 | 0.0682 | 0.3965 | 8.88% | 66.40% | 10.04% | -1.16% | 0.6250 | 32.91% | 58.33% |
| a046_t10x750_w30 | 1 | 0.0715 | 0.4056 | 8.70% | 70.77% | 10.70% | -2.00% | 0.6180 | 32.91% | 58.33% |
