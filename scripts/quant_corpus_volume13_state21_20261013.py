"""13-bar finite volume-sign monitor differs from opposite-sign search."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2021年度精选策略/21.策略coding吐槽帖——以“网红”ETF轮动为例.txt'
B='quant/2021年度精选策略/68.蒋老师吐槽了之后，我也想说说对ETF轮动策略的看法.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source132-20261013'
SPECS=[
 spec('etf21_volume13_up3_down6_state','十三根量七均线三上六下状态',A,'prior13V TA_MA7; +1 if last3 V-MA7>=0,-1 if last6<0,else0',
 'proxy literal finite13bar SMA7 of worstETF-associatedINDEX volume replaced eachstock volume. Unlike100bar30oppositesignsearch, no-cross positive returns1 not None. .001price threshold not prose1%, active top1. No fixedETF/globaltiming/executionclaim.'),
 spec('etf21_ret13_finitevolume_qualified','十三日收益与有限量状态约束',A,'C/lag13C-1 WHERE ret>=.001 AND C>=priorMA13 AND finitevolumeState>=0',
 'proxy completed tclose versus11:30 quote, exact sourceinclusive entry and finite13bar monitor, source68MonitorSwitchTrue. Fixed8ETFtop1/sale/5000currency rebalancing threshold omitted. Qualification factor_validbenchmark.'),
 spec('etf21_volume13_nonsell_state','有限量六下非卖出状态',A,'I(finite13barvolumeState != -1)',
 'proxy NEW eachstockrank of sourceonlyglobal CLEARtrigger; does not reproduce a timingportfolio. Binaryties audited, no source121/124no-opposite-None substitution.')]
for sp in SPECS:sp['source_paths']=[A,B]
SPECS[1]['gated']=True

def state(v,pos):
 out=np.full((len(pos),v.shape[1]),np.nan)
 for i,t in enumerate(pos):
  h=v[t-13:t].astype(float);ok=np.isfinite(h).all(axis=0);d=h-pd.DataFrame(h).rolling(7).mean().to_numpy()
  up=(d[-3:]>=0).all(axis=0);down=(d[-6:]<0).all(axis=0)
  out[i]=np.where(ok,np.where(d[-1]>=0,np.where(up,1.,0.),np.where(down,-1.,0.)),np.nan)
 return out

def values(f,pos):
 c=f['close'].astype(float);s=state(f['volume'],pos);ma=pd.DataFrame(c).rolling(13).mean().shift(1).to_numpy()[pos]
 ret=c[pos]/c[pos-13]-1;good=(ret>=.001)&(c[pos]>=ma)&(s>=0)
 return [s,np.where(good,ret,np.nan),np.where(np.isfinite(s),(s!=-1).astype(float),np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal13completevolume/7mean/3up/6down/boundaries beforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='raw13bar_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   h=sf['volume'][t-13:t,j].astype(float)
   if np.isfinite(h).all():
    d=np.array([h[k]-np.mean(h[k-6:k+1]) for k in range(6,13)])
    ref=(1 if (d[-3:]>=0).all() else 0) if d[-1]>=0 else(-1 if(d[-6:]<0).all() else 0)
    np.testing.assert_allclose(full[0][i,j],ref)
 np.testing.assert_array_equal(state(np.ones((14,1)),np.array([13])),[[1.]])
 checks.append(dict(test='independent_literal13bar7means_and_constantvolume_positive_state',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='INDEXvolume-to-ownstock and minute-to-close proxies'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED132',flush=True)
if __name__=='__main__':main()
