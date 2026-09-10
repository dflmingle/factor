# Oversold-Rebound Retrospective

- Formal window: 2021-09-07 to 2026-09-07
- Universe: PandaAI full A-share universe (`沪深全A`)
- Rebalance: 5 trading days
- Groups: 10
- Direction: 1 (higher score means more oversold)
- One-way cost assumption: 0.30%
- Candidates tested: 11
- Multiple-testing reference: p < 0.0045
- Runs completed: 11/11; formula failures: 0
- Compute balance after settlement: 936.185838 (44 credits used)

## Decision

No oversold-rebound candidate passes the competition screen. The best cost-adjusted result is
`OSR-SCALED-RET5-20D` at -8.78% net excess per year. The best gross long-side result is
`OSR-RSI14-20D` at +5.28%, but its implied annual turnover cost is 15.28%, leaving -10.00%
net excess. These workflows remain as research records; none is marked for submission.

## Candidate Review

| candidate | mechanism | Rank_IC | IC p | mono | long excess | turnover | annual cost | net excess | decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| OSR-SCALED-RET5-20D | 5-day loss scaled by 20-day volatility | 0.0767 | 0.0260 | 0.60 | -0.64% | 26.92% | 8.14% | -8.78% | abandon for pool |
| OSR-RSI14-20D | 14-day RSI oversold state | 0.0565 | 0.0010 | 0.71 | +5.28% | 50.53% | 15.28% | -10.00% | abandon for pool |
| OSR-DD20-20D | distance below 20-day high | 0.0133 | 0.0567 | 0.53 | +0.91% | 44.78% | 13.54% | -12.63% | abandon |
| OSR-MA20-20D | distance below 20-day moving average | 0.0523 | 0.0012 | 0.55 | +1.97% | 55.17% | 16.68% | -14.71% | abandon |
| OSR-Z20-20D | 20-day time-series price z-score | 0.0491 | 0.0007 | 0.64 | +3.36% | 75.56% | 22.85% | -19.49% | abandon |
| OSR-RET10-20D | 10-day reversal | 0.0453 | 0.0038 | 0.50 | -0.32% | 67.84% | 20.51% | -20.83% | abandon |
| OSR-RET5-RSI14-20D | average of 5-day loss and RSI oversold ranks | 0.0460 | 0.0016 | 0.55 | +2.09% | 78.16% | 23.64% | -21.55% | abandon |
| OSR-MFI14-20D | 14-day money-flow oversold state | 0.0318 | 0.1002 | 0.43 | -3.21% | 61.85% | 18.70% | -21.91% | abandon |
| OSR-RET5-DD20-20D | average of 5-day loss and drawdown | 0.0242 | 0.0203 | 0.49 | -1.78% | 75.26% | 22.76% | -24.54% | abandon |
| OSR-CAPITULATION-20D | 5-day loss plus turnover expansion | 0.0025 | 0.5210 | 0.22 | -0.55% | 90.11% | 27.25% | -27.80% | abandon |
| OSR-RET5-20D | raw 5-day loss reversal | 0.0326 | 0.0161 | 0.43 | -3.68% | 87.60% | 26.49% | -30.17% | abandon |

## Falsification and Interpretation

- Cost falsification: all 11 long-side excess returns are below their implied annual turnover
  cost. The candidate set therefore fails the stated investability test at the fixed 5-day cycle.
- Extreme-decile falsification: the scaled-loss factor's strongest gross excess appears in
  groups 6-8, while group 10 is negative. This is not a clean extreme-oversold rebound signal.
- RSI is the most coherent raw signal: it has the best monotonicity (0.71), passes the nominal
  multiple-testing reference, and has positive excess in the top decile. It still fails after
  turnover cost, so the result is not a competition candidate.
- No factor-value CSV was returned by the CLI download endpoint for these completed runs, so
  cross-sectional correlation against `paper-derived-composite` was not claimed. The comparison
  above uses the saved run metrics and group-return curves only.

## Next Research Direction

The useful part of this batch is the evidence against an immediate, high-frequency extreme-
oversold rule. A follow-up should test a lower-churn state signal: a longer lookback, a recovery
confirmation condition, or a moderate-oversold band rather than simply increasing the score as
the price falls. It should be a separately approved five-year batch and must again rank by net
long-side excess, not the long-short headline.
