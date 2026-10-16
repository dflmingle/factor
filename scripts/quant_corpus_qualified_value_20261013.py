"""Actual ROA threshold and sequential lowPEG/lowEBIT source filters."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
ROA='quant/2024年度精选策略1/16.大市值价值投资，从2005年至今超额稳定.txt'
PEG='quant/2023年度精选策略/36.PEG+EBIT对小市值因子的优化.txt'
MAG='quant/2023年度精选策略/32.最适合上班族的策略-神奇公式策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source56-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-qualified-value-schema-20261013'
SPECS=[
 spec('lowpb_roa_cash_profit_source','低PB现金扣非利润约束ROA',ROA,'ROA high where PB<1,operate_cash_inflow_YTD>1e6,profit_dedt_YTD>1e6,ROA>.15,netprofit_yoy>0',
 'proxy: actual code ROA>.15 not erroneous inventory>15; Tushare reportedROA%, c_inf_fr_operate_a and profit_dedt YTD mapping; no positivePB gate added; no largecap sorting in original code; source top5/raw/ST/IPO/index omissions'),
 spec('lowpeg_lowebit_small_source','低PEG低EBIT序贯筛小市值',PEG,'rank low PEG bottom10% of allA, then lowEBIT bottom25% of survivingPEG subset, then -totalMV',
 'proxy: original helper does not require positive PEG or EBIT; literal sortASC lowEBIT; PEG=(MV/parentNI_TTM)/reported_netprofit_yoy and reportedYTD EBIT as vendorfield proxies; totalMV explicitly replacescircMV; source IPO/ST/688 omissions; extremely restricted qualification benchmark'),
 spec('magic_pe_roa_rank_proxy','神奇公式PE与ROA双排名',MAG,'-rank(PE)+rank(ROA) within PE>0 and ROA>0',
 'proxy: source get_top30 combines default dataframe index of PEdesc and ROAasc then sorts descending; explicit ranks reproduce intended index orientation, source vendorindex exactness unverified; EPS secondary sorting and HS300top30/240day selection omitted'),
]
for s in SPECS:s['gated']=True

def build(fin,extra,cap):
 def b(ep,c):return fin[f'{ep}.{c}.q0'].astype(float)
 def e(ep,c):return extra[f'{ep}.{c}.q0'].astype(float)
 mv=cap*10000;pb=q.ratio(mv,b('balancesheet','total_hldr_eqy_exc_min_int'));pe=q.ratio(mv,b('income','n_income_attr_p_ttm'))
 roa=b('fina_indicator','roa');g=b('fina_indicator','netprofit_yoy');ebit=b('income','ebit')
 valid=(pb<1)&(e('cashflow','c_inf_fr_operate_a')>1e6)&(e('fina_indicator','profit_dedt')>1e6)&(roa>.15)&(g>0)&np.isfinite(pb)
 first=np.where(valid,roa,np.nan)
 peg=q.ratio(pe,g);second=np.full(cap.shape,np.nan)
 for i in range(len(cap)):
  # Source slice lengths use incoming universe length, not nonmissing count.
  active=cap[i]>0;n=int(active.sum()*.1)
  ids=np.flatnonzero(active&np.isfinite(peg[i]));ids=ids[np.argsort(peg[i,ids],kind='stable')][:n]
  m=int(len(ids)*.25);ids=ids[np.isfinite(ebit[i,ids])];ids=ids[np.argsort(ebit[i,ids],kind='stable')][:m]
  second[i,ids]=-cap[i,ids]
 gate=(pe>0)&(roa>0);third=-q.rank(np.where(gate,pe,np.nan))+q.rank(np.where(gate,roa,np.nan))
 return [first,second,third]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='literal source code thresholds frozen before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);base=q.financial_snapshot(grid,stocks)
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS={'fina_indicator':['profit_dedt'],'cashflow':['c_inf_fr_operate_a']}
  q.dump(SCHEMA/'schema.json',dict(fields=q.FIN_FIELDS,dates=[str(d) for d in grid],rule=q.ALIGNMENT_RULE_VERSION,lags=1))
  extra=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();checks=[];ids=np.arange(512);whole=build({k:v[:,ids] for k,v in base.items()},{k:v[:,ids] for k,v in extra.items()},f['cap'][pos][:,ids])
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='cashprofit-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cut=q.financial_snapshot(grid[:n],stocks[ids],lags=1)
    rebuilt=build({k:v[:n,ids] for k,v in base.items()},cut,f['cap'][pos[:n]][:,ids])
    for s,a,b in zip(SPECS,whole,rebuilt):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-6,atol=1e-6);checks.append(dict(key=s['key'],test='raw_cutoff_replay_added_cashprofit_and_prefix_sequential_filters',passed=True,nonempty=bool(np.isfinite(b).any())))
  q.OUT=oldout;q.pit_tables=loader;vals=build(base,extra,f['cap'][pos])
  q.dump(OUT/'qualification_coverage.json',{s['key']:dict(stocks_by_signal=np.isfinite(x).sum(axis=1).tolist(),median_stocks=float(np.median(np.isfinite(x).sum(axis=1))),benchmark='factor_valid qualification subset, NOT fullA unfiltered comparator') for s,x in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='allA PIT proxies of source financial selection; qualification subset outcomes',benchmark_warning='all3 use restricted factor_valid subset; cannot assert broad fiveyear stock alpha',statistics='exploratory no independent OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED56',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
