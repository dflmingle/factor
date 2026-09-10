# PandaAI Factor Research Report

- Candidates: 15; completed: 15; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0019
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OSR2-DD120 | 1 | 0.0329 | 0.1841 | 11.16% | 21.06% | 6.37% | 4.79% | 0.6278 | 38.08% | 58.33% |
| OSR2-DD60 | 1 | 0.0303 | 0.1736 | 9.82% | 26.03% | 7.87% | 1.95% | 0.5804 | 43.49% | 53.33% |
| OSR2-RET40 | 1 | 0.0731 | 0.2718 | 13.25% | 40.41% | 12.22% | 1.03% | 0.7374 | 40.20% | 58.33% |
| OSR2-SMOOTH-RSI28 | 1 | 0.0578 | 0.1933 | 5.48% | 24.26% | 7.34% | -1.86% | 0.5529 | 35.93% | 56.67% |
| OSR2-RET20 | 1 | 0.0637 | 0.2552 | 7.31% | 52.43% | 15.85% | -8.54% | 0.5685 | 40.60% | 56.67% |
| OSR2-MODERATE-RSI35 | 1 | 0.0389 | 0.1565 | 2.76% | 68.82% | 20.81% | -18.05% | 0.4520 | 38.16% | 53.33% |
| OSR2-RET20-REC5 | 1 | 0.0256 | 0.1179 | 4.15% | 84.30% | 25.49% | -21.34% | 0.5199 | 41.91% | 60.00% |
| OSR2-MODERATE-BIAS5 | 1 | 0.0211 | 0.0748 | 1.59% | 78.44% | 23.72% | -22.13% | 0.4260 | 31.56% | 55.00% |
| OSR2-DD60-REC5 | 1 | -0.0039 | 0.0085 | -2.14% | 73.76% | 22.31% | -24.45% | 0.2525 | 49.94% | 61.67% |
| OSR2-RSI-CROSS30 | 1 | 0.0018 | -0.0374 | 1.57% | 89.86% | 27.17% | -25.60% | 0.4305 | 35.13% | 58.33% |
| OSR2-MA20-REC5 | 1 | 0.0189 | 0.0636 | -1.58% | 84.01% | 25.40% | -26.98% | 0.2883 | 44.89% | 55.00% |
| OSR2-PRICE-CROSS-MA5 | 1 | 0.0006 | -0.0218 | -2.83% | 89.99% | 27.21% | -30.04% | 0.2645 | 33.70% | 53.33% |
| OSR2-RSI35-REC3 | 1 | -0.0027 | -0.0501 | -6.64% | 81.28% | 24.58% | -31.22% | 0.1120 | 43.81% | 51.67% |
| OSR2-MODERATE-DD60 | 1 | -0.0077 | -0.1281 | -8.98% | 74.30% | 22.47% | -31.45% | 0.0348 | 43.28% | 56.67% |
| OSR2-RSI35-REC5 | 1 | -0.0029 | -0.0359 | -6.34% | 83.26% | 25.18% | -31.52% | 0.1290 | 41.15% | 51.67% |
