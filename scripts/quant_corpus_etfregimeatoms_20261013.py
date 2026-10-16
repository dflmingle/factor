"""Reviewed volume and stock/bond timing helpers as disclosed stock extensions."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
VOL='quant/2021年度精选策略/18.6年17倍的etf+分级b的轮动趋势策略跟随感悟.txt'
BOND='quant/2024年度精选策略2/76.ETF-控制回撤性能拉满（国债ETF增强).txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source102-20261013'
SPECS=[
 spec('etf18_volume7_sixdown_threeup','量七日均线连续三上六下状态',VOL,
 'lag1(+1 if last3(V-MA7V)>=0 else -1 if last6<0 else0)',
 'proxy: exact reviewed EmotionMonitor state and inclusive >=0 vs <0 boundaries, complete13daily V needed. Source marketvolume is a single INDEX chosen by WORST ETF performance; perstock extension replaces that scalar, so NOT source strategy or exact fullsetup. Ties audited'),
 spec('etf18_return13_volume_partial','十三日动量与量价局部交集',VOL,
 'ret13 where ret13>.001 AND C>lag1MA13C AND volumeState>=0',
 'proxy: source actual13priorcloses versus currentminute replaced currentclose; source .1 PERCENT not prose1percent; stockvolume substituted for missing dynamic indexvolume is an explicit NEW partial adaptation. Original ranking only selects1ETF despite prose3; index/ETF/intradayposition execution omitted'),
 spec('bond76_no_bear_margin','十九条均线序列和九十九条回撤余量',BOND,
 '-max(min(1-MA19_endt2/MA19_endt22,1-MA19_endt22/MA19_endt42),.92MAX9_endt2/C_t1-1,.85MAX19_endt2/C_t1-1)',
 'proxy: exact source19/19/19 disjoint slices and9/19priorprice peak thresholds retained. NEW continuous stock safe-margin extension of source indexbad_sign Boolean. Portfolio2.5/5%DD hysteresis and30/40/50%risky allocation cannot become stockfeature; note source raises risky weight asDDdeepens, no automatic de-risk claim')]
SPECS[1]['gated']=True

def values(f):
 c=f['close'].astype(float);v=f['volume'].astype(float);vd=v-q.rolling(v,7)
 up=q.rolling(np.where(np.isfinite(vd),(vd>=0).astype(float),np.nan),3,'min');down=q.rolling(np.where(np.isfinite(vd),(vd<0).astype(float),np.nan),6,'min')
 good=np.isfinite(q.rolling(v,13));state=np.where(good,np.where(up==1,1,np.where(down==1,-1,0)),np.nan);state=q.delay(state)
 ret=c/q.delay(c,13)-1;ma13=q.delay(q.rolling(c,13));partial=np.where((ret>.001)&(c>ma13)&(state>=0),ret,np.nan)
 ma=q.rolling(c,19);near=q.delay(ma,2);mid=q.delay(ma,22);far=q.delay(ma,42);p=q.delay(c)
 falling=np.minimum(1-near/mid,1-mid/far)
 a=.92*q.delay(q.rolling(c,9,'max'),2)/p-1;b=.85*q.delay(q.rolling(c,19,'max'),2)/p-1
 return [state,partial,-np.maximum.reduce([falling,a,b])]

def literal_volume(v):
 diff=pd.Series(v)-pd.Series(v).rolling(7).mean();last=diff.iloc[-1]
 if last>=0:return 1 if (diff.iloc[-3:]>=0).all() else 0
 return -1 if (diff.iloc[-6:]<0).all() else 0

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all3 reviewed helpers/slices fixed before returns; proxy gaps explicit')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6);checks.append(dict(key=sp['key'],test='rawpricevolume_prefix_with_completedbar_slices',stop=stop,passed=True))
 obs=0
 for t in [1200,len(cal)-32]:
  for j in range(64):
   x=small['volume'][t-13:t,j].astype(float)
   if np.isfinite(x).all():assert whole[0][t,j]==literal_volume(x)
   x=small['close'][t-60:t,j].astype(float)
   if np.isfinite(x).all():
    n,m,o=x[-20:-1].mean(),x[-40:-21].mean(),x[-60:-41].mean()
    ref=-max(min(1-n/m,1-m/o),.92*max(x[-10:-1])/x[-1]-1,.85*max(x[-20:-1])/x[-1]-1)
    np.testing.assert_allclose(whole[2][t,j],ref,atol=1e-6);obs+=1
 checks.append(dict(test='independent_literal_EmotionMonitor_and_60bar_offbyone_slices',observations=obs,passed=True))
 assert literal_volume(np.ones(13))==1
 checks.append(dict(test='volume_allties_above_inclusive_boundary',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [VOL,BOND]})
 run(OUT,SPECS,[x[pos] for x in values(f)],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='indexETF helperstockextension, portfolio_state_NOTreproduced'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED102',flush=True)
if __name__=='__main__':main()
