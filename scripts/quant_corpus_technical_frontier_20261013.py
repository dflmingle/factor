"""Unimplemented MACD26 signal, full trend100 and multiweek momentum kernels."""
import sys,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import ols_slope
MACD='quant/2020年度精选策略/08 MACD单因子多头策略.txt'
TREND='quant/2023年度精选策略/33.趋势交易5.0 无择时-2年5倍不是梦.txt'
WEEK='quant/2021年度精选策略/22.“开弓”ETF轮动模型——改.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source52-20261013'
SPECS=[
 spec('macd12_26_26_cross_margin','MACD26信号线金叉余量',MACD,'min((DIF12_26-DEA26)/C,-lag1(DIF-DEA)/lag1C)',
      'proxy: TA-Lib12/26/26 continuous gold-cross conjunction; kuanke.wizard internal MACD_judge_jincha missing, equivalence not asserted; fullA/current daily signal rather than index20day pool'),
 spec('trend100_ma_full_margin','百日多头趋势完整余量',TREND,'min(C/MA100-1,MA30/MA60-1,MA60/MA100-1,pearson_corr(C,time)/.5-1,(slope/intercept)/.005-1,1-HHV30/(1.1C),1-VMA7/(1.5VMA180))',
      'proxy: literal source scipy linregress R (NOT R²) threshold and all technical gates; source index/stocks5/slope ranking omitted, fullA continuous margin'),
 spec('multiweek_momentum_source','一二三四八周加权动量',WEEK,'.4*RET_week1+.2*RET_week2+.15*RET_week3+.2*RET_week4+.05*RET_week8; current partial week close versus completed weekly closes',
      'proxy: exact active source weights/week definitions with current daily close replacing14:25partial week price, individual stocks replace ETF universe; no future week-close filling'),
]

def values(f,cal):
 c=f['close'].astype(float);diff=np.full(c.shape,np.nan)
 for j in range(c.shape[1]):
  # Price series follows documented forward-filled close after IPO, no bfill.
  ids=np.flatnonzero(np.isfinite(c[:,j]))
  if not len(ids):continue
  d,s,h=talib.MACD(np.ascontiguousarray(c[ids[0]:,j]),fastperiod=12,slowperiod=26,signalperiod=26)
  diff[ids[0]:,j]=d-s
 cross=np.minimum(q.ratio(diff,c),-q.ratio(q.delay(diff),q.delay(c)))
 n=100;slope=ols_slope(c,n);intercept=q.rolling(c,n)-slope*(n-1)/2
 cov=slope*((n*n-1)/12);corr=q.ratio(cov,np.sqrt(q.rolling(c,n,'var')*((n-1)/n)*((n*n-1)/12)))
 ma30,ma60,ma100=[q.rolling(c,k) for k in [30,60,100]]
 trend=np.min(np.stack([q.ratio(c,ma100)-1,q.ratio(ma30,ma60)-1,q.ratio(ma60,ma100)-1,corr/.5-1,
  q.ratio(q.ratio(slope,intercept),.005)-1,1-q.ratio(q.rolling(f['high'],30,'max'),1.1*c),1-q.ratio(q.rolling(f['volume'],7),1.5*q.rolling(f['volume'],180))]),axis=0)
 weeks=cal.to_period('W-FRI');done=[];weekly=np.full(c.shape,np.nan)
 for t in range(1,len(cal)):
  if weeks[t]!=weeks[t-1]:done.append(t-1)
  if len(done)>=8:weekly[t]=sum(w*(q.ratio(c[t],c[done[-k]])-1) for k,w in [(1,.4),(2,.2),(3,.15),(4,.2),(8,.05)])
 return [cross,trend,weekly]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source fixed before outcomes',platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:16] for k,v in f.items()};full=values(small,cal);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in small.items()},cal[:stop])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-5,atol=1e-5)
   checks.append(dict(key=sp['key'],test='daily_prefix_recompute_including_partial_week',passed=True,stop=stop))
 v=values(f,cal)
 run(OUT,SPECS,[a[pos] for a in v],cal,stocks,f,checks,dict(fidelity='daily source adaptation; unseen wizard implementation not inferred',statistics='exploratory no independent OOS',residual_guard='constant residual range<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED52',flush=True)
if __name__=='__main__':main()
