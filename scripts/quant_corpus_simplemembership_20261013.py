"""Old size-axis membership variants; not independent alpha claims."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2020年度精选策略/59 小市值轮动，修改了内容，剔除了停牌股，同时PE要求为正的股票。.txt'
B='quant/2024年度精选策略1/18.微盘股研究.txt'
C='quant/2021年度精选策略/15.小市值策略之再优化，年化接近翻倍.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source136-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-simplemembership-schema-20261013'
FIELDS={'income':['n_income_attr_p'],'balancesheet':['total_hldr_eqy_exc_min_int']}
SPECS=[
 spec('small59_PEgt1_literal','PE严格大于一小盘',A,'-totalMV WHERE PE_TTM>1',
 'proxy actual PE>1 not merely positive. Tushare parentNI_TTM vendor mapping; prior-dayPIT. Source every_bar period10 increments bars not necessarily sessions; current-day pause/index universe/top10/cash-repeatorders not reproduced. Old size-axis conditional membership,not independentnewcluster.'),
 spec('micro18_positivePB_literal','正PB微盘资格',B,'-totalMV WHERE PB>0',
 'proxy consolidatedPITequity/totalMV; source small120 candidates/100holdings,20% position band,limitbid/ask andcoldstart after_code_changed schedule absent. Pure existing size axis,qualification subset benchmark.'),
 spec('small15_activeMA5_entry_partial','小盘五均线实际入场代理',C,'-totalMV WHERE C>=priorMA5',
 'proxy NEW totalMV ranking explicitly replaces source circMV (NOT equivalent);14:30minute price replaced completedclose and external currentdateMA5 replaced priorcompletedMA5. Source MAfilter callcommented but open_position still ACTIVE; dormant sellMA1 not replicated. Index399101/top9then3/limit/orders absent;oldstyleadapter.')]
for sp in SPECS:sp['gated']=True

def values(fin,f,pos):
 cap=f['cap'][pos].astype(float);ni=fin['income.n_income_attr_p_ttm.q0'];eq=fin['balancesheet.total_hldr_eqy_exc_min_int.q0']
 pe=np.divide(cap*10000,ni,out=np.full(ni.shape,np.nan),where=np.abs(ni)>1e-12)
 pb=np.divide(cap*10000,eq,out=np.full(eq.shape,np.nan),where=np.abs(eq)>1e-12)
 ma=pd.DataFrame(f['close'].astype(float)).rolling(5).mean().shift(1).to_numpy()[pos]
 return [np.where(pe>1,-cap,np.nan),np.where(pb>0,-cap,np.nan),np.where(f['close'][pos]>=ma,-cap,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='simple membership literal thresholds before outcomes, not newly independent axes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),stocks=list(stocks),rule=q.ALIGNMENT_RULE_VERSION,lags=1));fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();ids=np.arange(128);checks=[]
  sf={k:v[:,:128] for k,v in f.items()};whole=values({k:v[:,ids] for k,v in fin.items()},sf,pos)
  for n in [35,79]:
   sub={ep:t[(t.ann_date<=dates[n-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='membership-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cut=q.financial_snapshot(dates[:n],stocks[ids],lags=1);cv=values(cut,{k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
    for sp,a,b in zip(SPECS,whole,cv):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawPIT_and_daily_prefix_replay',passed=True))
  q.OUT=oldout;q.pit_tables=loader
  q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
  run(OUT,SPECS,values(fin,f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='oldsizeaxis membership variants; no full strategyperformance',benchmark_warning='qualificationbenchmark; pure-size residual invalid does not evaluate membership value'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED136',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
