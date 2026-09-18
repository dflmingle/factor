# AlphaPROBE candidates vs existing positive-net factors

This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.

## Fixed inputs

- Candidates: `6` from `/data/games/factor_/quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare/orthogonal-fundamental-net-fast-20260915/gp_run.json`; existing records: `54` unique handlers across `384` rows.
- Window: `2021-09-07..2026-09-07`; signal sample: `241` aligned 5-day dates; warm-up starts `2018-01-01`.
- Universe: `沪深全A`; prices `qfq`; market cap `total_mv`.
- Correlation: `daily_cross_sectional_spearman_mean`; average of daily cross-sectional Spearman correlations using average ranks.
- Independence screen: maximum absolute correlation `< 0.45`.

## Candidate ranking

| Candidate | Formula | Net excess | Gross | Cost | Turnover | Max abs corr | Closest existing factor | Handler | Pass |
|---|---|---:|---:|---:|---:|---:|---|---|:---:|
| F-NET01 | `(1/(CONTRACT_LIABILITIES_LYR))` | 5.33% | 5.67% | 0.35% | 1.16% | 0.4300 | HT13-VALUE-SP | `value_sp` | yes |
| F-NET02 | `(1/(NET_PROFIT_PARENT_COMPANY_TTM))` | 5.17% | 6.08% | 0.90% | 2.99% | 0.2298 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET03 | `(1/(REF(EV_NO_CASH_TTM,10)))` | 3.91% | 4.90% | 0.99% | 3.27% | 0.3020 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET04 | `RETURNS(CONTRACT_LIABILITIES_LYR,30)` | 1.61% | 4.23% | 2.62% | 8.66% | 0.0576 | paper-derived-asset-growth | `asset_growth` | yes |
| F-NET05 | `BOOK_TO_MARKET_RATIO_LF` | 0.68% | 1.90% | 1.22% | 4.03% | 1.0000 | HT13-VALUE-BP | `value_bm` | no |
| F-NET06 | `(CURRENT_ASSETS_LYR/MA(CURRENT_ASSETS_LYR,50))` | -0.63% | 2.26% | 2.89% | 9.55% | 0.1803 | paper-derived-asset-growth | `asset_growth` | yes |

The full candidate-to-existing matrix is in the pairs CSV and JSON. Correlation is a redundancy diagnostic, not a return forecast.

- Pair rows: `384`; local rows: `9,401,373`; instruments: `5,456`.
- Summary CSV: `/data/games/factor_/research_reports/platform_alignment/gp-candidates-vs-positive-20260915-signal.summary.csv`.
- Pair CSV: `/data/games/factor_/research_reports/platform_alignment/gp-candidates-vs-positive-20260915-signal.pairs.csv`.
