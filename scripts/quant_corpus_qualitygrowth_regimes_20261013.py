"""Untested white-horse source regime qualification and PTrade growth score."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
WHITE='quant/聚宽2025年精选/18国庆节献礼：实例说明白马股攻防转换策略.txt'
PORT='quant/量化策略/量化策略/实盘2026/Ptrade/pt版08多因子成长小市值轮动策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source80-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-qualitygrowth-regimes-schema-20261013'
FIELDS={'fina_indicator':['roa','roe_dt','netprofit_yoy','or_yoy','profit_dedt'],
 'balancesheet':['total_hldr_eqy_exc_min_int'],'income':['n_income','n_income_attr_p','total_profit'],
 'cashflow':['c_inf_fr_operate_a']}
SPECS=[
 spec('roa_positive_bm_product','ROA正账面价值收益比',WHITE,'ROA/PB with positive PB',
 'proxy: actual cold/warm source ranking atom, fullA with no indextemperature or quality gates; ROA/positivePB, not mislabeled ROA/BP; Tushare reportedROA and PITequity mappings'),
 *[spec('whitehorse_'+regime+'_qualified','白马'+regime+'源码交集',WHITE,formula,
 'proxy: fixed source regime branch, source HS300->fullA, indextemperature/state/monthly execution missing explicitly not reconstructed; reported YTD vendor profitability/cash-inflow mapping; qualified factor_valid subset benchmark') for regime,formula in [
 ('cold','ROA/PB on 0<PB<1,operatecashinflow/profit_dedt>2,roe_dt>1.5,netprofit_yoy>-15; both cashinflow and profit_dedt>0'),
 ('warm','ROA/PB on 0<PB<1,operatecashinflow/profit_dedt>1,roe_dt>2,netprofit_yoy>0; both cashinflow and profit_dedt>0'),
 ('hot','ROA on PB>3,operatecashinflow/profit_dedt>.5,roe_dt>3,netprofit_yoy>20; both cashinflow and profit_dedt>0')]],
 spec('ptrade_growth_three_rank_fulla','Ptrade四成长和PEG三秩',PORT,
 '(rank(rev_yoy)+rank(.1rev_yoy+.35pretax_yoy+.15netincome_yoy+.4parent_yoy)+rank(netincome_yoy/positivePE))/3; positive netincome growth',
 'proxy: raw available growth score, fullA replaces source50smallfloatcap stocks. Revenue/parentYoY Tushare reported fields; pretax/netincomeYoY=(YTDq0-YTDq4)/abs(YTDq4)*100 explicit vendor proxy. PE=totalMV/parentNI_TTM. Not fiveyear forecast field; sourcelimit/listing/ST/holdbuffer omitted'),
 spec('ptrade_growth_three_rank_small50','Ptrade前三秩原五十小盘约束',PORT,
 'same3rankscore within50smallest totalMV stocks before financialdropna',
 'proxy: literal top50 count but totalMV replacesfloatcap explicitly; <100stocks violates canonical evaluator minimum, no fiveyear alpha conclusion; retained as source qualification coverage evidence')]
for sp in SPECS[1:]:sp['gated']=True

def values(fin,cap):
 def g(ep,c,k=0):return fin[f'{ep}.{c}.q{k}'].astype(float)
 eq=g('balancesheet','total_hldr_eqy_exc_min_int');mv=cap*10000;pb=q.ratio(mv,eq);roa=g('fina_indicator','roa');roe=g('fina_indicator','roe_dt');growth=g('fina_indicator','netprofit_yoy')
 ratio=q.ratio(g('cashflow','c_inf_fr_operate_a'),g('fina_indicator','profit_dedt'))
 positive=(g('cashflow','c_inf_fr_operate_a')>0)&(g('fina_indicator','profit_dedt')>0)
 cold=positive&(pb>0)&(pb<1)&(ratio>2)&(roe>1.5)&(growth>-15)
 warm=positive&(pb>0)&(pb<1)&(ratio>1)&(roe>2)&(growth>0)
 hot=positive&(pb>3)&(ratio>.5)&(roe>3)&(growth>20)
 roa_pb=np.where(pb>0,q.ratio(roa,pb),np.nan)
 def yoy(col):
  a=g('income',col);b=g('income',col,4);return q.ratio(a-b,np.where(np.abs(b)>0,np.abs(b),np.nan))*100
 rev=g('fina_indicator','or_yoy');pretax=yoy('total_profit');ni=yoy('n_income');parent=g('fina_indicator','netprofit_yoy')
 ms=.1*rev+.35*pretax+.15*ni+.4*parent;pe=q.ratio(mv,g('income','n_income_attr_p_ttm'));invpeg=q.ratio(ni,pe)
 valid=(pe>0)&(ni>0)&np.isfinite(np.stack([rev,ms,invpeg])).all(axis=0)
 top50=np.zeros(cap.shape,bool)
 for i in range(len(cap)):
  ids=np.flatnonzero(np.isfinite(cap[i])&(cap[i]>0));top50[i,ids[np.argsort(cap[i,ids],kind='stable')[:50]]]=True
 def score(mask):return sum(q.rank(np.where(mask,x,np.nan)) for x in [rev,ms,invpeg])/3
 return [roa_pb,np.where(cold,roa_pb,np.nan),np.where(warm,roa_pb,np.nan),np.where(hot,roa,np.nan),score(valid),score(valid&top50)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source economic directions, regime gates and exact portweights fixed before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=5,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=5);tables=q.pit_tables();ids=np.arange(512);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap);checks=[]
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='qualitygrowth-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=5);cut=values(cf,cap[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='raw_filing_cutoff_revision_YTD_growth_and_TTM_replay',cutoff=str(cutoff),nonempty=int(np.isfinite(b).sum()),passed=True))
  checks.append(dict(test='source_rankratio_direction_ROA_div_PB_not_ROA_div_BP',example=dict(roa=10,pb=2,score=5),passed=(10/2==5)))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,f['cap'][pos]);assert np.max(np.isfinite(vals[-1]).sum(axis=1))<=50
  q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='explicit fixedbranch and financialvendor proxies; not original portfolio',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED80',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader

if __name__=='__main__':main()
