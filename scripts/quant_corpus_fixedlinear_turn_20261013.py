"""Previously family-labelled fixed linear coefficients; causal vendor proxies."""
import ast,json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_semantic_review_20261012 import core
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source84-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-fixedlinear-turn-schema-20261013'
FIELDS={'income':['total_profit','total_cogs']}
PATHS=['quant/2024年度精选策略1/1.差不多得了.txt','quant/2024年度精选策略1/24.凑波热闹，也来试试多因子线性回归.txt','quant/聚宽2025年精选/19机器学习线性回归小市值.txt']
EXPECTED=[[-.0647128120839873,-.006385116279168804,-.0029867925845833217],[-1.6481969388084845,-.17062057099935446,-.061842557079243125],[-.007686604605324844,-.001064082235156668,-.0006372186835828526]]
FEATURES=['Price1Y','total_profit_to_cost_ratio','VOL120']
def extract(p):
 tree=ast.parse(core(q.ROOT/p))
 for n in ast.walk(tree):
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='factor_list' for t in n.targets):
   for fields,coeff in ast.literal_eval(n.value):
    if fields==FEATURES:return coeff
 raise ValueError(p)
COEFF=[extract(p) for p in PATHS]
assert COEFF==EXPECTED
SPECS=[]
for i,(p,weights) in enumerate(zip(PATHS,COEFF)):
 sp=spec('fixedlinear_priceprofitturn_variant'+str(i+1),'固定系数价差成本换手配方'+str(i+1),p,
 '+'.join(f'({w})*{col}' for w,col in zip(weights,FEATURES)),
 'proxy: exact AST-extracted source coefficients and direct rawfeature sum, no crosssection normalization. Price1Y=C/MA250-1 (explicit250dayyear vendor proxy); profitcost=100*PITtotalprofitTTM/positive totalcogsTTM (percentage unit explicit vendor proxy); VOL120=mean120(daily_basic turnover percent). Vendor defaults not byteequivalent. FullA ranking atom before source top10percent/EPS/circMV/weekly/calendar buffers; not full source strategy')
 SPECS.append(sp)

def values(fin,f,pos):
 price=(q.ratio(f['close'],q.rolling(f['close'],250))-1)[pos]
 profit=fin['income.total_profit_ttm.q0'];cost=fin['income.total_cogs_ttm.q0']
 ratio=q.ratio(profit,np.where(cost>0,cost,np.nan))*100;turn=q.rolling(f['turnover'],120)[pos]
 return [w[0]*price+w[1]*ratio+w[2]*turn for w in COEFF]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='allthree source coefficients in this supported-feature family, no fittedweights')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();ids=np.arange(512);sf={k:v[:,ids] for k,v in f.items()};whole=values({k:v[:,ids] for k,v in fin.items()},sf,pos);checks=[]
  for n in [35,79]:
   stop=pos[n-1]+1;cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='fixedlinear-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=1);cut=values(cf,{k:v[:stop] for k,v in sf.items()},pos[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='raw_PIT_cutoff_and_daily_price_turnover_prefix',cutoff=str(cutoff),nonempty=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader
  checks.append(dict(test='original_source_AST_feature_names_and_allthree_coefficient_lists',passed=COEFF==EXPECTED))
  q.dump(OUT/'source_feature_evidence.json',dict(source_paths=PATHS,features=FEATURES,coefficients=COEFF,missing_other_groups=['ARBR proprietary vendor definition','SGAI vendor quarterly annual convention','price_no_fq prohibited in canonical qfq result','sales_growth5year vendor history definition','Sharpe120 riskfree/window conventions'],not_full_strategy=True))
  vals=values(fin,f,pos)
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='exact source coefficients with explicitly disclosed field/window/unit proxies',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED84',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader

if __name__=='__main__':main()
