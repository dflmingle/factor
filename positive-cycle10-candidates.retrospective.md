# Positive candidates: 10-day rebalance retrospective

Date: 2026-09-08  
Source window: 2021-09-07 to 2026-09-07  
Rebalance: 10 trading days  
Groups: 10  
One-way cost assumption: 0.30%  
Batch: `T10POS-20260908-`

## Decision

All three candidates remain positive after the turnover haircut at a 10-day cycle. `OSR2-RET40`
is the strongest current candidate and should be retained for a later robustness check.
`HT13-TURN-BIAS-1M` is also competitive with materially lower turnover. `OSR2-DD120` remains
positive but its net excess is slightly below its earlier 5-day result, so it is a supporting
candidate rather than the lead.

## Results

| Candidate | Direction | Rank IC | IC IR | IC p | Monotonicity | Long excess | Turnover | Annual cost | Net excess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `OSR2-RET40` | 1 | 0.0908 | 0.3602 | 0.0001 | 0.91 | 13.35% | 55.02% | 8.32% | **5.03%** |
| `HT13-TURN-BIAS-1M` | 0 | -0.0737 | -0.3612 | 0.0019 | 0.86 | 9.04% | 26.97% | 4.08% | **4.96%** |
| `OSR2-DD120` | 1 | 0.0405 | 0.2085 | 0.0241 | 0.90 | 8.69% | 29.39% | 4.44% | **4.25%** |

## Comparison with the earlier 5-day run

| Candidate | 5-day net excess | 10-day net excess | Change |
| --- | ---: | ---: | ---: |
| `OSR2-RET40` | 1.03% | 5.03% | +4.00 pp |
| `HT13-TURN-BIAS-1M` | 6.43% | 4.96% | -1.47 pp |
| `OSR2-DD120` | 4.79% | 4.25% | -0.55 pp |

The 10-day cycle lowers annualized cost for all three. Per-rebalance turnover is higher because
the portfolio is changed less often but by a larger amount each time. `OSR2-RET40` also has a
higher gross excess and stronger Rank IC at the 10-day sampling cycle; the two other candidates
show lower gross excess that is partly offset by lower annual cost.

With 95 study-wide hypotheses, the rough multiple-testing reference is p < 0.0005. The displayed
IC p-value is for the IC-mean t-statistic, not Rank IC. These are in-sample five-year results; no
out-of-sample or additional robustness run was performed in this batch.

## Records

- Candidate manifest: `positive-cycle10-candidates.txt`
- Checkpoint: `positive-cycle10-candidates.txt.state.json`
- Ranked report: `positive-cycle10-candidates.report.md`
- Filterable table: `positive-cycle10-candidates.report.csv`
- New platform objects use the `T10POS-20260908-` prefix.
