# Factor correlation clusters

Offline clustering of the saved formal pairwise correlation matrix. No PandaAI factor or backtest was created or run.

## Method

- Source: `positive-factor-pair-correlation-20260917.pairs.csv`.
- Records: 65; pair rows: 2,080; window: `20210907..20260907`.
- Correlation: arithmetic mean of daily cross-sectional Spearman correlations.
- Edge threshold: `abs(rho) >= 0.80`.
- Cluster rule: connected components of the high-correlation graph (single-link).
- Cluster representative: the member with the highest platform net excess; this is only a label for the cluster, not a claim that it is the best factor for a portfolio.

## Result

The 65 covered records form **13 connected clusters**. There are 6 multi-record clusters and 7 singleton clusters.

| Cluster | Records | High-rho edges | Density | Representative | Platform net excess |
|---:|---:|---:|---:|---|---:|
| C01 | 42 | 191 | 22.18% | `T10-ADD-AGG-IMPACT-20260911` | 19.76% |
| C02 | 6 | 11 | 73.33% | `VERIFY-E260910-04` | 17.76% |
| C03 | 4 | 5 | 83.33% | `SIZE-ONLY-20260911` | 21.43% |
| C04 | 2 | 1 | 100.00% | `OSR2-DD120` | 4.79% |
| C05 | 2 | 1 | 100.00% | `OSR4-RET40-BP-CFP-VAL3` | 3.31% |
| C06 | 2 | 1 | 100.00% | `NONHT-FSCORELIKE-REV40-INTERACT` | 1.84% |
| C07 | 1 | 0 | 0.00% | `F-NET01-PLAT-20260914` | 13.63% |
| C08 | 1 | 0 | 0.00% | `NEW-VALUE-EVEBITDA` | 3.32% |
| C09 | 1 | 0 | 0.00% | `OSR2-DD60` | 1.95% |
| C10 | 1 | 0 | 0.00% | `paper-derived-asset-growth` | 0.76% |
| C11 | 1 | 0 | 0.00% | `NONHT-RESVOL-LOW` | 0.37% |
| C12 | 1 | 0 | 0.00% | `OSR3-RET40-BP-EP-CFP` | 0.14% |
| C13 | 1 | 0 | 0.00% | `HT13-VALUE-SP` | 0.11% |

## Membership

### C01: large composite chain (42 records)

`T10-ADD-AGG-IMPACT-20260911`; `T10-ADD-G13-20260911`; `T10-ADD-DOWNSIDE-IMPACT-20260911`; `T10-SIZE-PLUS-IMPACT`; `T10-ADD-BM-20260911`; `T10-ADD-FSCORE-20260911`; `T10-SIZE-PLUS-IMPACT-WC`; `T10-ADD-DD120-20260911`; `COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ`; `T10-SIZE-PLUS-WC-MCAP`; `T10-NOMCAP-PLUS-IMPACT`; `COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ`; `OSR2-RET40-TURN-BIAS-PAPER-EQ`; `COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD`; `COMBO-DIRECT-OSR2-CHIP-TURN-EQ`; `COMBO-DIRECT-OSR2-CHIP-EQ`; `OSR2-RET40-TURN-BIAS-PAPER-EQ-2026-YTD`; `OSR2-RET40-TURN-BIAS-EQ`; `HT13-TURN-BIAS-1M` (2 records); `HT13-TURN-BIAS-1M-POS`; `OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ`; `OSR2-RET40` (2 records); `OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD`; `NONHT-CHIP-COST-250`; `OSR3-RET40-BP-CFP`; `OSR4-RET40-BP-CFP-VAL2`; `OSR3-RET40-BP-VAL2`; `OSR3-RET40-BP-EQ`; `OSR4-RET40-BP-CFP-SP`; `OSR3-RET40-BP-INTERACT`; `HT-WREV-LOWTURN-21D`; `OSR4-RET40-BP-CFP-PCF`; `OSR3-RET40-BP-REV2`; `OSR4-RET40-BP-CFP-TSRANK756`; `OSR3-RET40-BP-MA63`; `OSR4-RET40-BP-CFP-REV2`; `HT13-MOMENTUM-120D-D0`; `HT13-VALUE-BP`; `OSR3-RET40-BP-TSRANK756`; `OSR4-RET40-BP-CFP-REV3`.

This is a single-link chain. The low density means this cluster contains several tighter subgroups rather than 42 uniformly interchangeable signals.

### C02: value-size / value-impact / paper composite (6 records)

`VERIFY-E260910-04`; `VERIFY10-E260910-04`; `VERIFY-F260910-12`; `VERIFY10-F260910-12`; `paper-derived-composite` (2 records).

### C03: size and impact (4 records)

`SIZE-ONLY-20260911`; `H03-T10-SINGLE`; `VERIFY-G260910-13`; `VERIFY10-G260910-13`.

### C04: drawdown-120 duplicates (2 records)

`OSR2-DD120` (2 records).

### C05: CFP value variants (2 records)

`OSR4-RET40-BP-CFP-VAL3`; `OSR4-RET40-BP-CFP-MA63`.

### C06: F-score reversal variants (2 records)

`NONHT-FSCORELIKE-REV40-INTERACT`; `NONHT-FSCORELIKE-REV40`.

### C07-C13: singleton clusters

`F-NET01-PLAT-20260914`; `NEW-VALUE-EVEBITDA`; `OSR2-DD60`; `paper-derived-asset-growth`; `NONHT-RESVOL-LOW`; `OSR3-RET40-BP-EP-CFP`; `HT13-VALUE-SP`.

## Interpretation

- Under the single-link definition, the covered universe has 13 high-correlation clusters. This is a lower-bound style count because transitive high-correlation links merge a large chain into C01.
- Under a stricter complete-link cut at the same `abs(rho) >= 0.80` level, the same 65 records produce 25 tighter clusters. This is a more conservative count when every member of a cluster is expected to be mutually similar.
- Five current positive-net records are not included because their local signal reconstruction is unsupported or newer than the source matrix: `F-I10-01`, `F-AP-MAIN-20260918-01`, `F-GFN-N02-20260916`, `F-NET01-PLAT-20260915`, and `F-NET03-PLAT-20260916`.
- Therefore, 13 is the confirmed coarse cluster count for the 65 covered records. The complete current 70-record count is not yet closed until those five signals are reconstructed or their platform signal values are exported.
