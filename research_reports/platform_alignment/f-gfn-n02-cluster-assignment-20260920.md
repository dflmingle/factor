# F-GFN-N02-20260916 cluster assignment

This is an offline cluster-assignment correction for `F-GFN-N02-20260916`.
The previous all-factor expansion marked the factor as `local_signal_unavailable`.
That status was caused by the financial-cache slimming bug and is superseded by
this record.

## Result

- Factor: `F-GFN-N02-20260916`
- Formula: `BOOK_TO_MARKET_RATIO_LF / OPER_MAIN_PROFIT_TTM`
- Platform net excess: `12.274464%`
- Platform RankIC: `0.0363`
- Local net excess: `9.154100%`
- Local RankIC: `0.0347`
- Local alignment: `aligned`
- Platform signal periods: `241`
- Top20 overlap: `19/20`
- Correlation window: `20210907..20260907`
- Correlation method: daily cross-sectional Spearman, arithmetic mean over valid dates
- Assignment threshold: `abs(rho) >= 0.80`

The factor does not reach the assignment threshold against any existing base
cluster representative. Under the current expansion numbering it should form a
new independent cluster, provisionally `N34`.

It is not marked as a visible composite by the current rule: the formula is a
single value/profitability ratio, not a weighted sum of existing factor signals.
Economically, it can be described as a value-plus-operating-profitability axis,
with B08 (book-to-price) as a partial interpretation only. There is no existing
standalone profitability cluster to which it can be attributed.

## Correlations to base-cluster representatives

| Cluster | Representative | Signed rho | abs(rho) | Valid dates | Mean common stocks |
|---|---|---:|---:|---:|---:|
| B01 | `SIZE-ONLY-20260911` | -0.7249016 | 0.7249016 | 1211 | 4775.5 |
| B02 | `HT13-TURN-BIAS-1M` | -0.0493081 | 0.0493081 | 1211 | 4333.8 |
| B03 | `OSR2-RET40` | 0.0260230 | 0.0260230 | 1211 | 4772.7 |
| B04 | `OSR2-DD120` | 0.0517684 | 0.0517684 | 1211 | 4748.8 |
| B05 | `NONHT-CHIP-COST-250` | 0.1031211 | 0.1031211 | 1211 | 4646.5 |
| B06 | `F-NET01-PLAT-20260914` | 0.4716239 | 0.4716239 | 1211 | 4772.9 |
| B07 | `NEW-VALUE-EVEBITDA` | 0.1365720 | 0.1365720 | 1211 | 4775.5 |
| B08 | `HT13-VALUE-BP` | 0.2211115 | 0.2211115 | 1211 | 4775.5 |
| B09 | `OSR2-DD60` | 0.0413233 | 0.0413233 | 1211 | 4769.9 |
| B10 | `paper-derived-asset-growth` | -0.1568786 | 0.1568786 | 1211 | 4775.5 |
| B11 | `NONHT-RESVOL-LOW` | 0.0240387 | 0.0240387 | 1211 | 4333.8 |
| B12 | `HT13-VALUE-SP` | -0.1664816 | 0.1664816 | 1211 | 4775.5 |

## Interpretation

The strongest overlap is a size exposure, but `0.7249` is below the formal
`0.80` cut. It should therefore be treated as a new independent cluster with a
moderate size correlation, not as a member of the size cluster.

The calculation used the refreshed full-field financial cache and the canonical
full-A/qfq/`total_mv` alignment data. The old
`all-factor-cluster-expansion-20260919.*` files remain historical outputs from
before this factor became locally reconstructible; they are not the final
assignment for this factor.
