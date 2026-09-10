# OSR2-RET40 and turnover-bias composite retrospective

Date: 2026-09-08  
Source window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10OSRTURN-20260908-`

## Definition

```text
(
  RANK(1 - RETURNS(CLOSE,40))
  + RANK(1 - MA(TURNOVER,21) / MA(TURNOVER,504))
) / 2
```

This is a local equal-rank composite: 40-day price reversal plus a direction-aligned
21-day-versus-504-day turnover preference. It is not a reported paper formula.

## Result

| Metric | Value |
| --- | ---: |
| Rank IC | 0.0987 |
| IC mean | 0.0563 |
| IC IR | 0.4228 |
| IC p-value | 0.0000 |
| Monotonicity | 0.90 |
| Long-side excess | 14.77% |
| Turnover | 48.77% |
| Annual cost | 7.37% |
| Net excess | **7.40%** |
| Long Sharpe | 0.8345 |
| Max drawdown | 30.05% |
| Monthly win rate | 55.00% |

## Comparison with the 10-day components

| Candidate | Long excess | Turnover | Annual cost | Net excess |
| --- | ---: | ---: | ---: | ---: |
| `OSR2-RET40` | 13.35% | 55.02% | 8.32% | 5.03% |
| `HT13-TURN-BIAS-1M` | 9.04% | 26.97% | 4.08% | 4.96% |
| `OSR2-RET40-TURN-BIAS-EQ` | **14.77%** | 48.77% | 7.37% | **7.40%** |

The composite improves net excess by 2.37 percentage points versus `OSR2-RET40` and by 2.44
percentage points versus `HT13-TURN-BIAS-1M`. It does not inherit the lowest turnover of the
turnover-bias component, but it is lower-turnover than `OSR2-RET40` in this run.

With 97 study-wide hypotheses, the rough multiple-testing reference is p < 0.0005. The displayed
IC p-value is for the IC-mean t-statistic, not Rank IC. This is an in-sample five-year result;
no non-overlapping out-of-sample validation or official pool score is available for this composite.

## Records

- Candidate manifest: `osr2-ret40-turn-bias-composite-cycle10-candidates.txt`
- Checkpoint: `osr2-ret40-turn-bias-composite-cycle10-candidates.txt.state.json`
- Ranked report: `osr2-ret40-turn-bias-composite-cycle10-candidates.report.md`
- Filterable table: `osr2-ret40-turn-bias-composite-cycle10-candidates.report.csv`
- New platform object uses the `T10OSRTURN-20260908-` prefix.
