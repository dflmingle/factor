# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `6795`; invalid: `28`
- GP search terminals: `388` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `TsMinDiff(amount,40)` | `(AMOUNT-TS_MIN(AMOUNT,40))` | 0.0362% | 0.073% | -0.1108% | -0.467% | 0.70% | 49.40% | -38.53% | 100.0% | n/a |
| 2 | `TsMinDiff(amount,50)` | `(AMOUNT-TS_MIN(AMOUNT,50))` | 0.0356% | 0.074% | -0.1117% | -0.460% | 0.69% | 48.23% | -38.74% | 100.0% | 0.9898 |
| 3 | `TsMinDiff(amount,30)` | `(AMOUNT-TS_MIN(AMOUNT,30))` | 0.0351% | 0.068% | -0.1076% | -0.471% | 0.69% | 51.22% | -38.57% | 100.0% | 0.9814 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `TsMinDiff(amount,40)`
- PandaAI formula: `(AMOUNT-TS_MIN(AMOUNT,40))`
- Full aligned net excess: `-38.53%`
- Early net excess through 2024-12-31: `-45.84%`
- Late net excess from 2025-01-01: `-23.31%`
- Full S_i: `0.0362%`; turnover `49.40%`; rank IC `-0.1108%`; ICIR `-0.467%`; win `0.70%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
