# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: annualized top `10.0%` excess minus turnover cost; round-trip cost `0.0060` (one-way `0.0030`)
- GP expressions scored: `6635`; invalid: `194`
- GP search terminals: `388` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | net excess | gross excess | turnover | annual cost | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Inv(a_share_market_val)` | `(1/(A_SHARE_MARKET_VAL))` | 20.12% | 21.42% | 8.64% | 1.31% | 100.0% | n/a |
| 2 | `Inv(cal_20d_amt_ma)` | `(1/(CAL_20D_AMT_MA))` | 13.54% | 16.77% | 21.33% | 3.23% | 100.0% | 0.6551 |
| 3 | `Inv(cal_20d_amt_std)` | `(1/(CAL_20D_AMT_STD))` | 12.36% | 16.21% | 25.49% | 3.85% | 100.0% | 0.9890 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Inv(a_share_market_val)`
- PandaAI formula: `(1/(A_SHARE_MARKET_VAL))`
- Full aligned net excess: `20.12%`
- Early net excess through 2024-12-31: `21.71%`
- Late net excess from 2025-01-01: `16.79%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
