"""Source weighted log trend and actual all-peer absolute correlation proxies."""
import json
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from threadpoolctl import threadpool_limits
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
TREND='quant/聚宽2025年精选/14安全摸狗策略.txt'
CORR='quant/量化策略/量化策略/ETF轮动策略2026/01趋势筛选后相关性最小etf轮动-调优版-25年62.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source60-20261013'
SPECS=[
 spec('weighted_logtrend25_literal','线性加权对数趋势二十五日',TREND,'(exp(250*slope)-1)*R2; polyfit(logC,time,w=linspace(1,2,25)); R2=1-sum(w*residual²)/sum(w*(logC-unweightedmean)²)',
      'proxy: literal squared fitting weights versus unsquared R2 weights retained; fullA qfq stock adaptation replaces fixed4ETFs, source9:30 prior close mapped to current saved close; no stop or position execution'),
 spec('weighted_logtrend25_safezone','加权趋势源码安全区间',TREND,'weighted_logtrend25_literal only where 0<score<=5',
      'proxy: actual positive/<=5 source qualification retained; factor_valid benchmark on qualified stocks; not whole fullA performance'),
 spec('peer_abs_logreturn_corr244_low','低全池绝对收益相关性',CORR,'-mean_other(abs(corr244(logreturn1_i,logreturn1_j)));245complete closes; exclude self',
      'proxy: actual245price/244logreturn pair correlations with diagonal excluded; fullA replaces fixedETFpool, current grid rather than intraday/monthly trade; no market correlation substitution; forward-filled calendar replaces skip_paused; dormant amount filter not applied'),
 spec('trend40_peer_abs_corr244_low','趋势前四成低同伴相关性',CORR,'top40pct(rank(RET20)+rank(C/MA60-1)), then negative mean absolute244logreturn correlation to qualified peers',
      'proxy: exact source active top_percent=.4 and peer-relative score, continuous individual-stock ranking replaces ETF top4/top2; current signal refresh replaces monthly trend universe; factor_valid qualified benchmark'),
]
SPECS[1]['gated']=True;SPECS[3]['gated']=True

def weighted(c,n=25):
 out=np.full(c.shape,np.nan);w=np.linspace(1,2,n);w2=w*w;x=np.arange(n);xm=np.sum(w2*x)/np.sum(w2);den=np.sum(w2*(x-xm)**2)
 log=np.log(np.where(c>0,c,np.nan))
 for t in range(n-1,len(c)):
  y=log[t-n+1:t+1];ym=np.sum(w2[:,None]*y,axis=0)/np.sum(w2)
  slope=np.sum(w2[:,None]*(x-xm)[:,None]*y,axis=0)/den;intercept=ym-slope*xm
  resid=y-(slope[None,:]*x[:,None]+intercept[None,:])
  r2=1-q.ratio(np.sum(w[:,None]*resid**2,axis=0),np.sum(w[:,None]*(y-np.mean(y,axis=0))**2,axis=0))
  out[t]=np.expm1(250*slope)*r2
 return out

def peer(c,positions,trend):
 allpeer=np.full((len(positions),c.shape[1]),np.nan);qualified=allpeer.copy()
 for i,t in enumerate(positions):
  hist=c[t-244:t+1].astype(float);good=np.isfinite(hist).all(axis=0)&(hist>0).all(axis=0)
  ids=np.flatnonzero(good);r=np.diff(np.log(hist[:,ids]),axis=0);r-=r.mean(axis=0);norm=np.sqrt(np.sum(r*r,axis=0));keep=norm>1e-12;ids=ids[keep];r=r[:,keep]/norm[keep]
  if len(ids)<100:continue
  # Complete-case windows reproduce pandas pair correlation exactly. Blocked
  # multiplication saves memory, not an approximation or market proxy.
  s=np.zeros(len(ids));sub=trend[i,ids];valid=np.isfinite(sub);qual=valid&(sub>=np.quantile(sub[valid],.6)) if valid.any() else valid
  sq=np.zeros(len(ids))
  for start in range(0,len(ids),512):
   stop=min(start+512,len(ids));block=np.abs(r[:,start:stop].T@r)
   s[start:stop]=block.sum(axis=1)-np.diag(block[:,start:stop])
   if qual.sum()>=100:
    sq[start:stop]=block[:,qual].sum(axis=1)-qual[start:stop].astype(float)
  allpeer[i,ids]=-s/(len(ids)-1)
  if qual.sum()>=100:qualified[i,ids[qual]]=-sq[qual]/(qual.sum()-1)
  if i%20==0:print('PEER_CORR',i+1,'/',len(positions),'full',len(ids),'qualified',int(qual.sum()),flush=True)
 return allpeer,qualified

def trendrank(c,pos):
 mom=(q.ratio(c,q.delay(c,20))-1)[pos];bias=(q.ratio(c,q.rolling(c,60))-1)[pos];out=np.full(mom.shape,np.nan)
 for i in range(len(pos)):
  good=np.isfinite(mom[i])&np.isfinite(bias[i]);out[i,good]=rankdata(mom[i,good])/good.sum()+rankdata(bias[i,good])/good.sum()
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='literal source kernels frozen before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);c=f['close'].astype(float);small=c[:,:384];checks=[]
 full=weighted(small);tr=trendrank(small,pos);pa,pq=peer(small,pos,tr)
 for stop in [1200,len(cal)-31]:
  np.testing.assert_allclose(full[:stop],weighted(small[:stop]),equal_nan=True,rtol=1e-8,atol=1e-8)
  use=pos<stop;ta,tq=peer(small[:stop],pos[use],trendrank(small[:stop],pos[use]))
  np.testing.assert_allclose(pa[use],ta,equal_nan=True,atol=1e-8);np.testing.assert_allclose(pq[use],tq,equal_nan=True,atol=1e-8)
  checks.append(dict(test='truncated_daily_weighted_polyfit_and_complete_peer_recompute',stop=stop,passed=True))
 for t in pos[::31]:
  for j in range(8):
   y=np.log(small[t-24:t+1,j]);x=np.arange(25);w=np.linspace(1,2,25);s,b=np.polyfit(x,y,1,w=w)
   den=np.sum(w*(y-y.mean())**2)
   ref=np.expm1(250*s)*(1-np.sum(w*(y-s*x-b)**2)/den) if den>1e-12 else np.nan
   np.testing.assert_allclose(full[t,j],ref,equal_nan=True,rtol=1e-6,atol=1e-6)
 checks.append(dict(test='independent_numpy_polyfit_source_literal',passed=True))
 for i,t in enumerate(pos[::31]):
  hist=pd.DataFrame(small[t-244:t+1]).dropna(axis=1);ref=np.log(hist).diff().iloc[1:].corr().abs();np.fill_diagonal(ref.values,np.nan)
  np.testing.assert_allclose(pa[i*31,ref.columns],-ref.mean().to_numpy(),equal_nan=True,atol=1e-8)
 checks.append(dict(test='independent_pandas_paircorr_diagonal_exclusion',passed=True))
 v=weighted(c)[pos];safe=np.where((v>0)&(v<=5),v,np.nan)
 with threadpool_limits(limits=8):a,b=peer(c,pos,trendrank(c,pos))
 run(OUT,SPECS,[v,safe,a,b],cal,stocks,f,checks,dict(fidelity='explicit ETF-to-stock factor adaptations; original portfolio not reproduced',statistics='exploratory no independent study OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED60',flush=True)
if __name__=='__main__':main()
