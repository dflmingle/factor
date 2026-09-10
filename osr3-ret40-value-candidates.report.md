# PandaAI Factor Research Report

- Candidates: 12; completed: 12; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0006
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OSR3-RET40-BP-CFP | 1 | 0.0670 | 0.2646 | 10.12% | 21.69% | 6.56% | 3.56% | 0.8024 | 31.14% | 61.67% |
| OSR3-RET40-BP-VAL2 | 1 | 0.0760 | 0.2408 | 10.02% | 22.66% | 6.85% | 3.17% | 0.7980 | 30.46% | 60.00% |
| OSR3-RET40-BP-EQ | 1 | 0.0844 | 0.2820 | 12.06% | 29.43% | 8.90% | 3.16% | 0.8247 | 34.26% | 60.00% |
| OSR3-RET40-BP-INTERACT | 1 | 0.0848 | 0.2928 | 13.18% | 34.57% | 10.45% | 2.73% | 0.8193 | 37.23% | 60.00% |
| OSR3-RET40-BP-REV2 | 1 | 0.0843 | 0.2973 | 12.98% | 34.73% | 10.50% | 2.48% | 0.8131 | 37.08% | 60.00% |
| OSR3-RET40-BP-MA63 | 1 | 0.0793 | 0.2707 | 11.09% | 28.70% | 8.68% | 2.41% | 0.7931 | 33.04% | 60.00% |
| OSR3-RET40-BP-TSRANK756 | 1 | 0.0715 | 0.2558 | 12.26% | 35.11% | 10.62% | 1.64% | 0.7420 | 40.20% | 60.00% |
| OSR3-RET40-BP-EP-CFP | 1 | 0.0605 | 0.1833 | 5.30% | 17.07% | 5.16% | 0.14% | 0.6873 | 25.28% | 58.33% |
| OSR3-RET40-BP-EP | 1 | 0.0717 | 0.2011 | 5.80% | 20.85% | 6.31% | -0.51% | 0.7091 | 24.03% | 58.33% |
| OSR3-RET40-BP-ROE | 1 | 0.0694 | 0.2043 | 7.09% | 25.45% | 7.70% | -0.61% | 0.7202 | 26.86% | 58.33% |
| OSR3-RET40-BP-EP-ROE | 1 | 0.0543 | 0.1348 | 3.74% | 18.81% | 5.69% | -1.95% | 0.6332 | 21.28% | 58.33% |
| OSR3-RET40-EP-EQ | 1 | 0.0631 | 0.1965 | 6.71% | 28.67% | 8.67% | -1.96% | 0.6683 | 29.34% | 58.33% |
