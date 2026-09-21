# Promising local combination: H03+RESVOL three-window reproduction

Machine: `home` (家用电脑).
No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.
Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+1+cycle)`; 10 groups; `factor_valid`; one-way cost `0.30%`.

## Candidate

`H03+RESVOL` is an equal-weight local combination selected by an offline exhaustive search from saved positive single-mechanism representatives. It is a research candidate, not a platform result.

Formula: `(RANK(H03) + RANK(-RESIDUAL_VOLATILITY)) / 2`

- `SIZE`: long the low-market-cap side of `RANK(MARKET_CAP)` (included only in the with-size variant).
- `H03`: 60-day high-low range relative to lagged close, scaled by 60-day amount.
- `RESVOL`: long low local market-model residual volatility; this is explicitly a proxy for the unavailable platform Barra field.

## Results

| window | periods | RankIC | gross excess | net excess | turnover | annual cost |
|---|---:|---:|---:|---:|---:|---:|
| `formal_5y` | 120 | 0.0802 | 12.43% | 11.07% | 8.97% | 1.36% |
| `recent_2026` | 15 | 0.0865 | 12.54% | 11.29% | 8.29% | 1.25% |
| `since_2026_06_01` | 5 | 0.1556 | 42.26% | 41.10% | 7.67% | 1.16% |

## Interpretation

A positive result in all three windows supports offline follow-up. It does not establish platform equivalence, and the RESVOL component must remain labeled as a proxy until separately verified.
