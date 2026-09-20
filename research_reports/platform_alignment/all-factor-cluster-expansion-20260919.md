# All-factor cluster expansion

This is an offline expansion of the saved factor cluster analysis. It does not contact PandaAI, create factors, or run backtests.

- Existing matrix: `research_reports\platform_alignment\positive-factor-pair-correlation-20260917.json`; 65 records, 20 retained base records, 45 historical composites.
- Added scope: `95` locally supported records; `36` visible composites are annotated without creating clusters.
- New single-mechanism records eligible for clustering: `57`.
- Not assigned: `22` records (`20` without a local handler, `2` with no finite local signal).
- Window: `20210907..20260907`; warm-up `20180101`; universe `沪深全A`; qfq; `total_mv`.
- Correlation: `daily_cross_sectional_spearman_mean`; average of daily cross-sectional Spearman correlations using average ranks.
- Assignment edge: `abs(rho) >= 0.80`. Composite formulas and unusable signals never create independent clusters.

## Expanded clusters

| Cluster | Records | Negative-net members | Representative | Representative net excess | Representative RankIC |
|---|---:|---:|---|---:|---:|
| B01 | 4 | 0 | SIZE-ONLY-20260911 | 21.43% | -0.0558 |
| B02 | 3 | 0 | HT13-TURN-BIAS-1M | 6.43% | -0.0652 |
| B03 | 2 | 0 | OSR2-RET40 | 5.03% | 0.0908 |
| B04 | 2 | 0 | OSR2-DD120 | 4.79% | 0.0329 |
| B05 | 3 | 1 | NONHT-CHIP-COST-250 | 4.28% | 0.0677 |
| B06 | 1 | 0 | F-NET01-PLAT-20260914 | 13.63% | 0.0577 |
| B07 | 1 | 0 | NEW-VALUE-EVEBITDA | 3.32% | 0.0202 |
| B08 | 1 | 0 | HT13-VALUE-BP | 2.10% | 0.0524 |
| B09 | 1 | 0 | OSR2-DD60 | 1.95% | 0.0303 |
| B10 | 1 | 0 | paper-derived-asset-growth | 0.76% | -0.0115 |
| B11 | 1 | 0 | NONHT-RESVOL-LOW | 0.37% | 0.0884 |
| B12 | 1 | 0 | HT13-VALUE-SP | 0.11% | 0.0333 |
| N01 | 18 | 18 | OSR2-RET20 | -0.10% | 0.0881 |
| N02 | 2 | 2 | NEW-GROWTH-REV-TTM | -2.22% | -0.0004 |
| N03 | 1 | 1 | NEW-GROWTH-ROE-TTM | -2.43% | 0.0113 |
| N04 | 1 | 1 | NEW-HIST-ROE-6Q | -2.71% | -0.0022 |
| N05 | 1 | 1 | HT13-VALUE-EP | -3.88% | 0.0174 |
| N06 | 1 | 1 | HT13-VALUE-OCFP-LOW-PCF | -2.84% | -0.0130 |
| N07 | 1 | 1 | HT13-GROWTH-OCF | -0.60% | 0.0034 |
| N08 | 1 | 1 | HT13-TURN-STD-1M | -4.25% | -0.0671 |
| N09 | 3 | 3 | NONHT-MAX-LOW-21D | -5.91% | 0.0862 |
| N10 | 2 | 2 | REPORT-ROIC-TTM-10D-20260910 | -9.50% | -0.0062 |
| N11 | 1 | 1 | HT13-QUALITY-CASH-DEBT | -3.11% | 0.0042 |
| N12 | 1 | 1 | HT13-HIST-EP-2Q | -12.17% | 0.0211 |
| N13 | 1 | 1 | HT13-HIST-ROA-6Q | -4.74% | -0.0008 |
| N14 | 2 | 2 | HT13-ALPHA44 | -9.62% | 0.0396 |
| N15 | 1 | 1 | NONHT-MAX5-LOW-21D | -11.93% | 0.0155 |
| N16 | 1 | 1 | NONHT-SKEW-LOW-60D | -0.44% | 0.0474 |
| N17 | 1 | 1 | NONHT-CASH-CONVERSION | -0.02% | 0.0120 |
| N18 | 1 | 1 | NONHT-LOW-BETA | -15.46% | 0.0096 |
| N19 | 1 | 1 | OSR-RET5-20D | -30.17% | 0.0326 |
| N20 | 1 | 1 | OSR-DD20-20D | -12.63% | 0.0133 |
| N21 | 1 | 1 | OSR-MFI14-20D | -21.91% | 0.0318 |
| N22 | 1 | 1 | OSR2-MODERATE-BIAS5 | -22.13% | 0.0211 |
| N23 | 1 | 1 | OSR2-MODERATE-DD60 | -31.45% | -0.0077 |
| N24 | 1 | 1 | OSR2-RSI-CROSS30 | -25.60% | 0.0018 |
| N25 | 1 | 1 | OSR2-PRICE-CROSS-MA5 | -30.04% | 0.0006 |
| N26 | 1 | 1 | OSR2-SMOOTH-RSI28 | -1.86% | 0.0578 |
| N27 | 1 | 1 | paper-derived-roe | -13.30% | -0.0114 |
| N28 | 1 | 1 | paper-derived-profitability | -4.47% | 0.0287 |
| N29 | 1 | 1 | REPORT-HIST-NETMARGIN-6Q-10D-20260910 | -4.22% | 0.0056 |
| N30 | 1 | 1 | REPORT-HIST-ASSETTURN-6Q-10D-20260910 | -1.27% | 0.0053 |
| N31 | 1 | 1 | HT13-NEW-HIST-GPM-6Q | -6.81% | -0.0002 |
| N32 | 1 | 1 | HT13-NEW-ALPHA40 | -17.02% | 0.0690 |
| N33 | 2 | 2 | WF6AA4-D0-PYTHON-OBV-20260912 | -13.10% | -0.0143 |

