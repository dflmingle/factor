"""Literal unusual BOLL windows, RSI integer band, volume count and trend90."""
import sys,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
BASE=q.ROOT/'quant/2024年度精选策略2'
def src(prefix):return str(next(BASE.glob(prefix+'*')).relative_to(q.ROOT))
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source82-20261013'
SPECS=[
 spec('volume_burst_samewindow10_count','十日共用均量放量次数',src('54.'),'count over last10 of V_i/mean(V_last10)>1.3',
 'proxy: source10day samewindow mean applied to all10values, not rolling daily V/MA10 count; fullA ranking atom. Source sales_growth top10percent, EPSpositive, floatcap10->5, indexgate omitted'),
 spec('boll_mean25_std20_prior8_rebound_margin','二十五均值二十标准差八日低点反弹',src('26.'),
 'min((mean25C-2*sampleSTD20C)/lag1C-1,C/lag1C-1,C/lag2MIN8C-1)',
 'proxy: actual source25bar MEAN,20bar sampleSTD and data[-10:-2]8bars retained; source previousclose oversold/currentrebound continuous margin; fullA replacesindex50smallcap, intraday execution and storedstoploss absent'),
 spec('boll_mean25_std20_prior8_rebound_qualified','源码布林反弹严格交集',src('26.'),
 'C/lag1C-1 on literal priorclose<mean25C-2sampleSTD20C,C>priorclose,C>lag2MIN8C',
 'proxy: exact buy conjunction, sparse source-event qualified benchmark, original index50/circMV/stops/intraday omitted; no observation when<100 qualified stocks'),
 spec('rsi6_reset61_low','六日RSI六十一观测重置低值',src('40.'),'-TA_Lib_RSI6(last61close)',
 'proxy: continuous companion of source oversold band; fixed41unique-stock list->fullA explicitly, original holdings and sell rules omitted'),
 spec('rsi6_integer16_24_qualified','整数RSI十六至二十四源码池',src('40.'),'-trunc(RSI6(last61close)) on 15<trunc(RSI)<25',
 'proxy: source int truncation and strict band retained, fullA stock extension; qualification benchmark and discrete tie sensitivity required'),
 spec('trend90_log_ann_r2_source31','九十观测对数斜率乘拟合优度',src('31.'),'expm1(250*OLS90slope(logC))*R2_90',
 'proxy: source90observations and scipy/numpy unweighted R2, highdirection; HS300->fullA, marketMA200/top60/ATR20 allocation omitted'),
 spec('trend90_ma100_gap98_qualified','九十趋势加百日线隔日缺口源码池',src('31.'),
 'trend90 on C>=MA100 and MAX98(L/lag2H-1)<=.15',
 'proxy: source100bar dataframe shift2 creates98valid gap pairs; exact gap constraint not MAX100 with two extra predecessors. FullA replacesHS300; qualified benchmark and source top60/marketMA200/ATR sizing omitted')]
for i in [2,4,6]:SPECS[i]['gated']=True

def values(f,pos):
 c=f['close'].astype(float);v=f['volume'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float)
 cnt=np.full((len(pos),c.shape[1]),np.nan);rsi=cnt.copy();trend=cnt.copy()
 for i,t in enumerate(pos):
  vol=v[t-9:t+1];good=np.isfinite(vol).all(axis=0)&(vol.mean(axis=0)>0)
  cnt[i,good]=(vol[:,good]/vol[:,good].mean(axis=0)>1.3).sum(axis=0)
  hist=c[t-89:t+1];good=np.isfinite(hist).all(axis=0)&(hist>0).all(axis=0)
  x=np.arange(90);xc=x-x.mean();den=np.sum(xc**2);y=np.log(hist[:,good]);yc=y-y.mean(axis=0)
  slope=(xc[:,None]*yc).sum(axis=0)/den;res=yc-xc[:,None]*slope
  total=(yc**2).sum(axis=0);r2=np.where(total>0,1-(res**2).sum(axis=0)/np.where(total>0,total,np.nan),np.nan)
  trend[i,good]=np.expm1(250*slope)*r2
  for j in range(c.shape[1]):
   a=c[t-60:t+1,j]
   if len(a)==61 and np.isfinite(a).all():rsi[i,j]=talib.RSI(a,timeperiod=6)[-1]
 df=pd.DataFrame(c);mean=df.rolling(25).mean().to_numpy()[pos];sd=df.rolling(20).std(ddof=1).to_numpy()[pos]
 prev=q.delay(c)[pos];low=q.delay(q.rolling(c,8,'min'),2)[pos];cur=c[pos]
 margin=np.minimum(np.minimum(q.ratio(mean-2*sd,prev)-1,q.ratio(cur,prev)-1),q.ratio(cur,low)-1)
 strict=(prev<mean-2*sd)&(cur>prev)&(cur>low)
 integer=np.trunc(rsi);rsigate=(integer>15)&(integer<25)
 ma100=df.rolling(100).mean().to_numpy()[pos]
 # Source Series.max skips NaN high/low during suspensions inside the 100bar
 # frame. Preserve that behavior; a complete98pair requirement is not source.
 gaps=q.ratio(l,q.delay(h,2))-1;maxgap=q.rolling(gaps,98,'max',minimum=1)[pos]
 trendgate=(cur>=ma100)&(maxgap<=.15)
 return [cnt,margin,np.where(strict,q.ratio(cur,prev)-1,np.nan),-rsi,np.where(rsigate,-integer,np.nan),trend,np.where(trendgate,trend,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal source parameters frozen before evaluation; no tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:128] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-7,atol=1e-7);checks.append(dict(key=sp['key'],test='raw_daily_prefix_rebuild',cutoff=str(cal[stop-1]),passed=True))
 obs=0
 for i in [12,60,119]:
  t=pos[i]
  for j in range(128):
   a=small['close'][t-24:t+1,j].astype(float)
   if not np.isfinite(a).all():continue
   buy=a[-2]<a.mean()-2*np.std(a[-20:],ddof=1) and a[-1]>a[-2] and a[-1]>a[-10:-2].min()
   assert bool(np.isfinite(whole[2][i,j]))==bool(buy)
   hist=pd.DataFrame({k:small[k][t-99:t+1,j].astype(float) for k in ['close','low','high']})
   mg=(hist.low/hist.high.shift(2)-1).max()
   expected=hist.close.iloc[-1]>=hist.close.mean() and mg<=.15
   if np.isfinite(whole[5][i,j]):assert bool(np.isfinite(whole[6][i,j]))==bool(expected)
   y=np.log(small['close'][t-89:t+1,j].astype(float));x=np.arange(90);s,b=np.polyfit(x,y,1)
   if np.isfinite(y).all() and np.var(y)>0:
    ref=np.expm1(250*s)*(1-np.sum((y-s*x-b)**2)/((len(y)-1)*np.var(y,ddof=1)))
    np.testing.assert_allclose(whole[5][i,j],ref,rtol=1e-6,atol=1e-6)
   obs+=1
 checks.append(dict(test='independent_original_slice_BOLL_and_dataframe100gap98_and_polyfit90',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{src(p):read_text(q.ROOT/src(p)) for p in ['26.','31.','40.','54.']})
 vals=values(f,pos);q.dump(OUT/'qualification_coverage.json',{s['key']:np.isfinite(a).sum(axis=1).tolist() for s,a in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='disclosed fullA adaptations of source precise windows',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED82',flush=True)

if __name__=='__main__':main()
