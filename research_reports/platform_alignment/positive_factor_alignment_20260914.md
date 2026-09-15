# Final platform/local alignment audit

This is an offline audit of saved PandaAI results. It creates no factor and runs no platform backtest.

## Conclusion

The local implementation rebuilt all `64/64` positive saved records; no positive records remain unsupported. The local reproduction still does not fully match the platform.
Among the supported records, `9/64` are within 1 percentage point and `39/64` still differ by at least 2 points of annualized net excess.
The mean absolute net-excess gap is `2.69` pp; the signed mean is `-2.65` pp, so the local result is generally lower.

## Fixed configuration

- local universe: `full-A Tushare qfq rows joined with daily_basic and filtered to .SH/.SZ`; observed instruments: `5456`
- local data start/end: `20180101..20260907`
- alignment rules: `full-a-qfq-label1-v1`; document: `research_reports/platform_alignment/ALIGNMENT_RULES.md`
- positive saved records: `64` (`64` supported locally, `0` unsupported)
- groups: `10`; one-way cost: `0.30%`
- local return label: `close(t+1) -> close(t+1+cycle)`
- `MARKET_CAP` mapping: `total_mv`
- recorded platform pools in these rows: `unknown, 沪深全A`

The workflow registry contains 171 workflows; 167 explicitly record the full-A pool label. Two positive historical records have no current registry binding, so their historical pool cannot be independently confirmed.

## Corrected label check

The saved platform benchmark is almost exactly reproduced by shifting both the current and future close one trading day forward:

| cycle | periods | benchmark correlation | RMSE (pp) | mean delta (pp) |
|---:|---:|---:|---:|---:|
| 5 | 241 | 1.000 | 0.170 | -0.026 |
| 10 | 120 | 1.000 | 0.243 | -0.049 |

Among the `45` records shared with the previous same-day calculation, the corrected label improves absolute error for `39/45` and reduces mean absolute error from `2.97` to `2.29` pp. It changes the large-gap count only from `30` to `22`.

This confirms a label mismatch in the old local calculation, but it does not explain the remaining factor-specific gaps.

Compared with the previous corrected-label implementation, the field-specific updates improve absolute error for `8/64` records and reduce mean absolute error from `2.96` to `2.69` pp; the >=2 pp count changes from `46` to `39`.

## Gap distribution

| category | records | mean abs net gap (pp) | signed mean (pp) | >=2 pp | within 1 pp |
|---|---:|---:|---:|---:|---:|
| 2026 YTD / short sample | 3 | 3.67 | -3.67 | 2 | 1 |
| Barra proxy | 1 | 0.56 | -0.56 | 0 | 1 |
| direct price / turnover | 15 | 2.57 | -2.49 | 9 | 1 |
| financial / paper | 35 | 2.25 | -2.22 | 19 | 6 |
| market proxy | 10 | 4.34 | -4.34 | 9 | 0 |

Across all rows, RankIC mean absolute error is `0.0042`, gross-excess mean absolute error is `2.91` pp, and turnover mean absolute error is `1.38` pp.

## Records still above 2 pp

The table uses the corrected label. `gross delta` and `turnover delta` are local minus platform, in percentage points.

