# OSR2-RET40 value combination review

## Test settings

- Window: `2021-09-07` to `2026-09-07`
- Rebalance: 5 trading days
- Groups: 10 deciles
- One-way cost: `0.30%`
- Study denominator: 89 candidates; rough reference threshold `p < 0.0006`

The cost estimate is `turnover x 0.30% x 2 x 252 / 5`. It uses the direction-selected
long decile and is a research proxy, not the official competition pool score.

## Comparison

| candidate | formula summary | Rank IC | IC p | monotonicity | long excess | turnover | annual cost | net excess | decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `OSR2-RET40` | 40-day reversal | 0.0731 | <0.0001* | 0.88 | 13.25% | 40.41% | 12.22% | 1.03% | baseline |
| `OSR3-RET40-BP-CFP` | reversal + B/P + cash-flow yield, equal ranks | 0.0670 | 0.0001 | 0.91 | 10.12% | 21.69% | 6.56% | 3.56% | retain as statistical reference |
| `OSR4-RET40-BP-CFP-VAL2` | reversal + 2x B/P + 2x cash-flow yield | 0.0550 | 0.0008 | 0.89 | 7.88% | 14.29% | 4.32% | 3.56% | **retain as low-turnover candidate** |
| `OSR4-RET40-BP-CFP-VAL3` | reversal + 3x B/P + 3x cash-flow yield | 0.0493 | 0.0027 | 0.88 | 6.80% | 11.55% | 3.49% | 3.31% | retain as lower-churn fallback |

`*` The platform rounded the baseline p value to `0.0000`; its exact value was not returned.

## Recommendation

Use `OSR4-RET40-BP-CFP-VAL2` as the current low-turnover research version:

```text
(RANK(1 - RETURNS(CLOSE,40)) + 2 * RANK(ratio_bm_ttm) + 2 * RANK(ratio_cfp_ttm)) / 5
```

Direction is `1` (higher is better). The 40-day reversal is the mean-reversion sleeve;
`ratio_bm_ttm` is book-to-market and `ratio_cfp_ttm` is cash-flow yield. Giving the two
slow value sleeves twice the rank weight reduces the sensitivity of the held decile to
short-term reversal rank changes.

The equal-weight `OSR3-RET40-BP-CFP` is a useful benchmark because it has the stronger IC
statistics and passes the rough study-wide p reference, but its turnover is 21.69%. The
`VAL2` version has the same rounded cost-adjusted net excess with 34% less turnover than
that benchmark, but its p value does not clear the study-wide reference threshold. This is
an in-sample tradeoff, not evidence that the weighting is stable out of sample.

## Research status

- Two batches tested 20 new value combinations; all runs completed.
- No independent sample-out-of-sample run has been made.
- The CLI result response did not include a CSV URL, so raw cross-sectional correlation
  against the existing factor set could not be measured; no independence claim is made.
- Decision: retain `OSR4-RET40-BP-CFP-VAL2` and `OSR3-RET40-BP-CFP` for a reserved-window
  check; do not treat either as competition-ready from this five-year screen alone.

Reports and raw platform responses remain in:

- `osr3-ret40-value-candidates.report.csv`
- `osr4-ret40-value-refine-candidates.report.csv`
- `osr3-ret40-value-candidates.results/`
- `osr4-ret40-value-refine-candidates.results/`
