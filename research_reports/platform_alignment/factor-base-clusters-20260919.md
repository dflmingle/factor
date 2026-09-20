# Base factor clusters

This report removes factors that are visibly composed from multiple other factor mechanisms before clustering. Composite factors remain part of the research archive, but they do not count as independent clusters and they are not allowed to connect two base-factor nodes.

## Scope and rule

- Source matrix: `positive-factor-pair-correlation-20260917.pairs.csv`.
- Covered records: 65; current positive-net catalog: 70.
- Correlation window: `20210907..20260907`.
- Correlation: arithmetic mean of daily cross-sectional Spearman correlations.
- High-correlation edge: `abs(rho) >= 0.80`.
- Cluster rule: connected components using edges between retained base-factor records only.
- Duplicate platform runs of the same base formula are retained as records, but they do not create additional clusters.

## Composite exclusion

The following visible composite families were excluded:

- `t10_*` and `*_plus_*` multi-component size/impact formulas: 10 records.
- `reversal_chip_*`: reversal plus chip/turnover/size/value formulas: 5 records.
- `reversal_turn_*`: reversal plus turnover/value formulas: 5 records.
- `reversal_bm_*`: reversal plus book-to-market/value/cash-flow/profitability formulas: 16 records.
- `book_to_market_lf_minus_size` and `book_to_market_lf_plus_impact`: 4 records.
- `paper_composite`: 2 records.
- `fscore_eq` and `fscore_interact`: 2 records.
- `weighted_reversal_lowturn`: reversal plus turnover: 1 record.

Total excluded composites: **45 records**. Retained base/single-mechanism records: **20**.

Single-mechanism transformations such as `RANK(MARKET_CAP)`, `RANK(1-RETURNS(CLOSE,40))`, `RANK(1-CLOSE/TS_MAX(CLOSE,120))`, the chip-cost signal, the impact signal, EV/EBITDA, and residual volatility remain eligible.

## Result

The 20 retained records form **12 base-factor clusters**.

| Cluster | Records | High-rho edges | Base information axis | Representative | RankIC | Platform net excess |
|---:|---:|---:|---|---|---:|---:|
| B01 | 4 | 5 | size / impact | `SIZE-ONLY-20260911` | -0.0558 | 21.43% |
| B02 | 3 | 3 | turnover bias and inverse | `HT13-TURN-BIAS-1M` | -0.0652 | 6.43% |
| B03 | 2 | 1 | 40-day reversal | `OSR2-RET40` | 0.0908 | 5.03% |
| B04 | 2 | 1 | 120-day drawdown | `OSR2-DD120` | 0.0329 | 4.79% |
| B05 | 2 | 1 | chip cost / momentum inverse | `NONHT-CHIP-COST-250` | 0.0677 | 4.28% |
| B06 | 1 | 0 | low volume | `F-NET01-PLAT-20260914` | 0.0577 | 13.63% |
| B07 | 1 | 0 | EV/EBITDA | `NEW-VALUE-EVEBITDA` | 0.0202 | 3.32% |
| B08 | 1 | 0 | book-to-price | `HT13-VALUE-BP` | 0.0524 | 2.10% |
| B09 | 1 | 0 | 60-day drawdown | `OSR2-DD60` | 0.0303 | 1.95% |
| B10 | 1 | 0 | asset growth | `paper-derived-asset-growth` | -0.0115 | 0.76% |
| B11 | 1 | 0 | residual volatility | `NONHT-RESVOL-LOW` | 0.0884 | 0.37% |
| B12 | 1 | 0 | sales-to-price | `HT13-VALUE-SP` | 0.0333 | 0.11% |

## Membership

- B01: `SIZE-ONLY-20260911`; `H03-T10-SINGLE`; `VERIFY-G260910-13`; `VERIFY10-G260910-13`.
- B02: `HT13-TURN-BIAS-1M` (2 records); `HT13-TURN-BIAS-1M-POS`.
- B03: `OSR2-RET40` (2 records).
- B04: `OSR2-DD120` (2 records).
- B05: `NONHT-CHIP-COST-250`; `HT13-MOMENTUM-120D-D0`.
- B06: `F-NET01-PLAT-20260914`.
- B07: `NEW-VALUE-EVEBITDA`.
- B08: `HT13-VALUE-BP`.
- B09: `OSR2-DD60`.
- B10: `paper-derived-asset-growth`.
- B11: `NONHT-RESVOL-LOW`.
- B12: `HT13-VALUE-SP`.

## Composite-factor annotations

The following records are annotated with their visible base components. They are not added as new clusters. `U-*` means that the component has no standalone retained base record in this 65-record matrix, so it is shown for attribution only.

