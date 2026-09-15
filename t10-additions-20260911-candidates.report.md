# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T10-ADD-G13-20260911 | 1 | 0.1043 | 0.4295 | 23.64% | 26.57% | 4.02% | 19.62% | 1.0722 | 30.32% | 61.67% |
| T10-ADD-BM-20260911 | 1 | 0.1192 | 0.4465 | 22.53% | 29.35% | 4.44% | 18.09% | 1.0813 | 27.72% | 63.33% |
| T10-ADD-DD120-20260911 | 1 | 0.1052 | 0.4312 | 21.70% | 32.18% | 4.87% | 16.83% | 0.9897 | 30.19% | 61.67% |
