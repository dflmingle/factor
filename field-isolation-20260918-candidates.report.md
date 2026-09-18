# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-ALIGN-VWAP-20260918 | 1 | -0.0434 | -0.1890 | -11.86% | 3.31% | 1.00% | -12.86% | -0.0862 | 65.01% | 43.33% |
| F-ALIGN-HIGH-20260918 | 1 | -0.0412 | -0.1995 | -12.04% | 3.14% | 0.95% | -12.99% | -0.0893 | 58.59% | 45.00% |
