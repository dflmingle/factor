"""Literal smooth120 price trend and different729bar low-risk peer universe."""
import json
import numpy as np
import pandas as pd
from scipy.stats import linregress
from threadpoolctl import threadpool_limits
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
TREND='quant/2023年度精选策略/3.苦咖啡-默默赚钱系列-改.txt'
CORR='quant/聚宽2025年精选/26波动率过滤后相关性最小etf轮动.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source71-20261013'
SPECS=[spec('smooth_price_slope120_source','一百二十日价格平滑趋势斜率',TREND,'OLS120(C~time).slope',
 'proxy: actual ranking variable is RAW price slope despite R-square comment; fullA replacesHS300, current savedclose replaces priorclose weeklytrade'),
 spec('smooth_price_slope120_qualified','源码平滑趋势完整行情约束',TREND,'slope120 on C<=500,MAX30(H)/C<=1.1,MA7(V)/MA180(V)<=1.5,slope/intercept>.005,rvalue>.9',
 'proxy: all source dailyprice andvolume gates retained, positive rvalue>.9 not R²>.8; fullA replacesHS300, ST/openlimit/listing/intraday execution omitted, qualified factor_valid benchmark'),
 spec('volband_peer_abs_corr728_low','长窗波动区间内低同伴相关性',CORR,'-mean_peer(abs(CORR728(logreturn_i,logreturn_j))), INCLUDINGSELF;729complete closes; .05<STD728(logret)*sqrt243<.33',
 'proxy: actual728returns,729closes and source self-correlation included; volriskband before peer calculation, stock fullA substitutes30fixedETFs; continuous rank replaces top4ETF+25trend selection. Source missing math import repaired; no claim full strategy')]
for s in SPECS[1:]:s['gated']=True

def trend(c,h,v):
 out=np.full(c.shape,np.nan);qual=out.copy();x=np.arange(120);xm=x.mean();den=np.sum((x-xm)**2)
 high=q.rolling(h,30,'max');vr=q.ratio(q.rolling(v,7),q.rolling(v,180))
 for t in range(119,len(c)):
  y=c[t-119:t+1];ym=y.mean(axis=0);slope=np.sum((x-xm)[:,None]*y,axis=0)/den;intercept=ym-slope*xm
  r=q.ratio(np.sum((x-xm)[:,None]*(y-ym),axis=0),np.sqrt(den*np.sum((y-ym)**2,axis=0)))
  out[t]=slope;good=(c[t]<=500)&(q.ratio(high[t],c[t])<=1.1)&(vr[t]<=1.5)&(q.ratio(slope,intercept)>.005)&(r>.9);qual[t]=np.where(good,slope,np.nan)
 return out,qual

def peer(c,pos):
 out=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  hist=c[t-728:t+1];good=np.isfinite(hist).all(axis=0)&(hist>0).all(axis=0);ids=np.flatnonzero(good)
  r=np.diff(np.log(hist[:,ids]),axis=0);vol=r.std(axis=0,ddof=1)*np.sqrt(243);keep=(vol>.05)&(vol<.33);ids=ids[keep];r=r[:,keep]
  if len(ids)<100:continue
  r-=r.mean(axis=0);r/=np.sqrt(np.sum(r*r,axis=0))
  for start in range(0,len(ids),512):
   end=min(start+512,len(ids));out[i,ids[start:end]]=-np.abs(r[:,start:end].T@r).mean(axis=1)
  if i%20==0:print('VOLBAND_PEER',i,int(len(ids)),flush=True)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source literal gates and longwindow fixed before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);ids=np.arange(1024);c=f['close'].astype(float);small=c[:,ids];h=f['high'][:,ids];v=f['volume'][:,ids];whole=trend(small,h,v);pa=peer(small,pos);checks=[]
 assert np.isfinite(pa).sum()>0
 for stop in [1200,len(cal)-31]:
  cut=trend(small[:stop],h[:stop],v[:stop]);use=pos<stop
  for a,b in zip(whole,cut):np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-7)
  np.testing.assert_allclose(pa[use],peer(small[:stop],pos[use]),equal_nan=True,atol=1e-8)
  checks.append(dict(test='dailyprice_prefix_and_volband_allpeer_recompute',stop=stop,finite_qualified=int(np.isfinite(whole[1][:stop]).sum()),passed=True))
 for t in pos[::31]:
  for j in range(8):
   y=small[t-119:t+1,j]
   if np.isfinite(y).all():np.testing.assert_allclose(whole[0][t,j],linregress(np.arange(120),y).slope,atol=1e-7)
 for i in range(0,len(pos),31):
  use=np.flatnonzero(np.isfinite(pa[i]));t=pos[i]
  if not len(use):continue
  ref=np.log(pd.DataFrame(small[t-728:t+1,use])).diff().iloc[1:].corr().abs().mean().to_numpy()
  np.testing.assert_allclose(pa[i,use],-ref,atol=1e-8)
 checks.append(dict(test='independent_scipyOLS_and_pandas_selfincluded_corr',passed=True))
 a,b=trend(c,f['high'],f['volume'])
 with threadpool_limits(limits=8):p=peer(c,pos)
 vals=[a[pos],b[pos],p];q.dump(OUT/'qualification_coverage.json',{s['key']:np.isfinite(x).sum(axis=1).tolist() for s,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='distinctsourcekernels fullA adaptations',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED71',flush=True)
if __name__=='__main__':main()
