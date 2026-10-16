"""Chip-distribution source moments; missing custom ops explicitly proxied."""
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source8-20261012'
SOURCE='quant/2024年度精选策略1/77.【复现】筹码分布因子.txt'
SPECS=[{'key':f'chip60_{name}_{side}','name':f'筹码60日{label}{"低" if sign==-1 else "高"}',
 'source_paths':[SOURCE],'formula':f'{sign}*{name}(60 prior-day VWAPs, turnover survival weights)',
 'fidelity':'source moment definition, missing imported custom ops proxied; direction not specified, both signs frozen',
 'gated':False} for name,label in [('arc','平均盈亏'),('vrc','分散度'),('src','偏度'),('krc','峰度')]
 for side,sign in [('low',-1),('high',1)]]

@njit(cache=True)
def moments(price,turn,positions):
 out=np.full((4,len(positions),price.shape[1]),np.nan,np.float32)
 for i in range(len(positions)):
  t=positions[i]
  if t<60:continue
  for j in range(price.shape[1]):
   now=price[t,j]
   if not np.isfinite(now) or now<=0:continue
   w=np.empty(60,np.float64);rc=np.empty(60,np.float64);survive=1.;valid=True
   for k in range(60):
    day=t-1-k;latest=turn[day+1,j];old=turn[day,j];p=price[day,j]
    if not np.isfinite(latest) or not np.isfinite(old) or not np.isfinite(p) or p<=0:
     valid=False;break
    if latest<0 or latest>=1 or old<0 or old>=1:
     valid=False;break
    survive*=1-latest;w[k]=old*survive;rc[k]=(now-p)/now
   if not valid or w.sum()<=0:continue
   w=w/w.sum();arc=np.sum(w*rc);diff=rc-arc
   vrc=np.sum(w*diff**2)*60/59
   out[0,i,j]=arc;out[1,i,j]=vrc
   if vrc>1e-15:
    out[2,i,j]=np.sum(w*diff**3)*60/59/vrc**1.5
    out[3,i,j]=np.sum(w*diff**4)*60/59/vrc**2
 return out

def verify(price,turn,positions,computed):
 checks=[]
 for stop in [int(positions[31])+1,int(positions[77])+1]:
  mask=positions<stop;cut=moments(price[:stop],turn[:stop],positions[mask])
  np.testing.assert_allclose(computed[:,mask],cut,equal_nan=True,rtol=1e-6,atol=1e-6)
  checks.append({'test':'prefix_daily_recompute','stop':stop,'passed':True})
 rng=np.random.default_rng(918273)
 p=np.exp(rng.normal(0,.1,(80,4)));tr=rng.uniform(.001,.10,(80,4));ix=np.array([60,79])
 actual=moments(p,tr,ix)
 for i,t in enumerate(ix):
  for j in range(4):
   weights=np.array([tr[d,j]*np.prod(1-tr[d+1:t+1,j]) for d in range(t-60,t)])
   weights/=weights.sum();returns=(p[t,j]-p[t-60:t,j])/p[t,j]
   mean=np.dot(weights,returns);diff=returns-mean;var=np.dot(weights,diff**2)*60/59
   expected=[mean,var,np.dot(weights,diff**3)*60/59/var**1.5,np.dot(weights,diff**4)*60/59/var**2]
   np.testing.assert_allclose(actual[:,i,j],expected,rtol=1e-5,atol=1e-6)
 checks.append({'test':'independent_product_weights_and_four_moments','passed':True})
 return checks

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 price=q.ratio(f['amount']*1000,f['volume']*100)*q.ratio(f['close'],f['raw_close'])
 turn=f['turnover']/100;computed=moments(price,turn,pos)
 verification=verify(price,turn,pos,computed)
 vals=[sign*computed[i] for i in range(4) for sign in [-1,1]]
 run(OUT,SPECS,vals,calendar,stocks,f,verification,{'proxy':'custom imported scr operators absent; turnover survival weighting explicitly reconstructed',
  'price':'qfq-adjusted raw daily VWAP (amount thousand yuan/volume hundred shares)',
  'turnover':'cached daily_basic turnover_rate percent divided by100; 100% or invalid daily rate excludes window',
  'window':'60 prior trading observations excluding today; today only reference VWAP; complete window required',
  'directions':'source signs unavailable; all eight sign hypotheses counted, no post-hoc sign choice',
  'model':'source Transformer not reproduced; atomic moments only'})
if __name__=='__main__':main()
