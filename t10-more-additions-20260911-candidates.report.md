# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10-ADD-AGG-IMPACT-20260911 | 1 | 0.1057 | 0.4379 | 23.78% | 26.59% | 4.02% | 19.76% | 1.0788 | 29.91% | 61.67% |
| T10-ADD-DOWNSIDE-IMPACT-20260911 | 1 | 0.1067 | 0.4389 | 23.48% | 27.05% | 4.09% | 19.39% | 1.0719 | 30.03% | 61.67% |
| T10-ADD-FSCORE-20260911 | 1 | 0.1118 | 0.4822 | 22.13% | 30.78% | 4.65% | 17.48% | 1.0709 | 26.48% | 65.00% |
