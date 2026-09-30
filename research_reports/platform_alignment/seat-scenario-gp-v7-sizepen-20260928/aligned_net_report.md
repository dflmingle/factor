# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `914`; invalid: `0`
- GP search terminals: `371` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `1` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `TsSum(cal_10d_vol_std,50)` | `SUM(CAL_10D_VOL_STD,50)` | 0.0083% | n/a | -0.0473% | -0.339% | 0.52% | 11.70% | -17.97% | 100.0% | n/a |
| 2 | `TsEMA(TsSum(cal_10d_vol_std,50),40)` | `EMA(SUM(CAL_10D_VOL_STD,50),40)` | 0.0064% | n/a | -0.0398% | -0.316% | 0.51% | 9.29% | -16.07% | 100.0% | 0.9857 |
| 3 | `TsMax(macd_diff,50)` | `TS_MAX(MACD_DIFF,50)` | 0.0091% | n/a | -0.0722% | -0.226% | 0.56% | 14.93% | -14.10% | 100.0% | 0.0521 |
| 4 | `TsEMA(volume,40)` | `EMA(VOLUME,40)` | 0.0130% | n/a | -0.0564% | -0.384% | 0.60% | 13.39% | -21.82% | 100.0% | 0.9752 |
| 5 | `TsEMA(volume,50)` | `EMA(VOLUME,50)` | 0.0119% | n/a | -0.0539% | -0.373% | 0.59% | 11.58% | -20.95% | 100.0% | 0.9988 |
| 6 | `TsSum(TsSum(cal_10d_vol_std,50),50)` | `SUM(SUM(CAL_10D_VOL_STD,50),50)` | 0.0053% | n/a | -0.0356% | -0.302% | 0.49% | 8.19% | -14.46% | 100.0% | 0.9929 |
| 7 | `Log(pb_ratio_ttm)` | `LOG(PB_RATIO_TTM)` | 0.0052% | n/a | -0.0596% | -0.185% | 0.48% | 8.07% | -13.15% | 100.0% | 0.4520 |
| 8 | `TsMean(volume,30)` | `MA(VOLUME,30)` | 0.0117% | n/a | -0.0540% | -0.367% | 0.59% | 13.43% | -20.60% | 100.0% | 0.9980 |
| 9 | `TsMax(volt20,50)` | `TS_MAX(VOLT20,50)` | 0.0049% | n/a | -0.0586% | -0.157% | 0.53% | 9.37% | -11.20% | 100.0% | 0.7368 |
| 10 | `TsStd(cal_10d_vol_std,50)` | `STDDEV(CAL_10D_VOL_STD,50)` | 0.0081% | n/a | -0.0455% | -0.330% | 0.54% | 15.20% | -16.40% | 100.0% | 0.9674 |
| 11 | `cal_limit_up` | `CAL_LIMIT_UP` | 0.0046% | n/a | -0.0499% | -0.176% | 0.53% | 6.70% | -12.88% | 100.0% | 0.8911 |
| 12 | `Abs(bbiboll_up)` | `ABS(BBIBOLL_UP)` | 0.0045% | n/a | -0.0506% | -0.168% | 0.53% | 8.82% | -13.74% | 100.0% | 0.9962 |
| 13 | `TsWMA(pb_ratio_ttm,10)` | `WMA(PB_RATIO_TTM,10)` | 0.0043% | n/a | -0.0567% | -0.276% | 0.28% | 7.16% | -11.74% | 100.0% | 0.9987 |
| 14 | `TsSum(ratio_pb_lyr,50)` | `SUM(RATIO_PB_LYR,50)` | 0.0042% | n/a | -0.0479% | -0.216% | 0.40% | 4.03% | -10.76% | 100.0% | 0.9773 |
| 15 | `TsWMA(TsMinMaxDiff(macd_hist,40),40)` | `WMA((TS_MAX(MACD_HIST,40)-TS_MIN(MACD_HIST,40)),40)` | 0.0041% | n/a | -0.0545% | -0.151% | 0.50% | 9.30% | -10.89% | 100.0% | 0.9801 |
| 16 | `TsMax(cal_limit_up,20)` | `TS_MAX(CAL_LIMIT_UP,20)` | 0.0039% | n/a | -0.0475% | -0.156% | 0.53% | 5.47% | -11.81% | 100.0% | 0.9980 |
| 17 | `TsMed(cal_limit_up,10)` | `TS_MEDIAN(CAL_LIMIT_UP,10)` | 0.0039% | n/a | -0.0462% | -0.163% | 0.52% | 5.73% | -12.08% | 100.0% | 0.9985 |
| 18 | `TsSum(vol60,40)` | `SUM(VOL60,40)` | 0.0038% | n/a | -0.0439% | -0.164% | 0.53% | 10.68% | -13.15% | 100.0% | 0.3537 |
| 19 | `TsMinMaxDiff(macd_hist,40)` | `(TS_MAX(MACD_HIST,40)-TS_MIN(MACD_HIST,40))` | 0.0048% | n/a | -0.0601% | -0.157% | 0.51% | 13.65% | -11.07% | 100.0% | 0.9772 |
| 20 | `TsSum(volume,50)` | `SUM(VOLUME,50)` | 0.0093% | n/a | -0.0475% | -0.344% | 0.57% | 9.32% | -19.15% | 100.0% | 0.9955 |
| 21 | `TsMed(TsMinMaxDiff(macd_hist,40),10)` | `TS_MEDIAN((TS_MAX(MACD_HIST,40)-TS_MIN(MACD_HIST,40)),10)` | 0.0041% | n/a | -0.0562% | -0.144% | 0.51% | 13.29% | -11.14% | 100.0% | 0.9890 |
| 22 | `TsEMA(Log(pb_ratio_ttm),40)` | `EMA(LOG(PB_RATIO_TTM),40)` | 0.0036% | n/a | -0.0509% | -0.148% | 0.48% | 4.69% | -10.25% | 100.0% | 0.9966 |
| 23 | `TsSum(TsMad(TsMed(cal_limit_up,10),20),50)` | `SUM(TS_MAD(TS_MEDIAN(CAL_LIMIT_UP,10),20),50)` | 0.0034% | n/a | -0.0510% | -0.137% | 0.49% | 10.02% | -10.55% | 100.0% | 0.9818 |
| 24 | `TsSum(TsMad(TsMinMaxDiff(macd_hist,40),20),50)` | `SUM(TS_MAD((TS_MAX(MACD_HIST,40)-TS_MIN(MACD_HIST,40)),20),50)` | 0.0034% | n/a | -0.0494% | -0.138% | 0.49% | 11.96% | -9.72% | 100.0% | 0.9205 |
| 25 | `TsSum(TsStd(sws,50),50)` | `SUM(STDDEV(SWS,50),50)` | 0.0033% | n/a | -0.0491% | -0.136% | 0.50% | 8.78% | -9.86% | 100.0% | 0.9703 |
| 26 | `TsMax(vol120,30)` | `TS_MAX(VOL120,30)` | 0.0033% | n/a | -0.0410% | -0.149% | 0.53% | 6.56% | -12.22% | 100.0% | 0.9587 |
| 27 | `TsWMA(cal_limit_up,40)` | `WMA(CAL_LIMIT_UP,40)` | 0.0032% | n/a | -0.0433% | -0.148% | 0.50% | 3.80% | -10.63% | 100.0% | 0.9989 |
| 28 | `TsMinMaxDiff(vma120,50)` | `(TS_MAX(VMA120,50)-TS_MIN(VMA120,50))` | 0.0032% | n/a | -0.0465% | -0.149% | 0.46% | 10.47% | -8.90% | 100.0% | 0.8438 |
| 29 | `TsEMA(TsEMA(volume,40),40)` | `EMA(EMA(VOLUME,40),40)` | 0.0085% | n/a | -0.0452% | -0.336% | 0.56% | 9.14% | -18.42% | 100.0% | 0.9988 |
| 30 | `TsMed(TsMinMaxDiff(vma120,50),10)` | `TS_MEDIAN((TS_MAX(VMA120,50)-TS_MIN(VMA120,50)),10)` | 0.0031% | n/a | -0.0452% | -0.146% | 0.47% | 10.41% | -8.90% | 100.0% | 0.9942 |
| 31 | `TsEMA(boll_up,30)` | `EMA(BOLL_UP,30)` | 0.0030% | n/a | -0.0434% | -0.140% | 0.49% | 4.35% | -10.57% | 100.0% | 0.9987 |
| 32 | `TsMin(book_to_market_ratio_ttm,20)` | `TS_MIN(BOOK_TO_MARKET_RATIO_TTM,20)` | 0.0030% | n/a | 0.0568% | 0.107% | 0.49% | 4.65% | 0.51% | 100.0% | 0.1368 |
| 33 | `TsVar(hma120,40)` | `VAR(HMA120,40)` | 0.0029% | n/a | -0.0461% | -0.169% | 0.38% | 12.92% | -8.80% | 100.0% | 0.9820 |
| 34 | `TsMed(book_to_market_ratio_lf,10)` | `TS_MEDIAN(BOOK_TO_MARKET_RATIO_LF,10)` | 0.0029% | n/a | 0.0558% | 0.110% | 0.48% | 4.89% | 1.18% | 100.0% | 0.9957 |
| 35 | `TsMean(TsMin(vol20,40),40)` | `MA(TS_MIN(VOL20,40),40)` | 0.0029% | n/a | -0.0368% | -0.146% | 0.54% | 11.93% | -11.16% | 100.0% | 0.9630 |
| 36 | `TsSum(bbiboll_up,50)` | `SUM(BBIBOLL_UP,50)` | 0.0028% | n/a | -0.0413% | -0.137% | 0.50% | 3.59% | -10.10% | 100.0% | 0.9985 |
| 37 | `TsSum(cal_limit_up,50)` | `SUM(CAL_LIMIT_UP,50)` | 0.0027% | n/a | -0.0401% | -0.141% | 0.48% | 3.16% | -10.12% | 100.0% | 0.9988 |
| 38 | `TsMed(cal_10d_vol_std,40)` | `TS_MEDIAN(CAL_10D_VOL_STD,40)` | 0.0091% | n/a | -0.0490% | -0.337% | 0.55% | 15.77% | -19.34% | 100.0% | 0.9771 |
| 39 | `TsSum(TsMad(TsMin(cal_limit_up,10),20),50)` | `SUM(TS_MAD(TS_MIN(CAL_LIMIT_UP,10),20),50)` | 0.0025% | n/a | -0.0457% | -0.118% | 0.47% | 9.93% | -9.42% | 100.0% | 0.9851 |
| 40 | `TsMax(TsMed(vma20,40),40)` | `TS_MAX(TS_MEDIAN(VMA20,40),40)` | 0.0025% | n/a | -0.0371% | -0.137% | 0.49% | 3.27% | -9.88% | 100.0% | 0.9969 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `TsSum(cal_10d_vol_std,50)`
- PandaAI formula: `SUM(CAL_10D_VOL_STD,50)`
- Full aligned net excess: `-17.97%`
- Early net excess through 2024-12-31: `-16.30%`
- Late net excess from 2025-01-01: `-21.44%`
- Full S_i: `0.0083%`; turnover `11.70%`; rank IC `-0.0473%`; ICIR `-0.339%`; win `0.52%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