## Remaining-factor assignments

`joined_existing_cluster` means an edge to an old base cluster at the threshold. `new_independent_cluster` means a new connected component among single-mechanism records. `composite_*` rows are attribution only. `local_signal_unavailable` rows are excluded from the graph.

| Factor | Net excess | RankIC | Composite | Assignment | High-correlation clusters | Nearest base factor | Nearest abs rho |
|---|---:|---:|:---:|---|---|---|---:|
| HT13-MOMENTUM-120D | -32.86% | -0.0562 | no | B05 (joined_existing_cluster) | B05 | HT13-MOMENTUM-120D-D0 | 1.0000 |
| DLS14-STREV-20D | -45.81% | -0.0052 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| DLS14-STREV-20D | -8.65% | 0.0624 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| F-A18 | -3.86% | 0.0674 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.7971 |
| F-A18 | -8.20% | 0.0646 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.7971 |
| HT13-REVERSAL-20D | -8.65% | 0.0624 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| HT13-REVERSAL-20D | -0.24% | 0.0867 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| OSR-MA20-20D | -14.71% | 0.0523 | no | N01 (new_independent_cluster) | N01 | OSR2-DD60 | 0.6049 |
| OSR-RET10-20D | -20.83% | 0.0453 | no | N01 (new_independent_cluster) | N01 | OSR2-DD60 | 0.5074 |
| OSR-RSI14-20D | -10.00% | 0.0565 | no | N01 (new_independent_cluster) | N01 | OSR2-DD60 | 0.6869 |
| OSR-RSI14-20D | -4.68% | 0.0664 | no | N01 (new_independent_cluster) | N01 | OSR2-DD60 | 0.6869 |
| OSR-Z20-20D | -19.49% | 0.0491 | no | N01 (new_independent_cluster) | N01 | OSR2-DD60 | 0.5298 |
| OSR2-MODERATE-RSI35 | -18.05% | 0.0389 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.5501 |
| OSR2-RET20 | -8.54% | 0.0637 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| OSR2-RET20 | -0.10% | 0.0881 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| WF6AA4-CLOSE20-MOM-20260911 | -42.83% | -0.0880 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| WF6AA4-D0-CLOSE20-MOM-20260912 | -0.10% | -0.0880 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.6084 |
| WF6AA4-D0-OPEN20-MOM-20260912 | -0.24% | -0.0843 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.5897 |
| WF6AA4-OPEN20-MOM-20260911 | -41.56% | -0.0843 | no | N01 (new_independent_cluster) | N01 | OSR2-RET40 | 0.5897 |
| HT13-GROWTH-NP | -4.44% | -0.0042 | no | N02 (new_independent_cluster) | N02 | NONHT-CHIP-COST-250 | 0.2545 |
| NEW-GROWTH-REV-TTM | -2.22% | -0.0004 | no | N02 (new_independent_cluster) | N02 | NONHT-CHIP-COST-250 | 0.2491 |
| NEW-GROWTH-ROE-TTM | -2.43% | 0.0113 | no | N03 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.1176 |
| NEW-HIST-ROE-6Q | -2.71% | -0.0022 | no | N04 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.1921 |
| HT13-VALUE-EP | -3.88% | 0.0174 | no | N05 (new_independent_cluster) | none | NEW-VALUE-EVEBITDA | 0.3903 |
| HT13-VALUE-OCFP-LOW-PCF | -2.84% | -0.0130 | no | N06 (new_independent_cluster) | none | HT13-VALUE-SP | 0.2748 |
| HT13-GROWTH-OCF | -0.60% | 0.0034 | no | N07 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.0571 |
| HT13-TURN-STD-1M | -4.25% | -0.0671 | no | N08 (new_independent_cluster) | none | HT13-TURN-BIAS-1M | 0.5456 |
| HT13-VOL-STD-1M | -8.23% | -0.0722 | no | N09 (new_independent_cluster) | N09 | NONHT-RESVOL-LOW | 0.5900 |
| NONHT-MAX-LOW-21D | -5.91% | 0.0862 | no | N09 (new_independent_cluster) | N09 | HT13-TURN-BIAS-1M | 0.4994 |
| OSR-SCALED-RET5-20D | -8.78% | 0.0767 | no | N09 (new_independent_cluster) | N09 | NONHT-RESVOL-LOW | 0.5756 |
| HT13-QUALITY-ROE | -11.21% | -0.0069 | no | N10 (new_independent_cluster) | N10 | SIZE-ONLY-20260911 | 0.3774 |
| REPORT-ROIC-TTM-10D-20260910 | -9.50% | -0.0062 | no | N10 (new_independent_cluster) | N10 | paper-derived-asset-growth | 0.3458 |
| HT13-QUALITY-CASH-DEBT | -3.11% | 0.0042 | no | N11 (new_independent_cluster) | none | SIZE-ONLY-20260911 | 0.1486 |
| HT13-HIST-EP-2Q | -12.17% | 0.0211 | no | N12 (new_independent_cluster) | none | OSR2-RET40 | 0.2022 |
| HT13-HIST-ROA-6Q | -4.74% | -0.0008 | no | N13 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.1657 |
| HT13-ALPHA44 | -18.11% | 0.0454 | no | N14 (new_independent_cluster) | N14 | OSR2-RET40 | 0.1497 |
| HT13-ALPHA44 | -9.62% | 0.0396 | no | N14 (new_independent_cluster) | N14 | OSR2-RET40 | 0.1497 |
| NONHT-MAX5-LOW-21D | -11.93% | 0.0155 | no | N15 (new_independent_cluster) | none | HT13-VALUE-BP | 0.0778 |
| NONHT-SKEW-LOW-60D | -0.44% | 0.0474 | no | N16 (new_independent_cluster) | none | HT13-TURN-BIAS-1M | 0.2253 |
| NONHT-CASH-CONVERSION | -0.02% | 0.0120 | no | N17 (new_independent_cluster) | none | NEW-VALUE-EVEBITDA | 0.3515 |
| NONHT-LOW-BETA | -15.46% | 0.0096 | no | N18 (new_independent_cluster) | none | NONHT-RESVOL-LOW | 0.4297 |
| OSR-RET5-20D | -30.17% | 0.0326 | no | N19 (new_independent_cluster) | none | OSR2-DD60 | 0.4026 |
| OSR-DD20-20D | -12.63% | 0.0133 | no | N20 (new_independent_cluster) | none | OSR2-DD60 | 0.6548 |
| OSR-MFI14-20D | -21.91% | 0.0318 | no | N21 (new_independent_cluster) | none | OSR2-DD60 | 0.4570 |
| OSR2-MODERATE-BIAS5 | -22.13% | 0.0211 | no | N22 (new_independent_cluster) | none | OSR2-DD60 | 0.2747 |
| OSR2-MODERATE-DD60 | -31.45% | -0.0077 | no | N23 (new_independent_cluster) | none | OSR2-DD60 | 0.3906 |
| OSR2-RSI-CROSS30 | -25.60% | 0.0018 | no | N24 (new_independent_cluster) | none | OSR2-RET40 | 0.0891 |
| OSR2-PRICE-CROSS-MA5 | -30.04% | 0.0006 | no | N25 (new_independent_cluster) | none | OSR2-DD60 | 0.0136 |
| OSR2-SMOOTH-RSI28 | -1.86% | 0.0578 | no | N26 (new_independent_cluster) | none | OSR2-RET40 | 0.7999 |
| paper-derived-roe | -13.30% | -0.0114 | no | N27 (new_independent_cluster) | none | paper-derived-asset-growth | 0.5136 |
| paper-derived-profitability | -4.47% | 0.0287 | no | N28 (new_independent_cluster) | none | paper-derived-asset-growth | 0.3989 |
| REPORT-HIST-NETMARGIN-6Q-10D-20260910 | -4.22% | 0.0056 | no | N29 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.2257 |
| REPORT-HIST-ASSETTURN-6Q-10D-20260910 | -1.27% | 0.0053 | no | N30 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.1343 |
| HT13-NEW-HIST-GPM-6Q | -6.81% | -0.0002 | no | N31 (new_independent_cluster) | none | NONHT-CHIP-COST-250 | 0.1249 |
| HT13-NEW-ALPHA40 | -17.02% | 0.0690 | no | N32 (new_independent_cluster) | none | F-NET01-PLAT-20260914 | 0.3517 |
| WF6AA4-D0-PYTHON-OBV-20260912 | -13.10% | -0.0143 | no | N33 (new_independent_cluster) | N33 | OSR2-DD60 | 0.3443 |
| WF6AA4-PYTHON-OBV-20260911 | -23.35% | -0.0144 | no | N33 (new_independent_cluster) | N33 | OSR2-DD60 | 0.3443 |
| DLS14-DR-BROAD-20D | -8.50% | 0.0515 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| DLS14-DR-OPCF-20D | -7.59% | 0.0510 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| DLS14-NCF-PROXY-20D | -33.70% | -0.0039 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| DLS14-NCF-PROXY-20D | -7.79% | 0.0434 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT-EXPWREV-63D | -0.97% | 0.0809 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT-WREV-21D | -8.96% | 0.0750 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT-WREV-21D | -0.81% | 0.0927 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT-WREV-LOWTURN-21D | -2.05% | 0.0817 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA13 | -20.20% | 0.0476 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA13 | -9.01% | 0.0457 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA15 | -20.22% | 0.0359 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA16 | -20.01% | 0.0480 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA3 | -18.04% | 0.0294 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA50-TP | -18.88% | 0.0388 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-ALPHA55 | -22.26% | 0.0343 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-EXPWRET-3M | -1.59% | 0.0946 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-EXPWRET-6M | -26.28% | 0.0991 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-STYLE-EQ | -5.71% | 0.0667 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-VALUE-EQ | -0.06% | 0.0428 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| HT13-WGTRET-1M | -1.00% | 0.0915 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| NONHT-LTMOM-EXHIGH-252-21 | -2.93% | 0.0213 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| NONHT-RESVOL-MAX-INTERACT-21D | -5.71% | 0.0754 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR-CAPITULATION-20D | -27.80% | 0.0025 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR-RET5-DD20-20D | -24.54% | 0.0242 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR-RET5-RSI14-20D | -21.55% | 0.0460 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR2-DD60-REC5 | -24.45% | -0.0039 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR2-MA20-REC5 | -26.98% | 0.0189 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR2-RET20-REC5 | -21.34% | 0.0256 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR2-RSI35-REC3 | -31.22% | -0.0027 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR2-RSI35-REC5 | -31.52% | -0.0029 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR3-RET40-BP-EP | -0.51% | 0.0717 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR3-RET40-BP-EP-ROE | -1.95% | 0.0543 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR3-RET40-BP-ROE | -0.61% | 0.0694 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| OSR3-RET40-EP-EQ | -1.96% | 0.0631 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| PAPER-DERIVED-COMPOSITE-NOMCAP | -0.11% | 0.0478 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| VWAP10-VOL20-MOM20-RAW | -10.06% | 0.0449 | yes | composite-only (composite_not_clustered) | none | n/a | n/a |
| F-GFN-N02-20260916 | 12.27% | 0.0363 | no | unassigned (local_signal_unavailable) | none | n/a | n/a |
| HT13-NEW-HIST-OPPROFIT-6Q | -3.76% | 0.0021 | no | unassigned (local_signal_unavailable) | none | n/a | n/a |

