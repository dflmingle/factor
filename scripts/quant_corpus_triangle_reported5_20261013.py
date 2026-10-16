"""Source triangle actually sorts only reported ROE change, not three ranks."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2023年度精选策略/64.韶华研究之七--不可多得的基本面三角.txt'
B='quant/2023年度精选策略/86.【基本面三角3.0】看过之前策略的就略过吧.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source129-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-triangle-reported5-schema-20261013'
FIELDS={'fina_indicator':['roe','tr_yoy','ocf_to_or']}
SPECS=[
 spec('triangle64_reportedroe_ratio5','报告ROE对比前四期均值',A,'priorPIT reportedROE.q0/mean(reportedROE.q1..q4)',
 'proxy NEW ungated continuous source sorting atom, reportedROE not earlier q_roe quarter proxy. Fivecontiguousreportperiods, signalpriorbar, no smoothing across signalgrid. JQindicator.roe reporting basis not byteverified; fullA not CSI800+1000.'),
 spec('triangle64_reportedroe_positive5_gate','三角实际五期正值约束ROE排序',A,'reportedROE0/mean(ROE1..4) WHERE all5 ROE>0,trYoy>0,ocf_to_or>0 and ROEratio>1',
 'proxy literal actual source only ROEratio descending; revenue/ocf changes calculated unused, three-way intersection COMMENTED. Latest reported roe,tr_yoy,ocf_to_or vendor proxies rather prior quarter q_roe/q_sales_yoy/q_ocf_to_or. Original top10/monthly20/industryC27 exclusion/positionMACD exits omitted. Qualified factor_valid benchmark.'),
 spec('triangle64_cashratio_positive5_extension','五期现金营收率变化腿',A,'ocf_to_or0/mean(ocf_to_or1..4) WHERE all5 roe,trYoy,ocf_to_or>0',
 'proxy NEW ranking of source calculated but UNUSED ocf_chg; does not claim source original sorting. Contiguous five reportperiods priorbar, explicit reported-vendorproxy and qualificationbenchmark. Fixed source horizon, no fitted thresholds.')]
for sp in SPECS:sp['source_paths']=[A,B]
SPECS[1]['gated']=SPECS[2]['gated']=True

def values(fin):
 a={c:np.stack([fin[f'fina_indicator.{c}.q{k}'].astype(float) for k in range(5)],axis=-1) for c in FIELDS['fina_indicator']}
 with np.errstate(divide='ignore',invalid='ignore'):
  rr=a['roe'][:,:,0]/np.mean(a['roe'][:,:,1:],axis=-1);cr=a['ocf_to_or'][:,:,0]/np.mean(a['ocf_to_or'][:,:,1:],axis=-1)
 pos=np.stack([(z>0).all(axis=-1) for z in a.values()]).all(axis=0)
 return [rr,np.where(pos&(rr>1),rr,np.nan),np.where(pos,cr,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefivepositiveperiods,reportedROEratio not qROEproxy; frozenbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),lags=5,rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(dates,stocks,lags=5);tables=q.pit_tables();ids=np.arange(128);small={k:v[:,ids] for k,v in fin.items()};full=values(small);checks=[]
  for n in [35,79]:
   sub={ep:t[(t.ann_date<=dates[n-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='trianglePIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cut=values(q.financial_snapshot(dates[:n],stocks[ids],lags=5))
    for sp,a,b in zip(SPECS,full,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-7,atol=1e-8);checks.append(dict(key=sp['key'],test='rawpriorPITfiling_cutoff_replay',passed=True))
  for i in [35,79]:
   for j in ids:
    r=[float(fin[f'fina_indicator.roe.q{k}'][i,j]) for k in range(4,-1,-1)];ref=r[-1]/np.mean(r[:-1])
    np.testing.assert_allclose(full[0][i,j],ref,equal_nan=True,atol=1e-8)
  checks.append(dict(test='independent_chronological_source_last_over_prior4_slices',passed=True))
  q.OUT=oldout;q.pit_tables=loader;vv=values(fin)
  q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
  q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vv)})
  run(OUT,SPECS,vv,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='reportedfinancial vendorproxies, priorPIT, no fullstrategyclaim'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED129',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
