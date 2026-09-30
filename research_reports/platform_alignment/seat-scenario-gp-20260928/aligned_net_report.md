# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `200`; invalid: `0`
- GP search terminals: `33` via `verified`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `TsMax(TsSum(TsEMA(current_assets,50),50),10)` | `TS_MAX(SUM(EMA(CURRENT_ASSETS,50),50),10)` | 0.0006% | n/a | -0.0156% | -0.085% | 0.43% | 0.79% | -7.12% | 100.0% | n/a |
| 2 | `TsMean(TsWMA(current_liabilities,40),30)` | `MA(WMA(CURRENT_LIABILITIES,40),30)` | 0.0004% | n/a | -0.0115% | -0.081% | 0.41% | 0.90% | -7.52% | 100.0% | 0.8449 |
| 3 | `TsWMA(TsWMA(inventory,10),50)` | `WMA(WMA(INVENTORY,10),50)` | 0.0004% | n/a | -0.0100% | -0.102% | 0.42% | 1.04% | -5.50% | 100.0% | 0.7639 |
| 4 | `Add(TsStd(TsSum(TsMaxDiff(TsCorr(TsStd(Constant(0.5),20),TsMean(Constant(-2.0),50),20),30),30),10),Mul(TsMean(TsMin(TsEMA(TsMean(inventory,50),40),50),10),TsMed(inventory,20)))` | `(STDDEV(SUM((CORR(STDDEV(0.5,20),MA((-2),50),20)-TS_MAX(CORR(STDDEV(0.5,20),MA((-2),50),20),30)),30),10)+(MA(TS_MIN(EMA(MA(INVENTORY,50),40),50),10)*TS_MEDIAN(INVENTORY,20)))` | 0.0000% | n/a | -0.0096% | 0.000% | 0.00% | 1.02% | -5.43% | 100.0% | 0.9987 |
| 5 | `TsMin(TsSum(inventory,10),40)` | `TS_MIN(SUM(INVENTORY,10),40)` | 0.0004% | n/a | -0.0096% | -0.102% | 0.42% | 1.19% | -5.65% | 100.0% | 0.9984 |
| 6 | `TsWMA(TsMean(TsMax(TsMax(open,50),40),50),10)` | `WMA(MA(TS_MAX(TS_MAX(OPEN,50),40),50),10)` | 0.0026% | n/a | -0.0379% | -0.138% | 0.49% | 2.84% | -9.22% | 100.0% | -0.0012 |
| 7 | `TsMax(Add(Constant(0.01),ratio_ep_ttm),50)` | `TS_MAX((0.01+RATIO_EP_TTM),50)` | 0.0003% | n/a | 0.0126% | -0.046% | 0.43% | 4.06% | -4.45% | 100.0% | 0.3523 |
| 8 | `TsCorr(Sign(TsMean(TsMax(TsMean(current_assets,40),20),20)),inventory,20)` | `CORR(SIGN(MA(TS_MAX(MA(CURRENT_ASSETS,40),20),20)),INVENTORY,20)` | 0.0000% | n/a | 0.1209% | -0.091% | 0.00% | 4.09% | -2.69% | 100.0% | 0.1042 |
| 9 | `TsDelta(TsMaxDiff(Less(TsRank(TsStd(high,50),20),TsMinMaxDiff(TsPctChange(Constant(30.0),20),50)),10),30)` | `DIFF((MIN(TS_RANK(STDDEV(HIGH,50),20),(TS_MAX(RETURNS(30,20),50)-TS_MIN(RETURNS(30,20),50)))-TS_MAX(MIN(TS_RANK(STDDEV(HIGH,50),20),(TS_MAX(RETURNS(30,20),50)-TS_MIN(RETURNS(30,20),50))),10)),30)` | 0.0000% | n/a | 0.1562% | 0.000% | 0.00% | 4.14% | -2.78% | 100.0% | 0.1208 |
| 10 | `TsDiv(Pow(Ref(Constant(1.0),20),Ref(ratio_sp_ttm,30)),30)` | `(POWER(REF(1,20),REF(RATIO_SP_TTM,30))/MA(POWER(REF(1,20),REF(RATIO_SP_TTM,30)),30))` | 0.0000% | n/a | 0.1562% | 0.000% | 0.00% | 4.14% | -2.78% | 100.0% | 0.5000 |
| 11 | `Ref(TsCov(TsStd(TsPctChange(oper_roe_lyr,40),20),TsDelta(TsMin(Constant(-5.0),40),10),20),20)` | `REF(COV(STDDEV(RETURNS(OPER_ROE_LYR,40),20),DIFF(TS_MIN((-5),40),10),20),20)` | 0.0000% | n/a | 0.0375% | 0.000% | 0.00% | 4.14% | -2.76% | 100.0% | 0.0833 |
| 12 | `TsSum(TsSum(TsCorr(book_to_market_ratio_lf,book_to_market_ratio_lf,10),30),20)` | `SUM(SUM(CORR(BOOK_TO_MARKET_RATIO_LF,BOOK_TO_MARKET_RATIO_LF,10),30),20)` | 0.0000% | n/a | 0.0792% | 0.030% | 0.00% | 4.31% | -2.80% | 100.0% | 0.1208 |
| 13 | `Log(book_to_market_ratio_lyr)` | `LOG(BOOK_TO_MARKET_RATIO_LYR)` | 0.0057% | n/a | 0.0606% | 0.194% | 0.48% | 5.89% | 2.04% | 100.0% | 0.3753 |
| 14 | `TsEMA(TsMinMaxDiff(TsCorr(Constant(-5.0),open,30),10),10)` | `EMA((TS_MAX(CORR((-5),OPEN,30),10)-TS_MIN(CORR((-5),OPEN,30),10)),10)` | 0.0000% | n/a | 0.0896% | 0.000% | 0.00% | 4.52% | -2.95% | 100.0% | 0.1104 |
| 15 | `TsCov(TsMad(Constant(-1.0),50),TsSkew(turnover,50),20)` | `COV(TS_MAD((-1),50),TS_SKEW(TURNOVER,50),20)` | 0.0000% | n/a | 0.0417% | 0.000% | 0.00% | 4.62% | -4.07% | 100.0% | 0.1500 |
| 16 | `TsCorr(TsMaxDiff(TsMed(market_cap,40),40),TsCov(TsSum(Constant(5.0),10),TsEMA(inventory,10),30),10)` | `CORR((TS_MEDIAN(MARKET_CAP,40)-TS_MAX(TS_MEDIAN(MARKET_CAP,40),40)),COV(SUM(5,10),EMA(INVENTORY,10),30),10)` | 0.0000% | n/a | 0.0125% | 0.000% | 0.00% | 4.76% | -4.18% | 100.0% | 0.0958 |
| 17 | `TsMean(TsMed(TsCorr(TsPctChange(book_to_market_ratio_lyr,10),TsMaxDiff(Constant(1.0),10),50),40),40)` | `MA(TS_MEDIAN(CORR(RETURNS(BOOK_TO_MARKET_RATIO_LYR,10),(1-TS_MAX(1,10)),50),40),40)` | 0.0000% | n/a | 0.0375% | 0.000% | 0.00% | 5.06% | -5.06% | 100.0% | 0.1375 |
| 18 | `Ref(TsCorr(TsMinMaxDiff(Constant(0.5),50),TsSum(ratio_pcf_ocf_ttm,10),40),50)` | `REF(CORR((TS_MAX(0.5,50)-TS_MIN(0.5,50)),SUM(RATIO_PCF_OCF_TTM,10),40),50)` | 0.0000% | n/a | 0.0854% | 0.000% | 0.00% | 5.09% | -4.90% | 100.0% | 0.1187 |
| 19 | `TsMinMaxDiff(TsCorr(Sign(TsCov(Constant(30.0),low,50)),TsDelta(TsMinDiff(amount,30),50),40),40)` | `(TS_MAX(CORR(SIGN(COV(30,LOW,50)),DIFF((AMOUNT-TS_MIN(AMOUNT,30)),50),40),40)-TS_MIN(CORR(SIGN(COV(30,LOW,50)),DIFF((AMOUNT-TS_MIN(AMOUNT,30)),50),40),40))` | 0.0000% | n/a | 0.0854% | 0.000% | 0.00% | 5.16% | -3.81% | 100.0% | 0.0979 |
| 20 | `TsMax(Sign(TsMed(TsRank(market_cap,40),40)),40)` | `TS_MAX(SIGN(TS_MEDIAN(TS_RANK(MARKET_CAP,40),40)),40)` | 0.0002% | n/a | -0.0120% | 0.035% | 0.44% | 5.22% | -3.00% | 100.0% | 0.3271 |
| 21 | `TsCorr(Ref(TsMinMaxDiff(Mul(current_assets,volume),30),50),TsVar(TsCorr(TsMax(amount,40),TsMinMaxDiff(Constant(1.0),30),10),40),50)` | `CORR(REF((TS_MAX((CURRENT_ASSETS*VOLUME),30)-TS_MIN((CURRENT_ASSETS*VOLUME),30)),50),VAR(CORR(TS_MAX(AMOUNT,40),(TS_MAX(1,30)-TS_MIN(1,30)),10),40),50)` | 0.0000% | n/a | 0.0604% | 0.000% | 0.00% | 5.20% | -5.74% | 100.0% | 0.1063 |
| 22 | `Ref(TsMad(TsCorr(TsMin(TsWMA(TsStd(Constant(2.0),20),50),10),TsMinMaxDiff(TsDiv(Greater(volume,amount),30),40),20),20),40)` | `REF(TS_MAD(CORR(TS_MIN(WMA(STDDEV(2,20),50),10),(TS_MAX((MAX(VOLUME,AMOUNT)/MA(MAX(VOLUME,AMOUNT),30)),40)-TS_MIN((MAX(VOLUME,AMOUNT)/MA(MAX(VOLUME,AMOUNT),30)),40)),20),20),40)` | 0.0000% | n/a | 0.0917% | 0.000% | 0.00% | 5.30% | -4.57% | 100.0% | 0.1229 |
| 23 | `TsMed(gr_total_asset_lyr,20)` | `TS_MEDIAN(GR_TOTAL_ASSET_LYR,20)` | 0.0002% | n/a | -0.0131% | -0.039% | 0.38% | 5.58% | -5.00% | 100.0% | 0.3914 |
| 24 | `TsMin(TsRank(TsSum(TsCov(Constant(-2.0),book_to_market_ratio_lyr,10),50),20),30)` | `TS_MIN(TS_RANK(SUM(COV((-2),BOOK_TO_MARKET_RATIO_LYR,10),50),20),30)` | 0.0000% | n/a | -0.0033% | 0.034% | 0.40% | 5.78% | -6.11% | 100.0% | 0.8518 |
| 25 | `TsMin(TsMin(TsMinMaxDiff(TsVar(ratio_sp_ttm,20),30),50),50)` | `TS_MIN(TS_MIN((TS_MAX(VAR(RATIO_SP_TTM,20),30)-TS_MIN(VAR(RATIO_SP_TTM,20),30)),50),50)` | 0.0001% | n/a | 0.0060% | -0.098% | 0.23% | 6.10% | -2.89% | 100.0% | 0.5681 |
| 26 | `TsMed(TsStd(Mul(Abs(Constant(2.0)),TsMaxDiff(market_cap,10)),30),50)` | `TS_MEDIAN(STDDEV((ABS(2)*(MARKET_CAP-TS_MAX(MARKET_CAP,10))),30),50)` | 0.0034% | n/a | -0.0567% | -0.139% | 0.43% | 7.72% | -11.72% | 100.0% | 0.5825 |
| 27 | `TsMad(TsStd(TsMinMaxDiff(amount,40),20),40)` | `TS_MAD(STDDEV((TS_MAX(AMOUNT,40)-TS_MIN(AMOUNT,40)),20),40)` | 0.0143% | n/a | -0.0660% | -0.371% | 0.58% | 17.21% | -18.79% | 100.0% | 0.4959 |
| 28 | `TsRank(Ref(TsSkew(TsKurt(inventory,30),30),30),40)` | `TS_RANK(REF(TS_SKEW(TS_KURT(INVENTORY,30),30),30),40)` | 0.0002% | n/a | 0.0779% | 0.063% | 0.03% | 14.45% | -5.33% | 100.0% | 0.2750 |
| 29 | `Ref(Sign(TsEMA(TsSum(TsVar(current_liabilities,10),50),40)),40)` | `REF(SIGN(EMA(SUM(VAR(CURRENT_LIABILITIES,10),50),40)),40)` | 0.0001% | n/a | -0.0023% | 0.080% | 0.43% | 15.31% | -2.02% | 100.0% | 0.4459 |
| 30 | `Ref(Greater(TsMad(current_assets,50),Mul(book_to_market_ratio_lf,ratio_sp_ttm)),40)` | `REF(MAX(TS_MAD(CURRENT_ASSETS,50),(BOOK_TO_MARKET_RATIO_LF*RATIO_SP_TTM)),40)` | 0.0000% | n/a | 0.0008% | -0.080% | 0.42% | 16.88% | -8.69% | 100.0% | 0.6729 |
| 31 | `TsMad(TsSum(TsMad(TsSum(market_cap,10),20),20),40)` | `TS_MAD(SUM(TS_MAD(SUM(MARKET_CAP,10),20),20),40)` | 0.0033% | n/a | -0.0546% | -0.149% | 0.41% | 18.20% | -12.86% | 100.0% | 0.8319 |
| 32 | `TsWMA(Add(TsStd(ratio_sp_ttm,30),TsSkew(book_to_market_ratio_lf,40)),20)` | `WMA((STDDEV(RATIO_SP_TTM,30)+TS_SKEW(BOOK_TO_MARKET_RATIO_LF,40)),20)` | 0.0001% | n/a | 0.0041% | -0.066% | 0.41% | 17.82% | -6.05% | 100.0% | 0.8801 |
| 33 | `TsMin(TsMax(TsVar(TsMinMaxDiff(inventory,20),30),40),40)` | `TS_MIN(TS_MAX(VAR((TS_MAX(INVENTORY,20)-TS_MIN(INVENTORY,20)),30),40),40)` | 0.0000% | n/a | -0.0101% | -0.006% | 0.00% | 18.18% | -7.30% | 100.0% | 0.5268 |
| 34 | `TsMin(TsMad(close,40),10)` | `TS_MIN(TS_MAD(CLOSE,40),10)` | 0.0029% | n/a | -0.0514% | -0.119% | 0.47% | 19.18% | -10.30% | 100.0% | 0.8843 |
| 35 | `TsMed(Mul(TsIr(ratio_sp_ttm,40),TsMin(ratio_pcf_ocf_ttm,50)),30)` | `TS_MEDIAN(((MA(RATIO_SP_TTM,40)/STDDEV(RATIO_SP_TTM,40))*TS_MIN(RATIO_PCF_OCF_TTM,50)),30)` | 0.0000% | n/a | 0.0022% | -0.080% | 0.09% | 19.20% | -5.73% | 100.0% | 0.1549 |
| 36 | `TsWMA(TsMad(Ref(ratio_bm_ttm,50),20),50)` | `WMA(TS_MAD(REF(RATIO_BM_TTM,50),20),50)` | 0.0000% | n/a | 0.0113% | 0.001% | 0.40% | 20.15% | -6.84% | 100.0% | 0.6952 |
| 37 | `TsCov(TsMinMaxDiff(TsMed(TsRank(TsMean(book_to_market_ratio_lyr,10),20),10),40),TsSum(TsEMA(TsDelta(Sign(turnover),30),30),50),30)` | `COV((TS_MAX(TS_MEDIAN(TS_RANK(MA(BOOK_TO_MARKET_RATIO_LYR,10),20),10),40)-TS_MIN(TS_MEDIAN(TS_RANK(MA(BOOK_TO_MARKET_RATIO_LYR,10),20),10),40)),SUM(EMA(DIFF(SIGN(TURNOVER),30),30),50),30)` | 0.0002% | n/a | -0.0047% | -0.229% | 0.18% | 20.24% | -7.03% | 100.0% | 0.1104 |
| 38 | `TsMad(TsMinMaxDiff(TsMaxDiff(inventory,30),20),40)` | `TS_MAD((TS_MAX((INVENTORY-TS_MAX(INVENTORY,30)),20)-TS_MIN((INVENTORY-TS_MAX(INVENTORY,30)),20)),40)` | 0.0002% | n/a | -0.0032% | -0.154% | 0.36% | 20.25% | -9.56% | 100.0% | 0.2423 |
| 39 | `TsMinMaxDiff(TsIr(TsIr(TsVar(amount,50),50),40),50)` | `(TS_MAX((MA((MA(VAR(AMOUNT,50),50)/STDDEV(VAR(AMOUNT,50),50)),40)/STDDEV((MA(VAR(AMOUNT,50),50)/STDDEV(VAR(AMOUNT,50),50)),40)),50)-TS_MIN((MA((MA(VAR(AMOUNT,50),50)/STDDEV(VAR(AMOUNT,50),50)),40)/STDDEV((MA(VAR(AMOUNT,50),50)/STDDEV(VAR(AMOUNT,50),50)),40)),50))` | 0.0001% | n/a | 0.0054% | 0.104% | 0.27% | 20.39% | -1.08% | 100.0% | 0.1208 |
| 40 | `TsVar(TsPctChange(TsKurt(TsCorr(Sub(turnover,Constant(1.0)),TsCorr(ratio_pcf_ocf_ttm,high,20),30),10),50),50)` | `VAR(RETURNS(TS_KURT(CORR((TURNOVER-1),CORR(RATIO_PCF_OCF_TTM,HIGH,20),30),10),50),50)` | 0.0000% | n/a | 0.0016% | -0.066% | 0.03% | 20.80% | -3.30% | 100.0% | 0.1167 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `TsMax(TsSum(TsEMA(current_assets,50),50),10)`
- PandaAI formula: `TS_MAX(SUM(EMA(CURRENT_ASSETS,50),50),10)`
- Full aligned net excess: `-7.12%`
- Early net excess through 2024-12-31: `-5.15%`
- Late net excess from 2025-01-01: `-11.21%`
- Full S_i: `0.0006%`; turnover `0.79%`; rank IC `-0.0156%`; ICIR `-0.085%`; win `0.43%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
