# PandaAI Factor Research Report

- Candidates: 3; completed: 2; failed: 1
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CT-VOL-STD10-20261006 | 1 | 0.0772 | 0.5341 | 6.63% | 47.04% | 7.11% | -0.48% | 0.6624 | 27.70% | 63.33% |
| CT-COMP-TURNOVER-20261006 | 1 | 0.0879 | 0.2366 | 3.54% | 42.65% | 6.45% | -2.91% | 0.6304 | 23.33% | 60.00% |

## Failures

- `CT-COMP-ACTIVITY-20261006`: result: fewer than two group rows returned
