# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL5-SWAP-IMPACT-K10-20261005 | 1 | 0.1067 | 0.3957 | 22.91% | 20.21% | 3.06% | 19.85% | 1.1030 | 30.87% | 66.67% |
| POOL5-SWAP-E-K10-20261005 | 1 | 0.1031 | 0.4098 | 22.50% | 20.15% | 3.05% | 19.45% | 1.0789 | 31.00% | 65.00% |
| POOL5-SWAP-SIZE-K10-20261005 | 1 | 0.1070 | 0.4052 | 21.18% | 19.56% | 2.96% | 18.22% | 1.0674 | 29.01% | 65.00% |
