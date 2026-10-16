"""Literal source75 PB<1 (without PB>0) and reported cash-inflow gates."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/75大市值价值投资优化一波.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source93-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-qualitygrowth-regimes-schema-20261013'
SPECS=[spec('value75_roa_actual_intersection','价值七十五实际ROA交集',SRC,
 'high reportedROA on PB<1,operatingcashINFLOW>1e6,YTDdeductedNI>1e6,ROA>.15,reportedNI_yoy>0; negativePB retained',
 'proxy: literal source cashINFLOW, not netOCF; ROA>.15 reported percentunits, not15percent. NegativePB permitted by source, not silently excluded. Tushare reportedROA/profit_dedt/netprofit_yoy and PITequity; canonical fullA,qfq,total_mv. Original200calendar-day listing, ST/pause, singleholding monthly/indexETF/limit-up state omitted; restricted factor_valid benchmark')]
SPECS[0]['gated']=True

def values(fin,cap):
 def g(ep,c):return fin[f'{ep}.{c}.q0'].astype(float)
 roa=g('fina_indicator','roa');eq=g('balancesheet','total_hldr_eqy_exc_min_int');pb=q.ratio(cap*10000,eq)
 good=(pb<1)&(g('cashflow','c_inf_fr_operate_a')>1e6)&(g('fina_indicator','profit_dedt')>1e6)&(roa>.15)&(g('fina_indicator','netprofit_yoy')>0)
 return [np.where(good,roa,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source exactreported gate, no tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 fin=pd.read_pickle(SCHEMA/'financial_signal_snapshots_lags5.pkl');meta=json.loads((SCHEMA/'schema.json').read_text());assert pd.DatetimeIndex(meta['dates']).equals(grid) and meta['rule']==q.ALIGNMENT_RULE_VERSION
 oldfields,oldout,oldloader=q.FIN_FIELDS,q.OUT,q.pit_tables;checks=[]
 try:
  q.FIN_FIELDS=meta['fields'];tables=q.pit_tables();ids=np.arange(256);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap)
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='source75-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);replay=q.financial_snapshot(grid[:n],stocks[ids],lags=5);cut=values(replay,cap[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True);checks.append(dict(key=sp['key'],test='raw_report_actual_announcement_cutoff_PIT_revision_replay',cutoff=str(cutoff),finite=int(np.isfinite(b).sum()),passed=True))
 finally:q.FIN_FIELDS,q.OUT,q.pit_tables=oldfields,oldout,oldloader
 checks.append(dict(test='literal_negative_PB_allowed_ROA_percentunits',passed=(-2<1 and .2>.15)))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 vals=values(fin,f['cap'][pos]);q.dump(OUT/'qualification_coverage.json',{SPECS[0]['key']:np.isfinite(vals[0]).sum(axis=1).tolist()})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='literal source qualification with reported-vendor proxies',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED93',flush=True)
if __name__=='__main__':main()
