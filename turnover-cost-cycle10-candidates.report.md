# PandaAI Factor Research Report

- Candidates: 7; completed: 7; failed: 0
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0005
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HT-WREV-LOWTURN-21D | 1 | 0.0998 | 0.4790 | 11.94% | 61.03% | 9.23% | 2.71% | 0.8141 | 26.72% | 58.33% |
| OSR2-RET20 | 1 | 0.0881 | 0.4036 | 10.61% | 70.85% | 10.71% | -0.10% | 0.6723 | 33.24% | 61.67% |
| HT13-REVERSAL-20D | 1 | 0.0867 | 0.4653 | 10.48% | 70.89% | 10.72% | -0.24% | 0.6707 | 33.28% | 61.67% |
| HT-WREV-21D | 1 | 0.0927 | 0.4575 | 9.90% | 70.81% | 10.71% | -0.81% | 0.7008 | 26.72% | 60.00% |
| OSR-RSI14-20D | 1 | 0.0664 | 0.2778 | 5.31% | 66.05% | 9.99% | -4.68% | 0.5404 | 30.44% | 53.33% |
| HT13-ALPHA13 | 1 | 0.0457 | 0.2466 | 3.92% | 85.52% | 12.93% | -9.01% | 0.4877 | 31.06% | 58.33% |
| HT13-ALPHA44 | 1 | 0.0396 | 0.2485 | 3.57% | 87.26% | 13.19% | -9.62% | 0.4992 | 27.42% | 61.67% |