## Unresolved records

These records are retained in the catalog but are not forced into a cluster.

| Factor | Net excess | Status | Reason |
|---|---:|---|---|
| F-GFN-N02-20260916 | 12.27% | local_signal_unavailable | local handler returned no finite signal values in the formal window |
| HT13-NEW-HIST-OPPROFIT-6Q | -3.76% | local_signal_unavailable | local handler returned no finite signal values in the formal window |
| BASE-DIV-YIELD-TTM | -0.07% | no_local_handler | local snapshot has no complete point-in-time dividend history for dividend_yield_ttm |
| DISTRIBUTION-INTRADAY-3SIGNAL-10D | -20.85% | no_local_handler | platform intraday cal_* fields are not present in the local daily cache |
| DISTRIBUTION-RISK-10D | -5.77% | no_local_handler | platform intraday cal_* fields are not present in the local daily cache |
| DISTRIBUTION-RISK-CORE-10D | -12.00% | no_local_handler | platform intraday cal_* fields are not present in the local daily cache |
| F-A19 | -36.16% | no_local_handler | no local handler for this formula |
| F-A20 | -15.35% | no_local_handler | book_to_market_ratio_lf is not mapped in the local financial cache |
| F-ALIGN-HIGH-20260918 | -12.99% | no_local_handler | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| F-ALIGN-VWAP-20260918 | -12.86% | no_local_handler | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| F-AP-MAIN-20260918-01 | 18.16% | no_local_handler | book_to_market_ratio_lf is not mapped in the local financial cache |
| F-GFN-N01-20260916 | -8.49% | no_local_handler | HIGH/AMOUNT/VOLUME field semantics do not match the saved platform ranking; qfq high proxy is rejected |
| F-I10-01 | 21.42% | no_local_handler | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| F-NET-D02 | -24.73% | no_local_handler | insurance_commission_expense_mrq_9 needs a verified MRQ field mapping; no local equivalent |
| F-NET-D03 | -12.92% | no_local_handler | no local handler for this formula |
| F-NET01-PLAT-20260915 | 5.05% | no_local_handler | no local handler for this formula |
| F-NET03-PLAT-20260916 | 2.79% | no_local_handler | EV/EBITDA fields are not mapped in the local financial cache |
| F-QTLD60-PY-20260919-01 | 7.32% | no_local_handler | no local handler for this formula |
| F-QTLD60-PY-INDEX1-20260919-01 | -0.18% | no_local_handler | no local handler for this formula |
| GFN-UNT-20260916-EVPRICE | -25.49% | no_local_handler | EV/EBITDA fields are not mapped in the local financial cache |
| KMID2-ALPHA158-20260918 | -25.36% | no_local_handler | market formula needs high/low/amount; use the rich market cache or the explicit local proxy |
| NEW-HIST-ADJPROFIT-6Q | -3.43% | no_local_handler | local financial cache has no adjusted-profit/non-recurring-income fields |

## Artifacts

- Pair matrix: `research_reports\platform_alignment\all-factor-cluster-expansion-20260919.pairs.csv`.
- Remaining-factor assignments: `research_reports\platform_alignment\all-factor-cluster-expansion-20260919.assignments.csv`.
- Expanded cluster summary: `research_reports\platform_alignment\all-factor-cluster-expansion-20260919.clusters.csv`.
- Unresolved records: `research_reports\platform_alignment\all-factor-cluster-expansion-20260919.unresolved.csv`.
- Machine-readable report: `research_reports\platform_alignment\all-factor-cluster-expansion-20260919.json`.
- The 45 old composite annotations remain in `factor-base-clusters-20260919.md` and are not counted again.
