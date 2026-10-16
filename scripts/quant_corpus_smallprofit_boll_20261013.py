"""Exact positive-profit source intersections and >50bn ROA/Boll branch."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/64大小外择时小市值3.0.txt'
B='quant/聚宽2025年精选/83大小外择时小市值.txt'
C='quant/聚宽2025年精选/15小市值排除3个bug版，22年至今收益506.txt'
D='quant/聚宽2025年精选/8国九条后中小板微盘小改，年化135.40.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source118-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-smallprofit-boll-schema-20261013'
FIELDS={'fina_indicator':['roa','profit_dedt','netprofit_yoy'], 'income':['n_income','n_income_attr_p','revenue'],
 'cashflow':['c_inf_fr_operate_a'],'balancesheet':['total_hldr_eqy_exc_min_int']}
SPECS=[
 spec('sizeprofit64_mv5_30_ytd','五至三十亿正利润营收小盘',A,'-totalMV where5e8<=MV<=30e8,parentNI_YTD>0,totalNI_YTD>0,revenue_YTD>1e8',
 'proxy: actualget_stock_list_2 financial gates use YTD not TTM. FullA replaces399101, no top50/price50/holdexception imposed for100stock support; alpha remains size ranking; not entireunionwhere firstunconditional50 generally dominates.'),
 spec('sizeprofit15_mv10_100_ytd','十至百亿正利润营收小盘',C,'-totalMV where10e8<=MV<=100e8,parentNI_YTD>0,totalNI_YTD>0,revenue_YTD>1e8',
 'proxy exact source financialqualification beforetop3*g.stocknum andrawprice50. DefaultauditFalse, not required or silentlyfabricated. Original3..6holdcount controlledINDEXpointgap notstockbias, moneyETF/1&4month/stop9%state unimplemented.'),
 spec('roa83_cashprofit_pb1_mv50','八十三号现金质量低PB大于五十亿',B,'reportedROA where PB<1,MV>50e8,operatecashinflowYTD>1e6,profit_dedtYTD>1e6,ROA>.15,netprofitYoY>0',
 'proxy exact extraMV>50e8 distinctsource56noMVgate; signed PB permitted. Source nameROIC_BIG actually ordersROA, never ROIC sorting. No indexHS300/Boll/3stock truncation or style switch claimed.'),
 spec('roa83_cashprofit_boll20_mv50','八十三号现金质量布林通道交集',B,'sameROA where lag1C<MA20+2popSTD20 AND lag1L>MA20-2popSTD20',
 'proxy literalBoll eligibility beforeROAquery; reportedsource technicalBollinger_Bands vendor populationstd20 proxy, previouscompletedOHLC. include_now True onpreviousdate; no Intradayfields, no stop/ETF/indexreproduction.')]
for sp in SPECS:sp['gated']=True
SPECS[0]['source_paths']=[A,B]
SPECS[1]['source_paths']=[C,D]

def values(fin,f,pos):
 def g(ep,c):return fin[f'{ep}.{c}.q0'].astype(float)
 cap=f['cap'][pos].astype(float);mv=cap*10000;profit=(g('income','n_income')>0)&(g('income','n_income_attr_p')>0)&(g('income','revenue')>1e8)
 small=np.where(profit&(mv>=5e8)&(mv<=30e8),-cap,np.nan);mid=np.where(profit&(mv>=10e8)&(mv<=100e8),-cap,np.nan)
 pb=q.ratio(mv,g('balancesheet','total_hldr_eqy_exc_min_int'));roa=g('fina_indicator','roa')
 good=(pb<1)&np.isfinite(pb)&(mv>50e8)&(g('cashflow','c_inf_fr_operate_a')>1e6)&(g('fina_indicator','profit_dedt')>1e6)&(roa>.15)&(g('fina_indicator','netprofit_yoy')>0)
 c=pd.DataFrame(f['close'].astype(float));ma=c.rolling(20).mean();sd=c.rolling(20).std(ddof=0);upper=(ma+2*sd).to_numpy()[pos-1];lower=(ma-2*sd).to_numpy()[pos-1]
 boll=(f['close'][pos-1]<upper)&(f['low'][pos-1]>lower)
 return [small,mid,np.where(good,roa,np.nan),np.where(good&boll,roa,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixedYTDpositive,5..30/10..100/50bn,Boll20/2; prior-dayPIT')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();ids=np.arange(128);sf={k:v[:,ids] for k,v in f.items()};whole=values({k:v[:,ids] for k,v in fin.items()},sf,pos);checks=[]
  for n in [35,79]:
   cutoff=dates[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='smallprofit-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(dates[:n],stocks[ids],lags=1);stop=pos[n-1]+1;cut=values(cf,{k:v[:stop] for k,v in sf.items()},pos[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='prior-dayPIT_and_completedOHLC_cutoff_replay',nonempty=int(np.isfinite(b).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,f,pos)
  q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C,D]});q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='financialsubset proxy, nooriginal smallcount orindexorders',benchmark_warning='factor_validsubset, residualdegeneracy doesnot invalidate membership'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED118',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
