# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U01-LOWPRICE-20261010 | 1 | 0.0485 | 0.2609 | 7.22% | 4.82% | 0.73% | 6.49% | 0.6955 | 18.76% | 61.67% |
| U02-CURRENTASSETS-20261010 | 1 | 0.0095 | 0.1393 | 5.48% | 10.02% | 1.52% | 3.96% | 0.4756 | 33.91% | 53.33% |