| Composite family | Records | Component clusters / unrepresented components |
|---|---|---|
| `t10_size_plus_impact`, `t10_size_plus_impact_aggregate`, `t10_size_plus_impact_downside`, `t10_size_plus_impact_g13` | 4 | B01(size+impact) + B02(turnover) + B03(reversal) + B05(chip) |
| `t10_size_plus_impact_bm` | 1 | B01 + B02 + B03 + B05 + B08(book-to-price) |
| `t10_size_plus_impact_dd120` | 1 | B01 + B02 + B03 + B04(drawdown-120) + B05 |
| `t10_size_plus_impact_fscore` | 1 | B01 + B02 + B03 + B05 + U-FSCORE/quality |
| `t10_size_plus_impact_wc`, `t10_size_plus_wc_mcap` | 2 | B01 + B02 + B03 + B05 + U-working-capital |
| `t10_nomcap_plus_impact` | 1 | B01(impact only) + B02 + B03 + B05 |
| `book_to_market_lf_minus_size` | 2 | B01(size) + B08 |
| `book_to_market_lf_plus_impact` | 2 | B01(impact) + B08 |
| `paper_composite` | 2 | B01(size) + B08 + B10(asset growth) + U-ROE/profitability |
| `fscore_eq`, `fscore_interact` | 2 | B03(reversal) + U-FSCORE/quality |
| `reversal_bm_eq`, `reversal_bm_interact`, `reversal_bm_ma63`, `reversal_bm_rev2`, `reversal_bm_tsrank756`, `reversal_bm_val2` | 6 | B03 + B08 |
| `reversal_bm_cfp`, `reversal_bm_cfp_ma63`, `reversal_bm_cfp_rev2`, `reversal_bm_cfp_rev3`, `reversal_bm_cfp_tsrank756`, `reversal_bm_cfp_val2`, `reversal_bm_cfp_val3` | 7 | B03 + B08 + U-CFP/cash-flow |
| `reversal_bm_cfp_pcf` | 1 | B03 + B08 + U-CFP + U-PCF |
| `reversal_bm_cfp_sp` | 1 | B03 + B08 + B12(sales-to-price) + U-CFP |
| `reversal_bm_ep_cfp` | 1 | B03 + B08 + U-EP + U-CFP |
| `reversal_chip_eq` | 1 | B03 + B05 |
| `reversal_chip_turn_eq` | 1 | B02 + B03 + B05 |
| `reversal_chip_turn_size_eq` | 2 | B01 + B02 + B03 + B05 |
| `reversal_chip_turn_paper` | 1 | B01 + B02 + B03 + B05 + B08 + B10 + U-ROE/profitability |
| `reversal_turn_eq` | 1 | B02 + B03 |
| `reversal_turn_paper` | 2 | B01 + B02 + B03 + B08 + B10 + U-ROE/profitability |
| `reversal_turn_paper_nomcap` | 2 | B02 + B03 + B08 + B10 + U-ROE/profitability |
| `weighted_reversal_lowturn` | 1 | B02 + B03 |

This accounts for all 45 excluded composite records. The platform net excess of these records can still be used as a performance annotation, but it must not increase the independent-cluster count.

## Current catalog gap

Five current positive-net records are not assigned because their signal values were not available in the source matrix and cannot be reconstructed under the current local handler set: `F-I10-01`, `F-AP-MAIN-20260918-01`, `F-GFN-N02-20260916`, `F-NET01-PLAT-20260915`, and `F-NET03-PLAT-20260916`.

Therefore, the confirmed count is **12 base-factor clusters among 20 retained records**. The five unresolved records may join existing clusters; they should not be counted as new independent clusters until their signals are reconstructed or exported from the platform.

## All base-family relationships above 0.60

The official cluster cut remains `abs(rho) >= 0.80`. The table below expands the review to every distinct base-factor family pair with `abs(rho) > 0.60`. Negative correlations are included because they represent the same exposure with the opposite ranking direction. Repeated runs of the same formula are collapsed; those duplicate records have `|rho| = 1.0000` and do not create another relationship.

| Base family A | Base family B | Signed rho | Official 0.80 relation | Interpretation |
|---|---|---:|---|---|
| B02 turnover bias | B02 inverse turnover signal | -1.0000 | same cluster | Same turnover mechanism, opposite sign |
| B01 pure impact | B01 absolute-return impact | +0.9656 | same cluster | Two impact implementations are almost identical |
| B05 chip cost | B05 120-day momentum inverse | -0.8377 | same cluster | Same weak-price/chip-cost direction with opposite sign |
| B01 size | B01 absolute-return impact | -0.8056 | same cluster | Size and absolute-impact exposure are strongly inverse |
| B04 120-day drawdown | B09 60-day drawdown | +0.7899 | separate at 0.80 | Same drawdown family, just below the formal cut |
| B01 pure impact | B01 size | -0.7695 | same cluster | Strong inverse size/impact relation, below 0.80 |
| B01 pure impact | B06 low volume | +0.7239 | different clusters | Low-volume signal overlaps with impact |
| B01 absolute-return impact | B06 low volume | +0.7110 | different clusters | Low-volume signal overlaps with absolute impact |
| B01 size | B06 low volume | -0.6237 | different clusters | Low-volume signal has an inverse size component |
| B09 60-day drawdown | B03 40-day reversal | +0.6362 | different clusters | Related short-/medium-term weakness |
| B04 120-day drawdown | B03 40-day reversal | +0.6025 | different clusters | Related, but weaker overlap than 60-day drawdown |

The duplicate-run relationships omitted from the table are: the two `OSR2-RET40` records, the two `OSR2-DD120` records, the two `HT13-TURN-BIAS-1M` records, and the two `impact_abs_return60` records, each at `rho = +1.0000`; `HT13-TURN-BIAS-1M` versus `HT13-TURN-BIAS-1M-POS` is `rho = -1.0000`.

## Final persisted conclusion

- Composite factors do not count as independent clusters; they are annotated by their component clusters.
- Among the 20 retained single-mechanism records, the formal `abs(rho) >= 0.80` graph produces 12 base clusters.
- `abs(rho) > 0.60` is an overlap review threshold only, not a new clustering threshold.
- B04 (120-day drawdown), B09 (60-day drawdown), and B03 (40-day reversal) remain separate under the formal cut, but should be treated as one broader price-weakness/reversal family when assessing portfolio diversification.
- The five unresolved positive-net records remain outside the count until their signal values can be reconstructed or exported from the platform.
