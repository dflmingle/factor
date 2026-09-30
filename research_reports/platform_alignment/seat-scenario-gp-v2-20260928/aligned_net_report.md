# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `706`; invalid: `0`
- GP search terminals: `33` via `verified`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `2` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Log(Rank(TsMinMaxDiff(market_cap,40)))` | `LOG(RANK((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40))))` | 0.0167% | n/a | -0.0727% | -0.331% | 0.69% | 11.96% | -11.71% | 100.0% | n/a |
| 2 | `Log(Rank(market_cap))` | `LOG(RANK(MARKET_CAP))` | 0.0127% | n/a | -0.0560% | -0.316% | 0.72% | 3.77% | -11.13% | 100.0% | 0.8855 |
| 3 | `Log(Rank(TsVar(market_cap,40)))` | `LOG(RANK(VAR(MARKET_CAP,40)))` | 0.0152% | n/a | -0.0696% | -0.315% | 0.69% | 13.78% | -12.12% | 100.0% | 0.9914 |
| 4 | `Log(TsWMA(TsMinMaxDiff(market_cap,40),20))` | `LOG(WMA((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40)),20))` | 0.0107% | n/a | -0.0671% | -0.256% | 0.62% | 9.49% | -10.46% | 100.0% | 0.9858 |
| 5 | `Log(TsMin(Rank(TsVar(market_cap,30)),50))` | `LOG(TS_MIN(RANK(VAR(MARKET_CAP,30)),50))` | 0.0105% | n/a | -0.0565% | -0.273% | 0.68% | 6.47% | -9.94% | 100.0% | 0.9283 |
| 6 | `Log(TsMin(Rank(Log(TsWMA(Rank(TsVar(market_cap,30)),20))),50))` | `LOG(TS_MIN(RANK(LOG(WMA(RANK(VAR(MARKET_CAP,30)),20))),50))` | 0.0105% | n/a | -0.0565% | -0.274% | 0.68% | 5.52% | -9.65% | 100.0% | 0.9887 |
| 7 | `Log(TsWMA(TsVar(market_cap,30),20))` | `LOG(WMA(VAR(MARKET_CAP,30),20))` | 0.0111% | n/a | -0.0679% | -0.261% | 0.62% | 13.19% | -11.85% | 100.0% | 0.9943 |
| 8 | `Log(TsMin(Rank(TsMinMaxDiff(market_cap,40)),50))` | `LOG(TS_MIN(RANK((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40))),50))` | 0.0103% | n/a | -0.0562% | -0.275% | 0.67% | 6.23% | -9.64% | 100.0% | 0.9881 |
| 9 | `Log(TsWMA(Rank(TsVar(market_cap,30)),20))` | `LOG(WMA(RANK(VAR(MARKET_CAP,30)),20))` | 0.0137% | n/a | -0.0667% | -0.301% | 0.68% | 13.97% | -11.59% | 100.0% | 0.9986 |
| 10 | `Log(Rank(TsSum(market_cap,30)))` | `LOG(RANK(SUM(MARKET_CAP,30)))` | 0.0096% | n/a | -0.0487% | -0.286% | 0.69% | 2.26% | -10.27% | 100.0% | 0.9963 |
| 11 | `Log(TsWMA(TsMin(Rank(TsMinMaxDiff(market_cap,40)),50),20))` | `LOG(WMA(TS_MIN(RANK((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40))),50),20))` | 0.0095% | n/a | -0.0547% | -0.268% | 0.65% | 5.40% | -9.48% | 100.0% | 0.9941 |
| 12 | `Log(TsMin(TsMinMaxDiff(market_cap,40),40))` | `LOG(TS_MIN((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40)),40))` | 0.0089% | n/a | -0.0600% | -0.247% | 0.60% | 7.90% | -11.36% | 100.0% | 0.9813 |
| 13 | `Log(TsMin(TsMinMaxDiff(market_cap,40),50))` | `LOG(TS_MIN((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40)),50))` | 0.0084% | n/a | -0.0583% | -0.241% | 0.60% | 6.97% | -10.15% | 100.0% | 0.9913 |
| 14 | `Log(Rank(TsMinMaxDiff(TsMinMaxDiff(market_cap,40),40)))` | `LOG(RANK((TS_MAX((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40)),40)-TS_MIN((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40)),40))))` | 0.0133% | n/a | -0.0642% | -0.319% | 0.65% | 14.24% | -11.95% | 100.0% | 0.8874 |
| 15 | `Log(TsMin(Rank(Log(TsMin(Rank(TsMinMaxDiff(market_cap,40)),50))),50))` | `LOG(TS_MIN(RANK(LOG(TS_MIN(RANK((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40))),50))),50))` | 0.0080% | n/a | -0.0492% | -0.248% | 0.65% | 3.71% | -8.91% | 100.0% | 0.9669 |
| 16 | `Log(TsMin(Rank(Log(market_cap)),50))` | `LOG(TS_MIN(RANK(LOG(MARKET_CAP)),50))` | 0.0073% | n/a | -0.0422% | -0.261% | 0.67% | 1.92% | -9.22% | 100.0% | 0.9948 |
| 17 | `Log(TsMed(volume,50))` | `LOG(TS_MEDIAN(VOLUME,50))` | 0.0066% | n/a | -0.0434% | -0.280% | 0.54% | 9.46% | -17.29% | 100.0% | 0.4660 |
| 18 | `Log(Log(Log(book_to_market_ratio_lyr)))` | `LOG(LOG(LOG(BOOK_TO_MARKET_RATIO_LYR)))` | 0.0064% | n/a | 0.0606% | 0.211% | 0.50% | 5.89% | 2.04% | 100.0% | 0.1307 |
| 19 | `TsMax(Log(TsSum(market_cap,10)),50)` | `TS_MAX(LOG(SUM(MARKET_CAP,10)),50)` | 0.0061% | n/a | -0.0494% | -0.217% | 0.57% | 2.18% | -9.71% | 100.0% | 0.9972 |
| 20 | `Log(Log(ratio_bm_ttm))` | `LOG(LOG(RATIO_BM_TTM))` | 0.0057% | n/a | 0.0596% | 0.198% | 0.48% | 5.68% | 1.85% | 100.0% | 0.9892 |
| 21 | `Log(TsSum(TsMax(market_cap,20),40))` | `LOG(SUM(TS_MAX(MARKET_CAP,20),40))` | 0.0057% | n/a | -0.0477% | -0.212% | 0.56% | 2.15% | -9.81% | 100.0% | 0.9986 |
| 22 | `Log(TsMean(TsWMA(market_cap,20),50))` | `LOG(MA(WMA(MARKET_CAP,20),50))` | 0.0052% | n/a | -0.0450% | -0.207% | 0.56% | 1.88% | -9.55% | 100.0% | 0.9988 |
| 23 | `Log(TsMin(Log(market_cap),50))` | `LOG(TS_MIN(LOG(MARKET_CAP),50))` | 0.0049% | n/a | -0.0429% | -0.209% | 0.55% | 2.10% | -9.60% | 100.0% | 0.9989 |
| 24 | `Greater(Constant(-0.5),high)` | `MAX((-0.5),HIGH)` | 0.0048% | n/a | -0.0509% | -0.178% | 0.52% | 6.90% | -13.11% | 100.0% | 0.3208 |
| 25 | `Ref(Log(market_cap),50)` | `REF(LOG(MARKET_CAP),50)` | 0.0046% | n/a | -0.0411% | -0.202% | 0.55% | 3.85% | -9.01% | 100.0% | 0.9952 |
| 26 | `Log(TsMax(ratio_bm_ttm,10))` | `LOG(TS_MAX(RATIO_BM_TTM,10))` | 0.0042% | n/a | 0.0534% | 0.164% | 0.47% | 4.89% | 1.11% | 100.0% | 0.9960 |
| 27 | `TsEMA(TsMean(TsMinMaxDiff(market_cap,20),30),30)` | `EMA(MA((TS_MAX(MARKET_CAP,20)-TS_MIN(MARKET_CAP,20)),30),30)` | 0.0041% | n/a | -0.0648% | -0.142% | 0.45% | 6.65% | -11.18% | 100.0% | 0.9815 |
| 28 | `Log(Rank(TsMed(book_to_market_ratio_lyr,50)))` | `LOG(RANK(TS_MEDIAN(BOOK_TO_MARKET_RATIO_LYR,50)))` | 0.0041% | n/a | 0.0468% | 0.176% | 0.50% | 2.93% | 0.42% | 100.0% | 0.9852 |
| 29 | `TsSum(open,10)` | `SUM(OPEN,10)` | 0.0040% | n/a | -0.0468% | -0.164% | 0.52% | 5.49% | -11.87% | 100.0% | 0.9985 |
| 30 | `TsEMA(TsWMA(TsMad(high,50),50),40)` | `EMA(WMA(TS_MAD(HIGH,50),50),40)` | 0.0036% | n/a | -0.0506% | -0.144% | 0.50% | 7.85% | -10.06% | 100.0% | 0.8985 |
| 31 | `TsStd(Mul(Abs(Constant(2.0)),TsMaxDiff(market_cap,10)),30)` | `STDDEV((ABS(2)*(MARKET_CAP-TS_MAX(MARKET_CAP,10))),30)` | 0.0036% | n/a | -0.0612% | -0.127% | 0.47% | 12.56% | -11.99% | 100.0% | 0.9425 |
| 32 | `TsMax(TsMed(TsStd(Mul(Abs(Constant(2.0)),TsMaxDiff(market_cap,10)),30),50),10)` | `TS_MAX(TS_MEDIAN(STDDEV((ABS(2)*(MARKET_CAP-TS_MAX(MARKET_CAP,10))),30),50),10)` | 0.0034% | n/a | -0.0564% | -0.141% | 0.43% | 7.45% | -11.30% | 100.0% | 0.9353 |
| 33 | `TsMed(TsStd(Mul(Abs(Constant(2.0)),TsMaxDiff(market_cap,10)),30),50)` | `TS_MEDIAN(STDDEV((ABS(2)*(MARKET_CAP-TS_MAX(MARKET_CAP,10))),30),50)` | 0.0034% | n/a | -0.0567% | -0.139% | 0.43% | 7.72% | -11.72% | 100.0% | 0.9894 |
| 34 | `Log(Inv(TsWMA(book_to_market_ratio_lf,50)))` | `LOG((1/(WMA(BOOK_TO_MARKET_RATIO_LF,50))))` | 0.0034% | n/a | -0.0495% | -0.144% | 0.47% | 4.44% | -10.31% | 100.0% | 0.5684 |
| 35 | `TsMax(TsMax(open,50),40)` | `TS_MAX(TS_MAX(OPEN,50),40)` | 0.0034% | n/a | -0.0441% | -0.148% | 0.52% | 3.46% | -10.43% | 100.0% | 0.9906 |
| 36 | `TsMax(open,50)` | `TS_MAX(OPEN,50)` | 0.0033% | n/a | -0.0451% | -0.145% | 0.51% | 4.19% | -10.69% | 100.0% | 0.9963 |
| 37 | `Log(TsWMA(TsEMA(TsVar(close,30),30),20))` | `LOG(WMA(EMA(VAR(CLOSE,30),30),20))` | 0.0033% | n/a | -0.0528% | -0.124% | 0.50% | 11.86% | -11.31% | 100.0% | 0.9503 |
| 38 | `TsMad(Add(Constant(30.0),market_cap),50)` | `TS_MAD((30+MARKET_CAP),50)` | 0.0033% | n/a | -0.0647% | -0.118% | 0.43% | 12.68% | -10.77% | 100.0% | 0.9853 |
| 39 | `TsMed(TsStd(Mul(Abs(Constant(2.0)),TsStd(Mul(Abs(Constant(2.0)),TsMaxDiff(market_cap,10)),30)),30),50)` | `TS_MEDIAN(STDDEV((ABS(2)*STDDEV((ABS(2)*(MARKET_CAP-TS_MAX(MARKET_CAP,10))),30)),30),50)` | 0.0030% | n/a | -0.0465% | -0.151% | 0.43% | 10.85% | -12.01% | 100.0% | 0.8889 |
| 40 | `TsMax(TsSum(Log(book_to_market_ratio_lyr),50),10)` | `TS_MAX(SUM(LOG(BOOK_TO_MARKET_RATIO_LYR),50),10)` | 0.0030% | n/a | 0.0459% | 0.140% | 0.47% | 2.64% | 0.33% | 100.0% | 0.9986 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Log(Rank(TsMinMaxDiff(market_cap,40)))`
- PandaAI formula: `LOG(RANK((TS_MAX(MARKET_CAP,40)-TS_MIN(MARKET_CAP,40))))`
- Full aligned net excess: `-11.71%`
- Early net excess through 2024-12-31: `-15.89%`
- Late net excess from 2025-01-01: `-3.03%`
- Full S_i: `0.0167%`; turnover `11.96%`; rank IC `-0.0727%`; ICIR `-0.331%`; win `0.69%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
