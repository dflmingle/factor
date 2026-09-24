# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: annualized top `10.0%` excess minus turnover cost; round-trip cost `0.0060` (one-way `0.0030`)
- GP expressions scored: `10024`; invalid: `3290`
- GP search terminals: `371` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | net excess | gross excess | turnover | annual cost | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Div(Div(Div(Div(Div(Div(ratio_bm_lyr,vma250),cal_20d_amt_ma),bs_total_assets),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)` | `((((((RATIO_BM_LYR/VMA250)/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)` | 20.41% | 23.24% | 18.78% | 2.84% | 100.0% | n/a |
| 2 | `Div(Div(Div(Div(Div(Div(Div(Div(ratio_bm_lyr,vma250),cal_20d_amt_ma),bs_total_assets),cal_20d_amt_ma),cal_20d_amt_ma),qtyr_5_20),bs_total_assets),bs_total_assets)` | `((((((((RATIO_BM_LYR/VMA250)/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/CAL_20D_AMT_MA)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS)` | 20.04% | 22.63% | 17.16% | 2.59% | 100.0% | 0.9737 |
| 3 | `Div(Div(Div(Div(Div(Div(Div(Div(ratio_bm_lyr,Log(vma250)),cal_20d_amt_ma),Log(vma250)),cal_20d_amt_ma),qtyr_5_20),cal_20d_amt_ma),bs_total_assets),bs_total_assets)` | `((((((((RATIO_BM_LYR/LOG(VMA250))/CAL_20D_AMT_MA)/LOG(VMA250))/CAL_20D_AMT_MA)/QTYR_5_20)/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS)` | 20.03% | 22.95% | 19.29% | 2.92% | 100.0% | 0.9923 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Div(Div(Div(Div(Div(Div(ratio_bm_lyr,vma250),cal_20d_amt_ma),cal_20d_amt_ma),bs_total_assets),qtyr_5_20),bs_total_assets)`
- PandaAI formula: `((((((RATIO_BM_LYR/VMA250)/CAL_20D_AMT_MA)/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/QTYR_5_20)/BS_TOTAL_ASSETS)`
- Full aligned net excess: `20.41%`
- Early net excess through 2024-12-31: `21.84%`
- Late net excess from 2025-01-01: `17.40%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
