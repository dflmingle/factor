# Exhaustive representative combination search

Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`.

This is an offline local proxy. It did not create factors, spend PandaAI compute, or claim an official pool score.

## Scope and method

- Candidates: `12` explicit single-mechanism representatives.
- Non-empty subsets evaluated: `4095` (`2^12-1`).
- Common local cycle: `10` trading days; signal dates: `120`.
- Formal window: `2021-09-07` to `2026-09-07`; recent diagnostic: `2026-01-01` onward.
- Warm-up: `2018-01-01`; universe: full A `.SH/.SZ`; price: qfq; cap: `total_mv`.
- Label: `close(t+1) -> close(t+1+cycle)`; groups: `10`; one-way cost: `0.30%`.
- Each input is direction-aligned, converted to a daily cross-sectional percentile rank, and combined with equal weights.
- Net excess is arithmetic annualized gross excess minus annualized cost from the combination's actual held-group turnover.
- Training ends at `2024-09-06`; validation is the later formal period and is diagnostic only.

The saved platform source cycle is shown below. A few representatives only have a saved five-day source record; their formula signal is evaluated at the common ten-day schedule for this comparison. That makes the local portfolios comparable, but it does not turn their saved five-day platform result into a ten-day platform result.

## Candidate inputs

| key | cluster | handler | dir | source cycle | platform net | alignment | source name |
|---|---|---|---:|---:|---:|---|---|
| `SIZE` | B01 | `size_only` | 0 | 10 | 21.43% | aligned | SIZE-ONLY-20260911 |
| `H03` | B01 | `impact60` | 1 | 10 | 16.44% | aligned | H03-T10-SINGLE |
| `TURN` | B02 | `turn_bias` | 0 | 10 | 4.96% | field_or_path_mismatch | HT13-TURN-BIAS-1M |
| `RET40` | B03 | `reversal40` | 1 | 10 | 5.03% | aligned | OSR2-RET40 |
| `DD120` | B04 | `drawdown120` | 1 | 10 | 4.25% | aligned | OSR2-DD120 |
| `CHIP250` | B05 | `chip250` | 1 | 10 | 4.28% | aligned | NONHT-CHIP-COST-250 |
| `EVEBITDA` | B07 | `ev_ebitda_proxy` | 1 | 10 | 3.32% | field_or_path_mismatch | NEW-VALUE-EVEBITDA |
| `BM` | B08 | `value_bm` | 1 | 5 | 2.10% | field_or_path_mismatch | HT13-VALUE-BP |
| `DD60` | B09 | `drawdown60` | 1 | 5 | 1.95% | aligned | OSR2-DD60 |
| `ASSET_GROWTH` | B10 | `asset_growth` | 0 | 5 | 0.76% | aligned | paper-derived-asset-growth |
| `RESVOL` | B11 | `residual_volatility` | 1 | 10 | 0.37% | field_or_path_mismatch | NONHT-RESVOL-LOW |
| `SP` | B12 | `value_sp` | 1 | 5 | 0.11% | field_or_path_mismatch | HT13-VALUE-SP |

## Correlation and clusters

Direction-aligned daily cross-sectional Spearman correlations at or above 0.60:

| factor A | factor B | rho | days |
|---|---|---:|---:|
| `DD120` | `DD60` | 0.7892 | 120 |
| `SIZE` | `H03` | 0.7509 | 120 |
| `RET40` | `DD60` | 0.6317 | 120 |
| `RET40` | `DD120` | 0.6003 | 120 |

Connected components at abs(rho) >= 0.80:

| local cluster | members |
|---|---|
| C01 | `SIZE` |
| C02 | `H03` |
| C03 | `TURN` |
| C04 | `RET40` |
| C05 | `DD120` |
| C06 | `CHIP250` |
| C07 | `EVEBITDA` |
| C08 | `BM` |
| C09 | `DD60` |
| C10 | `ASSET_GROWTH` |
| C11 | `RESVOL` |
| C12 | `SP` |

## Best result by factor count

The `all` columns include highly correlated additions. The `<0.80` columns require every pair in the subset to have abs(rho) below 0.80.

| count | all train | all valid | all full | all recent | <0.80 train | <0.80 valid |
|---:|---|---|---|---|---|---|
| 1 | SIZE (17.27%) | H03 (17.38%) | SIZE (17.13%) | H03 (15.87%) | SIZE (17.27%) | H03 (17.38%) |
| 2 | SIZE+RESVOL (19.56%) | SIZE+H03 (18.73%) | SIZE+H03 (18.61%) | H03+EVEBITDA (16.55%) | SIZE+RESVOL (19.56%) | SIZE+H03 (18.73%) |
| 3 | SIZE+H03+RESVOL (21.28%) | SIZE+H03+RET40 (17.70%) | SIZE+H03+RESVOL (18.31%) | SIZE+H03+EVEBITDA (15.40%) | SIZE+H03+RESVOL (21.28%) | SIZE+H03+RET40 (17.70%) |
| 4 | SIZE+H03+RESVOL+SP (21.07%) | SIZE+H03+EVEBITDA+RESVOL (18.23%) | SIZE+H03+EVEBITDA+RESVOL (18.13%) | SIZE+H03+EVEBITDA+RESVOL (17.97%) | SIZE+H03+RESVOL+SP (21.07%) | SIZE+H03+EVEBITDA+RESVOL (18.23%) |
| 5 | SIZE+H03+DD120+RESVOL+SP (20.57%) | SIZE+H03+TURN+RET40+EVEBITDA (17.56%) | SIZE+H03+DD120+RESVOL+SP (16.43%) | SIZE+H03+EVEBITDA+ASSET_GROWTH+RESVOL (16.75%) | SIZE+H03+DD120+RESVOL+SP (20.57%) | SIZE+H03+TURN+RET40+EVEBITDA (17.56%) |
| 6 | SIZE+H03+DD120+BM+RESVOL+SP (19.62%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA (17.06%) | SIZE+H03+CHIP250+EVEBITDA+BM+RESVOL (15.56%) | SIZE+H03+EVEBITDA+BM+DD60+RESVOL (14.05%) | SIZE+H03+DD120+BM+RESVOL+SP (19.62%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA (17.06%) |
| 7 | SIZE+H03+TURN+BM+ASSET_GROWTH+RESVOL+SP (17.02%) | SIZE+H03+TURN+RET40+EVEBITDA+ASSET_GROWTH+SP (15.96%) | SIZE+H03+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL+SP (14.64%) | SIZE+H03+RET40+EVEBITDA+DD60+ASSET_GROWTH+RESVOL (11.70%) | SIZE+H03+TURN+BM+ASSET_GROWTH+RESVOL+SP (17.02%) | SIZE+H03+TURN+RET40+EVEBITDA+ASSET_GROWTH+SP (15.96%) |
| 8 | SIZE+H03+TURN+DD120+BM+ASSET_GROWTH+RESVOL+SP (16.11%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+SP (15.15%) | SIZE+H03+TURN+EVEBITDA+DD60+ASSET_GROWTH+RESVOL+SP (14.13%) | SIZE+H03+RET40+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (11.49%) | SIZE+H03+TURN+DD120+BM+ASSET_GROWTH+RESVOL+SP (16.11%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+SP (15.15%) |
| 9 | SIZE+H03+TURN+DD120+CHIP250+BM+ASSET_GROWTH+RESVOL+SP (14.80%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL (14.64%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL+SP (13.24%) | SIZE+H03+TURN+RET40+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (10.15%) | SIZE+H03+TURN+DD120+CHIP250+BM+ASSET_GROWTH+RESVOL+SP (14.80%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL (14.64%) |
| 10 | SIZE+H03+TURN+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (13.66%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL+SP (12.90%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (12.04%) | SIZE+H03+TURN+RET40+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (6.49%) | SIZE+H03+TURN+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (13.66%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL+SP (12.90%) |
| 11 | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (13.28%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL+SP (12.28%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (11.95%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (5.39%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (13.28%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL+SP (12.28%) |
| 12 | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (10.20%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (10.59%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (10.35%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (2.58%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (10.20%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (10.59%) |

## Top combinations selected on training

| rank | count | components | max abs rho | train net | validation net | full net | recent net | full turnover | full max DD | full RankIC |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | `SIZE+H03+RESVOL` | 0.7509 | 21.28% | 13.70% | 18.31% | 14.49% | 8.12% | 29.07% | 0.0871 |
| 2 | 4 | `SIZE+H03+RESVOL+SP` | 0.7509 | 21.07% | 10.60% | 16.97% | 10.38% | 8.39% | 26.41% | 0.0897 |
| 3 | 5 | `SIZE+H03+DD120+RESVOL+SP` | 0.7509 | 20.57% | 10.00% | 16.43% | 7.39% | 19.44% | 26.01% | 0.1005 |
| 4 | 5 | `SIZE+H03+CHIP250+RESVOL+SP` | 0.7509 | 20.18% | 10.47% | 16.38% | 8.91% | 15.90% | 25.53% | 0.1036 |
| 5 | 3 | `SIZE+H03+SP` | 0.7509 | 19.90% | 14.38% | 17.74% | 10.02% | 8.54% | 28.72% | 0.0736 |
| 6 | 5 | `SIZE+H03+ASSET_GROWTH+RESVOL+SP` | 0.7509 | 19.74% | 10.51% | 16.13% | 9.12% | 8.66% | 27.54% | 0.0828 |
| 7 | 6 | `SIZE+H03+DD120+BM+RESVOL+SP` | 0.7509 | 19.62% | 8.26% | 15.17% | 7.48% | 17.89% | 23.02% | 0.1003 |
| 8 | 5 | `SIZE+H03+BM+RESVOL+SP` | 0.7509 | 19.61% | 7.42% | 14.84% | 8.75% | 8.22% | 24.91% | 0.0906 |
| 9 | 2 | `SIZE+RESVOL` | 0.0697 | 19.56% | 11.25% | 16.30% | 11.07% | 8.03% | 28.89% | 0.0899 |
| 10 | 4 | `SIZE+H03+BM+RESVOL` | 0.7509 | 19.21% | 11.63% | 16.24% | 13.16% | 8.26% | 26.34% | 0.0934 |
| 11 | 4 | `SIZE+H03+BM+SP` | 0.7509 | 19.05% | 9.72% | 15.40% | 7.72% | 8.79% | 25.54% | 0.0820 |
| 12 | 5 | `SIZE+H03+DD120+BM+RESVOL` | 0.7509 | 19.00% | 11.68% | 16.13% | 9.41% | 19.20% | 26.46% | 0.1044 |
| 13 | 4 | `SIZE+H03+CHIP250+RESVOL` | 0.7509 | 18.99% | 13.07% | 16.67% | 8.63% | 16.09% | 28.74% | 0.1036 |
| 14 | 6 | `SIZE+H03+CHIP250+BM+RESVOL+SP` | 0.7509 | 18.91% | 6.72% | 14.14% | 4.58% | 14.72% | 23.44% | 0.1021 |
| 15 | 2 | `H03+RESVOL` | 0.1506 | 18.82% | 7.39% | 14.34% | 12.41% | 9.19% | 23.58% | 0.0896 |
| 16 | 3 | `SIZE+H03+BM` | 0.7509 | 18.67% | 14.56% | 17.06% | 11.95% | 9.11% | 28.96% | 0.0794 |
| 17 | 5 | `SIZE+H03+CHIP250+BM+RESVOL` | 0.7509 | 18.56% | 10.15% | 15.27% | 9.27% | 15.60% | 27.04% | 0.1062 |
| 18 | 2 | `SIZE+H03` | 0.7509 | 18.52% | 18.73% | 18.61% | 16.02% | 8.23% | 30.88% | 0.0613 |
| 19 | 5 | `SIZE+H03+TURN+RESVOL+SP` | 0.7509 | 18.51% | 9.50% | 14.98% | 8.02% | 16.18% | 25.00% | 0.1045 |
| 20 | 6 | `SIZE+H03+BM+ASSET_GROWTH+RESVOL+SP` | 0.7509 | 18.50% | 6.96% | 13.98% | 5.78% | 8.59% | 25.87% | 0.0860 |
| 21 | 5 | `SIZE+H03+EVEBITDA+RESVOL+SP` | 0.7509 | 18.47% | 13.17% | 16.39% | 12.42% | 9.01% | 28.89% | 0.0818 |
| 22 | 4 | `SIZE+H03+ASSET_GROWTH+RESVOL` | 0.7509 | 18.45% | 14.13% | 16.76% | 12.80% | 8.41% | 30.67% | 0.0777 |
| 23 | 5 | `SIZE+H03+BM+ASSET_GROWTH+RESVOL` | 0.7509 | 18.45% | 11.18% | 15.60% | 11.61% | 8.73% | 28.94% | 0.0860 |
| 24 | 4 | `SIZE+H03+TURN+RESVOL` | 0.7509 | 18.35% | 12.52% | 16.07% | 11.28% | 16.75% | 26.72% | 0.1031 |
| 25 | 3 | `H03+CHIP250+RESVOL` | 0.1506 | 18.31% | 6.66% | 13.74% | 7.66% | 17.99% | 22.93% | 0.1067 |

## Key diagnostics

- Best training-period combination: `SIZE+H03+RESVOL`; count `3`; train/validation/full/recent net = `21.28%` / `13.70%` / `18.31%` / `14.49%`; max abs rho `0.7509`.
- Best validation-period combination (diagnostic ranking): `SIZE+H03`; count `2`; train/validation/full/recent net = `18.52%` / `18.73%` / `18.61%` / `16.02%`; max abs rho `0.7509`.
- Best full-period combination (descriptive ranking): `SIZE+H03`; count `2`; train/validation/full/recent net = `18.52%` / `18.73%` / `18.61%` / `16.02%`; max abs rho `0.7509`.
- Best recent-period combination (diagnostic ranking): `SIZE+H03+EVEBITDA+RESVOL`; count `4`; train/validation/full/recent net = `18.06%` / `18.23%` / `18.13%` / `17.97%`; max abs rho `0.7509`.
- Exact requested C1-style subset `SIZE+TURN+RET40+DD120+CHIP250`: train/validation/full/recent net = `7.97%` / `11.52%` / `9.36%` / `-1.28%`; full turnover `36.04%`, full max drawdown `32.49%`.
- Same-cluster check `SIZE+H03`: train/validation/full/recent net = `18.52%` / `18.73%` / `18.61%` / `16.02%`; max abs rho `0.7509`.

## Interpretation boundary

- Training ranking is the only ranking used for a prospective selection. Validation and recent winners were selected after seeing those periods and are diagnostics, not unbiased out-of-sample choices.
- A low correlation only means different signal exposure. It does not prove independent alpha or remove the common small-cap/market-regime exposure.
- The combination is an equal-weight local portfolio proxy. PandaAI's official pool treatment and C score are not reproduced by averaging single-factor platform headlines.
- EV/EBITDA and residual-volatility inputs are retained because they were in the requested representative set, but their saved alignment quality is marked as a field/path proxy issue. Results involving them need separate confirmation before platform submission.

## Artifacts

- All 4095 combinations: `research_reports\platform_alignment\exhaustive-representative-combination-20260920-v2\all_combinations.csv`
- Selected combinations with exact RankIC/IC: `research_reports\platform_alignment\exhaustive-representative-combination-20260920-v2\selected_combinations.csv`
- Per-period holdings diagnostics for selected combinations: `research_reports\platform_alignment\exhaustive-representative-combination-20260920-v2\selected_periods.csv`
- Machine-readable payload: `research_reports\platform_alignment\exhaustive-representative-combination-20260920-v2\report.json`
