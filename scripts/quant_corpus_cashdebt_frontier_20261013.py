"""Previously untested library atoms; source active/dormant distinctions retained."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2022年度精选策略/95.医疗行业多因子模型及单行业多因子测试代码模板.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source67-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-cashdebt-schema-20261013'
FIELDS={'fina_indicator':['profit_dedt','netdebt','longdebt_to_workingcapital','ocf_to_netdebt','ocf_to_debt'],
 'balancesheet':['total_assets','total_liab','total_ncl'], 'income':['n_income','revenue'], 'cashflow':['n_cashflow_act']}
DEFS=[
 ('noncurrent_debt_equity_low','低非流动负债权益比','-total_ncl/(assets-liab); equity>0'),
 ('longdebt_workingcapital_low','低长期债务营运资本比','-PIT longdebt_to_workingcapital'),
 ('ocf_netdebt_reported_high','经营现金净债务覆盖','PIT ocf_to_netdebt'),
 ('ocf_debt_reported_high','经营现金总债务覆盖','PIT ocf_to_debt'),
 ('ocf_profit_ttm_high','现金净利润TTM比','TTM OCF/TTM netincome; nonzero NI'),
 ('deducted_profitmargin_ytd_high','扣非利润率YTD','profit_dedt/YTD revenue; revenue>0'),
 ('ocf_revenue_mixed_source','现金收入源码混合口径','TTM OCF/YTD revenue; revenue>0'),
]
SPECS=[spec(k,n,SOURCE,f,'proxy: dormant get_factor_data library atom, NOT active g.factor alpha; fullA replaces medical industry. Economic direction frozen, PIT vendor ratios/fields not byte-equivalent; no IC.csv model or fullsample imputation') for k,n,f in DEFS]

def values(fin):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 a=g('balancesheet','total_assets');li=g('balancesheet','total_liab');equity=a-li
 ni=g('income','n_income_ttm');rev=g('income','revenue');ocf=g('cashflow','n_cashflow_act_ttm')
 return [-q.ratio(g('balancesheet','total_ncl'),np.where(equity>0,equity,np.nan)),
  -g('fina_indicator','longdebt_to_workingcapital'),g('fina_indicator','ocf_to_netdebt'),g('fina_indicator','ocf_to_debt'),
  q.ratio(ocf,np.where(ni!=0,ni,np.nan)),q.ratio(g('fina_indicator','profit_dedt'),np.where(rev>0,rev,np.nan)),q.ratio(ocf,np.where(rev>0,rev,np.nan))]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True)
 plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all 7 previously untested available dormant atoms, economic directions fixed before evaluation')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();checks=[]
  ids=np.arange(512);whole=values({k:v[:,ids] for k,v in fin.items()})
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='cashdebt-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=1)
    for sp,a,b in zip(SPECS,whole,values(cf)):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6)
     checks.append(dict(key=sp['key'],test='raw_filing_cutoff_revision_and_TTM_replay',cutoff=str(cutoff),nonempty=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin)
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='dormant library atoms with frozen economic direction; original medical model not reproduced',statistics='exploratory no untouched OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED67',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
