# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `1410`; invalid: `0`
- GP search terminals: `1149` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `TsEMA(TsStd(mcst,10),40)` | `EMA(STDDEV(MCST,10),40)` | 0.0096% | n/a | -0.0771% | -0.227% | 0.55% | 12.29% | -16.47% | 100.0% | n/a |
| 2 | `TsEMA(TsStd(mcst,10),50)` | `EMA(STDDEV(MCST,10),50)` | 0.0092% | n/a | -0.0751% | -0.219% | 0.56% | 10.92% | -16.44% | 100.0% | 0.9982 |
| 3 | `TsMax(TsStd(mcst,10),30)` | `TS_MAX(STDDEV(MCST,10),30)` | 0.0092% | n/a | -0.0773% | -0.217% | 0.55% | 13.56% | -15.56% | 100.0% | 0.9823 |
| 4 | `TsEMA(TsMaxDiff(mcst,10),40)` | `EMA((MCST-TS_MAX(MCST,10)),40)` | 0.0080% | n/a | 0.0713% | 0.214% | 0.53% | 10.24% | 3.59% | 100.0% | -0.9593 |
| 5 | `TsMax(TsStd(mcst,10),50)` | `TS_MAX(STDDEV(MCST,10),50)` | 0.0079% | n/a | -0.0722% | -0.202% | 0.54% | 10.00% | -13.67% | 100.0% | 0.9691 |
| 6 | `TsMean(TsStd(mcst,10),40)` | `MA(STDDEV(MCST,10),40)` | 0.0078% | n/a | -0.0715% | -0.205% | 0.53% | 10.49% | -15.40% | 100.0% | 0.9964 |
| 7 | `TsWMA(TsWMA(TsStd(mcst,10),40),20)` | `WMA(WMA(STDDEV(MCST,10),40),20)` | 0.0076% | n/a | -0.0704% | -0.203% | 0.53% | 11.98% | -14.41% | 100.0% | 0.9980 |
| 8 | `TsMed(TsStd(mcst,10),50)` | `TS_MEDIAN(STDDEV(MCST,10),50)` | 0.0073% | n/a | -0.0665% | -0.198% | 0.55% | 9.77% | -15.13% | 100.0% | 0.9836 |
| 9 | `TsMinMaxDiff(TsMinDiff(mcst,20),30)` | `(TS_MAX((MCST-TS_MIN(MCST,20)),30)-TS_MIN((MCST-TS_MIN(MCST,20)),30))` | 0.0098% | n/a | -0.0801% | -0.225% | 0.54% | 14.75% | -16.77% | 100.0% | 0.9713 |
| 10 | `TsMin(TsMaxDiff(mcst,30),30)` | `TS_MIN((MCST-TS_MAX(MCST,30)),30)` | 0.0070% | n/a | 0.0693% | 0.194% | 0.52% | 10.45% | 3.25% | 100.0% | 0.9765 |
| 11 | `TsSum(TsMinMaxDiff(mcst,40),10)` | `SUM((TS_MAX(MCST,40)-TS_MIN(MCST,40)),10)` | 0.0070% | n/a | -0.0704% | -0.191% | 0.52% | 12.96% | -13.78% | 100.0% | 0.9884 |
| 12 | `TsEMA(TsMinDiff(mcst,10),40)` | `EMA((MCST-TS_MIN(MCST,10)),40)` | 0.0104% | n/a | -0.0799% | -0.234% | 0.56% | 15.37% | -17.00% | 100.0% | 0.9830 |
| 13 | `TsEMA(TsEMA(TsStd(mcst,10),40),40)` | `EMA(EMA(STDDEV(MCST,10),40),40)` | 0.0068% | n/a | -0.0673% | -0.192% | 0.53% | 9.35% | -13.43% | 100.0% | 0.9946 |
| 14 | `TsMean(TsMaxDiff(mcst,10),40)` | `MA((MCST-TS_MAX(MCST,10)),40)` | 0.0067% | n/a | 0.0673% | 0.197% | 0.51% | 8.49% | 3.38% | 100.0% | 0.9923 |
| 15 | `TsWMA(TsStd(mcst,40),20)` | `WMA(STDDEV(MCST,40),20)` | 0.0067% | n/a | -0.0684% | -0.190% | 0.52% | 12.61% | -12.44% | 100.0% | 0.9969 |
| 16 | `TsMinMaxDiff(TsMaxDiff(mcst,30),50)` | `(TS_MAX((MCST-TS_MAX(MCST,30)),50)-TS_MIN((MCST-TS_MAX(MCST,30)),50))` | 0.0066% | n/a | -0.0678% | -0.186% | 0.53% | 8.76% | -12.12% | 100.0% | 0.9660 |
| 17 | `TsMax(TsStd(mcst,40),40)` | `TS_MAX(STDDEV(MCST,40),40)` | 0.0065% | n/a | -0.0682% | -0.186% | 0.52% | 8.24% | -12.10% | 100.0% | 0.9728 |
| 18 | `TsMin(TsStd(mcst,10),50)` | `TS_MIN(STDDEV(MCST,10),50)` | 0.0065% | n/a | -0.0621% | -0.204% | 0.51% | 10.63% | -16.04% | 100.0% | 0.9540 |
| 19 | `TsMad(TsStd(mcst,10),50)` | `TS_MAD(STDDEV(MCST,10),50)` | 0.0066% | n/a | -0.0688% | -0.190% | 0.51% | 13.20% | -12.30% | 100.0% | 0.9905 |
| 20 | `TsWMA(TsMinMaxDiff(mcst,40),40)` | `WMA((TS_MAX(MCST,40)-TS_MIN(MCST,40)),40)` | 0.0063% | n/a | -0.0672% | -0.179% | 0.53% | 9.97% | -12.76% | 100.0% | 0.9911 |
| 21 | `TsMed(TsMad(mcst,40),20)` | `TS_MEDIAN(TS_MAD(MCST,40),20)` | 0.0063% | n/a | -0.0645% | -0.182% | 0.53% | 12.53% | -12.32% | 100.0% | 0.9909 |
| 22 | `TsWMA(TsStd(mcst,40),40)` | `WMA(STDDEV(MCST,40),40)` | 0.0062% | n/a | -0.0659% | -0.180% | 0.53% | 10.50% | -11.96% | 100.0% | 0.9981 |
| 23 | `TsMin(TsStd(mcst,10),30)` | `TS_MIN(STDDEV(MCST,10),30)` | 0.0084% | n/a | -0.0691% | -0.222% | 0.55% | 14.50% | -17.34% | 100.0% | 0.9686 |
| 24 | `TsMax(mabias,50)` | `TS_MAX(MABIAS,50)` | 0.0069% | n/a | -0.0681% | -0.195% | 0.52% | 13.47% | -12.85% | 100.0% | 0.8576 |
| 25 | `TsMax(TsWMA(TsStd(mcst,40),20),40)` | `TS_MAX(WMA(STDDEV(MCST,40),20),40)` | 0.0060% | n/a | -0.0649% | -0.179% | 0.52% | 7.94% | -11.67% | 100.0% | 0.9948 |
| 26 | `TsMed(TsStd(mcst,40),30)` | `TS_MEDIAN(STDDEV(MCST,40),30)` | 0.0058% | n/a | -0.0630% | -0.173% | 0.53% | 11.93% | -10.80% | 100.0% | 0.9939 |
| 27 | `TsWMA(TsWMA(TsStd(mcst,40),40),20)` | `WMA(WMA(STDDEV(MCST,40),40),20)` | 0.0058% | n/a | -0.0631% | -0.173% | 0.53% | 9.84% | -11.35% | 100.0% | 0.9951 |
| 28 | `TsEMA(TsStd(mcst,50),40)` | `EMA(STDDEV(MCST,50),40)` | 0.0058% | n/a | -0.0645% | -0.174% | 0.52% | 9.06% | -11.79% | 100.0% | 0.9979 |
| 29 | `TsWMA(TsMad(mcst,50),40)` | `WMA(TS_MAD(MCST,50),40)` | 0.0058% | n/a | -0.0635% | -0.173% | 0.53% | 9.46% | -11.86% | 100.0% | 0.9989 |
| 30 | `TsWMA(TsMaxDiff(mcst,20),40)` | `WMA((MCST-TS_MAX(MCST,20)),40)` | 0.0057% | n/a | 0.0639% | 0.179% | 0.50% | 11.80% | 2.41% | 100.0% | 0.9925 |
| 31 | `TsEMA(TsMinDiff(mcst,50),30)` | `EMA((MCST-TS_MIN(MCST,50)),30)` | 0.0076% | n/a | -0.0723% | -0.201% | 0.53% | 14.32% | -14.80% | 100.0% | 0.9486 |
| 32 | `TsEMA(TsVar(mcst,10),40)` | `EMA(VAR(MCST,10),40)` | 0.0056% | n/a | -0.0771% | -0.183% | 0.40% | 12.41% | -16.34% | 100.0% | 0.9984 |
| 33 | `TsStd(mcst,40)` | `STDDEV(MCST,40)` | 0.0079% | n/a | -0.0739% | -0.205% | 0.53% | 14.58% | -14.67% | 100.0% | 0.9925 |
| 34 | `TsWMA(TsMax(mabias,50),20)` | `WMA(TS_MAX(MABIAS,50),20)` | 0.0055% | n/a | -0.0627% | -0.172% | 0.51% | 11.68% | -11.86% | 100.0% | 0.9806 |
| 35 | `TsWMA(TsWMA(TsStd(mcst,40),40),40)` | `WMA(WMA(STDDEV(MCST,40),40),40)` | 0.0054% | n/a | -0.0612% | -0.168% | 0.53% | 8.97% | -12.08% | 100.0% | 0.9953 |
| 36 | `TsEMA(tr,40)` | `EMA(TR,40)` | 0.0053% | n/a | -0.0620% | -0.168% | 0.51% | 9.49% | -12.40% | 100.0% | 0.9174 |
| 37 | `TsMax(TsMed(TsStd(mcst,40),30),40)` | `TS_MAX(TS_MEDIAN(STDDEV(MCST,40),30),40)` | 0.0053% | n/a | -0.0598% | -0.169% | 0.53% | 8.03% | -12.01% | 100.0% | 0.9848 |
| 38 | `TsEMA(TsMinDiff(mcst,20),40)` | `EMA((MCST-TS_MIN(MCST,20)),40)` | 0.0092% | n/a | -0.0762% | -0.222% | 0.54% | 15.70% | -16.05% | 100.0% | 0.9929 |
| 39 | `TsMax(TsPctChange(mcst,50),50)` | `TS_MAX(RETURNS(MCST,50),50)` | 0.0066% | n/a | -0.0511% | -0.238% | 0.54% | 14.01% | -18.68% | 100.0% | 0.6520 |
| 40 | `TsWMA(TsMean(TsMinDiff(wma10,10),50),40)` | `WMA(MA((WMA10-TS_MIN(WMA10,10)),50),40)` | 0.0049% | n/a | -0.0597% | -0.169% | 0.49% | 12.20% | -12.19% | 100.0% | 0.9599 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `TsEMA(TsStd(mcst,10),40)`
- PandaAI formula: `EMA(STDDEV(MCST,10),40)`
- Full aligned net excess: `-16.47%`
- Early net excess through 2024-12-31: `-25.94%`
- Late net excess from 2025-01-01: `3.22%`
- Full S_i: `0.0096%`; turnover `12.29%`; rank IC `-0.0771%`; ICIR `-0.227%`; win `0.55%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
