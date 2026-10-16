"""Literal differing team-coin source and untested compound daily entry margins."""
import argparse
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
COIN='quant/2024年度精选策略1/81.方正证券-多因子选股系列研究之四：“球队硬币”.txt'
SEVEN='quant/2023年度精选策略/49.【7日趋势】交易策略.txt'
BOLL='quant/2023年度精选策略/93.布林线追龙头战法.txt'
GAP='quant/聚宽2025年精选/54发一个学习策略5年70倍，思路可以学习.txt'
SPECS={45:[
 spec('coin_narrative_interday','硬币叙述版本日间合成',COIN,'-z(RET20*IF(STD20ret>CSmean,1,-1))-z(MEAN20(ret1*IF(delta_turn>CSmean,1,-1)))',
      'proxy: source81 RET20 product distinct from source75 mean daily return; low score oriented by reversal interpretation; raw-price->qfq and volume/floatshares->daily_basic.turnover'),
 spec('coin_narrative_intraday_bug','硬币叙述版本日内源码',COIN,'-z(RET20*IF(STD20intraday>CSmean,1,-1))-z(MEAN20(intraday*delta_turn_flag))',
      'proxy: retains source81 fac3 using RET20 instead of mean intraday return; not silently repaired'),
 spec('coin_narrative_overnight_abs','硬币叙述版本隔夜绝对值',COIN,'-z(abs(MEAN20(open/prevclose-1)))-z(abs(MEAN20(overnight*delta_turn_flag)))',
      'proxy: source fac5 abs removes volatility flip exactly; fac6 same-day turnover flip; low abs preference per source text; distinct source75 distance/lag flag'),
 spec('coin_narrative_final6','硬币叙述版本六腿原合成',COIN,'sum of above three two-leg CS zscore composites; no second group zscoring',
      'proxy: exact source81 additive six-leg final structure with source bugs; qfq and turnover field proxies; all missing preserved'),
],46:[
 spec('seven_day_volume_trend_margin','七日趋势量价完整技术余量',SEVEN,'min((count6(MA13>MA21)-5)/6,(count6(MA21>MA55)-5)/6,(count8(V/prevV>1.7)-3)/8,V/(1.5prevV)-1,C/(1.05O)-1,C/prevC-1)',
      'proxy: literal ACTIVE source conjunction including off-by-one8volume jumps; continuous fullA margin, source size/turnover filters and next-open/intraday orders omitted; not full narrative7candle pattern'),
 spec('boll_three_red_pullback_margin','三均线向上布林回撤余量',BOLL,'min((round(MA_n-lag1MA_n,4)-round(C/10000,4))/C for n25,60,200, round(MA20,2)/C-1)',
      'proxy: exact source three slope rounded thresholds plus below-middle buy atom; index/largecap/quality gates and holding-cost-dependent exits omitted'),
 spec('gap_below_low_trend_margin','上升趋势跌破昨低开盘余量',GAP,'min(.2-(lag1MAX4H/lag1MIN4L-1),lag1C/lag1EMA5_60bar-1,lag1L/O-1)',
      'proxy: source previous4day range<=20%, previousclose>EMA5 computed60bar, current open<prior low; daily signal dated current close and entered nextday label1, source same-open execution not reproduced; no smallcap term'),
]}

@njit
def ema5_last60(c):
 out=np.full(c.shape,np.nan,np.float32)
 for j in range(c.shape[1]):
  for t in range(59,len(c)):
   a=c[t-59:t+1,j]
   if not np.isfinite(a).all():continue
   e=np.mean(a[:5])
   for k in range(5,60):e=e+(a[k]-e)/3
   out[t,j]=e
 return out

