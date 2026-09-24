# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: annualized top `10.0%` excess minus turnover cost; round-trip cost `0.0060` (one-way `0.0030`)
- GP expressions scored: `6646`; invalid: `1882`
- GP search terminals: `388` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | net excess | gross excess | turnover | annual cost | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Inv(ratio_market_cap_total)` | `(1/(RATIO_MARKET_CAP_TOTAL))` | 20.12% | 21.42% | 8.64% | 1.31% | 100.0% | n/a |
| 2 | `Inv(TsMax(market_cap_3,50))` | `(1/(TS_MAX(MARKET_CAP_3,50)))` | 18.84% | 19.74% | 5.98% | 0.90% | 100.0% | 0.9935 |
| 3 | `Div(Inv(ratio_market_cap_total),amount)` | `((1/(RATIO_MARKET_CAP_TOTAL))/AMOUNT)` | 16.12% | 20.88% | 31.48% | 4.76% | 100.0% | 0.8752 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Inv(ratio_market_cap_total)`
- PandaAI formula: `(1/(RATIO_MARKET_CAP_TOTAL))`
- Full aligned net excess: `20.12%`
- Early net excess through 2024-12-31: `21.71%`
- Late net excess from 2025-01-01: `16.79%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
