"""Causal low-latency filter, literal channel EMA and public Alpha022 proxy."""
import json
import numpy as np
import pandas as pd
from numba import njit
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
LLT='quant/2022年度精选策略/49.LLT低延迟趋势线择时交易初探.txt'
CH='quant/2021年度精选策略/69.（12.3更新v1.2）朱虽自用1号（神虽顶底+趋势）.txt'
ALPHA='quant/2023年度精选策略/61.分享一个最近两年非常有效的因子.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source61-20261013'
SPECS=[
 spec('llt005_relative_slope','低延迟趋势线相对斜率',LLT,'LLT(alpha=.05); initialize first2available closes, recurse source coefficients; LLT/lag1LLT-1',
      'proxy: literal LLT recurrence, original +/-0.5% entry/exit replaced continuous slope, one update per daily bar from20180101warmup; fixed510300ETF replaced fullA individual stocks, source handle_data repeated intraday recurrence not simulated'),
 spec('channel25_90_source200_margin','源码二十五九十日通道余量',CH,'min(C/EMA25adaptive200(H)-1,C/EMA90adaptive200(H)-1); each latest200bar reinitializes EMA, firstn coefficient2/(count+1)',
      'proxy: exact source trend kernel adaptive EMA/reset200; continuous joint upper-channel distance;200daily OHLC replace199daily+one14:30minute high/low, fullA replacesindex, MACD divergence state and actual0/.4/.6/1trade position omitted explicitly'),
 spec('alpha022_public_nan_proxy','公开二十二号量价相关衰减',ALPHA,'-delta5(corr5(H,V))*CSrank(STD20(C))',
      'proxy: source invokes jqlib.alpha101.alpha_022 despite alpha024 comment; published Alpha022 formula independently available but jqlib equivalence not verified; preserve missing/zero-variance correlation asNaN instead of public-library fill0; fullA current saved grid replacesHS300monthlytop5'),
]

@njit
def llt(c):
 out=np.full(c.shape,np.nan);a=.05
 for j in range(c.shape[1]):
  start=-1
  for t in range(len(c)):
   if not np.isfinite(c[t,j]):start=-1;continue
   if start<0:start=t
   if t-start<2:out[t,j]=c[t,j]
   else:out[t,j]=(a-a*a/4)*c[t,j]+a*a/2*c[t-1,j]-(a-.75*a*a)*c[t-2,j]+2*(1-a)*out[t-1,j]-(1-a)**2*out[t-2,j]
 return out

@njit
def channel(high,pos,n):
 out=np.full((len(pos),high.shape[1]),np.nan)
 for i,t in enumerate(pos):
  if t<199:continue
  for j in range(high.shape[1]):
   v=high[t-199,j]
   for k in range(1,200):
    a=2/(min(k+1,n)+1);v=a*high[t-199+k,j]+(1-a)*v
   out[i,j]=v
 return out

def alpha(f,pos):
 h=pd.DataFrame(f['high'].astype(float));v=pd.DataFrame(f['volume'].astype(float));corr=h.rolling(5).corr(v).to_numpy();delta=(corr-q.delay(corr,5))[pos]
 std=q.rolling(f['close'].astype(float),20,'std')[pos];ranks=np.full(std.shape,np.nan)
 for i in range(len(pos)):
  good=np.isfinite(std[i]);ranks[i,good]=rankdata(std[i,good])/good.sum()
 return -delta*ranks

def values(f,pos):
 c=f['close'].astype(float);low=llt(c);slope=(q.ratio(low,q.delay(low))-1)[pos]
 ch=np.minimum(q.ratio(c[pos],channel(f['high'],pos,25))-1,q.ratio(c[pos],channel(f['high'],pos,90))-1)
 return [slope,ch,alpha(f,pos)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source formula and public adaptation fixed before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:256] for k,v in f.items()};full=values(small,pos);checks=[]
 for stop in [1200,len(cal)-31]:
  use=pos<stop;cut=values({k:v[:stop] for k,v in small.items()},pos[use])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[use],b,equal_nan=True,rtol=1e-7,atol=1e-7);checks.append(dict(key=sp['key'],test='daily_prefix_rebuild',stop=stop,passed=True))
 for t in pos[::31]:
  for j in range(8):
   h=small['high'][t-199:t+1,j]
   for n in [25,90]:
    y=h[0]
    for k in range(1,200):
     a=2/(min(k+1,n)+1);y=a*h[k]+(1-a)*y
    np.testing.assert_allclose(channel(small['high'],np.array([t]),n)[0,j],y,equal_nan=True,atol=1e-7)
 checks.append(dict(test='independent_literal_source_adaptiveEMA200',passed=True))
 vals=values(f,pos)
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='explicit source-kernel proxies, not complete original trade strategies',statistics='exploratory no independent OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED61',flush=True)
if __name__=='__main__':main()
