"""Reset-window RTS smoother and explicitly ordered WR/RSRS exits."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_lowlog2_motion36_20261013 import rsrs_series
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/18.动量ETF轮动-RSRS择时-卡尔曼滤波.txt'
B='quant/2024年度精选策略1/42.大盘ETF动量轮动RSRS择时策略-无纳指（5年半861%）.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source147-20261013'
SPECS=[
 spec('kalman18_reset20_normalized_slope','二十价卡尔曼平滑斜率',A,'OLS20(RTSsmooth20(C/Cfirst,Q=.1,R=.15,P0=.15,mean0=Cfirst/Cfirst)).slope',
 'proxy fullAstock replaces4ETF; exact source kf.smooth reset20 not fullhistory smoothed20. Backward smoothing only within each historical completed20window; no future beyond signal. The normalized20pricekernel is known but smoothing transform was not previously reproduced. Source returns [code,score] pair to order iterators defect, not fullstrategy.'),
 spec('kalman18_reset20_rsrs_nonsell','卡尔曼斜率与RSRS非卖出',A,'reset20_Kalman_slope WHERE rsrs18_z600_R2>=-.7',
 'proxy NEW perstock joint gate replacesGLOBALHS300, rolling600seed proxy; source BUY/KEEP bothadjust, not persistenthysteresis. Same reset20 source parameters; factor_valid qualifiedbenchmark; no ETFportfolio.'),
 spec('guard42_WR_RSRS_slope8_nonsell','WR优先的多分支RSRS非卖出',B,'priority: WR14>=97 AND WR21>=97 BUY; rsSlope8<0 AND rs>0 SELL; priceSlope8<0 AND rsSlope8>0 AND rs<-.43 SELL; priceSlope8>12 AND rsSlope8>0 BUY; else rs>-.68',
 'proxy NEW individualstock fullA adapter of globalHS300. Exact WR positive0..100 convention reconstructed from OHLC; jqlib internals unverified proxy. Literal12 absolute INDEXpricepoints is retained on stockqfqprice, not silently normalized/retuned. Rolling600RSRSseed, source19/4.8motionstop/1.04holding/60minMA20 not included in this guardatom; no orderclaim.')]
SPECS[1]['gated']=True

def smooth_weights(n=20):
 # Kalman covariance path independent of observations. Compute affine linear
 # transform on basis vectors, using original reset initial guess y[0].
 def smooth(y):
  m=np.zeros(n);p=np.zeros(n);pred=np.zeros(n);pc=np.zeros(n)
  for t in range(n):
   pred[t]=y[0] if t==0 else m[t-1];pc[t]=.15 if t==0 else p[t-1]+.1
   gain=pc[t]/(pc[t]+.15);m[t]=pred[t]+gain*(y[t]-pred[t]);p[t]=(1-gain)*pc[t]
  for t in range(n-2,-1,-1):m[t]+=p[t]/pc[t+1]*(m[t+1]-pred[t+1])
  return m
 x=np.arange(n)-(n-1)/2
 return np.array([x@smooth(np.eye(n)[:,j])/(x@x) for j in range(n)])

def ref_smooth(y):
 # Independent Gaussian precision solve: P0=.15 and fixed mean0=y[0].
 n=len(y);precision=np.eye(n)/.15;rhs=y/.15;precision[0,0]+=1/.15;rhs[0]+=y[0]/.15
 for i in range(1,n):
  precision[i,i]+=10;precision[i-1,i-1]+=10;precision[i,i-1]-=10;precision[i-1,i]-=10
 return np.linalg.solve(precision,rhs)

def priority(w14,w21,rs,sl,price):
 valid=np.isfinite(w14)&np.isfinite(w21)&np.isfinite(rs)&np.isfinite(sl)&np.isfinite(price)
 allow=np.where((w14>=97)&(w21>=97),True,np.where((sl<0)&(rs>0),False,np.where((price<0)&(sl>0)&(rs<-.43),False,np.where((price>12)&(sl>0),True,rs>-.68))))
 return np.where(valid,allow.astype(float),np.nan)

def values(f,pos):
 c=f['close'].astype(float);out=np.full((len(pos),c.shape[1]),np.nan);weights=smooth_weights()
 for i,t in enumerate(pos):
  a=c[t-19:t+1];out[i]=np.sum(weights[:,None]*(a/a[0]),axis=0)
 rs,sl=rsrs_series(f);cv=pd.DataFrame(c);hh=pd.DataFrame(f['high'].astype(float));ll=pd.DataFrame(f['low'].astype(float))
 wr=[]
 for n in [14,21]:
  hi=hh.rolling(n).max().to_numpy()[pos];lo=ll.rolling(n).min().to_numpy()[pos]
  wr.append(100*(hi-c[pos])/(hi-lo))
 ps=np.full(out.shape,np.nan);x=np.arange(8)-3.5
 for i,t in enumerate(pos):ps[i]=(x[:,None]*c[t-7:t+1]).sum(axis=0)/(x*x).sum()
 return [out,np.where(np.isfinite(rs[pos])&(rs[pos]>=-.7),out,np.nan),priority(*wr,rs[pos],sl[pos],ps)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixed reset20 Q.1R.15 and WRpriority beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:32] for k,v in f.items()};full=values(sf,pos);checks=[]
 for nn in [35,79]:
  cut=values({k:v[:pos[nn-1]+1] for k,v in sf.items()},pos[:nn])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:nn],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_reset_smoother_no_future',passed=True))
 for i in [35,79]:
  for j in range(32):
   t=pos[i];a=sf['close'][t-19:t+1,j].astype(float)
   if np.isfinite(a).all():np.testing.assert_allclose(full[0][i,j],np.polyfit(np.arange(20),ref_smooth(a/a[0]),1)[0],atol=1e-9)
 checks.append(dict(test='independent_Gaussian_precision_solve_matches_reset_RTS',passed=True))
 tests=[(98,98,1,-1,-1,1),(0,0,1,-1,20,0),(0,0,-.5,1,-1,0),(0,0,-1,1,13,1),(0,0,-.68,0,0,0),(0,0,-.679,0,0,1)]
 for a,b,r,s,p,want in tests:assert priority(a,b,r,s,p)==want
 checks.append(dict(test='WR_priority_and_strict_RSRS_price_branch_toy',passed=True))
 q.dump(OUT/'source_evidence.json',{p:read_text(q.ROOT/p) for p in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='ETF/index adaptation; no futurewindow smoothing'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED147',flush=True)
if __name__=='__main__':main()
