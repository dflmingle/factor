# Yesterday's factor vs positive-net factors

This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.

## Fixed inputs

- Target: `WMA((((1/LOW)/LOW)/VOLUME),40)` (`F-NET01`, handler `wma_low_volume40`).
- Existing set: `64` saved completed factors with platform net excess greater than zero; `54` unique local handlers.
- Window: `2021-09-07..2026-09-07`; warm-up starts `2018-01-01`.
- Universe: `沪深全A`; prices `qfq`; market cap `total_mv`.
- Correlation: `daily_cross_sectional_spearman_mean`; average of daily cross-sectional Spearman correlations using average ranks.
- Pairwise valid stocks are intersected separately on every date. Platform direction, forward returns, rebalance cycle, grouping, turnover, and transaction cost do not enter this statistic.

## Highest absolute correlations

| Rank | Factor | Handler | Platform net | Correlation | Abs correlation | Days | Mean stocks |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | VERIFY-F260910-12 | `book_to_market_lf_plus_impact` | 15.59% | +0.751164 | 0.751164 | 1211 | 4847.6 |
| 2 | VERIFY10-F260910-12 | `book_to_market_lf_plus_impact` | 15.05% | +0.751164 | 0.751164 | 1211 | 4847.6 |
| 3 | H03-T10-SINGLE | `impact60` | 16.44% | +0.723887 | 0.723887 | 1211 | 4940.4 |
| 4 | VERIFY-G260910-13 | `impact_abs_return60` | 14.70% | +0.711041 | 0.711041 | 1211 | 4940.4 |
| 5 | VERIFY10-G260910-13 | `impact_abs_return60` | 13.94% | +0.711041 | 0.711041 | 1211 | 4940.4 |
| 6 | VERIFY-E260910-04 | `book_to_market_lf_minus_size` | 17.76% | +0.691718 | 0.691718 | 1211 | 4865.3 |
| 7 | VERIFY10-E260910-04 | `book_to_market_lf_minus_size` | 16.74% | +0.691718 | 0.691718 | 1211 | 4865.3 |
| 8 | T10-ADD-G13-20260911 | `t10_size_plus_impact_g13` | 19.62% | +0.683916 | 0.683916 | 1211 | 4433.3 |
| 9 | T10-ADD-AGG-IMPACT-20260911 | `t10_size_plus_impact_aggregate` | 19.76% | +0.681918 | 0.681918 | 1211 | 4433.3 |
| 10 | T10-ADD-DOWNSIDE-IMPACT-20260911 | `t10_size_plus_impact_downside` | 19.39% | +0.675163 | 0.675163 | 1211 | 4433.3 |
| 11 | T10-ADD-BM-20260911 | `t10_size_plus_impact_bm` | 18.09% | +0.659967 | 0.659967 | 1211 | 4344.4 |
| 12 | SIZE-ONLY-20260911 | `size_only` | 21.43% | -0.623662 | 0.623662 | 1211 | 4958.2 |
| 13 | paper-derived-composite | `paper_composite` | 11.20% | +0.607046 | 0.607046 | 1211 | 4838.4 |
| 14 | paper-derived-composite | `paper_composite` | 11.41% | +0.607046 | 0.607046 | 1211 | 4838.4 |
| 15 | T10-SIZE-PLUS-IMPACT | `t10_size_plus_impact` | 18.16% | +0.600083 | 0.600083 | 1211 | 4433.3 |

## Closest to independent

| Rank | Factor | Handler | Correlation | Abs correlation | Days | Mean stocks |
|---:|---|---|---:|---:|---:|---:|
| 1 | NONHT-FSCORELIKE-REV40 | `fscore_eq` | +0.011282 | 0.011282 | 1211 | 4784.0 |
| 2 | NEW-VALUE-EVEBITDA | `ev_ebitda_proxy` | +0.038333 | 0.038333 | 1211 | 4793.6 |
| 3 | NONHT-FSCORELIKE-REV40-INTERACT | `fscore_interact` | +0.045184 | 0.045184 | 1211 | 4784.0 |
| 4 | OSR2-DD120 | `drawdown120` | -0.075414 | 0.075414 | 1211 | 4886.5 |
| 5 | OSR2-DD120 | `drawdown120` | -0.075414 | 0.075414 | 1211 | 4886.5 |
| 6 | OSR2-RET40 | `reversal40` | +0.085632 | 0.085632 | 1211 | 4957.4 |
| 7 | OSR2-RET40 | `reversal40` | +0.085632 | 0.085632 | 1211 | 4957.4 |
| 8 | OSR4-RET40-BP-CFP-TSRANK756 | `reversal_bm_cfp_tsrank756` | +0.127312 | 0.127312 | 1211 | 3453.8 |
| 9 | OSR2-DD60 | `drawdown60` | -0.141279 | 0.141279 | 1211 | 4941.3 |
| 10 | OSR3-RET40-BP-TSRANK756 | `reversal_bm_tsrank756` | +0.150596 | 0.150596 | 1211 | 4002.4 |

## Complete result

The complete 64-row table is in the JSON and CSV artifacts. The daily CSV keeps the date-level values used in each arithmetic mean.

- Local rows loaded: `9,401,373`; instruments: `5,456`.
- Daily detail rows: `77,504`.
- JSON: `/data/games/factor_/research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915.json`.
- Summary CSV: `/data/games/factor_/research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915.summary.csv`.
- Daily CSV: `/data/games/factor_/research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915.daily.csv`.
