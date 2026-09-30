# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `690`; invalid: `0`
- GP search terminals: `371` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `1` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `TsMax(TsMax(cal_12d_vol_ma,20),10)` | `TS_MAX(TS_MAX(CAL_12D_VOL_MA,20),10)` | 0.0107% | n/a | -0.0533% | -0.371% | 0.54% | 13.14% | -20.04% | 100.0% | n/a |
| 2 | `TsMax(TsMax(cal_20d_vol_std,30),10)` | `TS_MAX(TS_MAX(CAL_20D_VOL_STD,30),10)` | 0.0098% | n/a | -0.0506% | -0.364% | 0.53% | 11.91% | -19.08% | 100.0% | 0.9714 |
| 3 | `TsMax(cal_20d_vol_std,50)` | `TS_MAX(CAL_20D_VOL_STD,50)` | 0.0096% | n/a | -0.0488% | -0.370% | 0.53% | 10.22% | -18.23% | 100.0% | 0.9882 |
| 4 | `TsMax(TsMax(cal_20d_vol_std,30),30)` | `TS_MAX(TS_MAX(CAL_20D_VOL_STD,30),30)` | 0.0090% | n/a | -0.0471% | -0.366% | 0.53% | 9.16% | -18.16% | 100.0% | 0.9919 |
| 5 | `TsMax(TsMax(TsMax(cal_12d_vol_ma,20),30),10)` | `TS_MAX(TS_MAX(TS_MAX(CAL_12D_VOL_MA,20),30),10)` | 0.0089% | n/a | -0.0471% | -0.361% | 0.53% | 8.88% | -18.31% | 100.0% | 0.9872 |
| 6 | `TsMax(Sub(TsMax(TsSum(cal_20d_vol_std,10),30),TsEMA(TsMinMaxDiff(mtm,40),30)),10)` | `TS_MAX((TS_MAX(SUM(CAL_20D_VOL_STD,10),30)-EMA((TS_MAX(MTM,40)-TS_MIN(MTM,40)),30)),10)` | 0.0084% | n/a | -0.0468% | -0.349% | 0.52% | 11.66% | -17.33% | 100.0% | 0.9906 |
| 7 | `Sub(TsMax(TsMax(TsMax(TsMax(cal_20d_vol_std,30),10),30),10),TsEMA(TsMinMaxDiff(mtm,40),30))` | `(TS_MAX(TS_MAX(TS_MAX(TS_MAX(CAL_20D_VOL_STD,30),10),30),10)-EMA((TS_MAX(MTM,40)-TS_MIN(MTM,40)),30))` | 0.0083% | n/a | -0.0449% | -0.354% | 0.53% | 7.73% | -17.06% | 100.0% | 0.9802 |
| 8 | `TsMax(TsMax(TsMax(cal_20d_vol_std,30),10),30)` | `TS_MAX(TS_MAX(TS_MAX(CAL_20D_VOL_STD,30),10),30)` | 0.0083% | n/a | -0.0454% | -0.353% | 0.52% | 8.47% | -17.19% | 100.0% | 0.9931 |
| 9 | `TsMax(TsMinMaxDiff(cal_20d_vol_std,30),40)` | `TS_MAX((TS_MAX(CAL_20D_VOL_STD,30)-TS_MIN(CAL_20D_VOL_STD,30)),40)` | 0.0083% | n/a | -0.0444% | -0.349% | 0.53% | 9.88% | -16.89% | 100.0% | 0.9930 |
| 10 | `TsMax(TsMinMaxDiff(cal_20d_vol_std,50),30)` | `TS_MAX((TS_MAX(CAL_20D_VOL_STD,50)-TS_MIN(CAL_20D_VOL_STD,50)),30)` | 0.0076% | n/a | -0.0422% | -0.340% | 0.53% | 8.84% | -16.50% | 100.0% | 0.9930 |
| 11 | `Sub(TsMax(TsSum(cal_20d_vol_std,10),30),TsEMA(TsIr(cal_limit_down,30),30))` | `(TS_MAX(SUM(CAL_20D_VOL_STD,10),30)-EMA((MA(CAL_LIMIT_DOWN,30)/STDDEV(CAL_LIMIT_DOWN,30)),30))` | 0.0089% | n/a | -0.0470% | -0.344% | 0.55% | 13.43% | -17.41% | 100.0% | 0.9916 |
| 12 | `TsMax(TsMax(TsMax(cal_20d_vol_std,30),10),50)` | `TS_MAX(TS_MAX(TS_MAX(CAL_20D_VOL_STD,30),10),50)` | 0.0070% | n/a | -0.0406% | -0.335% | 0.52% | 6.94% | -16.47% | 100.0% | 0.9907 |
| 13 | `TsMax(TsWMA(cal_20d_vol_std,30),50)` | `TS_MAX(WMA(CAL_20D_VOL_STD,30),50)` | 0.0068% | n/a | -0.0409% | -0.328% | 0.51% | 9.22% | -15.50% | 100.0% | 0.9931 |
| 14 | `TsMax(TsMean(cal_20d_vol_std,20),30)` | `TS_MAX(MA(CAL_20D_VOL_STD,20),30)` | 0.0068% | n/a | -0.0431% | -0.316% | 0.50% | 12.81% | -16.39% | 100.0% | 0.9965 |
| 15 | `TsMax(TsMax(TsMax(TsSum(cal_20d_vol_std,10),30),10),30)` | `TS_MAX(TS_MAX(TS_MAX(SUM(CAL_20D_VOL_STD,10),30),10),30)` | 0.0067% | n/a | -0.0404% | -0.327% | 0.51% | 8.32% | -15.20% | 100.0% | 0.9947 |
| 16 | `TsMax(TsMax(TsMean(cal_20d_vol_std,20),30),10)` | `TS_MAX(TS_MAX(MA(CAL_20D_VOL_STD,20),30),10)` | 0.0067% | n/a | -0.0418% | -0.325% | 0.49% | 11.27% | -15.83% | 100.0% | 0.9941 |
| 17 | `TsMax(TsMax(TsMax(TsMax(TsSum(cal_20d_vol_std,10),30),10),30),10)` | `TS_MAX(TS_MAX(TS_MAX(TS_MAX(SUM(CAL_20D_VOL_STD,10),30),10),30),10)` | 0.0064% | n/a | -0.0384% | -0.321% | 0.52% | 7.61% | -15.26% | 100.0% | 0.9953 |
| 18 | `Sub(TsVar(TsDelta(Constant(-30.0),40),20),TsEMA(TsMax(TsSum(cal_20d_vol_std,10),30),30))` | `(VAR(DIFF((-30),40),20)-EMA(TS_MAX(SUM(CAL_20D_VOL_STD,10),30),30))` | 0.0063% | n/a | 0.0410% | 0.316% | 0.48% | 12.77% | 4.07% | 100.0% | -0.9590 |
| 19 | `TsMax(TsMax(vol30,30),10)` | `TS_MAX(TS_MAX(VOL30,30),10)` | 0.0061% | n/a | -0.0551% | -0.207% | 0.53% | 12.27% | -17.39% | 100.0% | 0.2996 |
| 20 | `Rank(TsSum(cal_20d_vol_std,50))` | `RANK(SUM(CAL_20D_VOL_STD,50))` | 0.0055% | n/a | -0.0444% | -0.253% | 0.49% | 11.20% | -16.83% | 100.0% | 0.9918 |
| 21 | `TsMax(TsEMA(cal_10d_avg_turnover,50),30)` | `TS_MAX(EMA(CAL_10D_AVG_TURNOVER,50),30)` | 0.0052% | n/a | -0.0522% | -0.195% | 0.52% | 12.02% | -16.49% | 100.0% | 0.9945 |
| 22 | `TsMax(TsStd(TsCorr(vol30,ratio_pb_lf,30),50),10)` | `TS_MAX(STDDEV(CORR(VOL30,RATIO_PB_LF,30),50),10)` | 0.0050% | n/a | -0.0577% | -0.211% | 0.41% | 11.73% | -13.41% | 100.0% | 0.8012 |
| 23 | `TsMax(TsMean(TsMax(TsMax(TsSum(cal_20d_vol_std,10),30),10),20),30)` | `TS_MAX(MA(TS_MAX(TS_MAX(SUM(CAL_20D_VOL_STD,10),30),10),20),30)` | 0.0050% | n/a | -0.0342% | -0.296% | 0.49% | 7.93% | -14.14% | 100.0% | 0.9945 |
| 24 | `TsMax(TsSum(TsMax(TsSum(cal_20d_vol_std,10),30),50),10)` | `TS_MAX(SUM(TS_MAX(SUM(CAL_20D_VOL_STD,10),30),50),10)` | 0.0049% | n/a | -0.0337% | -0.296% | 0.49% | 9.27% | -14.22% | 100.0% | 0.9951 |
| 25 | `Sub(TsVar(TsDelta(Constant(-30.0),40),20),TsEMA(TsEMA(cal_10d_avg_turnover,50),30))` | `(VAR(DIFF((-30),40),20)-EMA(EMA(CAL_10D_AVG_TURNOVER,50),30))` | 0.0049% | n/a | 0.0514% | 0.187% | 0.51% | 8.29% | -2.35% | 100.0% | 0.2752 |
| 26 | `TsMax(TsMinMaxDiff(mtm,40),30)` | `TS_MAX((TS_MAX(MTM,40)-TS_MIN(MTM,40)),30)` | 0.0046% | n/a | -0.0563% | -0.154% | 0.53% | 8.50% | -11.42% | 100.0% | 0.5310 |
| 27 | `TsMax(TsMinMaxDiff(mabias,30),30)` | `TS_MAX((TS_MAX(MABIAS,30)-TS_MIN(MABIAS,30)),30)` | 0.0046% | n/a | -0.0576% | -0.153% | 0.52% | 9.65% | -11.96% | 100.0% | 0.9774 |
| 28 | `wma5` | `WMA5` | 0.0046% | n/a | -0.0496% | -0.175% | 0.53% | 6.22% | -12.81% | 100.0% | 0.8972 |
| 29 | `Sub(TsVar(TsDelta(Constant(-30.0),40),20),TsEMA(TsMinMaxDiff(mtm,40),30))` | `(VAR(DIFF((-30),40),20)-EMA((TS_MAX(MTM,40)-TS_MIN(MTM,40)),30))` | 0.0043% | n/a | 0.0551% | 0.150% | 0.52% | 11.03% | 2.83% | 100.0% | 0.3720 |
| 30 | `Add(TsDelta(TsMinMaxDiff(Constant(-30.0),10),40),TsEMA(TsMinMaxDiff(mtm,40),30))` | `(DIFF((TS_MAX((-30),10)-TS_MIN((-30),10)),40)+EMA((TS_MAX(MTM,40)-TS_MIN(MTM,40)),30))` | 0.0043% | n/a | -0.0551% | -0.150% | 0.52% | 9.65% | -11.46% | 100.0% | 0.9884 |
| 31 | `TsMax(mcst,30)` | `TS_MAX(MCST,30)` | 0.0039% | n/a | -0.0528% | -0.161% | 0.46% | 4.20% | -13.18% | 100.0% | 0.9793 |
| 32 | `TsSum(TsEMA(cal_10d_avg_turnover,50),50)` | `SUM(EMA(CAL_10D_AVG_TURNOVER,50),50)` | 0.0039% | n/a | -0.0442% | -0.164% | 0.53% | 11.50% | -13.09% | 100.0% | 0.9775 |
| 33 | `TsMax(Sub(TsVar(TsDelta(Constant(-30.0),40),20),TsEMA(TsMinMaxDiff(mtm,40),30)),30)` | `TS_MAX((VAR(DIFF((-30),40),20)-EMA((TS_MAX(MTM,40)-TS_MIN(MTM,40)),30)),30)` | 0.0039% | n/a | 0.0492% | 0.152% | 0.52% | 9.64% | 2.00% | 100.0% | 0.9734 |
| 34 | `TsMax(TsStd(TsCov(TsMean(vma30,50),TsMaxDiff(accer,20),20),50),10)` | `TS_MAX(STDDEV(COV(MA(VMA30,50),(ACCER-TS_MAX(ACCER,20)),20),50),10)` | 0.0038% | n/a | -0.0517% | -0.151% | 0.49% | 11.75% | -9.95% | 100.0% | 0.8927 |
| 35 | `TsMax(TsMinMaxDiff(vma20,40),30)` | `TS_MAX((TS_MAX(VMA20,40)-TS_MIN(VMA20,40)),30)` | 0.0038% | n/a | -0.0519% | -0.144% | 0.51% | 10.23% | -11.25% | 100.0% | 0.9471 |
| 36 | `TsMax(Abs(ma10),10)` | `TS_MAX(ABS(MA10),10)` | 0.0037% | n/a | -0.0461% | -0.157% | 0.52% | 5.11% | -11.90% | 100.0% | 0.9981 |
| 37 | `TsMax(TsSum(TsEMA(cal_10d_avg_turnover,50),50),10)` | `TS_MAX(SUM(EMA(CAL_10D_AVG_TURNOVER,50),50),10)` | 0.0037% | n/a | -0.0430% | -0.163% | 0.53% | 10.87% | -13.28% | 100.0% | 0.9978 |
| 38 | `TsMax(SLog1p(high),30)` | `TS_MAX((SIGN(HIGH)*LOG(1+ABS(HIGH))),30)` | 0.0034% | n/a | -0.0475% | -0.142% | 0.51% | 5.08% | -11.64% | 100.0% | 0.9975 |
| 39 | `TsMin(low,20)` | `TS_MIN(LOW,20)` | 0.0034% | n/a | -0.0430% | -0.159% | 0.49% | 4.89% | -11.95% | 100.0% | 0.9965 |
| 40 | `Sub(TsVar(TsDelta(Constant(-30.0),40),20),TsMed(wma5,20))` | `(VAR(DIFF((-30),40),20)-TS_MEDIAN(WMA5,20))` | 0.0033% | n/a | 0.0435% | 0.151% | 0.50% | 4.27% | 3.08% | 100.0% | 0.9085 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `TsMax(TsMax(cal_12d_vol_ma,20),10)`
- PandaAI formula: `TS_MAX(TS_MAX(CAL_12D_VOL_MA,20),10)`
- Full aligned net excess: `-20.04%`
- Early net excess through 2024-12-31: `-20.06%`
- Late net excess from 2025-01-01: `-19.97%`
- Full S_i: `0.0107%`; turnover `13.14%`; rank IC `-0.0533%`; ICIR `-0.371%`; win `0.54%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
