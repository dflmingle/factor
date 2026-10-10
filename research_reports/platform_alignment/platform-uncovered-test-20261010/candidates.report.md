# PandaAI Factor Research Report

- Candidates: 2; completed: 2; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-P1010-02 | 1 | 0.0651 | 0.4350 | 5.44% | 79.69% | 12.05% | -6.61% | 0.4800 | 32.97% | 55.00% |
| F-P1010-01 | 1 | -0.0217 | -0.1026 | -9.21% | 88.00% | 13.31% | -22.52% | -0.0232 | 46.22% | 51.67% |
