# Quantpedia price candidates: local reproduction

Machine: `home` (家用电脑).
No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.
Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+1+cycle)`; 10 groups; `factor_valid`; one-way cost `0.30%`.
Formal window: `2021-09-07..2026-09-07`. Diagnostics: `2026-01-01+` and `2026-06-01+`.
Signal schedule: every 10 trading days anchored at `2021-09-07`; diagnostics are not mixed into formal ranking.

## Results

| candidate | formula | window | periods | RankIC | gross excess | net excess | turnover | annual cost |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `low_volatility_21` | `RANK(-STDDEV(RETURNS(CLOSE,1),21))` | `formal_5y` | 120 | 0.0852 | 0.36% | -5.26% | 37.18% | 5.62% |
| `low_volatility_21` | `RANK(-STDDEV(RETURNS(CLOSE,1),21))` | `recent_2026` | 15 | 0.0725 | 2.54% | -2.65% | 34.30% | 5.19% |
| `low_volatility_21` | `RANK(-STDDEV(RETURNS(CLOSE,1),21))` | `since_2026_06_01` | 5 | 0.1476 | 27.07% | 22.14% | 32.63% | 4.93% |
| `short_term_reversal_20` | `RANK(1 - RETURNS(CLOSE,20))` | `formal_5y` | 120 | 0.0826 | 6.53% | -4.05% | 69.98% | 10.58% |
| `short_term_reversal_20` | `RANK(1 - RETURNS(CLOSE,20))` | `recent_2026` | 15 | 0.0487 | -3.54% | -13.94% | 68.79% | 10.40% |
| `short_term_reversal_20` | `RANK(1 - RETURNS(CLOSE,20))` | `since_2026_06_01` | 5 | 0.1472 | 23.67% | 13.45% | 67.62% | 10.22% |
| `short_term_reversal_5` | `RANK(1 - RETURNS(CLOSE,5))` | `formal_5y` | 120 | 0.0471 | -3.46% | -16.57% | 86.74% | 13.12% |
| `short_term_reversal_5` | `RANK(1 - RETURNS(CLOSE,5))` | `recent_2026` | 15 | -0.0215 | -25.29% | -38.50% | 87.38% | 13.21% |
| `short_term_reversal_5` | `RANK(1 - RETURNS(CLOSE,5))` | `since_2026_06_01` | 5 | -0.1121 | -62.49% | -75.82% | 88.17% | 13.33% |

## Candidate notes

### `short_term_reversal_5`: not three-window positive

- Formula: `RANK(1 - RETURNS(CLOSE,5))`
- Source: [https://quantpedia.com/strategies/short-term-reversal](https://quantpedia.com/strategies/short-term-reversal).
- Local note: Five-day short-term reversal: recent losers are expected to rebound.

### `short_term_reversal_20`: not three-window positive

- Formula: `RANK(1 - RETURNS(CLOSE,20))`
- Source: [https://quantpedia.com/strategies/short-term-reversal](https://quantpedia.com/strategies/short-term-reversal).
- Local note: Twenty-day short-term reversal variant, tested under the same local schedule.

### `low_volatility_21`: not three-window positive

- Formula: `RANK(-STDDEV(RETURNS(CLOSE,1),21))`
- Source: [https://quantpedia.com/strategies/low-volatility-factor-effect-in-stocks](https://quantpedia.com/strategies/low-volatility-factor-effect-in-stocks).
- Local note: 21-day realized volatility with an explicit negative sign so low volatility is the long direction.

## Interpretation

These are offline China A-share diagnostics using cached Tushare data. The candidates are not submitted to PandaAI; platform review remains a separate user decision.
