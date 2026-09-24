# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 40.00%` per rebalance and net excess `>= 15.00%`
- GP expressions scored: `4592`; invalid: `24`
- GP search terminals: `388` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Inv(a_share_market_val)` | `(1/(A_SHARE_MARKET_VAL))` | 0.0000% | 0.000% | 0.0560% | 0.245% | 0.00% | 8.64% | 20.12% | 100.0% | n/a |
| 2 | `TsMinDiff(amount,50)` | `(AMOUNT-TS_MIN(AMOUNT,50))` | 0.0356% | 0.074% | -0.1117% | -0.460% | 0.69% | 48.23% | -38.74% | 100.0% | -0.5311 |
| 3 | `TsMinDiff(amount,40)` | `(AMOUNT-TS_MIN(AMOUNT,40))` | 0.0362% | 0.073% | -0.1108% | -0.467% | 0.70% | 49.40% | -38.53% | 100.0% | 0.9898 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Inv(a_share_market_val)`
- PandaAI formula: `(1/(A_SHARE_MARKET_VAL))`
- Full aligned net excess: `20.12%`
- Early net excess through 2024-12-31: `21.71%`
- Late net excess from 2025-01-01: `16.79%`
- Full S_i: `0.0000%`; turnover `8.64%`; rank IC `0.0560%`; ICIR `0.245%`; win `0.00%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
