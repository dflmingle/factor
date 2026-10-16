"""Source 2022/8 previously untested financial library ratios; offline only.

The notebook is a feature-selection example, not a disclosed fitted alpha.
These economic directions are frozen before evaluation, not source-model claims.
"""
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec, audit, simultaneous_residual

SOURCE='quant/2022年度精选策略/8.多因子策略研究代码框架.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source75-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-libraryratios-schema-20261013'
FIELDS={
 'balancesheet':['total_hldr_eqy_inc_min_int','st_borr','non_cur_liab_due_1y','lt_borr','bond_payable','lt_payable','total_ncl','fix_assets','total_cur_assets'],
 'income':['n_income','fin_exp','income_tax','total_revenue','oper_cost','revenue','sell_exp','admin_exp','operate_profit','total_profit','fv_value_chg_gain','invest_income','forex_gain'],
 'cashflow':['n_cashflow_act','n_cashflow_inv_act']}
DEFS=[
 ('fcff_subtract_investing_ytd_ncl','源码现金流减投资现金非流动债务比','(YTD OCF-YTD ICF)/nonzero NCL'),
 ('calculated_roic_ytd_library','源码计算投入资本回报','(YTD NI+finexp+income_tax)/(total_equity+STloan+due1y+LTloan+bonds+LTpayable)'),
 ('sales_fixedassets_ytd_library','营业总收入固定资产比','YTD total_revenue/nonzero fixed_assets'),
 ('sales_currentassets_ytd_library','营业总收入流动资产比','YTD total_revenue/nonzero current_assets'),
 ('longloan_cost_ytd_library_low','低长期借款营业成本比','-LTloan/nonzero YTD oper_cost'),
 ('finexpense_sales_ytd_library_low','低财务费用收入比','-YTD fin_exp/nonzero revenue'),
 ('sellexpense_sales_ytd_library_low','低销售费用收入比','-YTD sell_exp/nonzero revenue'),
 ('adminexpense_sales_ytd_library_low','低管理费用收入比','-YTD admin_exp/nonzero revenue'),
 ('operatingprofit_pretax_ytd_library','营业利润税前利润比','YTD operate_profit/nonzero total_profit'),
 ('valuechange_pretax_ytd_library_low','低价值变动利润贡献','-(YTD fair_value_change+invest_income+forex_gain)/nonzero total_profit'),
]
SPECS=[spec(k,n,SOURCE,formula,
 'proxy: source fac_dict/adjust_factors available dormant library atom; source notebook2013/2014 has no disclosed causal fitted alpha. Latest consolidated PIT YTD semantics retained; no financial missing-to-zero or industry imputation. Economic direction fixed, fullA rather than initial static universe; vendor mappings not byte-equivalent') for k,n,formula in DEFS]

def values(fin):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 def bs(c):return g('balancesheet',c)
 def inc(c):return g('income',c)
 def div(a,b):return q.ratio(a,np.where(b!=0,b,np.nan))
 capital=sum(bs(c) for c in ['total_hldr_eqy_inc_min_int','st_borr','non_cur_liab_due_1y','lt_borr','bond_payable','lt_payable'])
 return [div(g('cashflow','n_cashflow_act')-g('cashflow','n_cashflow_inv_act'),bs('total_ncl')),
         div(inc('n_income')+inc('fin_exp')+inc('income_tax'),capital),
         div(inc('total_revenue'),bs('fix_assets')),div(inc('total_revenue'),bs('total_cur_assets')),
         -div(bs('lt_borr'),inc('oper_cost')),-div(inc('fin_exp'),inc('revenue')),
         -div(inc('sell_exp'),inc('revenue')),-div(inc('admin_exp'),inc('revenue')),
         div(inc('operate_profit'),inc('total_profit')),
         -div(sum(inc(c) for c in ['fv_value_chg_gain','invest_income','forex_gain']),inc('total_profit'))]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True)
 plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='untested source library ratios; directions frozen before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates']
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=1,rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();checks=[];ids=np.arange(512)
  whole=values({k:v[:,ids] for k,v in fin.items()})
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='libraryratios-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=1)
    for sp,a,b in zip(SPECS,whole,values(cf)):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6)
     checks.append(dict(key=sp['key'],test='PIT_filing_cutoff_and_revision_replay',cutoff=str(cutoff),nonempty=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin)
  q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='dormant available financial source library ratios; no example model reproduction',missing='NaN retained; nonzero signed denominator retained',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED75',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader

if __name__=='__main__':main()
