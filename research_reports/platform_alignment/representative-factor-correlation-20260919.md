# Representative factor correlation screen

Offline derivation from the existing formal pairwise correlation matrix. No PandaAI factor or backtest was created or run.

- Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1`.
- Window: `20210907..20260907`; method: `daily_cross_sectional_spearman_mean`.
- Existing matrix: `65` records and `2080` pair rows; current positive catalog: `70` records.
- Representatives: `13`; remaining matrix records compared to every representative: `52`.
- Duplicate-exposure threshold: `|rho| >= 0.80`.

## Representatives

| Rank | Factor | Mechanism | Handler | Platform net excess | Platform RankIC |
|---:|---|---|---|---:|---:|
| 1 | SIZE-ONLY-20260911 | size | `size_only` | 21.43% | -0.0558 |
| 2 | T10-ADD-AGG-IMPACT-20260911 | size_plus_impact | `t10_size_plus_impact_aggregate` | 19.76% | 0.1057 |
| 3 | VERIFY-E260910-04 | value_minus_size | `book_to_market_lf_minus_size` | 17.76% | 0.0681 |
| 4 | H03-T10-SINGLE | pure_impact | `impact60` | 16.44% | 0.0665 |
| 5 | F-NET01-PLAT-20260914 | low_volume | `wma_low_volume40` | 13.63% | 0.0577 |
| 6 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | reversal_chip_turn_value_composite | `reversal_chip_turn_paper` | 12.77% | 0.115 |
| 7 | HT13-TURN-BIAS-1M | turnover_bias | `turn_bias` | 6.43% | -0.0652 |
| 8 | OSR2-RET40 | reversal | `reversal40` | 5.03% | 0.0908 |
| 9 | OSR2-DD120 | drawdown | `drawdown120` | 4.79% | 0.0329 |
| 10 | NONHT-CHIP-COST-250 | chip_cost | `chip250` | 4.28% | 0.0677 |
| 11 | OSR3-RET40-BP-CFP | value_cfp | `reversal_bm_cfp` | 3.56% | 0.067 |
| 12 | NEW-VALUE-EVEBITDA | ev_value | `ev_ebitda_proxy` | 3.32% | 0.0202 |
| 13 | NONHT-RESVOL-LOW | residual_volatility | `residual_volatility` | 0.37% | 0.0884 |

## Remaining factors

| Factor | Platform net excess | Max abs rho to reps | Nearest representative | Rho | Any abs rho >= 0.80 |
|---|---:|---:|---|---:|:---:|
| T10-ADD-G13-20260911 | 19.62% | 0.9987 | T10-ADD-AGG-IMPACT-20260911 | +0.9987 | yes |
| T10-ADD-DOWNSIDE-IMPACT-20260911 | 19.39% | 0.9994 | T10-ADD-AGG-IMPACT-20260911 | +0.9994 | yes |
| T10-SIZE-PLUS-IMPACT | 18.16% | 0.9786 | T10-ADD-AGG-IMPACT-20260911 | +0.9786 | yes |
| T10-ADD-BM-20260911 | 18.09% | 0.9364 | T10-ADD-AGG-IMPACT-20260911 | +0.9364 | yes |
| T10-ADD-FSCORE-20260911 | 17.48% | 0.9293 | T10-ADD-AGG-IMPACT-20260911 | +0.9293 | yes |
| T10-SIZE-PLUS-IMPACT-WC | 17.44% | 0.9393 | T10-ADD-AGG-IMPACT-20260911 | +0.9393 | yes |
| T10-ADD-DD120-20260911 | 16.83% | 0.9220 | T10-ADD-AGG-IMPACT-20260911 | +0.9220 | yes |
| VERIFY10-E260910-04 | 16.74% | 1.0000 | VERIFY-E260910-04 | +1.0000 | yes |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | 16.38% | 0.9350 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9350 | yes |
| VERIFY-F260910-12 | 15.59% | 0.9008 | VERIFY-E260910-04 | +0.9008 | yes |
| VERIFY10-F260910-12 | 15.05% | 0.9008 | VERIFY-E260910-04 | +0.9008 | yes |
| VERIFY-G260910-13 | 14.70% | 0.9656 | H03-T10-SINGLE | +0.9656 | yes |
| T10-SIZE-PLUS-WC-MCAP | 14.58% | 0.8944 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8944 | yes |
| T10-NOMCAP-PLUS-IMPACT | 14.23% | 0.9286 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9286 | yes |
| VERIFY10-G260910-13 | 13.94% | 0.9656 | H03-T10-SINGLE | +0.9656 | yes |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | 11.64% | 0.9465 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9465 | yes |
| paper-derived-composite | 11.41% | 0.8167 | VERIFY-E260910-04 | +0.8167 | yes |
| paper-derived-composite | 11.20% | 0.8167 | VERIFY-E260910-04 | +0.8167 | yes |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | 10.73% | 0.9350 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9350 | yes |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | 8.66% | 0.9281 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9281 | yes |
| COMBO-DIRECT-OSR2-CHIP-EQ | 7.88% | 0.8874 | NONHT-CHIP-COST-250 | +0.8874 | yes |
| OSR2-RET40-TURN-BIAS-PAPER-EQ-2026-YTD | 7.70% | 0.9465 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.9465 | yes |
| OSR2-RET40-TURN-BIAS-EQ | 7.40% | 0.8565 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8565 | yes |
| HT13-TURN-BIAS-1M-POS | 6.40% | 1.0000 | HT13-TURN-BIAS-1M | -1.0000 | yes |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | 5.22% | 0.8975 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8975 | yes |
| HT13-TURN-BIAS-1M | 4.96% | 1.0000 | HT13-TURN-BIAS-1M | +1.0000 | yes |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD | 4.67% | 0.8975 | COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | +0.8975 | yes |
| OSR2-DD120 | 4.25% | 1.0000 | OSR2-DD120 | +1.0000 | yes |
| OSR4-RET40-BP-CFP-VAL2 | 3.56% | 0.9614 | OSR3-RET40-BP-CFP | +0.9614 | yes |
| OSR4-RET40-BP-CFP-VAL3 | 3.31% | 0.4776 | OSR3-RET40-BP-CFP | +0.4776 | no |
| OSR3-RET40-BP-VAL2 | 3.17% | 0.7699 | OSR3-RET40-BP-CFP | +0.7699 | no |
| OSR3-RET40-BP-EQ | 3.16% | 0.8137 | OSR3-RET40-BP-CFP | +0.8137 | yes |
| OSR4-RET40-BP-CFP-SP | 2.88% | 0.9068 | OSR3-RET40-BP-CFP | +0.9068 | yes |
| OSR3-RET40-BP-INTERACT | 2.73% | 0.9429 | OSR2-RET40 | +0.9429 | yes |
| HT-WREV-LOWTURN-21D | 2.71% | 0.7996 | HT13-TURN-BIAS-1M | -0.7996 | no |
| OSR4-RET40-BP-CFP-PCF | 2.67% | 0.8791 | OSR3-RET40-BP-CFP | +0.8791 | yes |
| OSR4-RET40-BP-CFP-MA63 | 2.59% | 0.6450 | OSR3-RET40-BP-CFP | +0.6450 | no |
| OSR3-RET40-BP-REV2 | 2.48% | 0.9078 | OSR2-RET40 | +0.9078 | yes |
| OSR4-RET40-BP-CFP-TSRANK756 | 2.46% | 0.6883 | OSR2-RET40 | +0.6883 | no |
| OSR3-RET40-BP-MA63 | 2.41% | 0.8048 | OSR3-RET40-BP-CFP | +0.8048 | yes |
| OSR4-RET40-BP-CFP-REV2 | 2.37% | 0.8094 | OSR2-RET40 | +0.8094 | yes |
| HT13-MOMENTUM-120D-D0 | 2.29% | 0.8377 | NONHT-CHIP-COST-250 | -0.8377 | yes |
| HT13-VALUE-BP | 2.10% | 0.7158 | VERIFY-E260910-04 | +0.7158 | no |
| OSR2-DD60 | 1.95% | 0.7899 | OSR2-DD120 | +0.7899 | no |
| NONHT-FSCORELIKE-REV40-INTERACT | 1.84% | 0.6506 | OSR2-RET40 | +0.6506 | no |
| NONHT-FSCORELIKE-REV40 | 1.82% | 0.6887 | OSR2-RET40 | +0.6887 | no |
| OSR3-RET40-BP-TSRANK756 | 1.64% | 0.8123 | OSR2-RET40 | +0.8123 | yes |
| OSR4-RET40-BP-CFP-REV3 | 1.63% | 0.9033 | OSR2-RET40 | +0.9033 | yes |
| OSR2-RET40 | 1.03% | 1.0000 | OSR2-RET40 | +1.0000 | yes |
| paper-derived-asset-growth | 0.76% | 0.2789 | F-NET01-PLAT-20260914 | -0.2789 | no |
| OSR3-RET40-BP-EP-CFP | 0.14% | 0.6807 | OSR3-RET40-BP-CFP | +0.6807 | no |
| HT13-VALUE-SP | 0.11% | 0.3650 | VERIFY-E260910-04 | +0.3650 | no |

## Positive records not covered

| Factor | Platform net excess | Status | Reason |
|---|---:|---|---|
| F-I10-01 | 21.42% | unsupported_local_handler | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| F-AP-MAIN-20260918-01 | 18.16% | unsupported_local_handler | book_to_market_ratio_lf is not mapped in the local financial cache |
| F-GFN-N02-20260916 | 12.27% | supported_but_not_in_existing_matrix | new positive record was not present when the source matrix was generated |
| F-NET01-PLAT-20260915 | 5.05% | unsupported_local_handler | no local handler for this formula |
| F-NET03-PLAT-20260916 | 2.79% | unsupported_local_handler | EV/EBITDA fields are not mapped in the local financial cache |

The remaining-pairs CSV contains every remaining matrix factor against every representative. The representative-pairs CSV is included to check whether the selected representatives themselves overlap.

## Full-matrix de-duplication check

The representative screen is a first-pass filter only. The original 65-record matrix was also checked directly so that two non-representative factors cannot both appear independent merely because neither was selected as a representative.

- Of the 52 remaining records, 12 have `max abs rho < 0.80` against the 13 representatives.
- After checking all 2,080 original pairs, only 4 remaining records have no `|rho| >= 0.80` neighbor anywhere in the 65-record matrix.
- The other 8 are low versus the representative set but duplicate another non-representative cluster.

| Factor | Platform net excess | RankIC | Max abs rho in full 65-record matrix | Nearest factor |
|---|---:|---:|---:|---|
| OSR2-DD60 | 1.95% | 0.0303 | 0.7899 | OSR2-DD120 |
| paper-derived-asset-growth | 0.76% | -0.0115 | 0.4775 | paper-derived-composite |
| OSR3-RET40-BP-EP-CFP | 0.14% | 0.0605 | 0.7804 | OSR3-RET40-BP-VAL2 |
| HT13-VALUE-SP | 0.11% | 0.0333 | 0.7030 | OSR4-RET40-BP-CFP-SP |
