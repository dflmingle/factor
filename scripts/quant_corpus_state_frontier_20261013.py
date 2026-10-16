"""Causal source extreme-state and actual turtle parameter adaptations."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
EXT='quant/2021年度精选策略/23.玩趋势交易的看进来~~~~2.txt'
TUR='quant/2022年度精选策略/27.海龟交易体系-多资产版.txt'
BRK='quant/2023年度精选策略/44.海龟突破系统，19-21年化150，无未来函数和过拟合.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source53-20261013'
SPECS=[
 spec('ma8_extreme_threshold_distance','八日均线极值阈值距离',EXT,'MA8/current_confirmed_extreme-1; replay each latest508 closes, initialize extreme at local index8, update only beyond +/-4%',
      'proxy: causal current displacement from source extreme, not retrospective plotted transition lines; source has no specified trading/ranking rule, high upward displacement chosen before evaluation; original window508/reset retained'),
 spec('turtle20_atr_breakout','二十日海龟突破距离',TUR,'(C-lag1(HHV20(H)))/lag1(ATR20)',
      'proxy: source20bar high breakout and20bar volatility scale; Wilder unrounded ATR initialization, qfq daily close replaces minute price; not source fixed asset/position/add-on/stop execution'),
 spec('breakout81_prior_reversal_margin','八十一日突破前期回落余量',BRK,'min(C/lag1(HHV81(H))-1,-(lag1(C)/lag9(C)-1))',
      'proxy: actual code g.p55=81 (NOT comment55), previous9 closes span8gaps and negative return; continuous all-conjunction margin, qfq daily C replaces intraday; PE descending and HS300/stop-profit omitted'),
]

@njit
def extreme_sample(ma,pos):
 out=np.full((len(pos),ma.shape[1]),np.nan)
 for i,t in enumerate(pos):
  # Source508-price window first defined rolling mean at7; initial value index8.
  start=t-507+8
  if start<0:continue
  for j in range(ma.shape[1]):
   ep=ma[start,j]
   if not np.isfinite(ep):continue
   for k in range(start,t+1):
    v=ma[k,j]
    if v>ep*1.04:ep=v
    if v<ep*.96:ep=v
   if ep>0 and np.isfinite(ma[t,j]):out[i,j]=ma[t,j]/ep-1
 return out

@njit
def atr20(tr):
 out=np.full(tr.shape,np.nan)
 for j in range(tr.shape[1]):
  n=0;total=0.;last=np.nan
  for t in range(len(tr)):
   x=tr[t,j]
   if not np.isfinite(x):n=0;total=0.;last=np.nan;continue
   if n<20:
    total+=x;n+=1
    if n==20:last=total/20
   else:last=(last*19+x)/20
   out[t,j]=last
 return out

def values(f,pos):
 c=f['close'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float)
 tr=np.maximum.reduce([h-l,h-q.delay(c),q.delay(c)-l])
 a=atr20(tr)
 ex=extreme_sample(q.rolling(c,8),pos)
 tur=q.ratio(c-q.delay(q.rolling(h,20,'max')),q.delay(a))
 brk=np.minimum(q.ratio(c,q.delay(q.rolling(h,81,'max')))-1,-(q.ratio(q.delay(c),q.delay(c,9))-1))
 return [ex,tur[pos],brk[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source fixed before outcomes',platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:16] for k,v in f.items()};full=values(small,pos);checks=[]
 for stop in [1200,len(cal)-31]:
  take=pos<stop;cut=values({k:v[:stop] for k,v in small.items()},pos[take])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[take],b,equal_nan=True,rtol=1e-7,atol=1e-7)
   checks.append(dict(key=sp['key'],test='truncated_market_recompute_state_and_daily_features',stop=stop,passed=True))
 ma=q.rolling(small['close'],8)
 for i,t in enumerate(pos[::31]):
  for j in range(16):
   local=pd.Series(small['close'][t-507:t+1,j]).rolling(8).mean().to_numpy();ep=local[8]
   for v in local[8:]:
    if v>ep*1.04:ep=v
    if v<ep*.96:ep=v
   ref=local[-1]/ep-1 if ep>0 else np.nan
   np.testing.assert_allclose(full[0][i*31,j],ref,equal_nan=True,rtol=1e-6,atol=1e-6)
 checks.append(dict(key=SPECS[0]['key'],test='independent_literal_source508price_rolling8_loop',passed=True))
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no independent OOS',fidelity='source-grounded fullA stock proxies; fixed portfolio strategies not reproduced',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED53',flush=True)
if __name__=='__main__':main()
