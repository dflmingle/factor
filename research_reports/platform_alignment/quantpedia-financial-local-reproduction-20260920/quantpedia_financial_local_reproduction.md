# Quantpedia financial candidates: local reproduction

Machine: `home` (家用电脑).
No PandaAI factor was created or run. No Tushare network request was made; all inputs came from the local Tushare cache.
Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; warm-up `2018-01-01`; label `close(t+1) -> close(t+1+cycle)`; 10 groups; `factor_valid`; one-way cost `0.30%`.
Formal window: `2021-09-07..2026-09-07`. Diagnostic windows: `2026-01-01+` and `2026-06-01+`.
Signal schedule: every 10 trading days anchored at `2021-09-07`; diagnostics are not mixed into formal ranking.

## Results

Positive means the direction shown by the formula is profitable. `proxy`/`derived` labels are explicit and do not claim byte-level platform equivalence.

| candidate | formula | window | periods | RankIC | gross excess | net excess | turnover | annual cost |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `earnings_yield` | `RANK(ratio_ep_ttm)` | `formal_5y` | 120 | 0.0208 | -1.66% | -2.60% | 6.19% | 0.94% |
| `earnings_yield` | `RANK(ratio_ep_ttm)` | `recent_2026` | 15 | 0.0324 | 5.74% | 4.79% | 6.28% | 0.95% |
| `earnings_yield` | `RANK(ratio_ep_ttm)` | `since_2026_06_01` | 5 | 0.0247 | 25.63% | 24.71% | 6.09% | 0.92% |
| `profitability` | `RANK(PROFITABILITY)` | `formal_5y` | 120 | -0.0037 | -6.92% | -7.24% | 2.13% | 0.32% |
| `profitability` | `RANK(PROFITABILITY)` | `recent_2026` | 15 | 0.0191 | 4.36% | 4.08% | 1.83% | 0.28% |
| `profitability` | `RANK(PROFITABILITY)` | `since_2026_06_01` | 5 | -0.0128 | 6.28% | 6.25% | 0.24% | 0.04% |
| `roe_lyr` | `RANK(OPER_ROE_LYR)` | `formal_5y` | 120 | -0.0136 | -10.98% | -11.48% | 3.30% | 0.50% |
| `roe_lyr` | `RANK(OPER_ROE_LYR)` | `recent_2026` | 15 | 0.0142 | 0.88% | 0.39% | 3.28% | 0.50% |
| `roe_lyr` | `RANK(OPER_ROE_LYR)` | `since_2026_06_01` | 5 | -0.0223 | 0.23% | 0.17% | 0.39% | 0.06% |

## Candidate notes

### `earnings_yield`: not three-window positive

- Formula: `RANK(ratio_ep_ttm)`
- Treatment: `direct_local_handler`. TTM attributable net income / daily_basic.total_mv, with PIT announcement joins.
- Source family: Quantpedia value / earnings-yield family.

### `roe_lyr`: not three-window positive

- Formula: `RANK(OPER_ROE_LYR)`
- Treatment: `direct_field_proxy`. Annual PIT ROE from fina_indicator. The local field mapping is the available ROE proxy for OPER_ROE_LYR.
- Source family: Quantpedia quality / profitability family.

### `profitability`: not three-window positive

- Formula: `RANK(PROFITABILITY)`
- Treatment: `derived_proxy`. TTM operating profit / TTM revenue, ranked cross-sectionally; explicitly a local profitability proxy.
- Source family: Quantpedia profitability family.

## Interpretation

These are offline China A-share diagnostics using cached Tushare data. The candidate formulas are not submitted to PandaAI. Platform review remains a separate step selected by the user.
