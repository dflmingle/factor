# PandaAI Factor Research Report

- Candidates: 6; completed: 6; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0004
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NONHT-FSCORELIKE-REV40 | 1 | 0.0697 | 0.3681 | 8.14% | 41.77% | 6.32% | 1.82% | 0.6523 | 28.69% | 56.67% |
| NONHT-RESVOL-LOW | 1 | 0.0884 | 0.2831 | 2.97% | 17.19% | 2.60% | 0.37% | 0.7367 | 23.77% | 52.73% |
| NONHT-CASH-CONVERSION | 1 | 0.0120 | 0.0467 | 1.02% | 6.88% | 1.04% | -0.02% | 0.4158 | 24.70% | 58.33% |
| NONHT-SKEW-LOW-60D | 1 | 0.0474 | 0.2876 | 5.05% | 36.31% | 5.49% | -0.44% | 0.5682 | 24.93% | 60.00% |
| NONHT-MAX-LOW-21D | 1 | 0.0862 | 0.2379 | 1.91% | 51.71% | 7.82% | -5.91% | 0.5569 | 20.90% | 61.67% |
| NONHT-LOW-BETA | 1 | 0.0096 | -0.0764 | -13.40% | 13.60% | 2.06% | -15.46% | -0.2250 | 25.80% | 43.64% |
