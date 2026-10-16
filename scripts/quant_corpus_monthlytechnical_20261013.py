"""Completed monthly MACD, previous-year anchor and34bar trend kernels."""
import sys,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
MONTH='quant/聚宽2025年精选/85稳健型ETF策略.txt'
EPO='quant/聚宽2025年精选/17多品种ETF动量轮动+EPO优化.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source104-20261013'
SPECS=[
 spec('defensive85_completed_month_MACD','完整月线MACD十二二十六九',MONTH,'2*(monthlyEMA12-EMA26-monthlyDEA9), completedmonthsonly',
 'proxy: unit1M is calendarMONTH, include_now=False current partialmonth omitted. TA-LibSMAseeds on finite monthlysegments proxy vendor; rawmonetary MACD, no price division. FullAstockextension of ETFswitch kernel, source initial12.5/12.5/25/25/25%,costledger/annualreset not reproduced'),
 spec('defensive85_month_MACD_sign','完整月MACD正值分支',MONTH,'I(completedMonthlyMACD>0)',
 'proxy: source positive sign exact, explicit binarystockextension withties; previousmonthclose may be weeks old, no currentmonthfutureclose. FullETF allocation/positionstate absent'),
 spec('defensive85_priorclose_YTD','前收盘至去年末收益',MONTH,'100*(C_t-1/lastavailableClosePriorYearDec20..31-1)',
 'proxy: exact source get_zf dateanchor and priorclose, no rolling250 substitute; source threshold-6percent controlsdividendETF only, continuous highdirection stockextension and trueETF prices absent'),
 spec('epo17_logtrend34_priorclose','三十四价点趋势拟合度',EPO,'expm1(250*OLS34(logC).slope)*R2, priorcompletedclose',
 'proxy: exact34pricepoints/250annualization stockextension; source13ETFtop3positive and1200price EPO20%covshrink/ inversevarianceanchor not reproduced; horizonvariant ofknowntrend family'),
 spec('epo17_positive34_qualified','三十四条趋势正分资格',EPO,'trend34 where score>0',
 'proxy: literal source positivityqualification on fullA extension, restrictedfactor_valid benchmark; covarianceallocation andmonthlyfills absent')]
SPECS[-1]['gated']=True

def values(cal,c,pos):
 frame=pd.DataFrame(c,index=cal);m=frame.resample('ME').last();monthkeys=m.index.to_period('M');sigmonth=cal[pos].to_period('M');loc=monthkeys.get_indexer(sigmonth-1)
 hist=np.full(m.shape,np.nan);a=m.to_numpy().astype(float)
 for j in range(a.shape[1]):
  good=np.isfinite(a[:,j])&(a[:,j]>0);edges=np.diff(np.r_[False,good,False].astype(int))
  for start,end in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
   hist[start:end,j]=2*talib.MACD(np.ascontiguousarray(a[start:end,j]),fastperiod=12,slowperiod=26,signalperiod=9)[2]
 monthly=hist[loc];sign=np.where(np.isfinite(monthly),(monthly>0).astype(float),np.nan);ytd=np.full(monthly.shape,np.nan)
 for i,t in enumerate(pos):
  year=cal[t].year;mask=(cal.year==year-1)&(cal.month==12)&(cal.day>=20);idx=np.flatnonzero(mask)
  if len(idx):ytd[i]=100*(c[t-1]/c[idx[-1]]-1)
 trend=trend_at(c.astype(float),pos-1,34)
 return [monthly,sign,ytd,trend,np.where(trend>0,trend,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcecalendarperiods/34horizon fixed; nooutcome tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64];whole=values(cal,small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values(cal[:stop],small[:stop],pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_monthresample_excludes_partialmonth',stop=stop,passed=True))
 obs=0
 for i in [35,79,119]:
  t=pos[i];ym=cal[t].to_period('M')
  for j in range(64):
   s=pd.Series(small[:,j],index=cal).loc[:cal[t-1]];m=s.groupby(s.index.to_period('M')).last();m=m[m.index<ym];assert (m.index<ym).all()
   x=m.to_numpy().astype(float);good=np.flatnonzero(np.isfinite(x))
   if len(good) and np.isfinite(x[good[0]:]).all():
    ref=2*talib.MACD(np.ascontiguousarray(x[good[0]:]),fastperiod=12,slowperiod=26,signalperiod=9)[2][-1]
    np.testing.assert_allclose(whole[0][i,j],ref,equal_nan=True,atol=1e-10)
   anchor=s.loc[f'{cal[t].year-1}-12-20':f'{cal[t].year-1}-12-31'].iloc[-1]
   np.testing.assert_allclose(whole[2][i,j],100*(float(s.iloc[-1])/float(anchor)-1),equal_nan=True,atol=1e-5);obs+=1
 checks.append(dict(test='independent_Periodgroup_completedmonth_and_literal_priorDecemberanchor',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [MONTH,EPO]})
 run(OUT,SPECS,values(cal,f['close'],pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='monthlyETF technicalkernels fullAextension'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED104',flush=True)
if __name__=='__main__':main()
