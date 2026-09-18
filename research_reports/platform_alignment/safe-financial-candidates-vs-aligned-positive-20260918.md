# AlphaPROBE candidates vs existing positive-net factors

This is an offline local calculation. It does not contact PandaAI, create factors, or spend compute credits.

## Fixed inputs

- Candidates: `10` from `quantlab/.quantlab/cache/research/cn_equity/reports/local_safe_financial_blends_20260918/results.json`; existing records: `35` records and `30` unique handlers.
- Existing-record filter: `platform_net_excess>0 AND alignment_quality=aligned`. Records rejected by the alignment quality gate are excluded from this redundancy screen.
- Window: `2021-09-07..2026-09-07`; signal sample: `241` aligned 5-day dates; warm-up starts `2018-01-01`.
- Universe: `沪深全A`; prices `qfq`; market cap `total_mv`.
- Correlation: `daily_cross_sectional_spearman_mean`; average of daily cross-sectional Spearman correlations using average ranks.
- Independence screen: maximum absolute correlation `< 0.45`.

## Candidate ranking

| Candidate | Formula | Net excess | Gross | Cost | Turnover | Max abs corr | Closest existing factor | Handler | Pass |
|---|---|---:|---:|---:|---:|---:|---|---|:---:|
| SAFE-BLEND-V4-V5-80-20 | `0.80*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.20*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(RATIO_EP_TTM)+RANK(OPER_ROE_LYR))/5)` | 6.71% | 8.25% | 1.54% | 5.09% | 0.4159 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-SMOOTH-80-20 | `0.80*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.20*EMA(WMA((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4,40),20)` | 6.59% | 7.95% | 1.35% | 4.48% | 0.4195 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-SMOOTH-60-40 | `0.60*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.40*EMA(WMA((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4,40),20)` | 6.52% | 7.69% | 1.18% | 3.90% | 0.4205 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-SMOOTH-40-60 | `0.40*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.60*EMA(WMA((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4,40),20)` | 6.27% | 7.27% | 1.00% | 3.31% | 0.4205 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-V5-60-40 | `0.60*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.40*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(RATIO_EP_TTM)+RANK(OPER_ROE_LYR))/5)` | 6.13% | 7.71% | 1.58% | 5.23% | 0.4126 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-EP-90-10 | `0.90*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.10*RANK(RATIO_EP_TTM)` | 5.62% | 7.19% | 1.57% | 5.20% | 0.4101 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-SMOOTH-20-80 | `0.20*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.80*EMA(WMA((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4,40),20)` | 5.58% | 6.46% | 0.88% | 2.90% | 0.4195 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-V5-40-60 | `0.40*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.60*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(RATIO_EP_TTM)+RANK(OPER_ROE_LYR))/5)` | 5.13% | 6.70% | 1.57% | 5.18% | 0.4070 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-V5-20-80 | `0.20*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.80*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(RATIO_EP_TTM)+RANK(OPER_ROE_LYR))/5)` | 4.84% | 6.41% | 1.57% | 5.19% | 0.3994 | paper-derived-composite | `paper_composite` | yes |
| SAFE-BLEND-V4-EP-75-25 | `0.75*((RANK(1/CURRENT_ASSETS)+RANK(1/GR_TOTAL_ASSET_LYR)+RANK(BOOK_TO_MARKET_RATIO_LF)+RANK(OPER_ROE_LYR))/4)+0.25*RANK(RATIO_EP_TTM)` | 3.10% | 4.69% | 1.59% | 5.25% | 0.3771 | paper-derived-composite | `paper_composite` | yes |

The full candidate-to-existing matrix is in the pairs CSV and JSON. Correlation is a redundancy diagnostic, not a return forecast.

- Pair rows: `350`; local rows: `9,401,373`; instruments: `5,456`.
- Summary CSV: `research_reports/platform_alignment/safe-financial-candidates-vs-aligned-positive-20260918.summary.csv`.
- Pair CSV: `research_reports/platform_alignment/safe-financial-candidates-vs-aligned-positive-20260918.pairs.csv`.
