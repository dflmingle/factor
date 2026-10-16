"""Reviewed limit-strategy daily helpers; no synthetic limit prices or fills."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/72量化进阶学习笔记——打板策略.txt'
B='quant/聚宽2025年精选/88WY大神的“龙头打板”策略小改.txt'
C='quant/聚宽2025年精选/25冷饭热吃之三，14年至今年华99.99.txt'
D='quant/2024年度精选策略2/10.龙头首阴战法改版二.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source119-20261013'
SPECS=[
 spec('firstboard72_lowrange60_lastvalid','首板六十日末有效区间位置',A,'-(last_valid_C-MIN60(L))/(MAX60(H)-MIN60(L)), completed bars t-60..t-1',
 'proxy NEW continuous ordering of <=.5 eligibility; source drops incomplete HLC rows and uses last valid close. No actual firstboard, chain10, ST, IPO50, pause or intraday exit reproduced.'),
 spec('firstboard72_openband_range60_partial','首板六十日区间低开带部分腿',A,'-range60 where range60<=.5 AND .96<=open(t)/close(t-1)<=.97',
 'proxy partial eligibility scored at t close under next-close label; no firstlimit/nochain/emptyportfolio rule or original open fills. No lower range bound added.'),
 spec('leader88_lowturn5_priorclose','龙头源码五日低换手排序',B,'-MEAN5(turnover)t-1',
 'proxy VOL5 vendor 5day average turnover->daily_basic.turnover. Source ranks only highest limit chain20 names, here fullA daily ranking; not complete leader strategy or original liquidity qualification.'),
 spec('size25_lowrelativevolume120_dormant','小盘源码休眠放量控制连续腿',C,'-V(t)/MAX120(V)t, including current completed day',
 'proxy NEW ranking extension of dormant sell predicate V>.9*MAX120V. HV_control=False in original, not active alpha. Original14:30partial volume adapted to full completed-day volume; no holding/high_limit/paused filters.'),
 spec('leader10_firstyin_retrace_partial','首阴源码回落且不低昨收日线腿',D,'-(H-C)/H t-1 where C<.976H AND C>=lag1C AND O==H',
 'proxy NEW continuous ranking within daily shape. Missing preceding actual limit, count_limit_num>=2 and last8limitcount<=6, IPO1080, intraday buy/sell and portfolio state; not complete source strategy.'),
 spec('leader10_deeplow_reclaim_partial','首阴源码深低回收日线部分腿',D,'(C-L)/lag1C t-1 where O<.95H AND O>.986lag1C AND L<.92lag1C',
 'proxy NEW continuous ranking within second daily shape; omitted actual C==high_limit and 8/30limitcount qualification. No price return threshold invented to represent limits; not source hammer trading strategy.')]
for i in [1,4,5]:SPECS[i]['gated']=True

def values(f,pos):
 c,h,l,o=[pd.DataFrame(f[k].astype(float)) for k in ['close','high','low','open']]
 complete=np.isfinite(c)&np.isfinite(h)&np.isfinite(l)
 hi=h.where(complete).rolling(60,min_periods=1).max().shift(1)
 lo=l.where(complete).rolling(60,min_periods=1).min().shift(1)
 last=c.where(complete).ffill(limit=59).shift(1)
 r=(last-lo)/(hi-lo).where(hi>lo);gap=o/c.shift(1)
 g=(r<=.5)&(gap>=.96)&(gap<=.97)
 turn=pd.DataFrame(f['turnover'].astype(float)).rolling(5).mean().shift(1)
 v=pd.DataFrame(f['volume'].astype(float));peak=v.rolling(120).max()
 rel=v/peak.where(peak>0)
 prev=c.shift(1)
 yin=(c<.976*h)&(c>=prev)&(o==h)
 deep=(o<.95*h)&(o>.986*prev)&(l<.92*prev)
 return [(-r).to_numpy()[pos],(-r.where(g)).to_numpy()[pos],(-turn).to_numpy()[pos],(-rel).to_numpy()[pos],
         (-(h-c)/h).where(yin).shift(1).to_numpy()[pos],((c-l)/prev).where(deep).shift(1).to_numpy()[pos]]

def main():
 OUT.mkdir(exist_ok=True)
 plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixed60/5/120/.976/.986/.92; new rankings disclosed before evaluating')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawOHLCV_prefix_replay',passed=True))
 # Independent literal slices, including source HLC dropna and last valid C.
 count=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   a=np.column_stack([sf[k][t-60:t,j].astype(float) for k in ['close','high','low']]);a=a[np.isfinite(a).all(axis=1)]
   ref=-(a[-1,0]-a[:,2].min())/(a[:,1].max()-a[:,2].min()) if len(a) and a[:,1].max()>a[:,2].min() else np.nan
   np.testing.assert_allclose(full[0][i,j],ref,equal_nan=True,atol=1e-8)
   a=sf['turnover'][t-5:t,j].astype(float);ref=-a.mean() if np.isfinite(a).all() else np.nan
   np.testing.assert_allclose(full[2][i,j],ref,equal_nan=True,atol=1e-8)
   a=sf['volume'][t-119:t+1,j].astype(float);ref=-a[-1]/a.max() if np.isfinite(a).all() and a.max()>0 else np.nan
   np.testing.assert_allclose(full[3][i,j],ref,equal_nan=True,atol=1e-8);count+=1
 # Missing last row: source selects earlier complete HLC within the window.
 toy={k:v.copy() for k,v in sf.items()};t=pos[35];toy['close'][t-1,0]=np.nan
 a=np.column_stack([toy[k][t-60:t,0].astype(float) for k in ['close','high','low']]);a=a[np.isfinite(a).all(axis=1)]
 if len(a) and a[:,1].max()>a[:,2].min():
  np.testing.assert_allclose(values(toy,pos)[0][35,0],-(a[-1,0]-a[:,2].min())/(a[:,1].max()-a[:,2].min()),atol=1e-8)
 checks.append(dict(test='independent_literal_window_and_dropna_last_close',observations=count,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C,D]})
 vals=values(f,pos);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory, no untouched OOS',fidelity='daily helpers and disclosed new ranking extensions, not original strategy backtests'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED119',flush=True)
if __name__=='__main__':main()