| factor | category | cycle | periods | platform net | local net | delta | gross delta | turnover delta | top20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | 2026 YTD / short sample | 10 | 16 | 10.73% | 3.80% | -6.93 | -8.32 | -9.23 | 2/20 |
| T10-ADD-G13-20260911 | market proxy | 10 | 120 | 19.62% | 13.62% | -6.01 | -5.99 | 0.07 | 19/20 |
| T10-ADD-AGG-IMPACT-20260911 | market proxy | 10 | 120 | 19.76% | 14.23% | -5.53 | -5.52 | 0.09 | 19/20 |
| T10-ADD-DOWNSIDE-IMPACT-20260911 | market proxy | 10 | 120 | 19.39% | 14.15% | -5.24 | -5.24 | 0.02 | 19/20 |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | direct price / turnover | 10 | 120 | 16.38% | 11.17% | -5.22 | -5.36 | -0.93 | 19/20 |
| T10-SIZE-PLUS-IMPACT | market proxy | 10 | 120 | 18.16% | 13.15% | -5.01 | -5.06 | -0.32 | 19/20 |
| VERIFY-G260910-13 | market proxy | 5 | 241 | 14.70% | 9.73% | -4.97 | -5.04 | -0.24 | 15/20 |
| OSR3-RET40-BP-TSRANK756 | financial / paper | 5 | 241 | 1.64% | -3.05% | -4.69 | -6.06 | -4.53 | 4/20 |
| T10-ADD-DD120-20260911 | market proxy | 10 | 120 | 16.83% | 12.50% | -4.34 | -4.40 | -0.43 | 19/20 |
| COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | financial / paper | 10 | 120 | 12.77% | 8.45% | -4.32 | -4.48 | -1.03 | 20/20 |
| COMBO-DIRECT-OSR2-CHIP-EQ | direct price / turnover | 10 | 120 | 7.88% | 3.58% | -4.30 | -4.55 | -1.63 | 18/20 |
| OSR2-DD60 | direct price / turnover | 5 | 241 | 1.95% | -2.35% | -4.30 | -4.43 | -0.42 | 19/20 |
| SIZE-ONLY-20260911 | market proxy | 10 | 120 | 21.43% | 17.16% | -4.27 | -4.28 | -0.01 | 19/20 |
| T10-ADD-BM-20260911 | financial / paper | 10 | 120 | 18.09% | 13.84% | -4.25 | -4.18 | 0.45 | 19/20 |
| OSR2-RET40 | direct price / turnover | 5 | 241 | 1.03% | -3.09% | -4.12 | -4.37 | -0.83 | 19/20 |
| T10-ADD-FSCORE-20260911 | financial / paper | 10 | 120 | 17.48% | 13.37% | -4.11 | -3.97 | 0.91 | 7/20 |
| OSR3-RET40-BP-INTERACT | financial / paper | 5 | 241 | 2.73% | -1.31% | -4.04 | -4.17 | -0.44 | 19/20 |
| OSR3-RET40-BP-EQ | financial / paper | 5 | 241 | 3.16% | -0.41% | -3.58 | -3.67 | -0.32 | 18/20 |
| VERIFY10-G260910-13 | market proxy | 10 | 120 | 13.94% | 10.39% | -3.56 | -3.60 | -0.28 | 15/20 |
| OSR3-RET40-BP-REV2 | financial / paper | 5 | 241 | 2.48% | -0.97% | -3.45 | -3.59 | -0.48 | 19/20 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD | 2026 YTD / short sample | 10 | 16 | 4.67% | 1.35% | -3.32 | -4.11 | -5.22 | 0/20 |
| OSR2-RET40 | direct price / turnover | 10 | 120 | 5.03% | 1.71% | -3.32 | -3.40 | -0.53 | 19/20 |
| T10-NOMCAP-PLUS-IMPACT | market proxy | 10 | 120 | 14.23% | 10.91% | -3.31 | -3.40 | -0.54 | 19/20 |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | financial / paper | 10 | 120 | 11.64% | 8.45% | -3.19 | -3.40 | -1.36 | 20/20 |
| paper-derived-asset-growth | financial / paper | 5 | 241 | 0.76% | -2.35% | -3.11 | -3.18 | -0.24 | 18/20 |
| T10-SIZE-PLUS-IMPACT-WC | financial / paper | 10 | 120 | 17.44% | 14.35% | -3.10 | -3.00 | 0.61 | 19/20 |
| OSR3-RET40-BP-MA63 | financial / paper | 5 | 241 | 2.41% | -0.68% | -3.09 | -3.23 | -0.44 | 18/20 |
| OSR3-RET40-BP-VAL2 | financial / paper | 5 | 241 | 3.17% | 0.34% | -2.83 | -2.85 | -0.05 | 17/20 |
| VERIFY-F260910-12 | financial / paper | 5 | 241 | 15.59% | 12.76% | -2.82 | -2.86 | -0.13 | 17/20 |
| VERIFY-E260910-04 | financial / paper | 5 | 241 | 17.76% | 14.95% | -2.81 | -2.88 | -0.25 | 18/20 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | financial / paper | 10 | 120 | 5.22% | 2.65% | -2.57 | -2.77 | -1.29 | 20/20 |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | direct price / turnover | 10 | 120 | 8.66% | 6.13% | -2.53 | -2.83 | -1.96 | 18/20 |
| OSR2-DD120 | direct price / turnover | 10 | 120 | 4.25% | 1.81% | -2.44 | -2.79 | -2.33 | 18/20 |
| OSR4-RET40-BP-CFP-REV3 | financial / paper | 5 | 241 | 1.63% | -0.80% | -2.43 | -2.61 | -0.60 | 10/20 |
| OSR2-RET40-TURN-BIAS-EQ | direct price / turnover | 10 | 120 | 7.40% | 4.99% | -2.41 | -2.79 | -2.54 | 18/20 |
| VERIFY10-E260910-04 | financial / paper | 10 | 120 | 16.74% | 14.34% | -2.40 | -2.44 | -0.26 | 18/20 |
| VERIFY10-F260910-12 | financial / paper | 10 | 120 | 15.05% | 12.70% | -2.34 | -2.34 | 0.02 | 17/20 |
| OSR2-DD120 | direct price / turnover | 5 | 241 | 4.79% | 2.50% | -2.30 | -3.02 | -2.38 | 18/20 |
| T10-SIZE-PLUS-WC-MCAP | financial / paper | 10 | 120 | 14.58% | 12.32% | -2.27 | -2.27 | -0.05 | 19/20 |

