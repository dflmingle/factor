# PandaAI Factor Research Report

- Candidates: 11; completed: 11; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0045
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OSR-SCALED-RET5-20D | 1 | 0.0767 | 0.1443 | -0.64% | 26.92% | 8.14% | -8.78% | 0.5045 | 21.33% | 56.67% |
| OSR-RSI14-20D | 1 | 0.0565 | 0.2153 | 5.28% | 50.53% | 15.28% | -10.00% | 0.5283 | 35.01% | 55.00% |
| OSR-DD20-20D | 1 | 0.0133 | 0.1233 | 0.91% | 44.78% | 13.54% | -12.63% | 0.3256 | 42.79% | 56.67% |
| OSR-MA20-20D | 1 | 0.0523 | 0.2110 | 1.97% | 55.17% | 16.68% | -14.71% | 0.3725 | 41.55% | 55.00% |
| OSR-Z20-20D | 1 | 0.0491 | 0.2223 | 3.36% | 75.56% | 22.85% | -19.49% | 0.4667 | 32.21% | 53.33% |
| OSR-RET10-20D | 1 | 0.0453 | 0.1885 | -0.32% | 67.84% | 20.51% | -20.83% | 0.2990 | 42.20% | 53.33% |
| OSR-RET5-RSI14-20D | 1 | 0.0460 | 0.2061 | 2.09% | 78.16% | 23.64% | -21.55% | 0.3902 | 37.13% | 51.67% |
| OSR-MFI14-20D | 1 | 0.0318 | 0.1063 | -3.21% | 61.85% | 18.70% | -21.91% | 0.2410 | 47.49% | 55.00% |
| OSR-RET5-DD20-20D | 1 | 0.0242 | 0.1505 | -1.78% | 75.26% | 22.76% | -24.54% | 0.2448 | 43.62% | 53.33% |
| OSR-CAPITULATION-20D | 1 | 0.0025 | 0.0414 | -0.55% | 90.11% | 27.25% | -27.80% | 0.3127 | 36.90% | 51.67% |
| OSR-RET5-20D | 1 | 0.0326 | 0.1562 | -3.68% | 87.60% | 26.49% | -30.17% | 0.1921 | 42.30% | 51.67% |
