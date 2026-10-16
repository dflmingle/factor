"""EMA6/2 priority and literal size-band membership against full-A SIZE."""
import json,sys
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_ema_multima_20261013 import seeded_smooth
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/27.中证500指增+CTA，胜率52%盈亏比1.9。不输顶尖私募.txt'
B='quant/聚宽2025年精选/34十年回测 年化103.32% 最大回撤23.89%.txt'
C='quant/聚宽2025年精选/43小市值再优化【年化98 回撤27】无未来函数.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source155-20261013'
SPECS=[
 spec('cta27_ema6_2_priority_daily','CTA六二EMA优先级股票代理',A,'-1 if C<EMA6 else +1 if C>EMA2 else0',
      'proxy completedqfq stockclose replaces source11:15 partialindex close; seededSMA6/2 recursiveEMA. Original long_days=6, not source45EMA5. PreviousEMA values unused. IC futures/margin/roll/ATRallocation and stockaccount path missing; original exit uses sign==0 rather everynegative; only scalar signal adapter, no CTAreturn claim.'),
 spec('small34_size5_50_priority_fullA','五至五十亿资格全A优先',B,'2*I(5<=totalMV_billionyuan<=50)+CSrank(-totalMV)',
      'proxy NEW fullA lexicographic membership adapter preserving source literal totalMV5..50亿 (comment5..30wrong). KnownSIZEcontrol source144 shared support/benchmark. Actual399101/PITIPO375/mainboard/ST/80yuanprice/first100then50then5/Tuesdayhold/limitstops missing; source calendar exclusions04-05..04-30 and01-05..02-05 not encoded as fake alpha. No new independentcluster claim.'),
 spec('small43_size5_300_priority_fullA','五至三百亿资格全A优先',C,'2*I(5<=totalMV_billionyuan<=300)+CSrank(-totalMV)',
      'proxy NEW fullA lexicographic adapter source exact5..300亿, not source34or30亿upper. KnownSIZEcommoncontrol, strictsupport preserved. Actual399101/top27then9/375day/mainboard/ST/limit gates andholdingstop10%, indexmeanabsdayreturn5%, JanAprilcashETF omitted; no whole strategyreturn claim.')]

def values(f,pos):
 c=f['close'].astype(float);e6=seeded_smooth(c,6,2/7);e2=seeded_smooth(c,2,2/3)
 state=np.where(np.isfinite(c)&np.isfinite(e6)&np.isfinite(e2),np.where(c<e6,-1,np.where(c>e2,1,0)),np.nan)[pos]
 cap=f['cap'][pos].astype(float);base=q.rank(np.where(cap>0,-cap,np.nan));mv=cap/10000
 return [state,base+2*((mv>=5)&(mv<=50)),base+2*((mv>=5)&(mv<=300))]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,
  selection='literal sourceEMA6/2 andsizebounds5..50,5..300 beforeoutcomes; no tuning')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'));import talib
 observations=0;boundary_ties=0
 for j in range(64):
  c=sf['close'][:,j].astype(float);ids=np.flatnonzero(np.isfinite(c))
  if not len(ids) or not np.isfinite(c[ids[0]:]).all():continue
  start=ids[0];a=c[start:];e6=talib.EMA(a,6);e2=talib.EMA(a,2)
  own6=seeded_smooth(a[:,None],6,2/7)[:,0];own2=seeded_smooth(a[:,None],2,2/3)[:,0]
  np.testing.assert_allclose(own6,e6,equal_nan=True,atol=1e-10,rtol=1e-10)
  np.testing.assert_allclose(own2,e2,equal_nan=True,atol=1e-10,rtol=1e-10)
  for i in [35,79]:
   t=pos[i]-start
   if t<6:continue
   if abs(a[t]-e6[t])<1e-10 or abs(a[t]-e2[t])<1e-10:
    boundary_ties+=1
    continue
   ref=-1 if a[t]<e6[t] else(1 if a[t]>e2[t] else 0)
   np.testing.assert_allclose(full[0][i,j],ref);observations+=1
 assert observations>0
 checks.append(dict(test='independent_TALib_EMA6_EMA2_values_and_nontied_ordered_branch',observations=observations,
  numerical_boundary_ties=boundary_ties,note='EMA values must agree; branch comparison excludes 1e-10 equality ambiguity only in reference check, frozen factor remains strict',passed=True))
 vals=values(f,pos);baseline=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/signal_panels.pkl')
 base=baseline['panels']['membership144_size_control'].to_numpy()
 for x in vals[1:]:np.testing.assert_array_equal(np.isfinite(x),np.isfinite(base))
 checks.append(dict(test='fullA_same_support_as_saved_SIZE_control',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='daily stocksignal andfullA membership diagnostic only'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 b=pd.read_csv(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/results.csv');r=pd.read_csv(OUT/'results.csv');deltas=[]
 for _,x in r[r.form.eq('raw')&~r.key.eq(SPECS[0]['key'])].iterrows():
  z=b[b.key.eq('membership144_size_control')&b.window.eq(x.window)&b.form.eq('raw')].iloc[0]
  deltas.append(dict(key=x.key,window=x.window,form='raw',delta_net_excess_pct=x.net_excess_pct-z.net_excess_pct,
   delta_held_daily_max_drawdown_pct=x.held_daily_max_drawdown_pct-z.held_daily_max_drawdown_pct,delta_turnover_pct=x.turnover_pct-z.turnover_pct))
 pd.DataFrame(deltas).to_csv(OUT/'matched_size_control_deltas.csv',index=False)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED155',flush=True)
if __name__=='__main__':main()
