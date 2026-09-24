# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-3M-G03 | 1 | 0.1607 | 0.5637 | 50.06% | 13.22% | 2.00% | 48.06% | 1.2232 | 10.48% | 66.67% |
| F-3M-C08 | 1 | 0.1733 | 0.5793 | 45.76% | 11.09% | 1.68% | 44.08% | 1.2631 | 8.60% | 66.67% |
| F-3M-C02 | 1 | 0.1618 | 0.5669 | 45.16% | 8.20% | 1.24% | 43.92% | 1.2688 | 8.77% | 66.67% |
