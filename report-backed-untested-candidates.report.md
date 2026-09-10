# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0006
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HT13-NEW-HIST-OPPROFIT-6Q | 1 | 0.0021 | 0.1380 | 0.14% | 12.91% | 3.90% | -3.76% | 1.0299 | 21.44% | 62.96% |
| HT13-NEW-HIST-GPM-6Q | 1 | -0.0002 | -0.0577 | -3.42% | 11.21% | 3.39% | -6.81% | 0.9850 | 21.63% | 62.96% |
| HT13-NEW-ALPHA40 | 1 | 0.0690 | 0.3415 | 4.87% | 72.39% | 21.89% | -17.02% | 0.5666 | 37.76% | 61.67% |