## What is still different

- Direct price/turnover factors: the remaining loss is mainly in gross excess rather than turnover. qfq is materially closer than raw prices, but it is still not proof that the platform uses the same adjustment series, suspension handling, or portfolio construction.
- Financial and paper factors: the point-in-time Tushare cache is present, and CFP combinations now use the closest proxy selected per formula from the offline diagnosis. The platform's internal fields are still not byte-equivalent to documented Tushare fields, so residual differences remain.
- Top20 is the overlap of the 20 highest raw factor values on the platform's latest top-list date. It is separate from the direction-selected long group used for returns; this avoids comparing a direction-0 held bottom group with the platform's raw top list.
- Market-cap sensitivity: The offline `circ_mv` sensitivity is materially worse: size-only local net is `17.16%` with `total_mv` versus `5.43%` with `circ_mv` (platform `21.43%`), and T10 base is `13.15%` versus `12.54%`. Keep `total_mv` as the default mapping.
- 2026 YTD factors: these have only 16 periods. 2 of 3 supported YTD rows remain above 2 pp, and some platform configurations end on 2026-09-09 while the local snapshot ends on 2026-09-07. They are not reliable equivalence tests.
- Residual volatility: the local implementation is a market-model proxy for the platform Barra field. Its remaining gap is small, but exact field equivalence is not established.
- Missing data is no longer the blocker: all 64 supported records rebuild, the full-A qfq/daily_basic history covers the warm-up, and the financial tables are available. No positive records remain unsupported. Some handlers still use explicitly marked market and financial proxy fields, so the remaining gap is semantic equivalence to the platform's internal data and execution rules.

## Reproduction

```powershell
python scripts/positive_factor_local_compare.py --universe full_a --market-cap-field total_mv --data-start 20180101 --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a --output quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a_label1_cfpfix2 --label-offset 1
python scripts/build_final_alignment_report.py
```
