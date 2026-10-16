"""Triangular trend-run age, causal fixed-history stock adaptations of ETF source."""
import json,ast
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/74趋势筛选后相关性最小etf轮动.txt'
SRC2='quant/聚宽2025年精选/97趋势筛选后相关性最小etf轮动-加速10倍版.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source88-20261013'
SPECS=[]
for n in [250,500]:
 SPECS.append(spec(f'ma10_30_triangular_runage{n}',f'十日三十日均线的{n}日上涨日龄累积',SRC,f'sum(runage_i of MA10>MA30 for i=30..N-1)/(N-30); resetwindow N={n}',
 f'proxy: literal source triangular runage not aboveMAfraction. NEW fixed{n}bar stock extension replaces source3500ETF history, independently replayed source purefunction; source minpeer correlation and25trend execution omitted. No full3500 reproduction claim; positive duration direction fixed'))
SPECS.append(spec('ma10_30_runage500_monthly_cache','五百日上涨日龄月度缓存',SRC2,'same500bar triangular runage computed on monthly first-trading-day prior close and held until nextmonth',
 'proxy: actual acceleratedsource monthly cache idea retained, NEW500stock history; no use current firstdayclose in premarket cache; fullsource3500 andETF correlation selection not reproduced'))
for sp in SPECS[:2]:sp['source_paths'].append(SRC2)

@njit(cache=True)
def calc(c,pos,n):
 out=np.full((len(pos),c.shape[1]),np.nan)
 for ii in range(len(pos)):
  t=pos[ii]
  if t<n-1:continue
  for j in range(c.shape[1]):
   y=c[t-n+1:t+1,j]
   if not np.isfinite(y).all():continue
   count=0.;total=0.
   for i in range(30,n):
    # Source starts index30; MA30 index29 is deliberately not counted.
    s=0.;l=0.
    for z in range(i-29,i+1):
     l+=y[z]
     if z>=i-9:s+=y[z]
    if s/10>l/30:count+=1.;total+=count
    else:count=0.
   out[ii,j]=total/(n-30)
 return out

def values(c,cal,pos):
 v=[calc(c,pos,n) for n in [250,500]]
 first={}
 for i,d in enumerate(cal):first.setdefault((d.year,d.month),i)
 mp=np.array([first[(cal[t].year,cal[t].month)]-1 for t in pos])
 v.append(calc(c,mp,500));return v

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='250/500 causal adaptations fixed before outcomes; original3500 blocked by2018warmup')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64].astype(float);whole=values(small,cal,pos);checks=[]
 for stop in [1200,len(cal)-31]:
  mask=pos<stop;cut=values(small[:stop],cal[:stop],pos[mask])
  for a,b in zip(whole,cut):np.testing.assert_allclose(a[mask],b,equal_nan=True,atol=1e-8)
  checks.append(dict(test='raw_daily_prefix_rebuild_monthly_previousclose_cache',stop=stop,passed=True))
 tree=ast.parse(read_text(q.ROOT/SRC));defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['calculate_ma','count_days_above']];assert len(defs)==2
 ns={};exec(compile(ast.Module(body=defs,type_ignores=[]),SRC,'exec'),ns);obs=0
 for t in pos[::29]:
  for j in range(64):
   for n in [250,500]:
    y=small[t-n+1:t+1,j]
    if not np.isfinite(y).all():continue
    ref=ns['count_days_above'](pd.Series(y),10,30);a=calc(small,np.array([t]),n)[0,j]
    np.testing.assert_allclose(a,ref,atol=1e-8);obs+=1
 checks.append(dict(test='original_two_reviewed_purefunctions_independent_triangular_count',observations=obs,passed=True,corpus_module_executed=False))
 toy=np.arange(1,101,dtype=float)[:,None];a=calc(toy,np.array([99]),100)[0,0];assert a==35.5
 checks.append(dict(test='allup70eligiblebars_triangular_sum70x71over2_over70',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC),SRC2:read_text(q.ROOT/SRC2),'blocked_original_3500_history':dict(availabledays=len(cal),required=3500,original3500_tested=False),'monthly_cache_reconstruction':'first tradingday previous close, no intraday data'})
 vals=values(f['close'].astype(float),cal,pos)
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source exact math independent replay, clearly named fixedwindow adaptations',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED88',flush=True)
if __name__=='__main__':main()
