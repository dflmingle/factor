# Non-Huatai report directions: retrospective

- Window: 2021-09-07 to 2026-09-07
- Rebalance: 10 trading days
- Groups: 10
- One-way cost assumption: 0.30%
- Study-wide hypothesis count used for screening: 128
- Rough multiple-testing reference: `p < 0.0004`
- Three run attempts; two completed and one server-side execution failure

## Results

| Candidate | Rank IC | IC p | Mono | Long excess | Turnover | Annual cost | Net excess | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `NONHT-CHIP-COST-250` | 0.0677 | 0.0038 | 0.96 | 9.34% | 33.47% | 5.06% | 4.28% | retain as a survivor; no automatic follow-up |
| `NONHT-LTMOM-EXHIGH-252-21` | 0.0213 | 0.1486 | 0.72 | 1.74% | 30.91% | 4.67% | -2.93% | abandon for current pool |
| `NONHT-VAL-RESIDUAL` | - | - | - | - | - | - | - | execution failed; no conclusion |

## Attribution

- `NONHT-CHIP-COST-250` uses a 250-day volume-weighted transaction-price proxy for historical chip cost. The positive result survives the local turnover haircut, but its IC p-value does not meet the study-wide multiple-testing reference and it is still in-sample.
- `NONHT-LTMOM-EXHIGH-252-21` removes the highest-amplitude daily observations from a long-horizon momentum sum and skips the latest 21 days. The proxy did not cover its estimated trading cost in this window.
- `NONHT-VAL-RESIDUAL` was created as a Python cross-sectional residual factor. The platform accepted the workflow, but run `6aa124136df2a192a47e78d8` ended with status 3 and no detailed error. It is not treated as a negative factor result.

## Research decision

`NONHT-CHIP-COST-250` is the only initial survivor from this batch. No second-round lookback, direction, or formula adjustment was run automatically. The valuation-residual candidate requires a separately approved compatibility fix or a new implementation before it can be evaluated.

Records:

- Formula candidates: `nonht-report-directions-20260909-formula.txt`
- Python candidate: `nonht-report-directions-20260909-python.txt`
- Formula report: `nonht-report-directions-20260909-formula.report.md` and `.csv`
- Python report: `nonht-report-directions-20260909-python.report.md` and `.csv`
