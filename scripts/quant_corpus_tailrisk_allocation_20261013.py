"""Unexamined risk kernels from allocation sources, explicit stock adaptations."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
VOL='quant/2021年度精选策略/7.股债波动平衡.txt'
ES='quant/2024年度精选策略1/72.桥水 全天候策略 增加一致性度量ES 风险控制.txt'
ES2='quant/2024年度精选策略2/65.神级策略：桥水全天候策略-7年最大回撤仅3.5%.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source95-20261013'
SPECS=[
 spec('allocation_clipped_logvol39_low','四十价点裁剪对数波动低值',VOL,
 '-sampleSTD(clip(logreturns39,mean39+-3sampleSTD39))*sqrt250*100;40closes',
 'proxy: exact source40closes->39returns and perwindow sampleSTD/mean clipping before volatility; new stockalpha direction from inversevariance allocation with equal priors, original fixed8fund weights NOT replicated; qfq fullA replaces post-adjustedfunds, no down=True unused branch'),
 spec('allocation_es120_source_tail2_low','一百二十日尾部两收益风险低值',ES,
 'sum(two smallest of119returns plus first0)/int(120*(1-.99));120close observations',
 'proxy: source <=floor(1.2) includes TWO observations but divides1; literal source offbyone retained. Calendar weekend zeros removed in explicit tradingday stockadaptation, original firstreturn0 retained; require119 knownreturns, no unavailable stockprice null0fill; no multiasset allocation claim'),
 spec('allocation_es120_fractional_tail2_low','一百二十日分数分母尾险低值',ES2,
 'sum(two smallest of119returns plus first0)/(120*(1-.99))',
 'proxy: source i<1.2 includes TWO but denominator1.2 retained; same tradingday adaptation as other ES, proportional control expected SAMEranking, not independent mechanism or newcluster; source fixedfourETF/positions not replicated')]

@njit
def kernels(c):
 out=np.full((3,)+c.shape,np.nan)
 for j in range(c.shape[1]):
  for t in range(39,len(c)):
   y=c[t-39:t+1,j]
   if np.isfinite(y).all() and (y>0).all():
    r=np.log(y[1:]/y[:-1]);m=r.mean();sd=np.sqrt(((r-m)**2).sum()/38)
    clipped=np.minimum(np.maximum(r,m-3*sd),m+3*sd);d=clipped-clipped.mean()
    out[0,t,j]=-np.sqrt((d*d).sum()/38)*np.sqrt(250)*100
   if t<119:continue
   y=c[t-119:t+1,j]
   if not np.isfinite(y).all() or not (y>0).all():continue
   r=np.zeros(120);r[1:]=y[1:]/y[:-1]-1;tail=np.sort(r)[:2].sum()
   out[1,t,j]=tail/int(120*(1-.99));out[2,t,j]=tail/(120*(1-.99))
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='exact sourcekernel defaults plus proportionalcontrol frozenbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64].astype(float);whole=kernels(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=kernels(small[:stop]);np.testing.assert_allclose(whole[:,:stop],cut,equal_nan=True,atol=1e-9)
  checks.append(dict(test='dailyrawprefix_kernel_recompute',stop=stop,passed=True))
 for t in [1200,len(cal)-32]:
  for j in range(12):
   y=small[t-39:t+1,j]
   if np.isfinite(y).all():
    r=pd.Series(np.log(y[1:]/y[:-1]));ref=-r.clip(r.mean()-3*r.std(),r.mean()+3*r.std()).std()*np.sqrt(250)*100
    np.testing.assert_allclose(whole[0,t,j],ref,rtol=1e-9)
   y=small[t-119:t+1,j]
   if np.isfinite(y).all():
    r=pd.Series(y).pct_change().fillna(0);ss=sorted(r);ref=sum(ss[i] for i in range(len(ss)) if i<=int(120*(1-.99)))/int(120*(1-.99))
    np.testing.assert_allclose(whole[1,t,j],ref,rtol=1e-9)
 checks.append(dict(test='independent_pandas_literal_clip_and_ES_loop',passed=True))
 q.dump(OUT/'source_evidence.json',{p:read_text(q.ROOT/p) for p in [VOL,ES,ES2]})
 cache=OUT/'daily_kernels.pkl'
 if cache.exists():vals=pd.read_pickle(cache)
 else:vals=kernels(f['close'].astype(float));pd.to_pickle(vals,cache)
 run(OUT,SPECS,[x[pos] for x in vals],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='allocation kernel to stockproxy, proportionalES forms sameinformation',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED95',flush=True)
if __name__=='__main__':main()
