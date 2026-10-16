"""Literal bounded momentum plus MA9 eight-below guard; completed stock proxies."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_volume13_state21_20261013 import state
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2023年度精选策略/62.3年复合200+%收益+超低回撤11%以内，无惧大跌.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source138-20261013'
COMMON='proxy 14:37currentquote->completedtclose on fullA ownstock, sourceoriginalfixedfundpool includes leveraged150019/QDII/convertibles. Original maxeligibleETF INDEXvolume and CSI500MA9globalguard replaced ownstock volume/close; notETFstrategy. Source noDecemberban active,1initialETF plus qualifyingoldtop5 mayholdmorethan1,09:58costbased stopand3daycooldown/511880cash/orderstates unreproduced. factor_valid qualified benchmark.'
SPECS=[
 spec('etf62_bounded_ret13_entry','限定涨速十三日收益资格',A,'RET13 WHERE .031<=RET13<.31, C/priorMA13-1>=.001, -.053<RET2<.106, -.0212<RET1<.0636',COMMON+' Actualret>=3.1% dominates>=1%,not originalprose1% minimum. Two close intervalsnotthree days.'),
 spec('etf62_bounded_ret13_volume_priceguard','限定涨速量价双非卖出',A,'boundedRET13 WHERE finite13volumeState7run6!=-1 AND finite17priceState9run8!=-1',COMMON+' Bothownstock guards onpriorbars; literal currentindexdrop<-1.1% produces-2 but source caller comparesONLY-1 so -2 overridesclear (ownstockRET1 analoguekept).'),
 spec('etf62_bounded_safety_margin_extension','限定涨速最小安全余量',A,'min(RET13-.031,.31-RET13,C/priorMA13-1-.001,RET2+.053,.106-RET2,RET1+.0212,.0636-RET1) WHERE allentrygates',COMMON+' NEW continuous weakestboundaryrank, nooriginalstockranking claim, percentratio units.')]
for sp in SPECS:sp['gated']=True

def price_state(c,pos):
 out=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  h=c[t-17:t].astype(float);ok=np.isfinite(h).all(axis=0);d=h-pd.DataFrame(h).rolling(9).mean().to_numpy()
  out[i]=np.where(ok,np.where(d[-1]>=0,np.where((d[-3:]>=0).all(axis=0),1.,0.),np.where((d[-8:]<0).all(axis=0),-1.,0.)),np.nan)
 return out

def values(f,pos):
 c=f['close'].astype(float);r13=c[pos]/c[pos-13]-1;r2=c[pos]/c[pos-2]-1;r1=c[pos]/c[pos-1]-1
 bias=c[pos]/pd.DataFrame(c).rolling(13).mean().shift(1).to_numpy()[pos]-1
 good=(r13>=.031)&(r13<.31)&(bias>=.001)&(r2>-.053)&(r2<.106)&(r1>-.0212)&(r1<.0636)
 v=state(f['volume'],pos);p=price_state(c,pos);p=np.where(r1<-.011,-2.,p)
 qualified=good&np.isfinite(v)&np.isfinite(p)&(v!=-1)&(p!=-1)
 margin=np.minimum.reduce([r13-.031,.31-r13,bias-.001,r2+.053,.106-r2,r1+.0212,.0636-r1])
 return [np.where(good,r13,np.nan),np.where(qualified,r13,np.nan),np.where(good,margin,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal thresholds10.6/31 andclose17MA9/run8,-2override retained beforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_recompute',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   h=sf['close'][t-17:t,j].astype(float)
   if np.isfinite(h).all():
    d=np.array([h[k]-h[k-8:k+1].mean() for k in range(8,17)])
    ref=(1 if (d[-3:]>=0).all() else 0) if d[-1]>=0 else(-1 if(d[-8:]<0).all() else 0)
    np.testing.assert_allclose(price_state(sf['close'],pos[[i]])[0,j],ref)
 checks.append(dict(test='independent17price9means_3up8down',passed=True))
 q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED138',flush=True)
if __name__=='__main__':main()
