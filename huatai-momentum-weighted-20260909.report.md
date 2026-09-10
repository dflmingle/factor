# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0004
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HT13-WGTRET-1M | 1 | 0.0915 | 0.4978 | 9.71% | 70.85% | 10.71% | -1.00% | 0.6968 | 26.75% | 60.00% |
| HT13-EXPWRET-3M | 1 | 0.0946 | 0.4943 | 7.86% | 62.49% | 9.45% | -1.59% | 0.6252 | 27.14% | 61.67% |
| HT13-EXPWRET-6M | 1 | 0.0991 | 0.4398 | 6.49% | 216.73% | 32.77% | -26.28% | 0.5002 | 30.76% | 58.33% |
