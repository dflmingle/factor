# Non-Huatai literature batch retrospective

Date: 2026-09-09  
Window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Study hypotheses: 118  

## Results and decisions

| Candidate | Rank IC | IC IR | IC p | Monotonicity | Long excess | Turnover | Annual cost | Net excess | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `NONHT-FSCORELIKE-REV40` | 0.0697 | 0.3681 | 0.0001 | 0.91 | 8.14% | 41.77% | 6.32% | **1.82%** | Retain for later robustness |
| `NONHT-RESVOL-LOW` | 0.0884 | 0.2831 | 0.0073 | 0.74 | 2.97% | 17.19% | 2.60% | **0.37%** | Retain as weak orthogonal candidate |
| `NONHT-CASH-CONVERSION` | 0.0120 | 0.0467 | 0.6097 | 0.07 | 1.02% | 6.88% | 1.04% | -0.02% | Abandon |
| `NONHT-SKEW-LOW-60D` | 0.0474 | 0.2876 | 0.0021 | 0.95 | 5.05% | 36.31% | 5.49% | -0.44% | Abandon for current pool |
| `NONHT-MAX-LOW-21D` | 0.0862 | 0.2379 | 0.0103 | 0.78 | 1.91% | 51.71% | 7.82% | -5.91% | Abandon for current pool |
| `NONHT-LOW-BETA` | 0.0096 | -0.0764 | 0.4599 | 0.83 | -13.40% | 13.60% | 2.06% | -15.46% | Abandon as standalone alpha |

## Attribution

- `NONHT-FSCORELIKE-REV40` combines a 40-day loser signal with an eight-signal accounting-strength proxy. It is not an exact Piotroski F-Score: the no-new-share component was not available in the confirmed formula mapping. It is the only candidate whose displayed IC p-value is below the study-wide rough threshold of 0.0004, but it remains an in-sample proxy and its cost-adjusted excess is modest.
- `NONHT-RESVOL-LOW` uses PandaAI's precomputed residual-volatility field, which is distinct from the previously tested total-return volatility. It has the lowest turnover among the positive candidates, but the net result is too small to submit.
- `NONHT-MAX-LOW-21D` and `NONHT-SKEW-LOW-60D` show positive gross signals, but turnover costs remove the effect.
- `NONHT-CASH-CONVERSION` has no useful cross-sectional ordering in this sample.
- `NONHT-LOW-BETA` is not a standalone long-only alpha in this universe. The source literature motivates a long-low-beta/short-high-beta or leveraged BAB construction, which this single-factor long-only test does not reproduce.

No out-of-sample, size-exclusion, correlation, or composite test was started automatically. Raw responses and the complete metrics are in `nonhuatai-factor-6-20260909.report.csv` and its `.results/` directory.
