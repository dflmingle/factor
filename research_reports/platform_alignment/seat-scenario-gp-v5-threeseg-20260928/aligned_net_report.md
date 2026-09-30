# AlphaPROBE aligned net-excess search

- Alignment: `2021-09-07..2026-09-07`
- Signals: `120`; minimum candidate coverage: `100` periods; cycle: `10` trading days
- Universe: `5395` local full-A instruments; qfq + daily_basic
- Objective: maximise `S_i = |RankIC| x |ICIR| x IC win` under turnover `<= 12.00%` per rebalance and net excess `>= 12.00%`
- GP expressions scored: `1063`; invalid: `0`
- GP search terminals: `371` via `all`
- Minimum distinct search fields per expression: `1`
- Candidate deduplication: positive signal-panel Rank correlation `< 0.999`
- Historical formula exclusion: `0` candidates matched `factor_formula_registry.json`; selected formulas are required to have a new normalized signature.

| rank | raw AlphaPROBE formula | PandaAI formula | S_i | efficiency | rank IC | ICIR | win | turnover | net excess | coverage | max prior Rank corr |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Greater(Greater(vol10,Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,LOG(WMA(WMA(CAL_20D_AMT_MA,30),30))),LOG(CAL_20D_AMT_MA))` | 0.0332% | n/a | -0.0951% | -0.499% | 0.70% | 16.85% | -25.68% | 100.0% | n/a |
| 2 | `Greater(Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))),LOG(CAL_20D_AMT_MA))` | 0.0345% | n/a | -0.0977% | -0.504% | 0.70% | 18.03% | -25.65% | 100.0% | 0.9925 |
| 3 | `Greater(Greater(vol10,TsWMA(vol250,20)),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,WMA(VOL250,20)),LOG(CAL_20D_AMT_MA))` | 0.0374% | n/a | -0.1033% | -0.505% | 0.72% | 20.26% | -26.03% | 100.0% | 0.9862 |
| 4 | `Greater(Greater(vol10,Log(TsWMA(TsWMA(TsWMA(cal_20d_amt_ma,30),30),30))),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,LOG(WMA(WMA(WMA(CAL_20D_AMT_MA,30),30),30))),LOG(CAL_20D_AMT_MA))` | 0.0316% | n/a | -0.0932% | -0.496% | 0.68% | 17.13% | -25.41% | 100.0% | 0.9934 |
| 5 | `Greater(Greater(vol10,Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))),Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))))` | `MAX(MAX(VOL10,LOG(WMA(WMA(CAL_20D_AMT_MA,30),30))),MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))))` | 0.0297% | n/a | -0.0885% | -0.490% | 0.68% | 15.85% | -24.61% | 100.0% | 0.9887 |
| 6 | `Greater(Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))),TsStd(turnover,50))` | `MAX(MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))),STDDEV(TURNOVER,50))` | 0.0317% | n/a | -0.0915% | -0.496% | 0.70% | 17.27% | -24.64% | 100.0% | 0.9931 |
| 7 | `Greater(Greater(vol10,Log(TsWMA(TsWMA(TsWMA(TsWMA(cal_20d_amt_ma,30),30),30),30))),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,LOG(WMA(WMA(WMA(WMA(CAL_20D_AMT_MA,30),30),30),30))),LOG(CAL_20D_AMT_MA))` | 0.0317% | n/a | -0.0928% | -0.501% | 0.68% | 17.34% | -25.76% | 100.0% | 0.9943 |
| 8 | `Greater(Greater(vol10,Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))),TsMaxDiff(vma120,40))` | `MAX(MAX(VOL10,LOG(WMA(WMA(CAL_20D_AMT_MA,30),30))),(VMA120-TS_MAX(VMA120,40)))` | 0.0281% | n/a | -0.0853% | -0.489% | 0.68% | 15.98% | -24.62% | 100.0% | 0.9934 |
| 9 | `Greater(Log(TsWMA(cal_20d_amt_ma,30)),Log(cal_20d_amt_ma))` | `MAX(LOG(WMA(CAL_20D_AMT_MA,30)),LOG(CAL_20D_AMT_MA))` | 0.0239% | n/a | -0.0943% | -0.384% | 0.66% | 13.98% | -21.09% | 100.0% | 0.9944 |
| 10 | `Greater(Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))),TsMax(oper_roa_ttm,40))` | `MAX(MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))),TS_MAX(OPER_ROA_TTM,40))` | 0.0287% | n/a | -0.0923% | -0.484% | 0.64% | 17.37% | -24.50% | 100.0% | 0.9764 |
| 11 | `Greater(Greater(vol10,Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))),TsDelta(ma5,10))` | `MAX(MAX(VOL10,LOG(WMA(WMA(CAL_20D_AMT_MA,30),30))),DIFF(MA5,10))` | 0.0284% | n/a | -0.0848% | -0.502% | 0.67% | 17.90% | -25.22% | 100.0% | 0.9981 |
| 12 | `Greater(Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30)),Log(cal_20d_amt_ma))` | `MAX(LOG(WMA(WMA(CAL_20D_AMT_MA,30),30)),LOG(CAL_20D_AMT_MA))` | 0.0203% | n/a | -0.0906% | -0.353% | 0.63% | 12.63% | -20.75% | 100.0% | 0.9941 |
| 13 | `Greater(Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))),TsWMA(TsPctChange(ratio_ev_no_cash_ttm,40),50))` | `MAX(MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))),WMA(RETURNS(RATIO_EV_NO_CASH_TTM,40),50))` | 0.0270% | n/a | -0.0928% | -0.492% | 0.59% | 17.63% | -24.68% | 100.0% | 0.9962 |
| 14 | `Greater(TsMad(Rank(TsCorr(Div(ema120,ratio_ev_no_cash_ttm),Mul(davol5,ratio_pb_ttm),20)),50),Log(cal_20d_amt_ma))` | `MAX(TS_MAD(RANK(CORR((EMA120/RATIO_EV_NO_CASH_TTM),(DAVOL5*RATIO_PB_TTM),20)),50),LOG(CAL_20D_AMT_MA))` | 0.0265% | n/a | -0.1013% | -0.398% | 0.66% | 17.53% | -22.91% | 100.0% | 0.9951 |
| 15 | `Log(TsWMA(cal_20d_amt_ma,30))` | `LOG(WMA(CAL_20D_AMT_MA,30))` | 0.0198% | n/a | -0.0864% | -0.357% | 0.64% | 12.99% | -19.11% | 100.0% | 0.9905 |
| 16 | `Greater(Greater(vol10,Log(TsMin(TsMinMaxDiff(cost_of_goods_sold,30),40))),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,LOG(TS_MIN((TS_MAX(COST_OF_GOODS_SOLD,30)-TS_MIN(COST_OF_GOODS_SOLD,30)),40))),LOG(CAL_20D_AMT_MA))` | 0.0400% | n/a | -0.1033% | -0.553% | 0.70% | 27.24% | -32.03% | 100.0% | 0.9836 |
| 17 | `Greater(Greater(vol10,TsDelta(lma60,50)),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,DIFF(LMA60,50)),LOG(CAL_20D_AMT_MA))` | 0.0284% | n/a | -0.1015% | -0.455% | 0.62% | 21.00% | -26.03% | 100.0% | 0.9963 |
| 18 | `Greater(Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))),TsIr(gr_total_asset_lyr,20))` | `MAX(MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))),(MA(GR_TOTAL_ASSET_LYR,20)/STDDEV(GR_TOTAL_ASSET_LYR,20)))` | 0.0401% | n/a | -0.1080% | -0.564% | 0.66% | 28.98% | -34.68% | 100.0% | 0.9846 |
| 19 | `Greater(Greater(vol10,Log(TsWMA(cal_20d_amt_ma,30))),TsMax(amount,40))` | `MAX(MAX(VOL10,LOG(WMA(CAL_20D_AMT_MA,30))),TS_MAX(AMOUNT,40))` | 0.0177% | n/a | -0.0910% | -0.349% | 0.56% | 14.30% | -21.49% | 100.0% | 0.9692 |
| 20 | `Greater(Greater(vol10,TsVar(oper_roa_ttm,50)),Log(cal_20d_amt_ma))` | `MAX(MAX(VOL10,VAR(OPER_ROA_TTM,50)),LOG(CAL_20D_AMT_MA))` | 0.0318% | n/a | -0.1013% | -0.502% | 0.63% | 24.40% | -27.60% | 100.0% | 0.9720 |
| 21 | `Greater(Greater(ma120,Log(TsDiv(cal_20d_amt_ma,20))),TsEMA(cal_20d_amt_ma,20))` | `MAX(MAX(MA120,LOG((CAL_20D_AMT_MA/MA(CAL_20D_AMT_MA,20)))),EMA(CAL_20D_AMT_MA,20))` | 0.0168% | n/a | -0.0911% | -0.317% | 0.58% | 14.39% | -20.03% | 100.0% | 0.9969 |
| 22 | `Greater(Sub(cfd_flow_per_share_ttm,TsDelta(TsWMA(cal_20d_amt_ma,30),10)),TsMax(cal_20d_amt_ma,10))` | `MAX((CFD_FLOW_PER_SHARE_TTM-DIFF(WMA(CAL_20D_AMT_MA,30),10)),TS_MAX(CAL_20D_AMT_MA,10))` | 0.0182% | n/a | -0.0913% | -0.342% | 0.58% | 15.34% | -21.32% | 100.0% | 0.9972 |
| 23 | `Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))` | `LOG(WMA(WMA(CAL_20D_AMT_MA,30),30))` | 0.0147% | n/a | -0.0766% | -0.311% | 0.62% | 10.84% | -17.44% | 100.0% | 0.9855 |
| 24 | `Greater(vol10,oper_roa_lyr)` | `MAX(VOL10,OPER_ROA_LYR)` | 0.0198% | n/a | -0.0589% | -0.561% | 0.60% | 16.99% | -23.34% | 100.0% | 0.3476 |
| 25 | `Greater(Greater(vol10,Log(TsDiv(Ref(cal_vwap,30),10))),TsMinMaxDiff(cal_20d_amt_ma,50))` | `MAX(MAX(VOL10,LOG((REF(CAL_VWAP,30)/MA(REF(CAL_VWAP,30),10)))),(TS_MAX(CAL_20D_AMT_MA,50)-TS_MIN(CAL_20D_AMT_MA,50)))` | 0.0179% | n/a | -0.0836% | -0.347% | 0.62% | 15.71% | -20.83% | 100.0% | 0.9319 |
| 26 | `Greater(Greater(ps_ratio_ttm,TsWMA(TsMaxDiff(TsMaxDiff(cal_20d_amt_ma,40),40),40)),TsEMA(cal_20d_amt_ma,50))` | `MAX(MAX(PS_RATIO_TTM,WMA(((CAL_20D_AMT_MA-TS_MAX(CAL_20D_AMT_MA,40))-TS_MAX((CAL_20D_AMT_MA-TS_MAX(CAL_20D_AMT_MA,40)),40)),40)),EMA(CAL_20D_AMT_MA,50))` | 0.0137% | n/a | -0.0836% | -0.294% | 0.56% | 9.47% | -18.07% | 100.0% | 0.9949 |
| 27 | `TsWMA(TsStd(cal_20d_amt_ma,50),50)` | `WMA(STDDEV(CAL_20D_AMT_MA,50),50)` | 0.0135% | n/a | -0.0710% | -0.322% | 0.59% | 11.59% | -18.20% | 100.0% | 0.9312 |
| 28 | `Greater(TsCorr(ma250,TsMinDiff(TsDiv(total_liabilities,40),20),50),TsEMA(cal_20d_amt_ma,10))` | `MAX(CORR(MA250,((TOTAL_LIABILITIES/MA(TOTAL_LIABILITIES,40))-TS_MIN((TOTAL_LIABILITIES/MA(TOTAL_LIABILITIES,40)),20)),50),EMA(CAL_20D_AMT_MA,10))` | 0.0185% | n/a | -0.0926% | -0.342% | 0.58% | 16.64% | -21.42% | 100.0% | 0.9942 |
| 29 | `Greater(ma3,TsMax(TsWMA(cal_20d_amt_ma,30),50))` | `MAX(MA3,TS_MAX(WMA(CAL_20D_AMT_MA,30),50))` | 0.0129% | n/a | -0.0756% | -0.301% | 0.57% | 7.68% | -17.26% | 100.0% | 0.9636 |
| 30 | `Greater(Greater(skd_d,TsMad(TsIr(cal_5d_down_day_ratio,50),20)),TsMean(cal_20d_amt_ma,50))` | `MAX(MAX(SKD_D,TS_MAD((MA(CAL_5D_DOWN_DAY_RATIO,50)/STDDEV(CAL_5D_DOWN_DAY_RATIO,50)),20)),MA(CAL_20D_AMT_MA,50))` | 0.0125% | n/a | -0.0767% | -0.280% | 0.58% | 8.09% | -16.03% | 100.0% | 0.9907 |
| 31 | `TsEMA(Greater(vol10,oper_roa_lyr),50)` | `EMA(MAX(VOL10,OPER_ROA_LYR),50)` | 0.0122% | n/a | -0.0461% | -0.467% | 0.57% | 7.55% | -17.22% | 100.0% | 0.9368 |
| 32 | `TsWMA(TsWMA(TsMad(cal_20d_amt_ma,50),20),50)` | `WMA(WMA(TS_MAD(CAL_20D_AMT_MA,50),20),50)` | 0.0118% | n/a | -0.0663% | -0.315% | 0.57% | 11.82% | -17.87% | 100.0% | 0.9921 |
| 33 | `Greater(TsCorr(open,TsMax(TsWMA(cal_20d_amt_ma,30),30),40),TsMin(cal_20d_amt_ma,30))` | `MAX(CORR(OPEN,TS_MAX(WMA(CAL_20D_AMT_MA,30),30),40),TS_MIN(CAL_20D_AMT_MA,30))` | 0.0118% | n/a | -0.0731% | -0.284% | 0.57% | 11.67% | -17.28% | 100.0% | 0.9591 |
| 34 | `Greater(Greater(obos,Log(TsWMA(marsi10,40))),TsMed(cal_20d_amt_ma,40))` | `MAX(MAX(OBOS,LOG(WMA(MARSI10,40))),TS_MEDIAN(CAL_20D_AMT_MA,40))` | 0.0113% | n/a | -0.0755% | -0.277% | 0.54% | 10.65% | -16.88% | 100.0% | 0.9903 |
| 35 | `Greater(madpo,TsMed(cal_20d_amt_ma,50))` | `MAX(MADPO,TS_MEDIAN(CAL_20D_AMT_MA,50))` | 0.0113% | n/a | -0.0715% | -0.283% | 0.56% | 8.74% | -16.12% | 100.0% | 0.9858 |
| 36 | `Mul(Greater(cal_30d_close_avg_ratio,Log(TsWMA(lma5,30))),TsEMA(cal_20d_amt_ma,50))` | `(MAX(CAL_30D_CLOSE_AVG_RATIO,LOG(WMA(LMA5,30)))*EMA(CAL_20D_AMT_MA,50))` | 0.0113% | n/a | -0.0833% | -0.249% | 0.54% | 8.58% | -17.05% | 100.0% | 0.9531 |
| 37 | `Greater(TsCorr(mcst,TsMad(TsWMA(TsWMA(amp20,30),30),20),30),TsSum(cal_20d_amt_ma,40))` | `MAX(CORR(MCST,TS_MAD(WMA(WMA(AMP20,30),30),20),30),SUM(CAL_20D_AMT_MA,40))` | 0.0107% | n/a | -0.0803% | -0.239% | 0.56% | 9.12% | -16.50% | 100.0% | 0.9982 |
| 38 | `Greater(Greater(vol10,TsMed(TsWMA(cal_20d_amt_ma,30),30)),TsRank(vol10,20))` | `MAX(MAX(VOL10,TS_MEDIAN(WMA(CAL_20D_AMT_MA,30),30)),TS_RANK(VOL10,20))` | 0.0106% | n/a | -0.0717% | -0.272% | 0.54% | 11.28% | -17.05% | 100.0% | 0.9932 |
| 39 | `Greater(Greater(gr_total_asset_ttm,TsDiv(TsWMA(cal_20d_amt_ma,30),40)),Log(cal_20d_amt_ma))` | `MAX(MAX(GR_TOTAL_ASSET_TTM,(WMA(CAL_20D_AMT_MA,30)/MA(WMA(CAL_20D_AMT_MA,30),40))),LOG(CAL_20D_AMT_MA))` | 0.0107% | n/a | -0.0866% | -0.279% | 0.44% | 13.22% | -12.19% | 100.0% | 0.8527 |
| 40 | `Greater(Greater(vol10,TsMean(TsWMA(TsWMA(cal_20d_amt_ma,30),30),40)),Log(cal_20d_120d_turnover_ratio))` | `MAX(MAX(VOL10,MA(WMA(WMA(CAL_20D_AMT_MA,30),30),40)),LOG(CAL_20D_120D_TURNOVER_RATIO))` | 0.0103% | n/a | -0.0686% | -0.265% | 0.57% | 8.09% | -15.12% | 100.0% | 0.9787 |

## Best formula diagnostics

- Raw AlphaPROBE formula: `Greater(Greater(vol10,Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))),Log(cal_20d_amt_ma))`
- PandaAI formula: `MAX(MAX(VOL10,LOG(WMA(WMA(CAL_20D_AMT_MA,30),30))),LOG(CAL_20D_AMT_MA))`
- Full aligned net excess: `-25.68%`
- Early net excess through 2024-12-31: `-31.97%`
- Late net excess from 2025-01-01: `-12.61%`
- Full S_i: `0.0332%`; turnover `16.85%`; rank IC `-0.0951%`; ICIR `-0.499%`; win `0.70%`

The local score is a research proxy; no PandaAI factor was created or run by this search.
