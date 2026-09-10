# PandaAI Factor Research Report

- Candidates: 8; completed: 8; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0006
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OSR4-RET40-BP-CFP-VAL2 | 1 | 0.0550 | 0.2198 | 7.88% | 14.29% | 4.32% | 3.56% | 0.7585 | 27.70% | 63.33% |
| OSR4-RET40-BP-CFP-VAL3 | 1 | 0.0493 | 0.1950 | 6.80% | 11.55% | 3.49% | 3.31% | 0.7251 | 26.67% | 63.33% |
| OSR4-RET40-BP-CFP-SP | 1 | 0.0640 | 0.2193 | 8.32% | 18.00% | 5.44% | 2.88% | 0.7667 | 29.19% | 58.33% |
| OSR4-RET40-BP-CFP-PCF | 1 | 0.0600 | 0.2335 | 8.39% | 18.92% | 5.72% | 2.67% | 0.7493 | 30.77% | 61.67% |
| OSR4-RET40-BP-CFP-MA63 | 1 | 0.0640 | 0.2538 | 8.58% | 19.81% | 5.99% | 2.59% | 0.7437 | 31.55% | 61.67% |
| OSR4-RET40-BP-CFP-TSRANK756 | 1 | 0.0652 | 0.2587 | 12.38% | 32.80% | 9.92% | 2.46% | 0.7688 | 40.20% | 61.67% |
| OSR4-RET40-BP-CFP-REV2 | 1 | 0.0758 | 0.2881 | 11.50% | 30.20% | 9.13% | 2.37% | 0.7929 | 35.17% | 60.00% |
| OSR4-RET40-BP-CFP-REV3 | 1 | 0.0773 | 0.2896 | 12.01% | 34.31% | 10.38% | 1.63% | 0.7788 | 36.68% | 60.00% |
