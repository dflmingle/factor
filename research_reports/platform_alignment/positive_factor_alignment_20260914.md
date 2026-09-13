# Final platform/local alignment audit

This is an offline audit of saved PandaAI results. It creates no factor and runs no platform backtest.

## Conclusion

The data is complete enough to rebuild all `45/45` positive saved records, but the local reproduction does not fully match the platform.
With the recorded full-A proxy, qfq prices, and the corrected forward label, `5/45` records are within 1 percentage point and `29/45` still differ by at least 2 points of annualized net excess.
The mean absolute net-excess gap is `2.67` pp; the signed mean is `-2.65` pp, so the local result is generally lower.

## Fixed configuration

- local universe: `full-A Tushare qfq rows joined with daily_basic and filtered to .SH/.SZ`; observed instruments: `5456`
- local data start/end: `20180101..20260907`
- saved platform records: `45`; unsupported locally: `0`
- groups: `10`; one-way cost: `0.30%`
- local return label: `close(t+1) -> close(t+1+cycle)`
- recorded platform pools in these rows: `unknown, 沪深全A`

The workflow registry contains 171 workflows; 167 explicitly record the full-A pool label. Two positive historical records have no current registry binding, so their historical pool cannot be independently confirmed.

## Corrected label check

The saved platform benchmark is almost exactly reproduced by shifting both the current and future close one trading day forward:

| cycle | periods | benchmark correlation | RMSE (pp) | mean delta (pp) |
|---:|---:|---:|---:|---:|
| 5 | 241 | 1.000 | 0.170 | -0.026 |
| 10 | 120 | 1.000 | 0.243 | -0.049 |

Compared with the previous same-day label, the corrected label improves absolute error for `33/45` records and reduces mean absolute error from `2.97` to `2.67` pp. It changes the large-gap count only from `30` to `29`.

This confirms a label mismatch in the old local calculation, but it does not explain the remaining factor-specific gaps.

## Gap distribution

| category | records | mean abs net gap (pp) | signed mean (pp) | >=2 pp | within 1 pp |
|---|---:|---:|---:|---:|---:|
| 2026 YTD / short sample | 3 | 3.67 | -3.67 | 2 | 1 |
| Barra proxy | 1 | 0.56 | -0.56 | 0 | 1 |
| direct price / turnover | 15 | 2.57 | -2.49 | 9 | 1 |
| financial / paper | 26 | 2.69 | -2.69 | 18 | 2 |

Across all rows, RankIC mean absolute error is `0.0041`, gross-excess mean absolute error is `3.02` pp, and turnover mean absolute error is `1.96` pp.

## Records still above 2 pp

The table uses the corrected label. `gross delta` and `turnover delta` are local minus platform, in percentage points.

