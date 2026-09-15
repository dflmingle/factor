# PandaAI Factor Research Report

- Candidates: 5; completed: 5; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0100
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NEW-VALUE-EVEBITDA | 1 | 0.0202 | 0.1731 | 4.31% | 6.55% | 0.99% | 3.32% | 0.4379 | 37.18% | 58.33% |
| NEW-GROWTH-REV-TTM | 1 | -0.0004 | -0.0006 | -1.42% | 5.29% | 0.80% | -2.22% | 0.2765 | 50.81% | 46.67% |
| NEW-GROWTH-ROE-TTM | 1 | 0.0113 | -0.0209 | -1.44% | 6.56% | 0.99% | -2.43% | 0.3062 | 31.75% | 56.67% |
| NEW-HIST-ROE-6Q | 1 | -0.0022 | 0.0057 | -1.34% | 9.07% | 1.37% | -2.71% | 1.0689 | 17.16% | 62.96% |
| NEW-HIST-ADJPROFIT-6Q | 1 | 0.0038 | 0.1508 | -0.76% | 17.68% | 2.67% | -3.43% | 1.0211 | 19.17% | 70.37% |
