"""Extract only causal daily math from reviewed limitup/Longhu strategies."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/7追首板涨停 过去两年年化304%.txt'
B='quant/2023年度精选策略/26.追涨大师（超额142）.txt'
C='quant/2021年度精选策略/89.2020年效果很好的策略-龙回头策略v3.0.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source114-20261013'
SPECS=[
 spec('firstboard7_leftpressure101_volume_ratio','左压回看101条成交量恢复比例',A,'lag1V / MAX(volume prior zyts-1 bars), zyts=distance_to_high_since_t-3+5 with fallback105clamped101',
 'proxy NEW continuous ranking of literal source gate:101 completedcalendarbars, source skips paused bars instead; high/volume qfqcache. Originalauction3%volume/openband/firstlimitup/mainflow/money/size filters missing, only standalone helper, NOT firstboard strategy.'),
 spec('firstboard7_leftpressure101_event','左压成交量九成门槛',A,'I(lastV>.9*MAX(previousV in sourceadaptive101window))',
 'proxy: source strict .9 threshold and starts search[-3::-1]; Boolean stockextension ties, original universe/order path missing. No ratio-based alpha in original, original gate only.'),
 spec('chase26_rawslope121_multiup','多周期非负斜率约束百二十一日拟合',B,'round(OLS121(C),2) where roundedOLS31/46/61/91/360>=0, endingt-1',
 'proxy: source rawprice slopes rounded2, df.drop prior_date notassigned so priorclose remains; qfq price-scale proxy, normalization NOT applied. Missing moneyflow firstboard/net_pct_main>0 and sums over first2/3/4/5/15/20/30 of30 returns, IPO/ST/orderstate omitted; partialqualifiedbenchmark.'),
 spec('dragon89_yingxian_last2_event','近两日源码三点阴线条件',C,'I(anylast2(C<=O AND C<=prevC AND C/prevC<=.97)) endingt-1',
 'proxy: source yingxian returnsTrue after3%drop; narrative4%/body3% not actual. Binary standalone dailyhelper, no Longhu30/2consecutivelimits/pullback20%/minute5%reclaim; dormant Tline/upperwick not added.')]
SPECS[2]['gated']=True

@njit(cache=True)
def pressure(h,v,pos):
 out=np.full((len(pos),h.shape[1]),np.nan)
 for i in range(len(pos)):
  t=pos[i]
  for j in range(h.shape[1]):
   a=h[t-101:t,j];b=v[t-101:t,j]
   if len(a)!=101 or not np.isfinite(a).all() or not np.isfinite(b).all():continue
   d=100
   for k in range(98,-1,-1):
    if a[k]>=a[100]:d=99-k;break
   n=min(d+5,101);prev=np.max(b[101-n:100])
   if prev>0:out[i,j]=b[100]/prev
 return out

def values(f,pos):
 c=f['close'].astype(float);v=pressure(f['high'].astype(float),f['volume'].astype(float),pos);event=np.where(np.isfinite(v),(v>.9).astype(float),np.nan)
 slopes={};
 for n in [31,46,61,91,121,360]:
  x=np.arange(n)-(n-1)/2;s=np.full(v.shape,np.nan)
  for i,t in enumerate(pos):s[i]=(x[:,None]*c[t-n:t]).sum(axis=0)/(x*x).sum()
  slopes[n]=np.round(s,2)
 gate=np.ones(v.shape,dtype=bool)
 for n in [31,46,61,91,360]:gate&=slopes[n]>=0
 qualified=np.where(gate,slopes[121],np.nan)
 prev=q.delay(c);ok=np.isfinite(c)&np.isfinite(f['open'])&np.isfinite(prev);e=np.where(ok,((c<=f['open'])&(c<=prev)&((prev-c)/prev>=.03)).astype(float),np.nan)
 hist=np.stack([e[pos-1],e[pos-2]]);bear=np.where(np.isfinite(hist).all(axis=0),hist.max(axis=0),np.nan)
 return [v,event,qualified,bear]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal adaptivewindow/multihorizon/3percent helpers fixed before outcome')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_adaptivewindow',passed=True))
 obs=0
 for i in [35,79]:
  for j in range(64):
   t=pos[i];h=small['high'][t-101:t,j];v=small['volume'][t-101:t,j]
   if np.isfinite(h).all() and np.isfinite(v).all():
    d=next((i-1 for i,high in enumerate(h[-3::-1],2) if high>=h[-1]),100);vv=v[-(d+5):];ref=vv[-1]/max(vv[:-1]);np.testing.assert_allclose(whole[0][i,j],ref,rtol=1e-7);obs+=1
   if np.isfinite(whole[2][i,j]):
    a=small['close'][t-121:t,j].astype(float);ref=round(float(np.polyfit(np.arange(121),a,1)[0]),2);np.testing.assert_allclose(whole[2][i,j],ref,atol=1e-8)
 checks.append(dict(test='independent_original_reverse_enumerate_and_rounded121_polyfit',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='dailyhelpers only, missing external eventmembership NOT silently fabricated'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED114',flush=True)
if __name__=='__main__':main()
