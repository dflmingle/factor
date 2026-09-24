# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: annualized top `10.0%` excess minus turnover cost; round-trip cost `0.0060` (one-way `0.0030`)
- GP expressions scored: `4892`; invalid: `126`
- GP search terminals: `388` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | net excess | gross excess | turnover | annual cost | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Sign(ratio_ev_ebitda_lyr)` | `SIGN(RATIO_EV_EBITDA_LYR)` | 13.16% | 17.83% | 30.90% | 4.67% | 100.0% | n/a |
| 2 | `Sign(SLog1p(TsMax(Sign(bs_fin_lease_payable),20)))` | `SIGN((SIGN(TS_MAX(SIGN(BS_FIN_LEASE_PAYABLE),20))*LOG(1+ABS(TS_MAX(SIGN(BS_FIN_LEASE_PAYABLE),20)))))` | 13.05% | 17.52% | 29.57% | 4.47% | 100.0% | 0.1581 |
| 3 | `Sign(bs_fin_lease_payable)` | `SIGN(BS_FIN_LEASE_PAYABLE)` | 13.04% | 17.48% | 29.39% | 4.44% | 100.0% | 0.9973 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Sign(ratio_ev_ebitda_lyr)`
- PandaAI formula: `SIGN(RATIO_EV_EBITDA_LYR)`
- Full aligned net excess: `-2.91%`
- Early net excess through 2024-12-31: `-0.84%`
- Late net excess from 2025-01-01: `-7.20%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
