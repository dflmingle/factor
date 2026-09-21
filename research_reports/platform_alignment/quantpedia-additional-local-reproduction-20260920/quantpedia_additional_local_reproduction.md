# Additional Quantpedia local reproduction

Machine: `home` (家用电脑).
No PandaAI factor was created or run. No Tushare network request was made.
Data source: cached Tushare qfq price data and signal-day daily_basic.total_mv.
Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Universe: full-A `.SH/.SZ`; warm-up `2018-01-01`; label `close(t+1) -> close(t+1+cycle)`.
Formal window: `2021-09-07` to `2026-09-07`; recent diagnostic starts `2026-01-01`.

## Candidate status

| candidate | status | formula | local treatment | source |
|---|---|---|---|---|
| `momentum_reversal_volatility` | `computed_proxy` | `large-cap & high-volatility subset; rank RET126 and skip 5 days` | Local proxy: RET126 = CLOSE/DELAY(CLOSE,126)-1, VOL126 = STDDEV(RETURNS(CLOSE,1),126), both shifted by 5 trading days. Top 50% total_mv, then top 50% VOL126; top/bottom RET126 deciles. | [https://quantpedia.com/strategies/momentum-and-reversal-combined-with-volatility-effect-in-stocks](https://quantpedia.com/strategies/momentum-and-reversal-combined-with-volatility-effect-in-stocks) |
| `ncav_market_cap` | `unsupported` | `NCAV / MARKET_CAP` | Unsupported: the local financial cache does not contain a reliable current-assets field required by the source definition. | [https://quantpedia.com/strategies/net-current-asset-value-effect](https://quantpedia.com/strategies/net-current-asset-value-effect) |
| `accrual_anomaly` | `unsupported` | `BS_ACC / TOTAL_ASSETS` | Unsupported: the local cache lacks the cash, short-term debt, income-tax payable, and depreciation fields needed for the source balance-sheet accrual formula. | [https://quantpedia.com/strategies/accrual-anomaly](https://quantpedia.com/strategies/accrual-anomaly) |

## Computed proxy

The supported candidate is an explicit proxy, not a byte-level reproduction of the source portfolio.

- Six-month return and volatility use 126 trading days and are shifted back five trading days to skip the latest week.
- The signal-day universe keeps the top 50% by `daily_basic.total_mv`, then the top 50% by lagged volatility.
- Return is ranked into 10 groups; the local evaluator uses a 21-trading-day holding label because it does not model overlapping six-month positions.
- `factor_valid` top-group metrics are reported separately from the source-style top-minus-bottom long-short spread.

## Results

Recent results are diagnostics and are not mixed into formal ranking.

| window | periods | stocks | RankIC | IC | top gross excess | top cost | top net excess | long-short gross | long-short cost | long-short net | long turnover | short turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `formal_5y` | 57 | 1216.2 | -0.0658 | -0.0515 | -17.56% | 3.06% | -20.62% | -24.27% | 3.39% | -27.66% | 42.49% | 51.79% |
| `recent_diagnostic` | 7 | 1277.7 | 0.0190 | 0.0195 | 16.85% | 2.79% | 14.06% | 42.39% | 3.33% | 39.06% | 38.76% | 53.74% |

## Latest snapshot

Signal date: `2026-07-21 00:00:00`.

| rank | instrument | six-month return signal |
|---:|---|---:|
| 1 | 688146.SH | 4.98473956 |
| 2 | 603629.SH | 4.94061488 |
| 3 | 002636.SZ | 4.73998607 |
| 4 | 603256.SH | 4.59981628 |
| 5 | 301526.SZ | 4.58506723 |
| 6 | 300209.SZ | 4.57064220 |
| 7 | 001331.SZ | 4.49538578 |
| 8 | 301362.SZ | 4.35296463 |
| 9 | 300489.SZ | 4.17716535 |
| 10 | 688766.SH | 4.07182969 |
| 11 | 301396.SZ | 4.00004966 |
| 12 | 003036.SZ | 3.88547111 |
| 13 | 603115.SH | 3.86954392 |
| 14 | 688530.SH | 3.55900243 |
| 15 | 688519.SH | 3.54536726 |
| 16 | 603823.SH | 3.43854241 |
| 17 | 002980.SZ | 3.40673944 |
| 18 | 300903.SZ | 3.40020736 |
| 19 | 600396.SH | 3.18245614 |
| 20 | 603618.SH | 3.17990074 |

## Unsupported candidates

NCAV/MV and the balance-sheet accrual anomaly are intentionally not assigned proxy values. Their required fields are absent or incomplete in the local cache; substituting total assets, OCF, or other nearby fields would change the factor definition.

## Interpretation

This is a China A-share local diagnostic using Tushare cache data. Quantpedia source results use different markets, samples, portfolio rules, and holding periods, so their headline returns are not directly comparable to these numbers.
