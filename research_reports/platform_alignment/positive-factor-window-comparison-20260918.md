# Positive-factor local window comparison

All rows are saved platform records with full-window platform net excess greater than zero.
The five-year and recent columns are local arithmetic annualized diagnostics under the same alignment contract.
The recent window is short and must not replace the formal five-year result.

- five-year window: `2021-09-07 to 2026-09-07`
- recent window: `2026-01-01 to 2026-09-07 (usable signal dates end 2026-08-27)`
- platform-positive records: `70`
- five-year local values available: `66`
- recent local values available: `65`

## Comparison

`change` is recent local net excess minus five-year local net excess, in percentage points.

| name | handler | cycle | platform net | five-year local net | recent local net | change | five-year turnover | recent turnover | five-year RankIC | recent RankIC | recent periods | full quality | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| H03-T10-SINGLE | impact60 | 10 | 16.44% | 15.34% | 16.97% | 1.64% | 8.99% | 8.91% | 0.0629 | 0.0637 | 15 | aligned | available/available |
| VERIFY10-G260910-13 | impact_abs_return60 | 10 | 13.94% | 10.39% | 14.79% | 4.40% | 9.15% | 9.49% | 0.0507 | 0.0530 | 15 | aligned | available/available |
| SIZE-ONLY-20260911 | size_only | 10 | 21.43% | 17.16% | 12.66% | -4.50% | 8.50% | 8.88% | -0.0529 | -0.0453 | 15 | aligned | available/available |
| VERIFY-G260910-13 | impact_abs_return60 | 5 | 14.70% | 9.73% | 12.66% | 2.93% | 5.38% | 5.43% | 0.0402 | 0.0465 | 31 | field_or_path_mismatch | available/available |
| VERIFY10-F260910-12 | book_to_market_lf_plus_impact | 10 | 15.05% | 12.86% | 10.18% | -2.68% | 8.96% | 9.13% | 0.0759 | 0.0718 | 15 | aligned | available/available |
| VERIFY-F260910-12 | book_to_market_lf_plus_impact | 5 | 15.59% | 12.86% | 9.89% | -2.97% | 5.75% | 5.70% | 0.0615 | 0.0558 | 31 | aligned | available/available |
| VERIFY-E260910-04 | book_to_market_lf_minus_size | 5 | 17.76% | 15.11% | 9.50% | -5.62% | 6.77% | 6.75% | 0.0654 | 0.0556 | 31 | aligned | available/available |
| VERIFY10-E260910-04 | book_to_market_lf_minus_size | 10 | 16.74% | 14.54% | 9.25% | -5.29% | 9.59% | 9.45% | 0.0791 | 0.0684 | 15 | aligned | available/available |
| F-NET01-PLAT-20260914 | wma_low_volume40 | 5 | 13.63% | 11.01% | 8.75% | -2.26% | 6.47% | 5.79% | 0.0674 | 0.0541 | 31 | field_or_path_mismatch | available/available |
| F-GFN-N02-20260916 | book_to_market_lf_div_oper_main_profit_ttm | 5 | 12.27% | 9.15% | 7.62% | -1.54% | 3.94% | 4.30% | 0.0347 | 0.0316 | 31 | aligned | available/available |
| OSR4-RET40-BP-CFP-VAL3 | reversal_bm_cfp_val3 | 5 | 3.31% | 1.83% | 7.44% | 5.60% | 11.75% | 11.57% | 0.0455 | 0.0359 | 31 | field_or_path_mismatch | available/available |
| OSR2-RET40-TURN-BIAS-PAPER-EQ-2026-YTD | reversal_turn_paper | 10 | 7.70% | 7.27% | 7.27% | 0.00% | 37.18% | 37.18% | 0.0860 | 0.0860 | 16 | field_or_path_mismatch | available/available |
| OSR4-RET40-BP-CFP-MA63 | reversal_bm_cfp_ma63 | 5 | 2.59% | 2.25% | 6.97% | 4.72% | 19.70% | 19.41% | 0.0585 | 0.0434 | 31 | field_or_path_mismatch | available/available |
| OSR3-RET40-BP-EP-CFP | reversal_bm_ep_cfp | 5 | 0.14% | -1.36% | 6.68% | 8.04% | 15.69% | 16.62% | 0.0592 | 0.0410 | 31 | field_or_path_mismatch | available/available |
| T10-ADD-DOWNSIDE-IMPACT-20260911 | t10_size_plus_impact_downside | 10 | 19.39% | 14.15% | 6.60% | -7.55% | 27.07% | 25.88% | 0.1062 | 0.0734 | 15 | field_or_path_mismatch | available/available |
| T10-ADD-AGG-IMPACT-20260911 | t10_size_plus_impact_aggregate | 10 | 19.76% | 14.23% | 6.50% | -7.72% | 26.68% | 25.28% | 0.1055 | 0.0727 | 15 | field_or_path_mismatch | available/available |
| T10-ADD-G13-20260911 | t10_size_plus_impact_g13 | 10 | 19.62% | 13.62% | 6.03% | -7.59% | 26.64% | 25.34% | 0.1041 | 0.0714 | 15 | field_or_path_mismatch | available/available |
| T10-ADD-FSCORE-20260911 | t10_size_plus_impact_fscore | 10 | 17.48% | 13.36% | 5.89% | -7.48% | 31.69% | 29.94% | 0.1112 | 0.0782 | 15 | field_or_path_mismatch | available/available |
| T10-SIZE-PLUS-IMPACT-WC | t10_size_plus_impact_wc | 10 | 17.44% | 14.34% | 5.58% | -8.76% | 27.94% | 26.72% | 0.1087 | 0.0705 | 15 | aligned | available/available |
| NONHT-FSCORELIKE-REV40 | fscore_eq | 10 | 1.82% | 0.60% | 5.06% | 4.45% | 42.22% | 43.19% | 0.0639 | 0.0617 | 15 | field_or_path_mismatch | available/available |
| T10-ADD-BM-20260911 | t10_size_plus_impact_bm | 10 | 18.09% | 13.88% | 4.61% | -9.26% | 29.63% | 28.37% | 0.1155 | 0.0791 | 15 | aligned | available/available |
| NONHT-FSCORELIKE-REV40-INTERACT | fscore_interact | 10 | 1.84% | 1.10% | 4.30% | 3.20% | 42.33% | 43.35% | 0.0693 | 0.0637 | 15 | field_or_path_mismatch | available/available |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | reversal_turn_paper | 10 | 11.64% | 8.67% | 3.94% | -4.73% | 38.06% | 36.63% | 0.1103 | 0.0806 | 15 | aligned | available/available |
| T10-SIZE-PLUS-IMPACT | t10_size_plus_impact | 10 | 18.16% | 13.15% | 3.81% | -9.33% | 30.32% | 28.54% | 0.1088 | 0.0710 | 15 | field_or_path_mismatch | available/available |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | reversal_chip_turn_size_eq | 10 | 10.73% | 3.80% | 3.80% | 0.00% | 32.92% | 32.92% | 0.0760 | 0.0760 | 16 | field_or_path_mismatch | available/available |
| OSR4-RET40-BP-CFP-REV2 | reversal_bm_cfp_rev2 | 5 | 2.37% | 0.40% | 3.61% | 3.21% | 29.60% | 29.66% | 0.0751 | 0.0531 | 31 | field_or_path_mismatch | available/available |
| T10-NOMCAP-PLUS-IMPACT | t10_nomcap_plus_impact | 10 | 14.23% | 10.91% | 3.17% | -7.74% | 34.28% | 32.38% | 0.1073 | 0.0711 | 15 | aligned | available/available |
| paper-derived-composite | paper_composite | 5 | 11.41% | 9.54% | 2.97% | -6.57% | 6.21% | 6.38% | 0.0574 | 0.0443 | 31 | aligned | available/available |
| T10-ADD-DD120-20260911 | t10_size_plus_impact_dd120 | 10 | 16.83% | 12.50% | 2.93% | -9.56% | 31.75% | 30.07% | 0.1021 | 0.0618 | 15 | aligned | available/available |
| paper-derived-composite | paper_composite | 10 | 11.20% | 9.52% | 2.77% | -6.75% | 9.29% | 9.82% | 0.0690 | 0.0548 | 15 | aligned | available/available |
| OSR3-RET40-BP-CFP | reversal_bm_cfp | 5 | 3.56% | 3.44% | 2.62% | -0.82% | 21.43% | 21.28% | 0.0645 | 0.0434 | 31 | field_or_path_mismatch | available/available |
| OSR4-RET40-BP-CFP-VAL2 | reversal_bm_cfp_val2 | 5 | 3.56% | 3.40% | 2.41% | -0.99% | 13.69% | 13.25% | 0.0535 | 0.0369 | 31 | field_or_path_mismatch | available/available |
| HT13-VALUE-BP | value_bm | 5 | 2.10% | 0.51% | 2.30% | 1.79% | 3.97% | 4.14% | 0.0506 | 0.0368 | 31 | field_or_path_mismatch | available/available |
| OSR4-RET40-BP-CFP-SP | reversal_bm_cfp_sp | 5 | 2.88% | 1.88% | 1.52% | -0.37% | 17.41% | 17.74% | 0.0615 | 0.0427 | 31 | field_or_path_mismatch | available/available |
| OSR4-RET40-BP-CFP-TSRANK756 | reversal_bm_cfp_tsrank756 | 5 | 2.46% | 0.94% | 1.39% | 0.44% | 27.03% | 26.93% | 0.0668 | 0.0476 | 31 | field_or_path_mismatch | available/available |
| T10-SIZE-PLUS-WC-MCAP | t10_size_plus_wc_mcap | 10 | 14.58% | 12.30% | 1.27% | -11.03% | 32.12% | 29.85% | 0.1052 | 0.0643 | 15 | aligned | available/available |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD | reversal_turn_paper_nomcap | 10 | 4.67% | 1.10% | 1.10% | 0.00% | 37.00% | 37.00% | 0.0743 | 0.0743 | 16 | field_or_path_mismatch | available/available |
| OSR3-RET40-BP-VAL2 | reversal_bm_val2 | 5 | 3.17% | 0.59% | 1.09% | 0.50% | 22.69% | 22.71% | 0.0705 | 0.0481 | 31 | aligned | available/available |
| OSR4-RET40-BP-CFP-PCF | reversal_bm_cfp_pcf | 5 | 2.67% | 1.34% | 0.90% | -0.44% | 18.48% | 18.20% | 0.0572 | 0.0417 | 31 | field_or_path_mismatch | available/available |
| HT13-TURN-BIAS-1M-POS | turn_signal | 5 | 6.40% | 5.16% | 0.65% | -4.51% | 15.14% | 14.02% | 0.0646 | 0.0519 | 32 | aligned | available/available |
| HT13-TURN-BIAS-1M | turn_bias | 5 | 6.43% | 5.16% | 0.64% | -4.52% | 15.14% | 14.03% | -0.0646 | -0.0519 | 32 | field_or_path_mismatch | available/available |
| COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | reversal_chip_turn_paper | 10 | 12.77% | 8.68% | 0.41% | -8.28% | 36.02% | 34.49% | 0.1078 | 0.0688 | 15 | aligned | available/available |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | reversal_turn_paper_nomcap | 10 | 5.22% | 2.92% | -0.15% | -3.07% | 37.84% | 36.46% | 0.0984 | 0.0754 | 15 | aligned | available/available |
| NONHT-RESVOL-LOW | residual_volatility | 10 | 0.37% | -0.19% | -0.49% | -0.30% | 7.67% | 6.34% | 0.0671 | 0.0691 | 6 | field_or_path_mismatch | available/available |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | reversal_chip_turn_size_eq | 10 | 16.38% | 11.17% | -0.73% | -11.89% | 35.75% | 33.14% | 0.1053 | 0.0644 | 15 | field_or_path_mismatch | available/available |
| OSR4-RET40-BP-CFP-REV3 | reversal_bm_cfp_rev3 | 5 | 1.63% | -0.47% | -0.78% | -0.31% | 33.69% | 33.60% | 0.0755 | 0.0516 | 31 | field_or_path_mismatch | available/available |
| OSR3-RET40-BP-EQ | reversal_bm_eq | 5 | 3.16% | 0.04% | -1.10% | -1.14% | 29.23% | 29.84% | 0.0786 | 0.0534 | 31 | aligned | available/available |
| OSR3-RET40-BP-MA63 | reversal_bm_ma63 | 5 | 2.41% | -0.33% | -1.26% | -0.93% | 28.38% | 28.78% | 0.0755 | 0.0520 | 31 | aligned | available/available |
| HT13-TURN-BIAS-1M | turn_bias | 10 | 4.96% | 3.92% | -1.51% | -5.42% | 26.30% | 24.89% | -0.0737 | -0.0634 | 16 | field_or_path_mismatch | available/available |
| HT13-VALUE-SP | value_sp | 5 | 0.11% | -0.37% | -2.94% | -2.57% | 2.71% | 2.64% | 0.0318 | 0.0266 | 31 | field_or_path_mismatch | available/available |
| OSR2-RET40-TURN-BIAS-EQ | reversal_turn_eq | 10 | 7.40% | 4.99% | -3.14% | -8.13% | 46.23% | 42.74% | 0.0945 | 0.0722 | 15 | aligned | available/available |
| NEW-VALUE-EVEBITDA | ev_ebitda_proxy | 10 | 3.32% | 1.44% | -3.32% | -4.76% | 5.57% | 5.01% | -0.0071 | -0.0068 | 15 | field_or_path_mismatch | available/available |
| OSR3-RET40-BP-TSRANK756 | reversal_bm_tsrank756 | 5 | 1.64% | -2.77% | -3.72% | -0.94% | 30.72% | 31.05% | 0.0736 | 0.0511 | 31 | field_or_path_mismatch | available/available |
| OSR3-RET40-BP-REV2 | reversal_bm_rev2 | 5 | 2.48% | -0.53% | -3.83% | -3.30% | 34.41% | 34.69% | 0.0783 | 0.0516 | 31 | aligned | available/available |
| OSR2-RET40 | reversal40 | 10 | 5.03% | 1.71% | -4.11% | -5.83% | 54.49% | 53.65% | 0.0853 | 0.0687 | 15 | aligned | available/available |
| OSR3-RET40-BP-INTERACT | reversal_bm_interact | 5 | 2.73% | -0.72% | -4.67% | -3.95% | 34.24% | 34.59% | 0.0792 | 0.0520 | 31 | aligned | available/available |
| OSR2-DD120 | drawdown120 | 5 | 4.79% | 2.50% | -6.40% | -8.89% | 18.68% | 20.38% | 0.0270 | 0.0021 | 31 | aligned | available/available |
| COMBO-DIRECT-OSR2-CHIP-EQ | reversal_chip_eq | 10 | 7.88% | 3.58% | -6.42% | -10.00% | 41.65% | 42.28% | 0.0870 | 0.0541 | 15 | aligned | available/available |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | reversal_chip_turn_eq | 10 | 8.66% | 6.13% | -6.73% | -12.86% | 39.36% | 36.72% | 0.0953 | 0.0603 | 15 | aligned | available/available |
| HT-WREV-LOWTURN-21D | weighted_reversal_lowturn | 10 | 2.71% | 3.32% | -6.83% | -10.15% | 55.48% | 53.12% | 0.0984 | 0.0780 | 15 | aligned | available/available |
| paper-derived-asset-growth | asset_growth | 5 | 0.76% | -2.35% | -10.59% | -8.24% | 1.86% | 2.44% | -0.0097 | 0.0094 | 31 | aligned | available/available |
| OSR2-RET40 | reversal40 | 5 | 1.03% | -3.09% | -11.45% | -8.36% | 39.58% | 39.86% | 0.0681 | 0.0398 | 31 | aligned | available/available |
| NONHT-CHIP-COST-250 | chip250 | 10 | 4.28% | 2.63% | -12.79% | -15.42% | 23.74% | 24.17% | 0.0732 | 0.0275 | 15 | aligned | available/available |
| OSR2-DD120 | drawdown120 | 10 | 4.25% | 1.81% | -13.39% | -15.20% | 27.06% | 26.91% | 0.0347 | 0.0063 | 15 | aligned | available/available |
| OSR2-DD60 | drawdown60 | 5 | 1.95% | -2.35% | -13.69% | -11.34% | 25.61% | 25.93% | 0.0246 | 0.0084 | 31 | aligned | available/available |
| F-AP-MAIN-20260918-01 | n/a | 5 | 18.16% | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | missing/no_recent_window |
| F-I10-01 | n/a | 10 | 21.42% | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | missing/no_recent_window |
| F-NET01-PLAT-20260915 | n/a | 5 | 5.05% | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | missing/no_recent_window |
| F-NET03-PLAT-20260916 | n/a | 5 | 2.79% | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | missing/no_recent_window |
| HT13-MOMENTUM-120D-D0 | momentum120 | 10 | 2.29% | 0.42% | n/a | n/a | 35.15% | n/a | -0.0679 | n/a | n/a | field_or_path_mismatch | available/no_recent_window |

## Missing recent values

| name | platform net | reason |
|---|---:|---|
| F-AP-MAIN-20260918-01 | 18.16% | book_to_market_ratio_lf is not mapped in the local financial cache |
| F-I10-01 | 21.42% | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| F-NET01-PLAT-20260915 | 5.05% | no local handler for this formula |
| F-NET03-PLAT-20260916 | 2.79% | EV/EBITDA fields are not mapped in the local financial cache |
| HT13-MOMENTUM-120D-D0 | 2.29% | no usable signal dates in the recent window |

## Reading notes

- `platform net` is the saved platform full-window screening value, not a 2026 recent platform result.
- Five-day and ten-day records remain separate; rows with the same factor name but different cycles are not merged.
- Proxy and alignment quality are inherited from the canonical five-year report. A strong recent number does not repair a five-year `field_or_path_mismatch`.
