# Previously untested AlphaPROBE candidates: PandaAI validation

- Window: `20210907..20260907`
- Rebalance: 5 trading days
- Groups: 10
- Direction: `1`
- One-way cost: `0.30%`
- Study-wide multiple-testing reference: `199` candidates, nominal `p < 0.0003`

| Candidate | Platform formula | Platform status | Rank IC | Long gross excess | Turnover | Net excess | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GFN-UNT-20260916-EVPRICE | `1 / EV_TTM / CLOSE` | completed | 0.0044 | 1.68% | 89.85% | -25.49% | abandon |
| GFN-UNT-20260916-BMQUALITY | `POWER(BOOK_TO_MARKET_RATIO_LF, IF(TS_MAD(PS_RATIO_TTM,50) < CASH_FLOW_FROM_OPERATING_ACTIVITIES_TTM, 1, 0))` | status 3 | n/a | n/a | n/a | n/a | retain as attempted / do not retry |
| GP-UNT-20260916-CONTRACT-RET30 | `RETURNS(CONTRACT_LIABILITIES_LYR,30)` | status 3 | n/a | n/a | n/a | n/a | retain as attempted / do not retry |

The EV/price candidate has a positive but weak platform Rank IC and fails after the stated turnover
cost. Its platform p-value is `0.0076`, also above the study-wide threshold. The other two runs ended
with platform status `3`; the CLI returned no node-level error and `factor_result` has no
`factor_analysis`, so they are not interpreted as negative performance results. Their factor IDs and
run IDs are retained in `pandaai-workflow-registry.json`.
