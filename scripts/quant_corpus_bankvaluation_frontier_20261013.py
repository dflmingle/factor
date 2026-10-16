"""Actual source64 narrow PE band; untested fixed-asset library diagnostic."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
BANK='quant/2020年度精选策略/64 12年年化34%，Sharpe1.2，银行股轮动.txt'
LIB='quant/2022年度精选策略/74.基本面单因子测试——以BP因子为例.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source74-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-bankvaluation-schema-20261013'
FIELDS={'balancesheet':['total_assets','fix_assets'],'income':['n_income_attr_p'],'fina_indicator':['roe']}
SPECS=[spec('narrowpe4_55_roe_size_source','四至五点五PE质量规模源码交集',BANK,'rank(-PE)+rank(ROE)+rank(-totalMV) only4<PE<5.5',
 'proxy: actual PE band and equal .1 weights, highROE/lowPE/lowMV direction; title bank but NO bank industry gate in code; fullA replacesHS300, current10day signal replaces300day selection refresh, vendor wizardrank unavailable'),
 spec('fixedassets_fraction_library_low','固定资产比例模板低值',LIB,'-latest PIT fix_assets/total_assets;assets>0',
 'proxy: dormant FACR helper, active source g.factor=BP not FACR; economic lowassetintensity direction fixed before outcomes, fullA replacesCSI800; field mapping explicit not vendor-byte-equivalent')]
SPECS[0]['gated']=True

def values(fin,cap):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 pe=q.ratio(cap*10000,g('income','n_income_attr_p_ttm'));roe=g('fina_indicator','roe');good=(pe>4)&(pe<5.5)&np.isfinite(roe)
 score=q.rank(np.where(good,-pe,np.nan))+q.rank(np.where(good,roe,np.nan))+q.rank(np.where(good,-cap,np.nan))
 assets=g('balancesheet','total_assets');facr=-q.ratio(g('balancesheet','fix_assets'),np.where(assets>0,assets,np.nan))
 return [score,facr]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();checks=[]
  ids=np.arange(512);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap)
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='bankvalue-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=1);cut=values(cf,cap[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='PIT_filing_cutoff_and_TTM_replay',cutoff=str(cutoff),nonempty=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,f['cap'][pos]);q.dump(OUT/'qualification_coverage.json',{s['key']:np.isfinite(v).sum(axis=1).tolist() for s,v in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='actual narrow sourceband plus dormantlibrary atom',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED74',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
