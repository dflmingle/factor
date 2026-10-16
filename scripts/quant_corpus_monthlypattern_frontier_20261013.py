"""Completed-month CANSLIM base pattern; no current-month endpoint repaint."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2023年度精选策略/98.欧奈尔CANSLIM策略初探三.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source64-20261013'
SPECS=[
 spec('canslim_monthly_base_margin','完成月基底突破余量',SOURCE,'max_n3..10(min(C_last/O_last-1,C_last/MAX(O_A,C_A)-1,1-MAX(interior(O,C))/MAX(O_A,C_A)))',
      'proxy: literal source monthly three-part base conjunction converted continuous margin; only fully completed months, not unknown jqlib get_bars current-month inclusion; sourcefloat-top10ownership/growth/size/index regime gates omitted; qfq monthly firstavailableopen and monthendclose aggregated from same daily snapshot'),
 spec('canslim_monthly_base_positive','完成月基底突破已触发强度',SOURCE,'canslim_monthly_base_margin where>0',
      'proxy: source pattern exists qualification, highmargin ranks events instead of source unspecified equal ranking; factor_valid benchmark on event subset, not whole fullA performance'),
]
SPECS[1]['gated']=True

def values(f,cal,pos):
 periods=cal.to_period('M');months=periods.unique();opens=[];closes=[]
 for m in months:
  ids=np.flatnonzero(periods==m);o=f['open'][ids];finite=np.isfinite(o);ix=np.argmax(finite,axis=0);v=o[ix,np.arange(o.shape[1])];opens.append(np.where(finite.any(axis=0),v,np.nan));closes.append(f['close'][ids[-1]])
 op=np.asarray(opens);cl=np.asarray(closes);out=np.full((len(pos),op.shape[1]),np.nan)
 for i,t in enumerate(pos):
  last=months.get_loc(periods[t])-1
  if last<9:continue
  o=op[last-9:last+1].astype(float);c=cl[last-9:last+1].astype(float);oc=np.maximum(o,c);margins=[]
  for n in range(3,11):
   a=10-n;base=oc[a];mid=np.max(oc[a+1:-1],axis=0)
   margins.append(np.minimum.reduce([q.ratio(c[-1],o[-1])-1,q.ratio(c[-1],base)-1,1-q.ratio(mid,base)]))
  out[i]=np.max(margins,axis=0)
 return [out,np.where(out>0,out,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source monthly pattern and margin fixed before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:512] for k,v in f.items()};full=values(small,cal,pos);checks=[]
 for stop in [1200,len(cal)-31]:
  use=pos<stop;cut=values({k:v[:stop] for k,v in small.items()},cal[:stop],pos[use])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[use],b,equal_nan=True,rtol=1e-7,atol=1e-7);checks.append(dict(key=sp['key'],test='partial_final_month_prefix_reaggregation',stop=stop,passed=True))
 # The current month's price cannot change completed-month historical scores.
 t=pos[-1];same=np.flatnonzero(cal.to_period('M')==cal[t].to_period('M'));alter={k:v.copy() for k,v in small.items()}
 alter['close'][same]*=2;alter['open'][same]*=3
 for a,b in zip(full,values(alter,cal,pos)):np.testing.assert_allclose(a[-1],b[-1],equal_nan=True)
 checks.append(dict(test='current_month_price_perturbation_does_not_change_completed_month_signal',passed=True))
 vals=values(f,cal,pos);run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='completed-month source technical atom; missing ownership not inferred',statistics='exploratory no independent OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED64',flush=True)
if __name__=='__main__':main()
