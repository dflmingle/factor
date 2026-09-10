# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0004
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NONHT-FSCORELIKE-REV40-INTERACT | 1 | 0.0743 | 0.3348 | 8.11% | 41.45% | 6.27% | 1.84% | 0.6500 | 28.93% | 56.67% |
| NONHT-RESVOL-MAX-INTERACT-21D | 1 | 0.0754 | 0.2033 | 1.30% | 46.38% | 7.01% | -5.71% | 0.4771 | 28.67% | 61.67% |
