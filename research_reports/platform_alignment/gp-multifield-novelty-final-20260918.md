# AlphaPROBE GP final novel candidates

This is an offline local result. No PandaAI factor was created or run.

- Eligible after formula/split/size audit: `12`
- Historical platform formulas compared: `87` usable of `133`
- Final novel candidates: `4`
- Historical duplicate threshold: absolute daily RankIC `0.90`
- Current-batch duplicate threshold: absolute daily RankIC `0.90`

Only final novel candidates are listed below; rejected existing/duplicate formulas are retained in the JSON/CSV audit but are not presented as candidates.

| rank | formula | full net | valid net | test net | size RankIC | closest historical abs RankIC |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `(((-0.01)*BOOK_TO_MARKET_RATIO_LF)/OPER_ROE_LYR)` | 6.64% | 13.86% | 6.44% | -1.95% | 0.4984 |
| 2 | `(((-1)/OPER_ROE_LYR)/CURRENT_LIABILITIES)` | 7.18% | 16.34% | 4.74% | 23.51% | 0.4398 |
| 3 | `(((RATIO_EP_TTM/OPER_ROE_LYR)/OPER_ROE_LYR)/CURRENT_LIABILITIES)` | 7.59% | 12.08% | 1.20% | -16.97% | 0.4874 |
| 4 | `(RATIO_SP_TTM/TS_MAX(TS_MAX(TS_MAX(TS_MAX(TS_MAX(WMA(TS_MEDIAN(OPER_MAIN_PROFIT_TTM,10),30),40),40),40),40),40))` | 8.44% | 10.73% | 0.13% | -35.37% | 0.5073 |

The closest historical formula name/handler and all rejected rows are available only in the machine-readable JSON/CSV for audit purposes.
