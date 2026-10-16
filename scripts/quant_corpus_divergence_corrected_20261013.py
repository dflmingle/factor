"""Literal source MACD divergence state, including barslast off-by-one semantics."""
import json
import numpy as np
import pandas as pd
from numba import njit,prange,set_num_threads
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2021年度精选策略/69.（12.3更新v1.2）朱虽自用1号（神虽顶底+趋势）.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source66-20261013'
SPECS=[spec('macd199flags_corrected_divergence_state','一九九状态列纠正背离结构',SOURCE,
 '2*bottomgender+bottom-2*topgender-top; core_ssdd latest200close adaptiveEMA12/26/9,3cross-segment comparisons, persistent perstock199 flags',
 'proxy: exact core_ssdd flags and source starts199flags and append/pop preserves199; barslast199=199-index means latest stored flag age1; current dailyclose replaces199daily+currentminute; require3dead+3gold and complete200prices, pushfalse on undefined stocks instead of crashing; sourceindex/ETF portfolio exposure and tradeHelper24/isReal filters not simulated; binary ranked score has exact ties, jitter diagnostic required')]

@njit
def ema_window(y,n):
 out=np.empty(len(y));out[0]=y[0]
 for k in range(1,len(y)):
  a=2/(min(k+1,n)+1);out[k]=a*y[k]+(1-a)*out[k-1]
 return out

@njit(parallel=True)
def state(c):
 out=np.full(c.shape,np.nan)
 for j in prange(c.shape[1]):
  pt=False;pt2=False;ptg=False;ptg2=False;pb=False;pb2=False;pbg=False;pbg2=False
  for t in range(199,len(c)):
   y=c[t-199:t+1,j];ok=True
   for k in range(200):
    if not np.isfinite(y[k]):ok=False
   nt=False;ntg=False;nb=False;nbg=False
   if ok:
    dif=ema_window(y,12)-ema_window(y,26);hist=dif-ema_window(dif,9);deads=[];golds=[]
    for k in range(1,200):
     if hist[k]<0 and hist[k-1]>=0:deads.append(200-k)
     if hist[k]>0 and hist[k-1]<=0:golds.append(200-k)
    if len(deads)>=3 and len(golds)>=3:
     d1,d2,d3=deads[-1],deads[-2],deads[-3];g1,g2,g3=golds[-1],golds[-2],golds[-3]
     # Literal source uses [-age:-age] slices and drops the boundary cross.
     if d1>g1:
      last=y[200-g2:200-d1];second=y[200-g3:200-d2];ld=dif[200-g2:200-d1];sd=dif[200-g3:200-d2];now=dif[200-g1:]
      if len(last) and len(second) and len(ld) and len(sd) and len(now):
       maxlast=np.max(ld);maxsecond=np.max(sd);maxnow=np.max(now);age1=pt
       if age1:
        ntg=dif[-1]<=dif[-2]*.99 or (ptg and dif[-1]<=dif[-2]*1.01)
       if dif[-1]<=maxlast and maxnow<=maxlast:nt=y[-1]>np.max(last) or age1
       elif dif[-1]>maxlast and dif[-1]<maxsecond and maxnow<maxsecond:nt=y[-1]>np.max(second) or age1
     elif d1==1 and pt:
      ntg=dif[-1]<=dif[-2]*.99
     if d1<g1:
      last=y[200-d2:200-g1];second=y[200-d3:200-g2];ld=dif[200-d2:200-g1];sd=dif[200-d3:200-g2];now=dif[200-d1:]
      if len(last) and len(second) and len(ld) and len(sd) and len(now):
       minlast=np.min(ld);minsecond=np.min(sd);minnow=np.min(now);age1=pb
       if age1:
        nbg=dif[-1]>=dif[-2]*.99 or (pbg and dif[-1]>=dif[-2]*1.01)
       if dif[-1]>=minlast and minnow>=minlast:nb=y[-1]<np.min(last) or age1
       # Source second-green branch still compares price to LAST greens.
       elif dif[-1]<minlast and dif[-1]>=minsecond and minnow>=minsecond:nb=y[-1]<np.min(last) or age1
     elif g1==1 and pb:
      nbg=dif[-1]>=dif[-2]*.99
     out[t,j]=2*int(nbg)+int(nb)-2*int(ntg)-int(nt)
   pt2=pt;pt=nt;ptg2=ptg;ptg=ntg;pb2=pb;pb=nb;pbg2=pbg;pbg=nbg
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='corrected source199flaglist state and sign frozen before outcomes',platform_compute=0,tie_seeds=[918273,918274,918275])
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 set_num_threads(4);cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);c=f['close'].astype(float);small=c[:,:256];whole=state(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=state(small[:stop]);np.testing.assert_allclose(whole[:stop],cut,equal_nan=True);checks.append(dict(test='entire_daily_state_prefix_recompute_with_source200window_resets',stop=stop,passed=True))
 print('DIVERGENCE_FULL_START',flush=True);daily=state(c);v=daily[pos]
 q.dump(OUT/'state_coverage.json',dict(valid=np.isfinite(v).sum(axis=1).tolist(),nonzero=((v!=0)&np.isfinite(v)).sum(axis=1).tolist(),states=np.unique(v[np.isfinite(v)]).tolist(),source_flags_offbyone='source actual199flaglist barslast=199-index; age1 is latest event'))
 run(OUT,SPECS,[v],cal,stocks,f,checks,dict(fidelity='literal core divergence only; portfolio filters omitted',statistics='exploratory no independent OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dates_all=cal;rows=[]
 for seed in [918273,918274,918275]:
  rng=np.random.default_rng(seed);z=v.copy();good=np.isfinite(z);z[good]+=rng.uniform(-1e-5,1e-5,good.sum())
  for win,take in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
   a,_,_=q.evaluate(z[take],grid[take],stocks,pos[take],f);rows.append(dict(seed=seed,window=win,interpretation='tie-order return diagnostic; IC changes not original factor IC',**a))
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'tie_sensitivity.csv',index=False)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED66',flush=True)
if __name__=='__main__':main()
