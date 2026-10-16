"""Reviewed firstboard helper atoms; absent limit-event qualification is omitted.
No execution of source modules; literal mathematical helper replay only.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/量化策略/量化策略/首板向上趋势策略2026/04首板-固定点入场-教科书复盘.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source96-20261013'
SPECS=[
 spec('firstboard04_reversal_helper','首板四号止跌K线纯函数',SRC,
 'I(doji body/O<.01 with two positive shadows OR smallgreen body/O<.03 OR hammer lower>2body,upper<.3body,prevRET<-.02 OR simplified morningstar)',
 'proxy: exact reviewed helper mathematics on qfq daily bars; original previous-completed-bar helper delayed1 to preserve timing. NOT complete firstboard strategy: actual limit prices, boarddate, wait2..10, intraday6..15%callback, boardvolume anchor, orders and stops absent. Morningstar is a subset of smallgreen; no extra cluster'),
 spec('firstboard04_stabilization_count','首板四号企稳三条件计数',SRC,
 'lag1(I(C>prevC)+I(L>.99MIN(previous3L))+I(MIN(previous2L)>.99MIN(L_t-4..t-2)))',
 'proxy: exact source3 Boolean conditions including overlapping low windows and strict inequalities; no statistical normalization. Previous-completed-bar timing retained; count produces ties, not original stock economic ordering; full firstboard gates omitted'),
 spec('firstboard04_underma20_stable_partial','跌破均线与止跌条件局部交集',SRC,
 'lag1(I(C<.98MA20(C) AND (reversalHelper OR stabilizationCount>=2)))',
 'proxy: exact remaining daily conjunction ONLY. Actual boardvolume contraction, firstboard eligibility and intraday callback unavailable and omitted; NOT original strategy or complete eligibility. Original order abs(waitdays-4) absent; binary ranking adaptation disclosed')]

def values(f):
 c,o,h,l=[f[k].astype(float) for k in ['close','open','high','low']]
 body=np.abs(c-o);lower=np.minimum(c,o)-l;upper=h-np.maximum(c,o)
 br=body/o;pc=q.delay(c);po=q.delay(o);prevret=q.delay(c)/q.delay(c,2)-1
 reversal=(br<.01)&(lower>0)&(upper>0)
 reversal|=(c>o)&(br<.03)
 reversal|=(lower>2*body)&(upper<.3*body)&(prevret<-.02)
 reversal|=(pc<po)&((po-pc)/po>.02)&(c>o)&(br<.02)
 valid=np.isfinite(c)&np.isfinite(o)&np.isfinite(h)&np.isfinite(l)&(o>0)&np.isfinite(prevret)&np.isfinite(po)
 rv=np.where(valid,reversal.astype(float),np.nan)
 prev3=q.rolling(q.delay(l),3,'min');older3=q.rolling(q.delay(l,2),3,'min');prev2=q.rolling(q.delay(l),2,'min')
 count=(c>pc).astype(int)+(l>.99*prev3).astype(int)+(prev2>.99*older3).astype(int)
 valid2=valid&np.isfinite(prev3)&np.isfinite(older3)&np.isfinite(prev2)
 count=np.where(valid2,count,np.nan)
 ma=q.rolling(c,20);partial=np.where(valid2&np.isfinite(ma),((c<.98*ma)&(reversal|(count>=2))).astype(float),np.nan)
 return [q.delay(rv),q.delay(count),q.delay(partial)]

def literal(df):
 latest,prev=df.iloc[-1],df.iloc[-2];b=abs(latest.close-latest.open);br=b/latest.open
 lower=min(latest.open,latest.close)-latest.low;upper=latest.high-max(latest.open,latest.close)
 prevpct=(prev.close-df.iloc[-3].close)/df.iloc[-3].close
 rv=(br<.01 and lower>0 and upper>0) or (latest.close>latest.open and br<.03) or (lower>b*2 and upper<b*.3 and prevpct<-.02) or (prev.close<prev.open and (prev.open-prev.close)/prev.open>.02 and latest.close>latest.open and br<.02)
 score=sum([latest.close>prev.close,latest.low>df.low.iloc[-4:-1].min()*.99,df.low.iloc[-3:-1].min()>df.low.iloc[-5:-2].min()*.99])
 return [float(rv),float(score),float(latest.close<df.close.iloc[-20:].mean()*.98 and (rv or score>=2))]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all3 reviewed daily atoms fixed before evaluation; no parameter search')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 ids=np.flatnonzero(np.isfinite(f['close'][-700:]).all(axis=0))[:64];sf={k:v[:,ids] for k,v in f.items()};whole=values(sf);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in sf.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True);checks.append(dict(key=sp['key'],test='daily_prefix_completedbar_delay',stop=stop,passed=True))
 for t in [1200,len(cal)-32]:
  for j in range(len(ids)):
   df=pd.DataFrame({k:sf[k][t-31:t,j] for k in ['open','close','high','low']})
   if np.isfinite(df.to_numpy()).all():
    np.testing.assert_allclose([a[t,j] for a in whole],literal(df),rtol=0,atol=0)
 checks.append(dict(test='independent_literal_reviewed_reversal_and_stabilization_helpers',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,[x[pos] for x in values(f)],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='partial exact daily helper atoms, firstboard recipe NOT reproduced'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED96',flush=True)
if __name__=='__main__':main()
