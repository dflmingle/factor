# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0004
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NONHT-CHIP-COST-250 | 1 | 0.0677 | 0.2694 | 9.34% | 33.47% | 5.06% | 4.28% | 0.6102 | 29.22% | 53.33% |
| NONHT-LTMOM-EXHIGH-252-21 | 1 | 0.0213 | 0.1486 | 1.74% | 30.91% | 4.67% | -2.93% | 0.4172 | 28.25% | 53.33% |
