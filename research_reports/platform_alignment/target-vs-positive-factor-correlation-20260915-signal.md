# Yesterday's factor vs positive-net factors

This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.

## Fixed inputs

- Target: `WMA((((1/LOW)/LOW)/VOLUME),40)` (`F-NET01`, handler `wma_low_volume40`).
- Existing set: `64` saved completed factors with platform net excess greater than zero; `54` unique local handlers.
- Window: `2021-09-07..2026-09-07`; warm-up starts `2018-01-01`.
- Universe: `沪深全A`; prices `qfq`; market cap `total_mv`.
- Correlation: `daily_cross_sectional_spearman_mean`; average of daily cross-sectional Spearman correlations using average ranks.
- Date sampling mode: `signal`; `signal` uses the shared 5-day aligned signal dates as a screening sample, not the full daily series.
- Pairwise valid stocks are intersected separately on every date. Platform direction, forward returns, rebalance cycle, grouping, turnover, and transaction cost do not enter this statistic.

## Highest absolute correlations

| Rank | Factor | Handler | Platform net | Correlation | Abs correlation | Days | Mean stocks |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | VERIFY-F260910-12 | `book_to_market_lf_plus_impact` | 15.59% | +0.750690 | 0.750690 | 241 | 4933.9 |
| 2 | VERIFY10-F260910-12 | `book_to_market_lf_plus_impact` | 15.05% | +0.750690 | 0.750690 | 241 | 4933.9 |
| 3 | H03-T10-SINGLE | `impact60` | 16.44% | +0.723556 | 0.723556 | 241 | 4938.0 |
| 4 | VERIFY-G260910-13 | `impact_abs_return60` | 14.70% | +0.710784 | 0.710784 | 241 | 4938.0 |
| 5 | VERIFY10-G260910-13 | `impact_abs_return60` | 13.94% | +0.710784 | 0.710784 | 241 | 4938.0 |
| 6 | VERIFY-E260910-04 | `book_to_market_lf_minus_size` | 17.76% | +0.691653 | 0.691653 | 241 | 4951.7 |
| 7 | VERIFY10-E260910-04 | `book_to_market_lf_minus_size` | 16.74% | +0.691653 | 0.691653 | 241 | 4951.7 |
| 8 | T10-ADD-G13-20260911 | `t10_size_plus_impact_g13` | 19.62% | +0.684085 | 0.684085 | 241 | 4428.1 |
| 9 | T10-ADD-AGG-IMPACT-20260911 | `t10_size_plus_impact_aggregate` | 19.76% | +0.682052 | 0.682052 | 241 | 4428.1 |
| 10 | T10-ADD-DOWNSIDE-IMPACT-20260911 | `t10_size_plus_impact_downside` | 19.39% | +0.675307 | 0.675307 | 241 | 4428.1 |
| 11 | T10-ADD-BM-20260911 | `t10_size_plus_impact_bm` | 18.09% | +0.660248 | 0.660248 | 241 | 4424.0 |
| 12 | SIZE-ONLY-20260911 | `size_only` | 21.43% | -0.623348 | 0.623348 | 241 | 4955.8 |
| 13 | paper-derived-composite | `paper_composite` | 11.20% | +0.605222 | 0.605222 | 241 | 4925.8 |
| 14 | paper-derived-composite | `paper_composite` | 11.41% | +0.605222 | 0.605222 | 241 | 4925.8 |
| 15 | T10-SIZE-PLUS-IMPACT | `t10_size_plus_impact` | 18.16% | +0.600260 | 0.600260 | 241 | 4428.1 |

## Closest to independent

| Rank | Factor | Handler | Correlation | Abs correlation | Days | Mean stocks |
|---:|---|---|---:|---:|---:|---:|
| 1 | NONHT-FSCORELIKE-REV40 | `fscore_eq` | +0.013987 | 0.013987 | 241 | 4781.2 |
| 2 | NONHT-FSCORELIKE-REV40-INTERACT | `fscore_interact` | +0.047746 | 0.047746 | 241 | 4781.2 |
| 3 | NEW-VALUE-EVEBITDA | `ev_ebitda_proxy` | +0.048468 | 0.048468 | 241 | 4880.5 |
| 4 | OSR2-DD120 | `drawdown120` | -0.075559 | 0.075559 | 241 | 4883.6 |
| 5 | OSR2-DD120 | `drawdown120` | -0.075559 | 0.075559 | 241 | 4883.6 |
| 6 | OSR2-RET40 | `reversal40` | +0.089444 | 0.089444 | 241 | 4955.1 |
| 7 | OSR2-RET40 | `reversal40` | +0.089444 | 0.089444 | 241 | 4955.1 |
| 8 | OSR4-RET40-BP-CFP-TSRANK756 | `reversal_bm_cfp_tsrank756` | +0.125986 | 0.125986 | 241 | 3511.9 |
| 9 | OSR2-DD60 | `drawdown60` | -0.140017 | 0.140017 | 241 | 4938.8 |
| 10 | OSR3-RET40-BP-TSRANK756 | `reversal_bm_tsrank756` | +0.151793 | 0.151793 | 241 | 4076.4 |

## Complete result

The complete 64-row table is in the JSON and summary CSV artifacts. The daily CSV keeps the date-level values used in each arithmetic mean.

- Local rows loaded: `9,401,373`; instruments: `5,456`.
- Daily detail rows: `15,424`.
- JSON: `research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915-signal.json`.
- Summary CSV: `research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915-signal.summary.csv`.
- Daily CSV: `research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915-signal.daily.csv`.
