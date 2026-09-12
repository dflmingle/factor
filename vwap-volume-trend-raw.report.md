# PandaAI Factor Research Report

- Candidates: 1; completed: 1; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0004
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VWAP10-VOL20-MOM20-RAW | 1 | 0.0449 | 0.5835 | -0.74% | 61.65% | 9.32% | -10.06% | 0.3695 | 22.62% | 51.67% |
