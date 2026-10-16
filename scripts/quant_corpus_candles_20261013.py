"""Run the entire source TA-Lib pattern library, with explicit tie/rarity audits."""
import sys
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
SOURCE='quant/2022年度精选策略/50.K线形态识别与验证-升级.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-candles-library-safe-20261013'

def calculate(name,f):
 arrays=[f[k].astype(float) for k in ['open','high','low','close']];out=np.full(arrays[0].shape,np.nan,np.float32)
 fn=getattr(talib,name);lookback=talib.abstract.Function(name).lookback
 for j in range(out.shape[1]):
  good=np.isfinite(np.stack([x[:,j] for x in arrays])).all(axis=0)&(f['cap'][:,j]>0)
  edge=np.diff(np.r_[False,good,False].astype(int));starts=np.flatnonzero(edge==1);ends=np.flatnonzero(edge==-1)
  for s,e in zip(starts,ends):
   if e-s<=lookback:continue
   val=fn(*[np.ascontiguousarray(a[s:e,j]) for a in arrays])/100.
   out[s+lookback:e,j]=val[lookback:]
 return out

def main():
 from talib import abstract
 talib.abstract=abstract
 OUT.mkdir(exist_ok=True);names=talib.get_function_groups()['Pattern Recognition']
 specs=[spec('candle_'+name.lower(),name,SOURCE,name+'(qfq O,H,L,C)/100; positive library flag high, negative low; zero no event',
   'proxy: source library call exact TA-Lib0.6.8 default settings; source is a visualization/recognition study, not a specified alpha strategy; daily fullA adaptation; split at missing OHLC rather than source skip-paused compression') for name in names]
 plan=dict(specs=specs,rule=q.ALIGNMENT_RULE_VERSION,source_sha256=hashlib.sha256((q.ROOT/SOURCE).read_bytes()).hexdigest(),talib_version=talib.__version__,selection='ALL library functions named by source discern_pattern, fixed before outcomes; no opposite direction search',platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);summaries=[]
 for name,sp in zip(names,specs):
  out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-candle-safe-{name.lower()}-20261013';out.mkdir(exist_ok=True)
  if (out/'audit_complete.json').exists():
   summaries.append(pd.read_csv(out/'results.csv'));continue
  small={k:v[:,:8] for k,v in f.items()};full=calculate(name,small);checks=[]
  for stop in [1200,len(cal)-31]:
   cut=calculate(name,{k:v[:stop] for k,v in small.items()})
   np.testing.assert_array_equal(full[:stop],cut)
   checks.append(dict(key=sp['key'],test='OHLC_prefix_TALib_recompute',stop=stop,passed=True))
  x=calculate(name,f)[pos]
  q.dump(out/'event_coverage.json',dict(function=name,signal_period_nonzero_count=[int(np.sum(np.isfinite(z)&(z!=0))) for z in x],median_nonzero_stocks=float(np.median(np.sum(np.isfinite(x)&(x!=0),axis=1))),warning='Decile portfolio often mostly contains zero no-event ties; hard event cannot fill10% by itself. Tie-sensitive headline is not alpha.'))
  run(out,[sp],[x],cal,stocks,f,checks,dict(fidelity='qfq TA-Lib library atom, not original source strategy profit',statistics='exploratory 61-function family no independent OOS',tie_warning='symbols sort within equal values; explicit three-seed tie sensitivity mandatory',residual_guard='constant/tiny rank residual range <=1e-7 is invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(out,cal,stocks,f);tie_diagnostic(out,cal,stocks,f)
  q.dump(out/'audit_complete.json',dict(completed=True,platform_compute=0));summaries.append(pd.read_csv(out/'results.csv'))
  pd.concat(summaries,ignore_index=True).to_csv(OUT/'results_progress.csv',index=False)
  print('COMPLETE_PATTERN',name,len(summaries),'/',len(names),flush=True)
 q.dump(OUT/'completion.json',dict(completed=True,functions=len(names),platform_compute=0,independent_alpha_clusters=0))
 print('FINISHED_CANDLE_LIBRARY',len(names),flush=True)
if __name__=='__main__':main()
