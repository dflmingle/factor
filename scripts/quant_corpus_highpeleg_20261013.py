"""Source77 runnable PE branch; dividend/growth branches remain untested."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/77研报三因子II-新规高分红小市值-年化60回撤19.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source99-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-eps-ols-schema-20261013'
SPECS=[
 spec('threeleg77_highpe_epspositive','三腿七十七高PE正EPS排序',SRC,'PE=totalMV/parentNI_TTM high with reportedEPS>0',
 'proxy: actual PE.desc direction retained, NOT lowPE; isolated stockwide firststage ranking only, dividends and vendor5year salesgrowth unavailable. Tushare reportedEPS and totalMV/parentTTM PE proxy; no original final6+6+6union/top10/trading claims'),
 spec('threeleg77_highpe10pct_small','三腿七十七最高PE十分位后小市值',SRC,'-totalMV after topfloor(Nactive*.1) descending PE of EPSpositive subset',
 'proxy: exact source initial-universe count used to size topPE slice, then smalltotalMV; original top6 truncation would fail >=100contract so fullqualifiedset adaptation retained separately. Dividend/growth union missing, allqualified factor_valid subset benchmark')]
for sp in SPECS:sp['gated']=True

def values(fin,eps,cap):
 pe=q.ratio(cap*10000,fin['income.n_income_attr_p_ttm.q0']);gate=(eps>0)&np.isfinite(pe)&(cap>0)
 a=np.where(gate,pe,np.nan);b=np.full(cap.shape,np.nan)
 for i in range(len(cap)):
  n=int((cap[i]>0).sum()*.1);ids=np.flatnonzero(gate[i]);ids=ids[np.argsort(-pe[i,ids],kind='stable')][:n];b[i,ids]=-cap[i,ids]
 return [a,b]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcePE leg only, highdirection and10pct exactcount fixed')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks)
 meta=json.loads((SCHEMA/'schema.json').read_text());dates=pd.DatetimeIndex(meta['dates']);extra=pd.read_pickle(SCHEMA/'financial_signal_snapshots_lags1.pkl');eps=extra['fina_indicator.eps.q0'][dates.get_indexer(grid)]
 vals=values(fin,eps,f['cap'][pos]);checks=[];ids=np.arange(64);tables=q.pit_tables();oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.FIN_FIELDS={'income':['n_income_attr_p'],'fina_indicator':['eps']};q.pit_tables=loader;tables=q.pit_tables()
  cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},eps[:,ids],cap)
  for n in [35,79]:
   cutoff=grid[n-1];q.pit_tables=lambda:{ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
   with tempfile.TemporaryDirectory(prefix='highPE-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);fresh=q.financial_snapshot(grid[:n],stocks[ids],lags=1);cut=values(fresh,fresh['fina_indicator.eps.q0'],cap[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-6);checks.append(dict(key=sp['key'],test='raw_announcement_revision_EPS_TTM_replay',cutoff=str(cutoff),passed=True))
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
 for i in [35,79]:
  pe=vals[0][i];df=pd.DataFrame({'pe':pe,'cap':f['cap'][pos[i]]});ids0=df.dropna().sort_values('pe',ascending=False,kind='stable').index[:int((df.cap>0).sum()*.1)]
  assert set(ids0)==set(np.flatnonzero(np.isfinite(vals[1][i])))
 checks.append(dict(test='independent_dataframe_PEdesc_then_lowMV_and_initial_count',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)});q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='PE branch only, missingdividend_growth union'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED99',flush=True)
if __name__=='__main__':main()
