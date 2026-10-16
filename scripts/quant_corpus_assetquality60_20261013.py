"""Literal low leverage / intermediate impaired assets / turnover / ROA cascade."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/60.【深度解析 二】资产负债与ROA模型.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source137-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-assetquality60-schema-20261013'
BAD=['notes_receiv','accounts_receiv','oth_receiv','goodwill','intan_assets','inventories','cip']
FIELDS={'balancesheet':['total_assets','total_liab','total_hldr_eqy_exc_min_int']+BAD,'income':['total_revenue'],'fina_indicator':['roa']}
COMMON='proxy prior-dayconsolidatedPIT, bill_receivable->notes_receiv mapping notbyteequivalent; source total_operating_revenue mappedreported total_revenueYTD (vendor quarterly basis unverified). Chronological fourreportedROA ascendinghistorical source x.iloc[3] mapslatest q0; missingROA reports dropna, fewerthan4->0 if at least1 exists. Source1200calendar-day oldpool/ST/threehalts/monthlytop5 andexecution absent; fullA qualified benchmark.'
SPECS=[
 spec('asset60_reported_roa_delta4','四期ROA最新对均值增量',A,'reportedROAq0 - mean(q0..q3); requireall4',COMMON+' Literal distinctfrom prior erroneous ROA difference duplicate, no invented growth normalization.'),
 spec('asset60_cascade_roa_partial','资产质量三层约束ROA增量',A,'ROAdelta4 within lower70% liability/assets -> middle10..90% bad/assets -> top75% revenue/good_assets',COMMON+' Partial source kernel before final20%ROA/PB/PS selection; exact slice direction/counts, not sameunfiltered ROA.'),
 spec('asset60_cascade_lowPB_source','资产质量四层筛选低PB',A,'-PB on three asset filters then top20% ROAdelta4, PB>.7 and PS<3',COMMON+' Original final PBascendingnotROA ranking. No PBupper/PSpositive/sourceunmentioned positivity added.')]
SPECS[1]['gated']=True;SPECS[2]['gated']=True

def values(fin,cap):
 def g(ep,c,k=0):return fin[f'{ep}.{c}.q{k}'].astype(float)
 assets=g('balancesheet','total_assets');liab=g('balancesheet','total_liab');bad=np.stack([g('balancesheet',b) for b in BAD]).sum(axis=0)
 revenue=g('income','total_revenue');eq=g('balancesheet','total_hldr_eqy_exc_min_int');mv=cap*10000
 with np.errstate(divide='ignore',invalid='ignore'):
  lev=liab/assets;impaired=bad/assets;turn=revenue/(assets-bad);pb=mv/eq
  # Explicit YTD-sales valuation proxy, same mapping disclosed in frozen plan.
  ps=mv/g('income','total_revenue_ttm')
 roas=np.stack([g('fina_indicator','roa',k) for k in range(4)]);all4=np.isfinite(roas).all(axis=0)
 delta=roas[0]-roas.mean(axis=0);fallback=np.where(all4,delta,np.where(np.isfinite(roas).any(axis=0),0.,np.nan))
 partial=np.full(cap.shape,np.nan);source=np.full(cap.shape,np.nan)
 for i in range(len(cap)):
  ids=np.flatnonzero((cap[i]>0)&np.isfinite(assets[i])&np.isfinite(liab[i])&np.isfinite(lev[i]));ids=ids[np.argsort(-lev[i,ids],kind='stable')];ids=ids[int(.3*len(ids)):]
  ids=ids[np.isfinite(impaired[i,ids])];ids=ids[np.argsort(-impaired[i,ids],kind='stable')];ids=ids[int(.1*len(ids)):int(.9*len(ids))]
  ids=ids[np.isfinite(turn[i,ids])];ids=ids[np.argsort(-turn[i,ids],kind='stable')][:int(.75*len(ids))]
  ids=ids[np.isfinite(fallback[i,ids])];partial[i,ids]=fallback[i,ids]
  ids=ids[np.argsort(-fallback[i,ids],kind='stable')][:int(.2*len(ids))]
  ids=ids[(pb[i,ids]>.7)&(ps[i,ids]<3)&np.isfinite(pb[i,ids])&np.isfinite(ps[i,ids])];source[i,ids]=-pb[i,ids]
 return [np.where(all4,delta,np.nan),partial,source]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source cascade low70/middle80/top75/top20,PB>.7PS<3 beforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),stocks=list(stocks),lags=4,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(dates,stocks,lags=4);tables=q.pit_tables();ids=np.arange(512);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap);checks=[]
  for n in [35,79]:
   sub={ep:t[(t.ann_date<=dates[n-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='assetquality-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(dates[:n],stocks[ids],lags=4);cut=values(cf,cap[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawPITprefix_and_four_report_cascade_replay',finite=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader
  vals=values(fin,f['cap'][pos]);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
  q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON,benchmark_warning='qualification subset and explicit quarterly revenue proxy'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED137',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
