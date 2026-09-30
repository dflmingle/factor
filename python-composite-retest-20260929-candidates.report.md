# PandaAI Factor Research Report

- Candidates: 3; completed: 3; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0167
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POOL5-CTRL-RETEST-20260929 | 1 | 0.0919 | 0.3675 | 22.32% | 13.39% | 2.02% | 20.30% | 1.0648 | 31.64% | 65.00% |
| POOL6-LAMD10K5V2-RETEST-20260929 | 1 | 0.1019 | 0.3952 | 22.28% | 18.16% | 2.75% | 19.53% | 1.0759 | 31.18% | 65.00% |
| POOL6-LEGMIX7-RETEST-20260929 | 1 | 0.1048 | 0.4060 | 22.85% | 22.58% | 3.41% | 19.44% | 1.0888 | 31.49% | 65.00% |
