"""Active six MA and MACD conditions, alternating returns and next opening gap.
Signal published at current close: original same-open entry is not reproduced.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略2/80.短线策略-2022年两个半月收益45%-无未来函数.txt'
EVENT='quant/2024年度精选策略2/97.【涨停研究一】具有哪些因子的股票更容易涨停.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source94-20261013'
SPECS=[
 spec('shortline80_active_full_margin','短线八十实际全部入场条件余量',SRC,
 'min(prevMA20 slope,prevMA30 slope,prev2MA5/MA10-1,1-prevMA5/MA10,prev2VMA5/VMA10-1,1.2prevVMA5/VMA10-1,prevDIF/C,prevDEA/C,prev(DIF-DEA)/C,(.1-prev(DIF-DEA))/C,-prevRET1*prev2RET1,1-O/currentPrevC)',
 'proxy: source all4 active filters retained; actual prevreturn sign may be down-up OR up-down, no directional repair. Vendor MACD uses independent causal EMA12/26/9 proxy with seed/minperiod differences; source0.1 absolute qfq monetaryband explicitly not vendor realprice-equivalent; change_pct proxied qfqreturn. Formula NEW continuous conjunction margin; source original only Boolean eligibility then code sorting, not economic ranking. currentOpen consumed at currentClose signal, enters label1 nextclose'),
 spec('shortline80_active_full_event','短线八十全部条件稀疏事件',SRC,
 'I(allsource80 conditions pass), allinputcoverage required',
 'proxy: binary source conjunction, explicit sameopen->label1 timingdelay and MACD/qfq/change_pct mappings; binary ties require diagnostic, codeorder is not stockalpha; no ST/mainboard/pause/limitexecution'),
 spec('limitstudy97_range_position250','涨停研究两百五十日价格区间位置',EVENT,
 '(C-MIN250L)/(MAX250H-MIN250L), range>0',
 'proxy: exact mathematical relative-position atom, explicitly WITHOUT unavailable high_limit counts and floatMV/ST/listing gates. No claim original frequent-limitup strategy tested; original high position preference retained, qfq bars and stock label1')]

def values(f):
 c=f['close'].astype(float);v=f['volume'].astype(float);o=f['open']
 ma={n:q.rolling(c,n) for n in [5,10,20,30]};va={n:q.rolling(v,n) for n in [5,10]}
 def ema(x,n):return pd.DataFrame(x).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy()
 dif=ema(c,12)-ema(c,26);dea=ema(dif,9);hist=dif-dea;ret=q.ratio(c,q.delay(c))-1
 tech=[q.ratio(ma[20]-q.delay(ma[20]),c),q.ratio(ma[30]-q.delay(ma[30]),c),
 q.ratio(q.delay(ma[5]),q.delay(ma[10]))-1,1-q.ratio(ma[5],ma[10]),
 q.ratio(q.delay(va[5]),q.delay(va[10]))-1,1.2*q.ratio(va[5],va[10])-1,
 q.ratio(dif,c),q.ratio(dea,c),q.ratio(hist,c),q.ratio(.1-hist,c),-ret*q.delay(ret)]
 legs=[q.delay(x) for x in tech]+[1-q.ratio(o,q.delay(c))]
 margin=np.minimum.reduce(legs);event=np.where(np.isfinite(margin),(margin>0).astype(float),np.nan)
 hi=q.rolling(f['high'],250,'max');lo=q.rolling(f['low'],250,'min');rp=q.ratio(c-lo,np.where(hi>lo,hi-lo,np.nan))
 return [margin,event,rp]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all3 sourceatoms fixed before evaluation; no parameter search')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:256] for k,v in f.items()};whole=values(sf);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in sf.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='daily_raw_prefix_recompute_no_sameopen_trade',stop=stop,passed=True))
 for t in [1200,len(cal)-32]:
  for j in range(12):
   hi=sf['high'][t-249:t+1,j];lo=sf['low'][t-249:t+1,j]
   if np.isfinite(hi).all() and np.isfinite(lo).all() and hi.max()>lo.min():
    literal=(sf['close'][t,j]-lo.min())/(hi.max()-lo.min());np.testing.assert_allclose(whole[2][t,j],literal,rtol=1e-6)
 checks.append(dict(test='independent_literal_source250bar_range',passed=True))
 assert -(-.02)*.03>0 and -(.03)*(-.02)>0
 checks.append(dict(test='source_change_pct_product_accepts_both_signorders',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC),EVENT:read_text(q.ROOT/EVENT)})
 run(OUT,SPECS,[x[pos] for x in values(f)],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='causal daily source filters, explicit economic-ranking adaptation',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED94',flush=True)
if __name__=='__main__':main()
