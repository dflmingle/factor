"""Four exact-period technical inputs from ML notebook; no recreated ML claims."""
import sys,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2021年度精选策略/12.机器学习用于量化分析.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source97-20261013'
LABELS=['RSI20','DIF10_30','DEA10_30_15','MACD10_30_15']
SPECS=[spec('ml12_'+label.lower()+'_'+direction,label+' '+direction,SRC,
 ('-' if direction=='low_control' else '')+label+'(qfqC), MACD=2*(DIF-DEA)',
 'proxy: source RSI20,MACD10/30/15 vendor seed unverified; TA-LibWilder/EMA with finite-segment reset. Raw monetary DIF/DEA/MACD retained, NOT divided by price. High and low directions are preregistered atomic controls; source model learns coefficients and has no fixed direction. External all_jqfactors.pkl, industry neutralization, trained models, global70/30 split and model-selection path NOT reproduced; no new independent cluster claimed')
 for label in LABELS for direction in ['high','low_control']]

def values(f):
 c=f['close'].astype(float);out=[np.full_like(c,np.nan) for _ in LABELS]
 for j in range(c.shape[1]):
  good=np.isfinite(c[:,j])&(c[:,j]>0);edges=np.diff(np.r_[False,good,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
  for start,end in zip(starts,ends):
   x=np.ascontiguousarray(c[start:end,j]);rsi=talib.RSI(x,timeperiod=20)
   dif,dea,hist=talib.MACD(x,fastperiod=10,slowperiod=30,signalperiod=15)
   for a,b in zip(out,[rsi,dif,dea,2*hist]):a[start:end,j]=b
 return [direction*x for x in out for direction in [1,-1]]

def literal(x):
 diff=np.diff(x);up=np.maximum(diff,0);down=np.maximum(-diff,0);u=up[:20].mean();d=down[:20].mean()
 for a,b in zip(up[20:],down[20:]):u=(19*u+a)/20;d=(19*d+b)/20
 rsi=100*u/(u+d) if u+d else 0
 fast=x[20:30].mean();slow=x[:30].mean();ds=[fast-slow]
 for a in x[30:]:
  fast+=2/11*(a-fast);slow+=2/31*(a-slow);ds.append(fast-slow)
 dea=np.mean(ds[:15])
 for d0 in ds[15:]:dea+=2/16*(d0-dea)
 return [rsi,ds[-1],dea,2*(ds[-1]-dea)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='4 sourceinputs each with2 fixeddirection controls; no MLfit or tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-10,atol=1e-10);checks.append(dict(key=sp['key'],test='full_daily_finite_segment_prefix',stop=stop,passed=True))
 rng=np.random.default_rng(9712)
 for _ in range(20):
  x=np.exp(np.cumsum(rng.normal(0,.015,250)))*20
  actual=values({'close':x[:,None]});np.testing.assert_allclose([actual[i][-1,0] for i in [0,2,4,6]],literal(x),rtol=1e-10,atol=1e-10)
 checks.append(dict(test='independent_Wilder20_and_MACD103015_seed_and_recurrence',samples=20,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,[x[pos] for x in values(f)],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='MLtechnical inputs only, highlow atomic controls'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED97',flush=True)
if __name__=='__main__':main()
