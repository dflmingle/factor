# Quantocracy candidates: local reproduction

Machine: `home` (家用电脑).
No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.
Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+cycle+1)`; 10 groups; `factor_valid`; one-way cost `0.30%`.
Formal window: `2021-09-07..2026-09-07`. Diagnostics: `2026-01-01+` and `2026-06-01+`.
Signal schedule: every 10 trading days anchored at `2021-09-07`; diagnostics are not mixed into formal ranking.

## Results

`source RankIC/IC` use the source-sign formula. `oriented RankIC/IC` use the traded long direction. Monotonicity is a local group-return Spearman proxy, not a PandaAI byte-level field equivalent.

| candidate | window | periods | source RankIC | oriented RankIC | source IC | oriented IC | source monotonicity | oriented monotonicity | gross excess | net excess | turnover | annual cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `frog_in_pan_momentum` | `formal_5y` | 120 | -0.0168 | -0.0168 | -0.0068 | -0.0068 | -0.1273 | -0.1273 | -6.04% | -9.73% | 24.37% | 3.69% |
| `frog_in_pan_momentum` | `recent_2026` | 15 | -0.0169 | -0.0169 | 0.0087 | 0.0087 | 0.5273 | 0.5273 | 11.90% | 8.60% | 21.85% | 3.30% |
| `frog_in_pan_momentum` | `since_2026_06_01` | 5 | -0.1182 | -0.1182 | -0.1041 | -0.1041 | -0.9515 | -0.9515 | -56.83% | -59.68% | 18.85% | 2.85% |
| `price_path_convexity` | `formal_5y` | 120 | -0.0021 | 0.0021 | -0.0009 | 0.0009 | 0.4182 | -0.4182 | -9.58% | -23.27% | 90.53% | 13.69% |
| `price_path_convexity` | `recent_2026` | 15 | 0.0093 | -0.0093 | 0.0160 | -0.0160 | 0.8909 | -0.8909 | -11.60% | -25.24% | 90.24% | 13.64% |
| `price_path_convexity` | `since_2026_06_01` | 5 | 0.0570 | -0.0570 | 0.0715 | -0.0715 | 0.7333 | -0.7333 | -55.15% | -69.05% | 91.96% | 13.90% |
| `trend_clarity_momentum` | `formal_5y` | 120 | -0.0208 | -0.0208 | -0.0069 | -0.0069 | -0.3333 | -0.3333 | -5.73% | -8.36% | 17.35% | 2.62% |
| `trend_clarity_momentum` | `recent_2026` | 15 | -0.0139 | -0.0139 | 0.0087 | 0.0087 | 0.1879 | 0.1879 | 27.51% | 25.18% | 15.40% | 2.33% |
| `trend_clarity_momentum` | `since_2026_06_01` | 5 | -0.1212 | -0.1212 | -0.1041 | -0.1041 | -0.9394 | -0.9394 | -43.22% | -45.07% | 12.26% | 1.85% |

## Candidate definitions

### `price_path_convexity`

- Source formula: `(((P_first + P_last) / 2) - MEAN(P_daily)) / ((P_first + P_last) / 2)`
- Local evaluated formula: `-price_path_convexity (low source value is long)`
- Source: [https://aligrithm.com/price-path-convexity-a-new-cross-sectional-anomaly-45bp-per-s-2/](https://aligrithm.com/price-path-convexity-a-new-cross-sectional-anomaly-45bp-per-s-2/)
- Fidelity note: The source is monthly and uses daily dollar closes. The local 10-day evaluator uses a trailing 21-trading-day path as the one-month proxy; the source low-convexity side is held long.

### `trend_clarity_momentum`

- Source formula: `MOM12-1 = CLOSE[t-21]/CLOSE[t-252]-1; TC = rolling R2(CLOSE,231).shift(21)`
- Local evaluated formula: `5 momentum buckets, then TC percentile as a tie-break proxy`
- Source: [https://alphaarchitect.com/2024/05/momentum-and-the-clarity-of-the-trend/](https://alphaarchitect.com/2024/05/momentum-and-the-clarity-of-the-trend/)
- Fidelity note: The source double-sorts momentum and trend clarity. The local scalar proxy keeps the five momentum buckets primary and uses TC percentile within each bucket, so it is not a byte-level reproduction of the source two-way portfolio table.

### `frog_in_pan_momentum`

- Source formula: `FIP = (N_up - N_down) / N_total with MOM12-1`
- Local evaluated formula: `5 momentum buckets, then FIP percentile as a tie-break proxy`
- Source: [https://alphaarchitect.com/2015/11/23/frog-in-the-pan-identifying-the-highest-quality-momentum-stocks/](https://alphaarchitect.com/2015/11/23/frog-in-the-pan-identifying-the-highest-quality-momentum-stocks/)
- Fidelity note: FIP is the sign-reversed information-discreteness measure. The local proxy combines it with the same MOM12-1 five-bucket primary sort and reports high-FIP/high-momentum names.

## Interpretation

These are offline China A-share diagnostics on cached Tushare data. The source studies use different markets, universes, rebalance timing, weighting and holding rules; a positive local result is a screening signal, not platform validation.
