# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-A18 | 1 | 0.0646 | 0.2892 | 3.51% | 38.73% | 11.71% | -8.20% | 0.4393 | 43.66% | 53.33% |
| F-A20 | 1 | 0.0190 | 0.2224 | 3.21% | 61.37% | 18.56% | -15.35% | 0.4763 | 34.31% | 63.33% |
| F-A19 | 1 | -0.0010 | 0.0477 | -17.88% | 60.46% | 18.28% | -36.16% | -0.3357 | 64.98% | 55.00% |
