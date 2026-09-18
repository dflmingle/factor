# Recent local diagnostics for platform-net-positive factors

This report is a recent-window diagnostic, not a replacement for the canonical five-year alignment report.
Alignment rules: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Factor values use `2018-01-01 00:00:00` warm-up; portfolio statistics use signal dates from `2026-01-01 00:00:00`.
The platform net column is the saved full-window screening result. It is not a recent-window platform return.

- positive platform records: `70`
- locally reproduced: `65`
- no local handler or no usable recent dates: `5`
- recent signal dates: `2026-01-05 00:00:00` to `2026-08-27 00:00:00`

## Recent results

Net, gross and cost values are arithmetic annualized percentages over the recent signal dates.

| name | handler | cycle | recent periods | platform net full window | recent local net | recent gross | annual cost | turnover | RankIC |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H03-T10-SINGLE | impact60 | 10 | 15 | 16.44% | 16.97% | 18.32% | 1.35% | 8.91% | 0.0637 |
| VERIFY10-G260910-13 | impact_abs_return60 | 10 | 15 | 13.94% | 14.79% | 16.22% | 1.44% | 9.49% | 0.0530 |
| SIZE-ONLY-20260911 | size_only | 10 | 15 | 21.43% | 12.66% | 14.00% | 1.34% | 8.88% | -0.0453 |
| VERIFY-G260910-13 | impact_abs_return60 | 5 | 31 | 14.70% | 12.66% | 14.30% | 1.64% | 5.43% | 0.0465 |
| VERIFY10-F260910-12 | book_to_market_lf_plus_impact | 10 | 15 | 15.05% | 10.18% | 11.56% | 1.38% | 9.13% | 0.0718 |
| VERIFY-F260910-12 | book_to_market_lf_plus_impact | 5 | 31 | 15.59% | 9.89% | 11.61% | 1.72% | 5.70% | 0.0558 |
| VERIFY-E260910-04 | book_to_market_lf_minus_size | 5 | 31 | 17.76% | 9.50% | 11.54% | 2.04% | 6.75% | 0.0556 |
| VERIFY10-E260910-04 | book_to_market_lf_minus_size | 10 | 15 | 16.74% | 9.25% | 10.68% | 1.43% | 9.45% | 0.0684 |
| F-NET01-PLAT-20260914 | wma_low_volume40 | 5 | 31 | 13.63% | 8.75% | 10.50% | 1.75% | 5.79% | 0.0541 |
| F-GFN-N02-20260916 | book_to_market_lf_div_oper_main_profit_ttm | 5 | 31 | 12.27% | 7.62% | 8.92% | 1.30% | 4.30% | 0.0316 |
| OSR4-RET40-BP-CFP-VAL3 | reversal_bm_cfp_val3 | 5 | 31 | 3.31% | 7.44% | 10.94% | 3.50% | 11.57% | 0.0359 |
| OSR2-RET40-TURN-BIAS-PAPER-EQ-2026-YTD | reversal_turn_paper | 10 | 16 | 7.70% | 7.27% | 12.89% | 5.62% | 37.18% | 0.0860 |
| OSR4-RET40-BP-CFP-MA63 | reversal_bm_cfp_ma63 | 5 | 31 | 2.59% | 6.97% | 12.84% | 5.87% | 19.41% | 0.0434 |
| OSR3-RET40-BP-EP-CFP | reversal_bm_ep_cfp | 5 | 31 | 0.14% | 6.68% | 11.71% | 5.03% | 16.62% | 0.0410 |
| T10-ADD-DOWNSIDE-IMPACT-20260911 | t10_size_plus_impact_downside | 10 | 15 | 19.39% | 6.60% | 10.51% | 3.91% | 25.88% | 0.0734 |
| T10-ADD-AGG-IMPACT-20260911 | t10_size_plus_impact_aggregate | 10 | 15 | 19.76% | 6.50% | 10.33% | 3.82% | 25.28% | 0.0727 |
| T10-ADD-G13-20260911 | t10_size_plus_impact_g13 | 10 | 15 | 19.62% | 6.03% | 9.86% | 3.83% | 25.34% | 0.0714 |
| T10-ADD-FSCORE-20260911 | t10_size_plus_impact_fscore | 10 | 15 | 17.48% | 5.89% | 10.41% | 4.53% | 29.94% | 0.0782 |
| T10-SIZE-PLUS-IMPACT-WC | t10_size_plus_impact_wc | 10 | 15 | 17.44% | 5.58% | 9.62% | 4.04% | 26.72% | 0.0705 |
| NONHT-FSCORELIKE-REV40 | fscore_eq | 10 | 15 | 1.82% | 5.06% | 11.59% | 6.53% | 43.19% | 0.0617 |
| T10-ADD-BM-20260911 | t10_size_plus_impact_bm | 10 | 15 | 18.09% | 4.61% | 8.90% | 4.29% | 28.37% | 0.0791 |
| NONHT-FSCORELIKE-REV40-INTERACT | fscore_interact | 10 | 15 | 1.84% | 4.30% | 10.85% | 6.55% | 43.35% | 0.0637 |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | reversal_turn_paper | 10 | 15 | 11.64% | 3.94% | 9.48% | 5.54% | 36.63% | 0.0806 |
| T10-SIZE-PLUS-IMPACT | t10_size_plus_impact | 10 | 15 | 18.16% | 3.81% | 8.13% | 4.32% | 28.54% | 0.0710 |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | reversal_chip_turn_size_eq | 10 | 16 | 10.73% | 3.80% | 8.78% | 4.98% | 32.92% | 0.0760 |
| OSR4-RET40-BP-CFP-REV2 | reversal_bm_cfp_rev2 | 5 | 31 | 2.37% | 3.61% | 12.58% | 8.97% | 29.66% | 0.0531 |
| T10-NOMCAP-PLUS-IMPACT | t10_nomcap_plus_impact | 10 | 15 | 14.23% | 3.17% | 8.07% | 4.90% | 32.38% | 0.0711 |
| paper-derived-composite | paper_composite | 5 | 31 | 11.41% | 2.97% | 4.90% | 1.93% | 6.38% | 0.0443 |
| T10-ADD-DD120-20260911 | t10_size_plus_impact_dd120 | 10 | 15 | 16.83% | 2.93% | 7.48% | 4.55% | 30.07% | 0.0618 |
| paper-derived-composite | paper_composite | 10 | 15 | 11.20% | 2.77% | 4.26% | 1.48% | 9.82% | 0.0548 |
| OSR3-RET40-BP-CFP | reversal_bm_cfp | 5 | 31 | 3.56% | 2.62% | 9.05% | 6.44% | 21.28% | 0.0434 |
| OSR4-RET40-BP-CFP-VAL2 | reversal_bm_cfp_val2 | 5 | 31 | 3.56% | 2.41% | 6.41% | 4.01% | 13.25% | 0.0369 |
| HT13-VALUE-BP | value_bm | 5 | 31 | 2.10% | 2.30% | 3.55% | 1.25% | 4.14% | 0.0368 |
| OSR4-RET40-BP-CFP-SP | reversal_bm_cfp_sp | 5 | 31 | 2.88% | 1.52% | 6.88% | 5.36% | 17.74% | 0.0427 |
| OSR4-RET40-BP-CFP-TSRANK756 | reversal_bm_cfp_tsrank756 | 5 | 31 | 2.46% | 1.39% | 9.53% | 8.14% | 26.93% | 0.0476 |
| T10-SIZE-PLUS-WC-MCAP | t10_size_plus_wc_mcap | 10 | 15 | 14.58% | 1.27% | 5.79% | 4.51% | 29.85% | 0.0643 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD | reversal_turn_paper_nomcap | 10 | 16 | 4.67% | 1.10% | 6.69% | 5.60% | 37.00% | 0.0743 |
| OSR3-RET40-BP-VAL2 | reversal_bm_val2 | 5 | 31 | 3.17% | 1.09% | 7.95% | 6.87% | 22.71% | 0.0481 |
| OSR4-RET40-BP-CFP-PCF | reversal_bm_cfp_pcf | 5 | 31 | 2.67% | 0.90% | 6.40% | 5.50% | 18.20% | 0.0417 |
| HT13-TURN-BIAS-1M-POS | turn_signal | 5 | 32 | 6.40% | 0.65% | 4.89% | 4.24% | 14.02% | 0.0519 |
| HT13-TURN-BIAS-1M | turn_bias | 5 | 32 | 6.43% | 0.64% | 4.89% | 4.24% | 14.03% | -0.0519 |
| COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | reversal_chip_turn_paper | 10 | 15 | 12.77% | 0.41% | 5.62% | 5.21% | 34.49% | 0.0688 |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | reversal_turn_paper_nomcap | 10 | 15 | 5.22% | -0.15% | 5.37% | 5.51% | 36.46% | 0.0754 |
| NONHT-RESVOL-LOW | residual_volatility | 10 | 6 | 0.37% | -0.49% | 0.47% | 0.96% | 6.34% | 0.0691 |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | reversal_chip_turn_size_eq | 10 | 15 | 16.38% | -0.73% | 4.28% | 5.01% | 33.14% | 0.0644 |
| OSR4-RET40-BP-CFP-REV3 | reversal_bm_cfp_rev3 | 5 | 31 | 1.63% | -0.78% | 9.38% | 10.16% | 33.60% | 0.0516 |
| OSR3-RET40-BP-EQ | reversal_bm_eq | 5 | 31 | 3.16% | -1.10% | 7.93% | 9.02% | 29.84% | 0.0534 |
| OSR3-RET40-BP-MA63 | reversal_bm_ma63 | 5 | 31 | 2.41% | -1.26% | 7.44% | 8.70% | 28.78% | 0.0520 |
| HT13-TURN-BIAS-1M | turn_bias | 10 | 16 | 4.96% | -1.51% | 2.26% | 3.76% | 24.89% | -0.0634 |
| HT13-VALUE-SP | value_sp | 5 | 31 | 0.11% | -2.94% | -2.14% | 0.80% | 2.64% | 0.0266 |
| OSR2-RET40-TURN-BIAS-EQ | reversal_turn_eq | 10 | 15 | 7.40% | -3.14% | 3.32% | 6.46% | 42.74% | 0.0722 |
| NEW-VALUE-EVEBITDA | ev_ebitda_proxy | 10 | 15 | 3.32% | -3.32% | -2.57% | 0.76% | 5.01% | -0.0068 |
| OSR3-RET40-BP-TSRANK756 | reversal_bm_tsrank756 | 5 | 31 | 1.64% | -3.72% | 5.67% | 9.39% | 31.05% | 0.0511 |
| OSR3-RET40-BP-REV2 | reversal_bm_rev2 | 5 | 31 | 2.48% | -3.83% | 6.66% | 10.49% | 34.69% | 0.0516 |
| OSR2-RET40 | reversal40 | 10 | 15 | 5.03% | -4.11% | 4.00% | 8.11% | 53.65% | 0.0687 |
| OSR3-RET40-BP-INTERACT | reversal_bm_interact | 5 | 31 | 2.73% | -4.67% | 5.79% | 10.46% | 34.59% | 0.0520 |
| OSR2-DD120 | drawdown120 | 5 | 31 | 4.79% | -6.40% | -0.23% | 6.16% | 20.38% | 0.0021 |
| COMBO-DIRECT-OSR2-CHIP-EQ | reversal_chip_eq | 10 | 15 | 7.88% | -6.42% | -0.03% | 6.39% | 42.28% | 0.0541 |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | reversal_chip_turn_eq | 10 | 15 | 8.66% | -6.73% | -1.18% | 5.55% | 36.72% | 0.0603 |
| HT-WREV-LOWTURN-21D | weighted_reversal_lowturn | 10 | 15 | 2.71% | -6.83% | 1.20% | 8.03% | 53.12% | 0.0780 |
| paper-derived-asset-growth | asset_growth | 5 | 31 | 0.76% | -10.59% | -9.85% | 0.74% | 2.44% | 0.0094 |
| OSR2-RET40 | reversal40 | 5 | 31 | 1.03% | -11.45% | 0.60% | 12.05% | 39.86% | 0.0398 |
| NONHT-CHIP-COST-250 | chip250 | 10 | 15 | 4.28% | -12.79% | -9.13% | 3.65% | 24.17% | 0.0275 |
| OSR2-DD120 | drawdown120 | 10 | 15 | 4.25% | -13.39% | -9.33% | 4.07% | 26.91% | 0.0063 |
| OSR2-DD60 | drawdown60 | 5 | 31 | 1.95% | -13.69% | -5.84% | 7.84% | 25.93% | 0.0084 |

## Not locally reproduced

| name | handler | cycle | platform net full window | reason |
|---|---|---:|---:|---|
| F-AP-MAIN-20260918-01 | n/a | 5 | 18.16% | book_to_market_ratio_lf is not mapped in the local financial cache |
| F-NET01-PLAT-20260915 | n/a | 5 | 5.05% | no local handler for this formula |
| F-NET03-PLAT-20260916 | n/a | 5 | 2.79% | EV/EBITDA fields are not mapped in the local financial cache |
| F-I10-01 | n/a | 10 | 21.42% | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| HT13-MOMENTUM-120D-D0 | momentum120 | 10 | 2.29% | no usable signal dates in the recent window |

## Interpretation limits

- The recent window is short and regime-sensitive; it is not a standalone factor acceptance test.
- Local values follow the canonical qfq/full-A/total_mv/label-1 contract. Proxy and alignment status remain attached to the original five-year catalog.
- A positive recent local net excess does not override a large five-year local/platform mismatch.
