# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LAMD10-K5V2-20260929 | 1 | 0.1199 | 0.4667 | 18.34% | 37.57% | 5.68% | 12.66% | 1.0256 | 26.76% | 63.33% |
| LAMD20-K5V2-20260929 | 1 | 0.1040 | 0.4812 | 16.28% | 34.84% | 5.27% | 11.01% | 0.8853 | 30.97% | 65.00% |
| LAMD0-K8V2-20260929 | 1 | 0.1153 | 0.5229 | 17.90% | 51.71% | 7.82% | 10.08% | 0.9353 | 31.07% | 65.00% |
