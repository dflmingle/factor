# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e13rep-amihud20xrelT5252-w25 | 1 | 0.0934 | 0.4718 | 14.85% | 38.85% | 5.87% | 8.98% | 0.8873 | 26.60% | 63.33% |
| g17rep-amt60xrelT5252-w30 | 1 | 0.0983 | 0.4555 | 14.44% | 37.23% | 5.63% | 8.81% | 0.9095 | 24.36% | 63.33% |
| ks91rep-intr60xrelT5252-w45 | 1 | 0.0995 | 0.3899 | 11.91% | 46.97% | 7.10% | 4.81% | 0.7348 | 34.14% | 63.33% |
