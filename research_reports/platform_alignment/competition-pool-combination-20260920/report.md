# Exhaustive representative combination search

Alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`.

This is an offline local proxy. It did not create factors, spend PandaAI compute, or claim an official pool score.

## Scope and method

- Candidates: `12` explicit single-mechanism representatives.
- Non-empty subsets evaluated: `4095` (`2^12-1`); reported pool size is `>= 5` with `3302` combinations.
- Common local cycle: `10` trading days; signal dates: `120`.
- Formal window: `2021-09-07` to `2026-09-07`; recent diagnostic: `2026-01-01` onward.
- Warm-up: `2018-01-01`; universe: full A `.SH/.SZ`; price: qfq; cap: `total_mv`.
- Label: `close(t+1) -> close(t+1+cycle)`; groups: `10`; one-way cost: `0.30%`.
- Each component is direction-aligned, Winsorized at the daily 1st/99th percentiles, Z-scored, and then equal-weighted. The implementation uses population standard deviation and excludes stocks missing a selected component as a local proxy.
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
| 5 | SIZE+H03+TURN+CHIP250+RESVOL (19.13%) | SIZE+H03+TURN+RET40+EVEBITDA (17.65%) | SIZE+H03+TURN+EVEBITDA+RESVOL (16.82%) | SIZE+H03+EVEBITDA+ASSET_GROWTH+RESVOL (16.82%) | SIZE+H03+TURN+CHIP250+RESVOL (19.13%) | SIZE+H03+TURN+RET40+EVEBITDA (17.65%) |
| 6 | SIZE+H03+TURN+CHIP250+BM+RESVOL (17.20%) | SIZE+H03+TURN+RET40+EVEBITDA+ASSET_GROWTH (17.01%) | SIZE+H03+TURN+EVEBITDA+ASSET_GROWTH+RESVOL (15.72%) | SIZE+H03+TURN+EVEBITDA+ASSET_GROWTH+RESVOL (13.27%) | SIZE+H03+TURN+CHIP250+BM+RESVOL (17.20%) | SIZE+H03+TURN+RET40+EVEBITDA+ASSET_GROWTH (17.01%) |
| 7 | SIZE+H03+TURN+CHIP250+BM+ASSET_GROWTH+RESVOL (15.73%) | SIZE+H03+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (15.58%) | SIZE+H03+TURN+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (14.93%) | SIZE+H03+RET40+EVEBITDA+DD60+ASSET_GROWTH+RESVOL (11.23%) | SIZE+H03+TURN+CHIP250+BM+ASSET_GROWTH+RESVOL (15.73%) | SIZE+H03+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (15.58%) |
| 8 | SIZE+H03+TURN+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL+SP (14.45%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (15.18%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (13.73%) | SIZE+H03+TURN+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (10.13%) | SIZE+H03+TURN+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL+SP (14.45%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (15.18%) |
| 9 | SIZE+H03+TURN+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (13.09%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (14.78%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (12.82%) | SIZE+H03+TURN+RET40+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (8.71%) | SIZE+H03+TURN+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (13.09%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL (14.78%) |
| 10 | SIZE+H03+TURN+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (11.59%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL (12.63%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+ASSET_GROWTH+RESVOL+SP (11.43%) | SIZE+H03+TURN+RET40+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (5.22%) | SIZE+H03+TURN+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (11.59%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+DD60+ASSET_GROWTH+RESVOL (12.63%) |
| 11 | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (10.95%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (11.48%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (10.42%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (4.06%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+ASSET_GROWTH+RESVOL+SP (10.95%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL (11.48%) |
| 12 | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (8.99%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (8.71%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (8.88%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (2.09%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (8.99%) | SIZE+H03+TURN+RET40+DD120+CHIP250+EVEBITDA+BM+DD60+ASSET_GROWTH+RESVOL+SP (8.71%) |

## Top combinations selected on training

| rank | count | components | max abs rho | train net | validation net | full net | recent net | full turnover | full max DD | full RankIC |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5 | `SIZE+H03+TURN+CHIP250+RESVOL` | 0.7509 | 19.13% | 12.07% | 16.36% | 5.61% | 18.52% | 27.88% | 0.1134 |
| 2 | 5 | `SIZE+H03+CHIP250+RESVOL+SP` | 0.7509 | 18.51% | 6.90% | 13.97% | 4.72% | 15.16% | 23.59% | 0.1010 |
| 3 | 5 | `SIZE+H03+DD120+RESVOL+SP` | 0.7509 | 18.26% | 6.67% | 13.72% | 3.28% | 19.10% | 24.44% | 0.0974 |
| 4 | 5 | `SIZE+H03+TURN+RESVOL+SP` | 0.7509 | 17.83% | 7.54% | 13.80% | 6.90% | 12.95% | 24.81% | 0.1036 |
| 5 | 5 | `SIZE+H03+TURN+BM+RESVOL` | 0.7509 | 17.75% | 8.68% | 14.20% | 8.75% | 13.24% | 25.68% | 0.1081 |
| 6 | 5 | `SIZE+H03+CHIP250+BM+RESVOL` | 0.7509 | 17.71% | 7.14% | 13.57% | 6.33% | 15.73% | 27.10% | 0.1055 |
| 7 | 5 | `SIZE+H03+DD120+ASSET_GROWTH+RESVOL` | 0.7509 | 17.44% | 13.14% | 15.75% | 10.20% | 18.99% | 30.64% | 0.0883 |
| 8 | 5 | `SIZE+H03+TURN+EVEBITDA+RESVOL` | 0.7509 | 17.30% | 16.06% | 16.82% | 13.99% | 13.46% | 31.90% | 0.0934 |
| 9 | 5 | `SIZE+H03+TURN+ASSET_GROWTH+RESVOL` | 0.7509 | 17.26% | 12.41% | 15.36% | 10.11% | 13.57% | 31.08% | 0.0978 |
| 10 | 5 | `SIZE+H03+CHIP250+ASSET_GROWTH+RESVOL` | 0.7509 | 17.24% | 13.76% | 15.88% | 10.90% | 15.56% | 30.79% | 0.0952 |
| 11 | 5 | `SIZE+H03+TURN+DD120+RESVOL` | 0.7509 | 17.24% | 13.04% | 15.59% | 7.34% | 22.24% | 29.33% | 0.1126 |
| 12 | 6 | `SIZE+H03+TURN+CHIP250+BM+RESVOL` | 0.7509 | 17.20% | 6.90% | 13.17% | 5.23% | 17.85% | 26.78% | 0.1150 |
| 13 | 5 | `SIZE+H03+TURN+RET40+RESVOL` | 0.7509 | 17.13% | 13.23% | 15.60% | 10.11% | 26.21% | 29.05% | 0.1205 |
| 14 | 6 | `SIZE+H03+TURN+DD120+RESVOL+SP` | 0.7509 | 17.12% | 8.39% | 13.70% | 4.29% | 20.92% | 24.15% | 0.1111 |
| 15 | 5 | `SIZE+H03+DD120+BM+RESVOL` | 0.7509 | 17.08% | 8.36% | 13.67% | 6.57% | 19.34% | 26.88% | 0.1038 |
| 16 | 6 | `SIZE+H03+TURN+DD120+BM+RESVOL` | 0.7509 | 17.03% | 8.26% | 13.60% | 5.90% | 21.05% | 26.64% | 0.1164 |
| 17 | 5 | `SIZE+H03+RET40+BM+RESVOL` | 0.7509 | 16.98% | 8.29% | 13.58% | 8.50% | 23.25% | 27.97% | 0.1123 |
| 18 | 6 | `SIZE+H03+TURN+CHIP250+RESVOL+SP` | 0.7509 | 16.96% | 6.71% | 12.95% | 3.19% | 17.26% | 24.51% | 0.1111 |
| 19 | 6 | `SIZE+H03+TURN+DD120+ASSET_GROWTH+RESVOL` | 0.7509 | 16.90% | 12.97% | 15.36% | 9.23% | 21.02% | 30.47% | 0.1052 |
| 20 | 5 | `SIZE+H03+EVEBITDA+RESVOL+SP` | 0.7509 | 16.85% | 11.48% | 14.74% | 10.68% | 8.63% | 29.10% | 0.0771 |
| 21 | 6 | `SIZE+H03+TURN+ASSET_GROWTH+RESVOL+SP` | 0.7509 | 16.82% | 7.69% | 13.24% | 5.79% | 13.03% | 27.70% | 0.0972 |
| 22 | 5 | `SIZE+H03+ASSET_GROWTH+RESVOL+SP` | 0.7509 | 16.78% | 7.18% | 13.02% | 6.94% | 8.25% | 27.17% | 0.0784 |
| 23 | 6 | `SIZE+H03+TURN+CHIP250+ASSET_GROWTH+RESVOL` | 0.7509 | 16.71% | 12.26% | 14.97% | 6.99% | 17.88% | 30.46% | 0.1077 |
| 24 | 6 | `SIZE+H03+TURN+EVEBITDA+RESVOL+SP` | 0.7509 | 16.48% | 11.13% | 14.38% | 10.09% | 13.23% | 28.76% | 0.0954 |
| 25 | 6 | `SIZE+H03+TURN+BM+ASSET_GROWTH+RESVOL` | 0.7509 | 16.35% | 8.41% | 13.24% | 8.76% | 13.20% | 28.19% | 0.1016 |

## Key diagnostics

- Best training-period combination: `SIZE+H03+TURN+CHIP250+RESVOL`; count `5`; train/validation/full/recent net = `19.13%` / `12.07%` / `16.36%` / `5.61%`; max abs rho `0.7509`.
- Best validation-period combination (diagnostic ranking): `SIZE+H03+TURN+RET40+EVEBITDA`; count `5`; train/validation/full/recent net = `12.21%` / `17.65%` / `14.34%` / `12.95%`; max abs rho `0.7509`.
- Best full-period combination (descriptive ranking): `SIZE+H03+TURN+EVEBITDA+RESVOL`; count `5`; train/validation/full/recent net = `17.30%` / `16.06%` / `16.82%` / `13.99%`; max abs rho `0.7509`.
- Best recent-period combination (diagnostic ranking): `SIZE+H03+EVEBITDA+ASSET_GROWTH+RESVOL`; count `5`; train/validation/full/recent net = `15.25%` / `16.74%` / `15.83%` / `16.82%`; max abs rho `0.7509`.
- Exact requested C1-style subset `SIZE+TURN+RET40+DD120+CHIP250`: train/validation/full/recent net = `8.69%` / `12.00%` / `9.99%` / `-0.11%`; full turnover `36.87%`, full max drawdown `32.90%`.
- Same-cluster check `SIZE+H03`: train/validation/full/recent net = `18.65%` / `18.68%` / `18.66%` / `15.97%`; max abs rho `0.7509`.

## Interpretation boundary

- Training ranking is the only ranking used for a prospective selection. Validation and recent winners were selected after seeing those periods and are diagnostics, not unbiased out-of-sample choices.
- A low correlation only means different signal exposure. It does not prove independent alpha or remove the common small-cap/market-regime exposure.
- The combination is an equal-weight local portfolio proxy. PandaAI's official pool treatment and C score are not reproduced by averaging single-factor platform headlines.
- EV/EBITDA and residual-volatility inputs are retained because they were in the requested representative set, but their saved alignment quality is marked as a field/path proxy issue. Results involving them need separate confirmation before platform submission.

## Artifacts

- All 4095 combinations: `research_reports\platform_alignment\competition-pool-combination-20260920\all_combinations.csv`
- Selected combinations with exact RankIC/IC: `research_reports\platform_alignment\competition-pool-combination-20260920\selected_combinations.csv`
- Per-period holdings diagnostics for selected combinations: `research_reports\platform_alignment\competition-pool-combination-20260920\selected_periods.csv`
- Machine-readable payload: `research_reports\platform_alignment\competition-pool-combination-20260920\report.json`
