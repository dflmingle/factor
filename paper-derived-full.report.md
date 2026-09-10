# PandaAI Factor Research Report

- Candidates: 4; completed: 4; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0063
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| paper-derived-composite | 1 | 0.0597 | 0.2221 | 13.32% | 6.32% | 1.91% | 11.41% | 0.8395 | 35.74% | 63.33% |
| paper-derived-asset-growth | 0 | -0.0115 | -0.1111 | 1.40% | 2.10% | 0.64% | 0.76% | 0.3692 | 41.26% | 60.00% |
| paper-derived-profitability | 1 | 0.0287 | 0.0147 | -2.81% | 5.48% | 1.66% | -4.47% | 0.4366 | 19.45% | 50.00% |
| paper-derived-roe | 1 | -0.0114 | -0.1795 | -12.73% | 1.87% | 0.57% | -13.30% | -0.1215 | 59.55% | 55.00% |