def values(batch,f):
 c=f['close'].astype(float);o=f['open'];v=f['volume'];active=f['cap']>0
 if batch==45:
  r=q.ratio(c,q.delay(c))-1;intr=q.ratio(c,o)-1;night=q.ratio(o,q.delay(c))-1
  m=q.ratio(c,q.delay(c,20))-1;dt=f['turnover']-q.delay(f['turnover'])
  thresh=np.nanmean(np.where(active,dt,np.nan),axis=1)[:,None]
  flag=np.where(np.isfinite(dt),np.where(dt>thresh,1,-1),np.nan)
  def volflag(x):
   sd=q.rolling(x,20,'std');threshold=np.nanmean(np.where(active,sd,np.nan),axis=1)[:,None]
   return np.where(np.isfinite(sd),np.where(sd>threshold,1,-1),np.nan)
  z=q.zscore
  a=-z(m*volflag(r))-z(q.rolling(r*flag,20))
  b=-z(m*volflag(intr))-z(q.rolling(intr*flag,20))
  d=-z(np.abs(q.rolling(night,20)))-z(np.abs(q.rolling(night*flag,20)))
  return [a,b,d,a+b+d]
 ma13,ma21,ma55=[q.rolling(c,n) for n in [13,21,55]]
 def count(x,valid,n):return q.rolling(np.where(valid,x,np.nan),n)*n
 x=count(ma13>ma21,np.isfinite(ma13)&np.isfinite(ma21),6)
 y=count(ma21>ma55,np.isfinite(ma21)&np.isfinite(ma55),6)
 vr=q.ratio(v,q.delay(v));b=count(vr>1.7,np.isfinite(vr),8)
 seven=np.min(np.stack([(x-5)/6,(y-5)/6,(b-3)/8,q.ratio(v,1.5*q.delay(v))-1,q.ratio(c,1.05*o)-1,q.ratio(c,q.delay(c))-1]),axis=0)
 slopes=[]
 for n in [25,60,200]:
  ma=q.rolling(c,n);slopes.append(q.ratio(np.round(ma-q.delay(ma),4)-np.round(c/10000,4),c))
 boll=np.min(np.stack(slopes+[q.ratio(np.round(q.rolling(c,20),2),c)-1]),axis=0)
 ranges=q.ratio(q.delay(q.rolling(f['high'],4,'max')),q.delay(q.rolling(f['low'],4,'min')))-1
 gap=np.min(np.stack([.2-ranges,q.ratio(q.delay(c),q.delay(ema5_last60(c)))-1,q.ratio(q.delay(f['low']),o)-1]),axis=0)
 return [seven,boll,gap]

def checks(batch,f):
 # CS thresholds require same universe in both full/prefix comparisons.
 small={k:v[:,np.arange(128)] for k,v in f.items()};full=values(batch,small);out=[]
 for stop in [1200,len(f['close'])-31]:
  cut=values(batch,{k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS[batch],full,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6,rtol=1e-6)
   assert np.isfinite(b).any()
   out.append(dict(key=sp['key'],test='daily_prefix_recompute',stop=stop,passed=True))
 if batch==45:
  toy=np.array([-2.,-.2,0.,.5,2.]);sign=np.array([-1,1,-1,-1,1])
  np.testing.assert_array_equal(np.abs(toy*sign),np.abs(toy))
  out.append(dict(test='source_abs_cancels_volatility_flag',passed=True))
 else:
  a=small['close'][-60:,0];e=a[:5].mean()
  for p in a[5:]:e=e+(p-e)/3
  np.testing.assert_allclose(ema5_last60(small['close'])[-1,0],e,rtol=1e-6)
  out.append(dict(test='independent_window60_EMA_seed5',passed=True))
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--batches',type=int,nargs='+',default=[45,46]);args=p.parse_args()
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 for b in args.batches:
  out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{b}-20261013';out.mkdir(exist_ok=True)
  plan=dict(specs=SPECS[b],rule=q.ALIGNMENT_RULE_VERSION,selection='frozen source conditions before evaluation',platform_compute=0)
  path=out/'frozen_plan.json'
  if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
  q.dump(path,plan)
  if (out/'audit_complete.json').exists():continue
  verify=checks(b,f);v=values(b,f)
  run(out,SPECS[b],[a[pos] for a in v],cal,stocks,f,verify,dict(fidelity='daily source proxy; source executions not reproduced',statistics='exploratory no independent OOS'))
  audit(out,cal,stocks,f);q.dump(out/'audit_complete.json',dict(completed=True,batch=b,platform_compute=0));print('FINISHED',b,flush=True)
if __name__=='__main__':main()
