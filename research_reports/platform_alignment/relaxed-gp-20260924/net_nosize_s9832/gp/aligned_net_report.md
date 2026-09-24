# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: annualized top `10.0%` excess minus turnover cost; round-trip cost `0.0060` (one-way `0.0030`)
- GP expressions scored: `7851`; invalid: `1893`
- GP search terminals: `371` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | net excess | gross excess | turnover | annual cost | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `TsSum(TsSum(TsSum(TsSum(TsIr(cal_vwap,40),30),30),30),30)` | `SUM(SUM(SUM(SUM((MA(CAL_VWAP,40)/STDDEV(CAL_VWAP,40)),30),30),30),30)` | 10.17% | 10.65% | 3.20% | 0.48% | 100.0% | n/a |
| 2 | `TsSum(TsSum(TsIr(cal_vwap,40),30),30)` | `SUM(SUM((MA(CAL_VWAP,40)/STDDEV(CAL_VWAP,40)),30),30)` | 9.95% | 10.55% | 3.97% | 0.60% | 100.0% | 0.8854 |
| 3 | `TsMax(TsIr(cal_vwap,30),10)` | `TS_MAX((MA(CAL_VWAP,30)/STDDEV(CAL_VWAP,30)),10)` | 9.92% | 11.66% | 11.47% | 1.73% | 100.0% | 0.7246 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `TsMax(TsIr(cal_vwap,30),10)`
- PandaAI formula: `TS_MAX((MA(CAL_VWAP,30)/STDDEV(CAL_VWAP,30)),10)`
- Full aligned net excess: `9.92%`
- Early net excess through 2024-12-31: `5.63%`
- Late net excess from 2025-01-01: `18.79%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
