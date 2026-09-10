# Reversal-report follow-up retrospective

Date: 2026-09-08  
Source: Huatai multi-factor research reports, series 4/5-inspired follow-ups  
Window: 2021-09-07 to 2026-09-07  
Rebalance: 5 trading days  
Groups: 10  
One-way cost assumption: 0.30%

## Tested candidates

| Candidate | Formula | Mechanism | Decision |
| --- | --- | --- | --- |
| `HT-WREV-21D` | `RANK(-SUM(TURNOVER * RETURNS(CLOSE,1),21) / SUM(TURNOVER,21))` | Volume-weighted recent return reversal: recent losses on larger traded volume receive higher scores. | Abandon for current pool |
| `HT-EXPWREV-63D` | `RANK(-EMA(TURNOVER * RETURNS(CLOSE,1),63) / EMA(TURNOVER,63))` | Exponentially weighted volume-weighted reversal, giving more weight to recent observations. | Abandon for current pool |
| `HT-WREV-LOWTURN-21D` | `(RANK(-SUM(TURNOVER * RETURNS(CLOSE,1),21) / SUM(TURNOVER,21)) + RANK(1 - MA(TURNOVER,21) / MA(TURNOVER,504))) / 2` | Combines volume-weighted reversal with a long-term-low-turnover preference. The combination is a local research hypothesis, not a reported formula. | Abandon for current pool |

## Results

| Candidate | Rank IC | IC IR | Monotonicity | Long excess | Turnover | Annual cost | Net excess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HT-EXPWREV-63D` | 0.0809 | 0.2926 | 0.82 | 6.24% | 23.85% | 7.21% | **-0.97%** |
| `HT-WREV-LOWTURN-21D` | 0.0817 | 0.3550 | 0.84 | 11.12% | 43.55% | 13.17% | **-2.05%** |
| `HT-WREV-21D` | 0.0750 | 0.3102 | 0.79 | 6.91% | 52.47% | 15.87% | **-8.96%** |

All three have a displayed IC p-value of `0.0000`; with 85 study-wide hypotheses the rough multiple-testing reference is `p < 0.0006`. Rank IC itself has no separate p-value in the platform output. Statistical significance therefore does not rescue the cost-adjusted result.

## Attribution and falsification status

The common signal is a real and fairly monotonic reversal pattern. The decisive failure is implementation cost: the 21-day version has the highest turnover, while the low-turnover overlay reduces it only to 43.55%, still implying 13.17% annual cost at the stated assumptions. The exponential version is the relative winner because turnover falls to 23.85%, but its 6.24% gross long-side excess is still below the implied cost.

No cross-sectional correlation download or separate year/lookback/cycle falsification run was performed after this batch. Since every candidate failed the cost-adjusted screen, the batch is recorded as `abandon for current pool` and no second-round run is justified under the research rules. These results are in-sample five-year screening results, not out-of-sample validation.

## Records and billing

- Candidate registry: `reversal-report-followup-candidates.txt`
- Ranked report: `reversal-report-followup-candidates.report.md` and `.report.csv`
- Raw responses: `reversal-report-followup-candidates.results/`
- Charges: 2 + 4 + 4 = 10 credits; last recorded balance: `726.523142`
- No candidate from this batch should be added to the competition pool.
