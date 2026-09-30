# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `678`; invalid: `0`
- GP search terminals: `33` via `verified`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `3` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Log(Ref(Log(book_to_market_ratio_lyr),30))` | `LOG(REF(LOG(BOOK_TO_MARKET_RATIO_LYR),30))` | 0.0055% | n/a | 0.0409% | 0.276% | 0.48% | 8.03% | -3.07% | 100.0% | n/a |
| 2 | `Log(TsMed(Ref(Log(book_to_market_ratio_lyr),30),30))` | `LOG(TS_MEDIAN(REF(LOG(BOOK_TO_MARKET_RATIO_LYR),30),30))` | 0.0053% | n/a | 0.0394% | 0.274% | 0.49% | 6.75% | -2.82% | 100.0% | 0.9906 |
| 3 | `Log(Log(Log(Log(book_to_market_ratio_lyr))))` | `LOG(LOG(LOG(LOG(BOOK_TO_MARKET_RATIO_LYR))))` | 0.0050% | n/a | 0.0547% | 0.187% | 0.49% | 8.60% | -1.97% | 100.0% | 0.9763 |
| 4 | `Log(Log(ratio_bm_ttm))` | `LOG(LOG(RATIO_BM_TTM))` | 0.0046% | n/a | 0.0554% | 0.173% | 0.47% | 7.73% | -1.00% | 100.0% | 0.9892 |
| 5 | `Log(Log(TsMin(Abs(book_to_market_ratio_lyr),40)))` | `LOG(LOG(TS_MIN(ABS(BOOK_TO_MARKET_RATIO_LYR),40)))` | 0.0036% | n/a | 0.0504% | 0.146% | 0.48% | 7.04% | -1.15% | 100.0% | 0.9877 |
| 6 | `Log(TsMed(Ref(Log(TsMed(Ref(Log(book_to_market_ratio_lyr),30),30)),30),30))` | `LOG(TS_MEDIAN(REF(LOG(TS_MEDIAN(REF(LOG(BOOK_TO_MARKET_RATIO_LYR),30),30)),30),30))` | 0.0033% | n/a | 0.0343% | 0.203% | 0.47% | 7.18% | -4.50% | 100.0% | 0.9736 |
| 7 | `TsMax(Log(book_to_market_ratio_lyr),10)` | `TS_MAX(LOG(BOOK_TO_MARKET_RATIO_LYR),10)` | 0.0032% | n/a | 0.0490% | 0.141% | 0.47% | 6.79% | -1.30% | 100.0% | 0.9959 |
| 8 | `Log(Log(Log(TsMed(book_to_market_ratio_lyr,20))))` | `LOG(LOG(LOG(TS_MEDIAN(BOOK_TO_MARKET_RATIO_LYR,20))))` | 0.0032% | n/a | 0.0477% | 0.147% | 0.46% | 7.17% | -2.20% | 100.0% | 0.9974 |
| 9 | `Log(TsMax(ratio_bm_ttm,10))` | `LOG(TS_MAX(RATIO_BM_TTM,10))` | 0.0032% | n/a | 0.0493% | 0.139% | 0.47% | 6.76% | -1.28% | 100.0% | 0.9960 |
| 10 | `TsSum(book_to_market_ratio_lf,10)` | `SUM(BOOK_TO_MARKET_RATIO_LF,10)` | 0.0030% | n/a | 0.0553% | 0.115% | 0.47% | 5.47% | 0.84% | 100.0% | 0.9987 |
| 11 | `TsMin(Log(TsEMA(Log(book_to_market_ratio_lyr),30)),10)` | `TS_MIN(LOG(EMA(LOG(BOOK_TO_MARKET_RATIO_LYR),30)),10)` | 0.0030% | n/a | 0.0470% | 0.138% | 0.46% | 6.43% | -2.03% | 100.0% | 0.9985 |
| 12 | `Log(TsMed(Log(Log(book_to_market_ratio_lyr)),30))` | `LOG(TS_MEDIAN(LOG(LOG(BOOK_TO_MARKET_RATIO_LYR)),30))` | 0.0029% | n/a | 0.0453% | 0.137% | 0.47% | 6.89% | -2.63% | 100.0% | 0.9989 |
| 13 | `Log(Inv(TsWMA(book_to_market_ratio_lf,50)))` | `LOG((1/(WMA(BOOK_TO_MARKET_RATIO_LF,50))))` | 0.0027% | n/a | -0.0463% | -0.125% | 0.47% | 6.11% | -9.34% | 100.0% | -0.9475 |
| 14 | `Log(Ref(Ref(Ref(book_to_market_ratio_lyr,20),30),40))` | `LOG(REF(REF(REF(BOOK_TO_MARKET_RATIO_LYR,20),30),40))` | 0.0026% | n/a | 0.0348% | 0.156% | 0.48% | 7.62% | -3.51% | 100.0% | 0.9981 |
| 15 | `Log(Log(Log(TsSum(book_to_market_ratio_lyr,40))))` | `LOG(LOG(LOG(SUM(BOOK_TO_MARKET_RATIO_LYR,40))))` | 0.0026% | n/a | 0.0443% | 0.126% | 0.46% | 6.07% | -2.19% | 100.0% | 0.9985 |
| 16 | `TsWMA(ratio_bm_ttm,40)` | `WMA(RATIO_BM_TTM,40)` | 0.0025% | n/a | 0.0513% | 0.101% | 0.47% | 4.14% | 0.45% | 100.0% | 0.9977 |
| 17 | `TsMax(Log(book_to_market_ratio_lyr),50)` | `TS_MAX(LOG(BOOK_TO_MARKET_RATIO_LYR),50)` | 0.0023% | n/a | 0.0408% | 0.121% | 0.46% | 6.07% | -2.30% | 100.0% | 0.9922 |
| 18 | `TsMin(TsSum(TsSum(Log(book_to_market_ratio_lyr),30),20),30)` | `TS_MIN(SUM(SUM(LOG(BOOK_TO_MARKET_RATIO_LYR),30),20),30)` | 0.0022% | n/a | 0.0418% | 0.113% | 0.47% | 5.64% | -1.93% | 100.0% | 0.9954 |
| 19 | `Log(TsMed(TsWMA(TsMed(book_to_market_ratio_lyr,20),50),30))` | `LOG(TS_MEDIAN(WMA(TS_MEDIAN(BOOK_TO_MARKET_RATIO_LYR,20),50),30))` | 0.0021% | n/a | 0.0398% | 0.109% | 0.47% | 5.60% | -2.22% | 100.0% | 0.9984 |
| 20 | `Log(Log(open))` | `LOG(LOG(OPEN))` | 0.0020% | n/a | -0.0369% | -0.113% | 0.49% | 10.61% | -8.93% | 100.0% | 0.5104 |
| 21 | `Rank(Ref(Ref(Log(book_to_market_ratio_lyr),20),30))` | `RANK(REF(REF(LOG(BOOK_TO_MARKET_RATIO_LYR),20),30))` | 0.0019% | n/a | 0.0380% | 0.105% | 0.47% | 8.91% | -4.05% | 100.0% | 0.9964 |
| 22 | `TsMax(TsSum(Add(Constant(0.01),ratio_ep_ttm),50),10)` | `TS_MAX(SUM((0.01+RATIO_EP_TTM),50),10)` | 0.0017% | n/a | 0.0390% | 0.113% | 0.39% | 9.95% | -1.84% | 100.0% | 0.3434 |
| 23 | `TsMax(ratio_ep_ttm,50)` | `TS_MAX(RATIO_EP_TTM,50)` | 0.0012% | n/a | 0.0359% | 0.085% | 0.41% | 9.00% | -2.77% | 100.0% | 0.9879 |
| 24 | `Log(Log(Log(Log(current_assets))))` | `LOG(LOG(LOG(LOG(CURRENT_ASSETS))))` | 0.0012% | n/a | 0.0421% | 0.061% | 0.48% | 6.97% | -0.15% | 100.0% | 0.3880 |
| 25 | `Log(TsSum(open,10))` | `LOG(SUM(OPEN,10))` | 0.0012% | n/a | -0.0260% | -0.101% | 0.44% | 7.61% | -8.28% | 100.0% | 0.9987 |
| 26 | `TsMax(Add(TsMax(Add(Constant(0.01),ratio_ep_ttm),50),ratio_ep_ttm),50)` | `TS_MAX((TS_MAX((0.01+RATIO_EP_TTM),50)+RATIO_EP_TTM),50)` | 0.0011% | n/a | 0.0357% | 0.080% | 0.38% | 8.20% | -3.00% | 100.0% | 0.9928 |
| 27 | `Log(Log(TsEMA(TsMed(low,10),50)))` | `LOG(LOG(EMA(TS_MEDIAN(LOW,10),50)))` | 0.0010% | n/a | -0.0278% | -0.076% | 0.48% | 9.16% | -6.72% | 100.0% | 0.9969 |
| 28 | `Log(TsWMA(TsMin(Log(high),50),20))` | `LOG(WMA(TS_MIN(LOG(HIGH),50),20))` | 0.0007% | n/a | -0.0233% | -0.066% | 0.47% | 9.48% | -6.23% | 100.0% | 0.9956 |
| 29 | `Log(TsMean(Ref(Log(low),30),30))` | `LOG(MA(REF(LOG(LOW),30),30))` | 0.0007% | n/a | -0.0236% | -0.065% | 0.47% | 9.17% | -5.94% | 100.0% | 0.9967 |
| 30 | `TsMax(TsSum(TsEMA(current_assets,50),50),10)` | `TS_MAX(SUM(EMA(CURRENT_ASSETS,50),50),10)` | 0.0007% | n/a | 0.0543% | 0.041% | 0.32% | 6.86% | -3.02% | 100.0% | 0.9952 |
| 31 | `TsWMA(current_liabilities,40)` | `WMA(CURRENT_LIABILITIES,40)` | 0.0006% | n/a | 0.0477% | 0.041% | 0.31% | 5.88% | -3.77% | 100.0% | 0.8444 |
| 32 | `TsMax(TsWMA(current_liabilities,40),50)` | `TS_MAX(WMA(CURRENT_LIABILITIES,40),50)` | 0.0006% | n/a | 0.0475% | 0.041% | 0.31% | 5.96% | -3.95% | 100.0% | 0.9983 |
| 33 | `TsMean(TsMean(TsWMA(current_liabilities,40),30),30)` | `MA(MA(WMA(CURRENT_LIABILITIES,40),30),30)` | 0.0006% | n/a | 0.0475% | 0.040% | 0.31% | 5.86% | -3.71% | 100.0% | 0.9989 |
| 34 | `TsMax(open,50)` | `TS_MAX(OPEN,50)` | 0.0004% | n/a | -0.0148% | -0.068% | 0.43% | 5.91% | -7.82% | 100.0% | 0.9948 |
| 35 | `TsMean(TsMax(TsMax(open,50),40),50)` | `MA(TS_MAX(TS_MAX(OPEN,50),40),50)` | 0.0002% | n/a | -0.0086% | -0.057% | 0.43% | 4.66% | -7.27% | 100.0% | 0.9926 |
| 36 | `TsMax(TsWMA(TsMean(TsMax(TsMax(open,50),40),50),10),50)` | `TS_MAX(WMA(MA(TS_MAX(TS_MAX(OPEN,50),40),50),10),50)` | 0.0002% | n/a | -0.0070% | -0.054% | 0.42% | 4.52% | -6.80% | 100.0% | 0.9969 |
| 37 | `Log(TsMean(TsVar(TsSum(ratio_sp_ttm,50),40),40))` | `LOG(MA(VAR(SUM(RATIO_SP_TTM,50),40),40))` | 0.0001% | n/a | 0.0051% | 0.058% | 0.42% | 12.32% | -4.70% | 100.0% | 0.5333 |
| 38 | `Log(Log(Mul(Constant(5.0),inventory)))` | `LOG(LOG((5*INVENTORY)))` | 0.0001% | n/a | 0.0311% | 0.009% | 0.41% | 8.78% | -0.06% | 100.0% | 0.7648 |
| 39 | `Log(Log(Ref(TsWMA(current_assets,20),10)))` | `LOG(LOG(REF(WMA(CURRENT_ASSETS,20),10)))` | 0.0001% | n/a | 0.0422% | 0.007% | 0.41% | 6.69% | -0.08% | 100.0% | 0.9979 |
| 40 | `Log(Log(TsMax(current_assets,50)))` | `LOG(LOG(TS_MAX(CURRENT_ASSETS,50)))` | 0.0001% | n/a | 0.0417% | 0.007% | 0.41% | 6.62% | -0.28% | 100.0% | 0.9983 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Log(Ref(Log(book_to_market_ratio_lyr),30))`
- PandaAI formula: `LOG(REF(LOG(BOOK_TO_MARKET_RATIO_LYR),30))`
- Full aligned net excess: `-0.43%`
- Early net excess through 2024-12-31: `4.20%`
- Late net excess from 2025-01-01: `-10.06%`
- Full S_i: `0.0030%`; turnover `5.85%`; rank IC `0.0439%`; ICIR `0.140%`; win `0.48%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
