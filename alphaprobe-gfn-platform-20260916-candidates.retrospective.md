# AlphaPROBE GFlowNet PandaAI validation

- Window: 2021-09-07..2026-09-07
- Rebalance: 5 trading days
- Groups: 10
- Direction: 1 for all candidates
- One-way cost: 0.30%
- Multiple-testing reference: p < 0.0167

## Decisions

| Candidate | Platform formula | Platform Rank IC | Gross long excess | Turnover | Net long excess | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| F-A18 | `book_to_market_ratio_lf / MA(book_to_market_ratio_lf,40)` | 0.0646 | 3.51% | 38.73% | -8.20% | orthogonalize / reduce turnover |
| F-A20 | `TS_SKEW(book_to_market_ratio_lf * book_to_market_ratio_lf,30)` | 0.0190 | 3.21% | 61.37% | -15.35% | orthogonalize only if turnover can be reduced |
| F-A19 | `ps_ratio_ttm - TS_MAX(ps_ratio_ttm,40)` | -0.0010 | -17.88% | 60.46% | -36.16% | abandon |

F-A18 is the strongest platform result and is the only candidate with both a meaningful Rank IC and
a moderate turnover profile. Its positive gross long excess does not survive the stated cost model.
F-A20 has positive IC and a positive gross long side, but the turnover haircut is too large. F-A19
does not validate the local signal on the platform and should not be carried forward.

Cross-correlation against the existing platform factor set was not run in this batch; the platform
factor values were not downloaded. The complete raw responses and factor/run IDs are in the batch
state and results directory.
