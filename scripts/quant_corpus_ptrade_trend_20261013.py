"""Exact PTrade valid-session trend kernel and disclosed stock correlation proxy."""
import json
import numpy as np
import pandas as pd
from numba import njit
from scipy.stats import rankdata
from threadpoolctl import threadpool_limits
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/量化策略/量化策略/实盘2026/Ptrade/pt版01趋势强+低相关ETF轮动策略.txt'
B='quant/量化策略/量化策略/ETF轮动策略2026/02稳健型ETF策略-调优版-25年27.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source121-20261013'
SPECS=[
 spec('ptrade01_valid80_trend20_bias60','趋势源码八十条有效价点二十六十秩和',A,'rankpct(C_lastvalid/C_21stvalid-1)+rankpct(C_lastvalid/MEAN60validC-1), within80priorbars, volume>0 and finiteC',
 'proxy exact source20validintervals/60validmean after80bar volume>0 filtering. FullA rather ETF, per-signal insteadmonthlyfrozenpool, rankingatoms only; no missingvalidprice fabricated.'),
 spec('ptrade01_top40_lowabs_corr244','趋势前四成低绝对相关二百四十四收益',A,'-mean(abs(corr(logRET244))) within top40percent trend score, last245priorprices, excluding self',
 'proxy exact245prices->244returns, top40percent inclusive numpy percentile. Calendaraligned completehistories; fixes source individuallydropna/Seriesrangeindex datecompression hazard insteadpretendingitcausal. NEW fullA ranking before source top4->2 and no actualETFmonthlybuffer/fills.'),
 spec('monthly02_ytd_above_minus7','月度ETF源码负七点年度门槛',B,'I(round(100*(C_t-1/lastPriorYearSessionC-1),2)>-7)',
 'proxy literal new-7 boundary only for source legs1/2; leg3retains-6. FullA binary adaptation of red-dividendETFscalar, no actualETFfiveleg25/20/25/15/15allocation or monthlyfills; manyties sensitivity reported.')]
SPECS[1]['gated']=True

@njit(cache=True)
def features(c,v,pos):
 mom=np.full((len(pos),c.shape[1]),np.nan);bias=mom.copy()
 for i,t in enumerate(pos):
  for j in range(c.shape[1]):
   a=np.empty(80);n=0
   for z in range(t-80,t):
    if v[z,j]>0 and np.isfinite(c[z,j]):a[n]=c[z,j];n+=1
   if n>=60 and a[n-21]>0 and np.mean(a[n-60:n])>0:
    mom[i,j]=a[n-1]/a[n-21]-1;bias[i,j]=a[n-1]/np.mean(a[n-60:n])-1
 return mom,bias

def values(f,cal,pos,with_corr=True):
 c=f['close'].astype(float);mom,bias=features(c,f['volume'].astype(float),pos);score=np.full(mom.shape,np.nan);low=score.copy()
 for i,t in enumerate(pos):
  good=np.isfinite(mom[i])&np.isfinite(bias[i]);ids=np.flatnonzero(good)
  if not len(ids):continue
  score[i,ids]=(rankdata(mom[i,ids])+rankdata(bias[i,ids]))/len(ids)*100
  if with_corr:
   threshold=np.percentile(score[i,ids],60);sel=ids[score[i,ids]>=threshold]
   hist=c[t-245:t,sel];complete=np.isfinite(hist).all(axis=0)&(hist>0).all(axis=0);sel=sel[complete];hist=hist[:,complete]
   if len(sel)<2:continue
   r=np.diff(np.log(hist),axis=0);r-=r.mean(axis=0);norm=np.sqrt(np.square(r).sum(axis=0));live=norm>1e-12;sel=sel[live];r=r[:,live];norm=norm[live]
   if len(sel)<2:continue
   z=r/norm
   with threadpool_limits(limits=4):
    for at in range(0,len(sel),128):
     corr=np.clip(z[:,at:at+128].T@z,-1,1)
     low[i,sel[at:at+128]]=-(np.abs(corr).sum(axis=1)-1)/(len(sel)-1)
   if i%20==0:print('CORRELATION244',i,len(pos),len(sel),flush=True)
 ytd=np.full(score.shape,np.nan)
 for i,t in enumerate(pos):
  ids=np.flatnonzero(cal.year==cal[t].year-1)
  if not len(ids):continue
  x=np.round(100*(c[t-1]/c[ids[-1]]-1),2);ytd[i]=np.where(np.isfinite(x),(x>-7).astype(float),np.nan)
 return [score,low,ytd]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixed80/20valid/60valid/40percent/245prices/-7literal boundary')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:128] for k,v in f.items()};full=values(sf,cal,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},cal[:stop],pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawpricevolume_and_crosssection_prefix_replay',passed=True))
 mom,bias=features(sf['close'].astype(float),sf['volume'].astype(float),pos)
 for i in [35,79]:
  t=pos[i]
  for j in range(128):
   a=sf['close'][t-80:t,j].astype(float);v=sf['volume'][t-80:t,j];a=a[(v>0)&np.isfinite(a)]
   if len(a)>=60:
    np.testing.assert_allclose(mom[i,j],a[-1]/a[-21]-1,atol=1e-8);np.testing.assert_allclose(bias[i,j],a[-1]/a[-60:].mean()-1,atol=1e-8)
  good=np.isfinite(full[1][i]);sel=np.flatnonzero(good)
  if len(sel)>1:
   r=pd.DataFrame(np.log(sf['close'][t-245:t,sel].astype(float))).diff().dropna();corr=r.corr();ref=-(corr.abs().sum(axis=1)-1)/(len(sel)-1)
   np.testing.assert_allclose(full[1][i,sel],ref.to_numpy(),atol=1e-8)
 checks.append(dict(test='independent_source_valid80slices_and_pandas_datealigned_corr244',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]});vals=values(f,cal,pos)
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='ETFsource daily fullA extensions, originalETFstate unavailable'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED121',flush=True)
if __name__=='__main__':main()
