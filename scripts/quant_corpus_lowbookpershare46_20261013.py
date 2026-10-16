"""Low per-share book atom from reviewed three-union source, vendor proxy."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/46.【深度解析 四】聚宽三因子基本面 模型.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source139-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-lowbook46-schema-20261013'
FIELDS={'fina_indicator':['bps','eps']}
COMMON='proxy sourcevendor net_asset_per_share mappedreported Tusharebps,EPS mappedreported eps,prior-dayPIT. These fields not byte-equivalent and are explicit unverifiedsource diagnostics, not platformaligned fieldcertification. Original250/125calendar-day,ST/boardfilter,circMVtop5perleg union andweekly10holdings/minute/limits omitted. DEGM_8y/Barra non_linear_size otherlegs NOT reconstructed; no fabricated8yearshort proxy or genericcubiccap.'
SPECS=[
 spec('union46_low_reported_BPS','三腿模型低每股净资产原子',A,'-reportedBPS',COMMON+' Literal low, allows negativebps; source independentleg prefilter.'),
 spec('union46_low_BPS_positiveEPS','正EPS约束低每股净资产',A,'-reportedBPS WHERE EPS>0',COMMON+' NEW broad conditionalrank of originaltwoatoms, no bottom10%truncation/sourceunion claim.'),
 spec('union46_bottom10_BPS_small_partial','低每股净资产十分位小盘腿',A,'-totalMV WHERE BPS in lowestfloor(.1*NvalidBPS) AND EPS>0',COMMON+' Source dropnan BEFORE slice counts; explicit totalMV adaptation replacescirculatingMV. At mostoldsizeconditionalmembership, not independentalpha.')]
SPECS[1]['gated']=True;SPECS[2]['gated']=True

def values(fin,cap):
 b=fin['fina_indicator.bps.q0'].astype(float);e=fin['fina_indicator.eps.q0'].astype(float);third=np.full(b.shape,np.nan)
 for i in range(len(b)):
  ids=np.flatnonzero(np.isfinite(b[i])&(cap[i]>0));ids=ids[np.argsort(b[i,ids],kind='stable')][:int(.1*len(ids))];ids=ids[e[i,ids]>0];third[i,ids]=-cap[i,ids]
 return [-b,np.where(e>0,-b,np.nan),third]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source lowBPS/positiveEPS/dropnanbefore10% fixedbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),stocks=list(stocks),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();ids=np.arange(512);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap);checks=[]
  for n in [35,79]:
   sub={ep:t[(t.ann_date<=dates[n-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='lowBPS-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(dates[:n],stocks[ids],lags=1);cut=values(cf,cap[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawreportedBPS_EPS_cutoff_replay',finite=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader
  toy={'fina_indicator.bps.q0':np.array([[-3,0,1,2,3,4,5,6,7,8,np.nan]],float),'fina_indicator.eps.q0':np.ones((1,11))};v=values(toy,np.ones((1,11)));assert np.isfinite(v[2]).sum()==1 and v[2][0,0]==-1
  checks.append(dict(test='independent_negativeBPS_lowranking_dropna_before_floor10',passed=True))
  q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
  run(OUT,SPECS,values(fin,f['cap'][pos]),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON,diagnostic_unverified_fields=['bps','eps']),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED139',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
