"""Literal three-price smoothed ETF momentum, with disclosed full-A adapters."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/量化策略/量化策略/ETF轮动策略2026/03指数ETF动量轮动策略-25年27.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source128-20261013'
SPECS=[
 spec('etf03_smooth3_ret21_literal','三价和对比二十一日前三价和',SRC,'100*((C+lag1C+lag2C)/(lag21C+lag22C+lag23C)-1)',
 'proxy literal source prior30[-23:-20] denominator and prior[-2:]+14:50price numerator; completed tclose adapter. Eleven fixed ETFs replaced fullAstocks, not original strategy or new family claim. Source any ETF bad quote aborts whole loop; adapted perstockvalidity, source randomduplicate jitter replaced declared tieproxy.'),
 spec('etf03_smooth3_ret21_entry_partial','三价平滑动量及原买入价约束',SRC,'smooth3Ret21 WHERE C>1.001*lag21C',
 'proxy literal strict entry predicate, completedbar fullAstock extension. Original rank1 holding and ETF switch/sale/cash omitted; factor_valid qualified benchmark, not fulluniverse excess.'),
 spec('etf03_ret21_hysteresis_stock_adapter','二十一日收益滞回持仓状态适配',SRC,'causal daily state=1 if C>1.001lag21C,0 if C<.999lag21C,else carry; no quote ->missing',
 'proxy NEW eachstock state adapter of source only-rank1-held sell gate; original singleETF rank-switch/holdoldwhennewfails omitted. Full daily warmup from2018, binaryties audited; not actual ETF strategy.')]
SPECS[1]['gated']=True

@njit(cache=True)
def hysteresis(c):
 out=np.full(c.shape,np.nan)
 for j in range(c.shape[1]):
  state=0.
  for t in range(21,len(c)):
   if not np.isfinite(c[t,j]) or not np.isfinite(c[t-21,j]) or c[t-21,j]<=0:continue
   if c[t,j]>1.001*c[t-21,j]:state=1.
   elif c[t,j]<.999*c[t-21,j]:state=0.
   out[t,j]=state
 return out

def values(f,pos):
 c=f['close'].astype(float);den=c[pos-21]+c[pos-22]+c[pos-23]
 with np.errstate(divide='ignore',invalid='ignore'):raw=100*((c[pos]+c[pos-1]+c[pos-2])/den-1)
 raw=np.where((c[pos]>=.01)&(den/3>=.01),raw,np.nan)
 return [raw,np.where(c[pos]>1.001*c[pos-21],raw,np.nan),hysteresis(c)[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal source3price/21offset/strict.001/.999 fixedbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for s,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=s['key'],test='rawdaily_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   c=sf['close'][:,j].astype(float);prior=c[t-30:t];old=sum(prior[-23:-20]);new=prior[-2]+prior[-1]+c[t]
   ref=(new-old)*100/old if old/3>=.01 and c[t]>=.01 else np.nan
   np.testing.assert_allclose(full[0][i,j],ref,equal_nan=True,atol=1e-8)
 toy=np.ones((26,1))*100;toy[21:,0]=[100.1,100.11,99.9,99.89,100.]
 np.testing.assert_array_equal(hysteresis(toy)[21:,0],[0,1,1,0,0])
 checks.append(dict(test='independent_literal_prior30_python_slices_and_strict_hysteresis_boundary',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='14:50-to-close and fixedETF-to-fullA disclosed; state NEW adapter'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED128',flush=True)
if __name__=='__main__':main()