| factor | category | cycle | periods | platform net | local net | delta | gross delta | turnover delta | top20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | 2026 YTD / short sample | 10 | 16 | 10.73% | 3.80% | -6.93 | -8.32 | -9.23 | 0/20 |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | direct price / turnover | 10 | 120 | 16.38% | 11.17% | -5.22 | -5.36 | -0.93 | 5/20 |
| OSR3-RET40-BP-TSRANK756 | financial / paper | 5 | 241 | 1.64% | -3.05% | -4.69 | -6.06 | -4.53 | 4/20 |
| COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | financial / paper | 10 | 120 | 12.77% | 8.45% | -4.32 | -4.48 | -1.03 | 4/20 |
| OSR3-RET40-BP-CFP | financial / paper | 5 | 241 | 3.56% | -0.75% | -4.31 | -4.48 | -0.58 | 2/20 |
| COMBO-DIRECT-OSR2-CHIP-EQ | direct price / turnover | 10 | 120 | 7.88% | 3.58% | -4.30 | -4.55 | -1.63 | 8/20 |
| OSR2-DD60 | direct price / turnover | 5 | 241 | 1.95% | -2.35% | -4.30 | -4.43 | -0.42 | 11/20 |
| OSR2-RET40 | direct price / turnover | 5 | 241 | 1.03% | -3.09% | -4.12 | -4.37 | -0.83 | 6/20 |
| OSR3-RET40-BP-INTERACT | financial / paper | 5 | 241 | 2.73% | -1.31% | -4.04 | -4.17 | -0.44 | 6/20 |
| OSR3-RET40-BP-EQ | financial / paper | 5 | 241 | 3.16% | -0.41% | -3.58 | -3.67 | -0.32 | 7/20 |
| OSR4-RET40-BP-CFP-SP | financial / paper | 5 | 241 | 2.88% | -0.68% | -3.56 | -4.03 | -1.55 | 4/20 |
| OSR4-RET40-BP-CFP-REV2 | financial / paper | 5 | 241 | 2.37% | -1.09% | -3.45 | -3.85 | -1.31 | 5/20 |
| OSR3-RET40-BP-REV2 | financial / paper | 5 | 241 | 2.48% | -0.97% | -3.45 | -3.59 | -0.48 | 6/20 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD | 2026 YTD / short sample | 10 | 16 | 4.67% | 1.35% | -3.32 | -4.11 | -5.22 | 2/20 |
| OSR2-RET40 | direct price / turnover | 10 | 120 | 5.03% | 1.71% | -3.32 | -3.40 | -0.53 | 4/20 |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | financial / paper | 10 | 120 | 11.64% | 8.45% | -3.19 | -3.40 | -1.36 | 2/20 |
| paper-derived-asset-growth | financial / paper | 5 | 241 | 0.76% | -2.35% | -3.11 | -3.18 | -0.24 | 0/20 |
| OSR3-RET40-BP-MA63 | financial / paper | 5 | 241 | 2.41% | -0.68% | -3.09 | -3.23 | -0.44 | 7/20 |
| OSR4-RET40-BP-CFP-REV3 | financial / paper | 5 | 241 | 1.63% | -1.39% | -3.02 | -3.47 | -1.48 | 5/20 |
| OSR3-RET40-BP-VAL2 | financial / paper | 5 | 241 | 3.17% | 0.34% | -2.83 | -2.85 | -0.05 | 6/20 |
| OSR4-RET40-BP-CFP-MA63 | financial / paper | 5 | 241 | 2.59% | -0.22% | -2.81 | -2.86 | -0.17 | 2/20 |
| OSR4-RET40-BP-CFP-VAL2 | financial / paper | 5 | 241 | 3.56% | 0.77% | -2.79 | -3.00 | -0.72 | 2/20 |
| OSR4-RET40-BP-CFP-PCF | financial / paper | 5 | 241 | 2.67% | 0.01% | -2.65 | -3.11 | -1.52 | 2/20 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | financial / paper | 10 | 120 | 5.22% | 2.65% | -2.57 | -2.77 | -1.29 | 3/20 |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | direct price / turnover | 10 | 120 | 8.66% | 6.13% | -2.53 | -2.83 | -1.96 | 3/20 |
| OSR2-DD120 | direct price / turnover | 10 | 120 | 4.25% | 1.81% | -2.44 | -2.79 | -2.33 | 15/20 |
| OSR2-RET40-TURN-BIAS-EQ | direct price / turnover | 10 | 120 | 7.40% | 4.99% | -2.41 | -2.79 | -2.54 | 0/20 |
| OSR4-RET40-BP-CFP-VAL3 | financial / paper | 5 | 241 | 3.31% | 0.94% | -2.36 | -2.69 | -1.07 | 3/20 |
| OSR2-DD120 | direct price / turnover | 5 | 241 | 4.79% | 2.50% | -2.30 | -3.02 | -2.38 | 15/20 |

## What is still different

- Direct price/turnover factors: the remaining loss is mainly in gross excess rather than turnover. qfq is materially closer than raw prices, but it is still not proof that the platform uses the same adjustment series, suspension handling, or portfolio construction.
- Financial and paper factors: the point-in-time Tushare cache is present, but the platform's internal fields are not byte-equivalent to documented Tushare fields. The separate CFP proxy test finds no single cash-flow field that matches every CFP combination; differences are consistent with field definition, report-revision timing, or TTM treatment.
- 2026 YTD factors: these have only 16 periods. Two of the three YTD rows remain above 2 pp, and some platform configurations end on 2026-09-09 while the local snapshot ends on 2026-09-07. They are not reliable equivalence tests.
- Residual volatility: the local implementation is a market-model proxy for the platform Barra field. Its remaining gap is small, but exact field equivalence is not established.
- Missing data is no longer the blocker: all 45 records rebuild, the full-A qfq/daily_basic history covers the warm-up, and the financial tables are available. The unresolved part is semantic equivalence to the platform's internal data and execution rules.

## Reproduction

```powershell
python scripts/positive_factor_local_compare.py --universe full_a --data-start 20180101 --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a --output quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a_label1 --label-offset 1
python scripts/build_final_alignment_report.py
```
