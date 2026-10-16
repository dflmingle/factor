"""Source69 path-dependent peak/prior-trough/subsequent-trough kernels."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略2/69.场内基金定投价值平均增强策略，年化30%+.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source101-20261013'
SPECS=[
 spec('valueavg69_peak375_prior625_retracement','高点前三低点与高点后回撤占比',SRC,
 '-(1-(peak375-minCloseAfterPeak)/(peak375-min625CloseEndingAtPeak)), priorclose input',
 'proxy: exact reviewed max_increase mathematical path, source counts375.0/625.0 explicitly repaired to integer375/625. First idxmax ties retained, subsequent min is running minimum AFTER chosenpeak, not currentclose; require complete375 and chosenpeak625 history. Source final399324/159905 index/ETF->stockextension only; no monthly0.5% valueaveraging/cash/IRR/cost-state strategy claims'),
 spec('valueavg69_peak375_deep_retracement_event','高点前后深回撤入场事件',SRC,
 'I(max_increase.rate1<.318), priorclose input',
 'proxy: exact source entrythreshold .318; binary stockranking is explicit adaptation, source oneasset stateentry originally has no economic crosssection ordering; qfq/closeffill contract and integercount repair. Full strategy not reproduced, ties audited'),
 spec('valueavg69_peak250_aftermin_risk_low','一年高点至随后低点回撤低值',SRC,
 '-100*(MAX250Close/MINCloseAfterFirst250Peak-1), priorclose input',
 'proxy: exact max_increase1y kernel including argmax/AFTERpeak minimum; low risk direction is NEW crosssection adaptation of source >75percent exit threshold, not source stockalpha ranking. Currentclose not substituted for afterpeakmin; ETF/index/cash/positionstate absent')]

@njit(cache=True)
def kernels(c,pos):
 a=np.full((len(pos),c.shape[1]),np.nan);b=a.copy();d=a.copy()
 for i in range(len(pos)):
  t=pos[i]-1
  for j in range(c.shape[1]):
   if t<374:continue
   peak=-np.inf;p=-1;valid=True
   for k in range(t-374,t+1):
    x=c[k,j]
    if not np.isfinite(x) or x<=0:valid=False;break
    if x>peak:peak=x;p=k
   if valid and p>=624:
    pre=np.inf;post=np.inf
    for k in range(p-624,p+1):
     x=c[k,j]
     if not np.isfinite(x) or x<=0:valid=False;break
     if x<pre:pre=x
    if valid:
     for k in range(p,t+1):post=min(post,c[k,j])
     if peak>pre:
      rate=1-(peak-post)/(peak-pre);a[i,j]=-rate;b[i,j]=1.0 if rate<.318 else 0.0
   peak=-np.inf;p=-1;valid=True
   for k in range(t-249,t+1):
    x=c[k,j]
    if not np.isfinite(x) or x<=0:valid=False;break
    if x>peak:peak=x;p=k
   if valid:
    post=np.inf
    for k in range(p,t+1):post=min(post,c[k,j])
    d[i,j]=-100*(peak/post-1)
 return [a,b,d]

def literal(s,t):
 x=s.iloc[t-374:t+1];peak=x.max();p=x.idxmax();pre=s.iloc[p-624:p+1]
 a=b=np.nan
 if np.isfinite(x).all() and p>=624 and np.isfinite(pre).all() and peak>pre.min():
  rate=1-(peak-s.iloc[p:t+1].min())/(peak-pre.min());a=-rate;b=float(rate<.318)
 x=s.iloc[t-249:t+1];peak=x.max();p=x.idxmax();d=np.nan
 if np.isfinite(x).all():d=-100*(peak/s.iloc[p:t+1].min()-1)
 return [a,b,d]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='actual375/625/250 and.318 fixed, no parametersearch')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64].astype(float);whole=kernels(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=kernels(small[:stop],pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=0,atol=0);checks.append(dict(key=sp['key'],test='raw_daily_prefix_selectedpeak_history',stop=stop,passed=True))
 obs=0
 for i in [5,35,79,119]:
  for j in range(64):
   s=pd.Series(small[:,j]);ref=literal(s,pos[i]-1);np.testing.assert_allclose([v[i,j] for v in whole],ref,equal_nan=True,atol=1e-10);obs+=1
 # Adversarial firstpeak tie and recovery AFTER the running trough.
 s=pd.Series(np.linspace(8,10,1200));s.iloc[950]=20;s.iloc[960]=20;s.iloc[980]=6;s.iloc[1100:]=15
 toy=kernels(s.to_numpy()[:,None],np.array([1151]));np.testing.assert_allclose([x[0,0] for x in toy],literal(s,1150),atol=1e-10)
 assert toy[0][0,0]>0 and s.iloc[1150]>s.iloc[980]
 checks.append(dict(test='independent_pandas_idxmax_pre625_aftermin_and_tie_recovery',observations=obs+1,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 vals=kernels(f['close'].astype(float),pos);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='reviewed pathkernels stockadaptation; requireselectedpeak fullhistory'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED101',flush=True)
if __name__=='__main__':main()
