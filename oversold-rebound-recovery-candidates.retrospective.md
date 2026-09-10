# Oversold-Rebound Follow-up Retrospective

- Formal window: 2021-09-07 to 2026-09-07
- Universe: PandaAI full A-share universe (`沪深全A`)
- Rebalance: 5 trading days
- Groups: 10
- Direction: 1
- One-way cost assumption: 0.30%
- New candidates: 15
- Running study denominator: 26 (11 prior OSR candidates + 15 follow-up candidates)
- Multiple-testing reference: p < 0.0019
- Runs completed: 15/15; formula failures: 0
- Balance after settlement: 884.185838; this batch deducted 52 credits

## Decision

The recovery-confirmation hypothesis did not survive. All seven moderate-oversold or explicit
recovery-confirmation candidates had negative cost-adjusted long-side excess.

The longer-lookback hypothesis produced two research survivors:

- `OSR2-DD120`: `RANK(1 - CLOSE / TS_MAX(CLOSE,120))`, net excess `+4.79%`.
- `OSR2-RET40`: `RANK(1 - RETURNS(CLOSE,40))`, net excess `+1.03%`.

Neither replaces the existing `paper-derived-composite` (`+11.41%` net excess in its saved
five-year result), and neither is submitted without a separate validation decision. Both remain
research workflows.

## Survivors

| candidate | mechanism | Rank_IC | IC p | mono | long excess | turnover | annual cost | net excess | Sharpe | max DD | decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| OSR2-DD120 | persistent distance below the 120-day high with slow rank movement | 0.0329 | 0.0046 | 0.89 | +11.16% | 21.06% | 6.37% | +4.79% | 0.6278 | 38.08% | escalate to validation |
| OSR2-RET40 | 40-day loss reversal with less churn than the 5/10/20-day versions | 0.0731 | <0.0001* | 0.88 | +13.25% | 40.41% | 12.22% | +1.03% | 0.7374 | 40.20% | escalate cautiously |
| OSR2-DD60 | 60-day drawdown distance, a shorter lookback robustness check | 0.0303 | 0.0075 | 0.79 | +9.82% | 26.03% | 7.87% | +1.95% | 0.5804 | 43.49% | research backup |

`*` The platform displayed the `OSR2-RET40` p-value as `0.0000`; the exact value was rounded in
the returned report. The corrected threshold is still a reference, not proof of out-of-sample
performance.

## Falsification

- Cost test: `OSR2-DD120`, `OSR2-DD60`, and `OSR2-RET40` remain positive after the 0.30% one-way
  cost haircut; all other 12 candidates fail this test.
- Lookback test: moving from 20 to 40 days improved net excess from `-8.54%` to `+1.03%` for
  raw reversal. Moving from 60 to 120 days improved drawdown-distance net excess from `+1.95%`
  to `+4.79%` and reduced turnover from `26.03%` to `21.06%`.
- Year check on the direction-selected top decile, based on the saved cumulative excess-return
  curve and before the annual cost haircut:

  | candidate | 2021* | 2022 | 2023 | 2024 | 2025 | 2026* |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: |
  | OSR2-DD120 | -0.67% | +16.10% | -0.48% | +20.66% | +5.94% | +1.98% |
  | OSR2-RET40 | +11.92% | +11.85% | +2.06% | +18.27% | +5.33% | +1.52% |

  `*` 2021 and 2026 are partial years in the five-year window. These are changes in the
  cumulative excess curve, not official competition C returns.
- Recovery confirmation test: adding 3-day or 5-day return confirmation to RSI, drawdown,
  moving-average, or 20-day reversal signals increased turnover to 73.76%-84.30% and produced
  net excess between `-21.34%` and `-31.52%`. Explicit RSI/price crossing versions were worse.
- Redundancy test: the CLI result payload did not expose a downloadable factor-value URL, so local
  cross-sectional Spearman correlation against the existing composite was not measured and no
  orthogonality claim is made.

## Conclusion

The evidence favors a slow drawdown/reversal state over an event-style rebound trigger. `OSR2-DD120`
is the best new cost-adjusted candidate, while `OSR2-RET40` is the stronger statistical signal but
has a thinner cost margin. The next decision should be validation or abandonment; no additional
short-window tuning is justified by this batch.
