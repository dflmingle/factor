# AlphaPROBE candidates vs existing positive-net factors

This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.

## Fixed inputs

- Candidates: `10` from `quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare/orthogonal-fundamental-verified-multifield-net-20260918/gp_run.json`; existing records: `35` records and `30` unique handlers.
- Existing-record filter: `platform_net_excess>0 AND alignment_quality=aligned`. Records rejected by the alignment quality gate are excluded from this redundancy screen.
- Window: `2021-09-07..2026-09-07`; signal sample: `241` aligned 5-day dates; warm-up starts `2018-01-01`.
- Universe: `沪深全A`; prices `qfq`; market cap `total_mv`.
- Correlation: `daily_cross_sectional_spearman_mean`; average of daily cross-sectional Spearman correlations using average ranks.
- Independence screen: maximum absolute correlation `< 0.80`.

## Candidate ranking

| Candidate | Formula | Net excess | Gross | Cost | Turnover | Max abs corr | Closest existing factor | Handler | Pass |
|---|---|---:|---:|---:|---:|---:|---|---|:---:|
| F-NET01 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40),40),40),40),40),40),40))` | 13.09% | 14.35% | 1.27% | 4.19% | 0.7388 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET02 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40),40),40),40),40),40))` | 13.00% | 14.25% | 1.25% | 4.14% | 0.7405 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET03 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40),40),40),40),40))` | 12.83% | 14.09% | 1.26% | 4.17% | 0.7421 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET04 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40),40),40))` | 12.81% | 14.08% | 1.28% | 4.23% | 0.7452 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET05 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40))` | 12.77% | 14.08% | 1.30% | 4.32% | 0.7476 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET06 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40),40))` | 12.74% | 14.01% | 1.28% | 4.22% | 0.7465 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET07 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40),40),40),40),40))` | 12.71% | 13.98% | 1.26% | 4.18% | 0.7437 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET08 | `(RATIO_SP_TTM/TS_MEDIAN(WMA(TS_MAX(TS_MAX(MA(TS_MAX(CURRENT_LIABILITIES,40),20),40),40),50),50))` | 12.46% | 13.70% | 1.25% | 4.12% | 0.7451 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET09 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40),40))` | 12.35% | 13.65% | 1.31% | 4.32% | 0.7483 | SIZE-ONLY-20260911 | `size_only` | yes |
| F-NET10 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40),40),40))` | 12.10% | 13.40% | 1.30% | 4.29% | 0.7489 | SIZE-ONLY-20260911 | `size_only` | yes |

The full candidate-to-existing matrix is in the pairs CSV and JSON. Correlation is a redundancy diagnostic, not a return forecast.

- Pair rows: `350`; local rows: `9,401,373`; instruments: `5,456`.
- Summary CSV: `research_reports/platform_alignment/gp-multifield-vs-positive-20260918.summary.csv`.
- Pair CSV: `research_reports/platform_alignment/gp-multifield-vs-positive-20260918.pairs.csv`.
