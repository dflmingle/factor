"""Untested partial financial selectors; full-A matched-SIZE diagnostics."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_sweep_20261013 import tie_diagnostic
A='quant/2024年度精选策略1/36.【菜场大妈】股息率小市值策略,10年206倍,5年10.8倍.txt'
B='quant/2024年度精选策略1/26.【深度解析 六】高股息率-低PEG-低股价 模型.txt'
C='quant/聚宽2025年精选/6国九小市值策略【年化100.5】.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source157-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-partialpeg-guojiu-schema-20261013'
FIELDS={'fina_indicator':['netprofit_yoy'],'balancesheet':['total_hldr_eqy_exc_min_int'],
        'income':['n_income_attr_p','n_income','revenue']}
COMMON='proxy NEW fullA lexicographic membership adapter 2*I(gate)+rank(-totalMV); same support/benchmark as saved144SIZE. Prior-day announced consolidated financials; PE uses parentNI TTM, vendor reported netprofitYoY and PB map are not byte-equivalent. No complete strategy/OOS/poolComb claim. '
SPECS=[
 spec('partial36_negativePEG_PB3_priority','负PEG低PB资格同支持',A,'2*I(PE_TTM/netprofitYoY<0 AND PB<3)+rank(-totalMV)',COMMON+'Registered365day cashdividendtop25% explicitly OMITTED. No PB>0 inserted. Intraday newholdingprice<10, Aprilcash and holding/limitblacklist absent; not original highdividend recipe.'),
 spec('partial26_PEGpm3_conditional_lowprice_priority','双边PEG条件低价同支持',B,'2*I(-3<PEG<3 AND priorqfqC<eligible sortedprice[floor(.75N)])+rank(-totalMV)',COMMON+'Registered365daydividendtop25% OMITTED. Conditional price quantile computed AFTER partial PEG gate, strict<, original daily quote explicitly adapted priorqfqC; no guessed fixed price threshold or original 20holding/IPO/minute/limitpath.'),
 spec('guojiu6_positiveYTDNI_revenue_size_priority','国九盈利营收资格同支持',C,'2*I(10<=totalMV_billion<=1e8 AND parentNI_YTD>0 AND totalNI_YTD>0 AND revenue_YTD>1e8)+rank(-totalMV)',COMMON+'Literal source10..1e8亿 size bounds, not118upper100; latest YTD income, not TTM gates. Sourceaudit False and computed df_audit never applied. Actual399101/375day/mainboard/ST/price50/top3N/stops/index200pointadaptive3..6holdings/JanAprETF absent.')]

def values(fin,cap,priorclose):
 def g(ep,c):return fin[f'{ep}.{c}.q0'].astype(float)
 mv=cap.astype(float)*10000
 with np.errstate(divide='ignore',invalid='ignore'):
  pe=mv/g('income','n_income_attr_p_ttm');pb=mv/g('balancesheet','total_hldr_eqy_exc_min_int');peg=pe/g('fina_indicator','netprofit_yoy')
 valid=np.isfinite(peg);m1=valid&(peg<0)&np.isfinite(pb)&(pb<3)
 eligible=valid&(peg>-3)&(peg<3)&np.isfinite(priorclose);m2=np.zeros(cap.shape,bool)
 for i in range(len(cap)):
  x=np.sort(priorclose[i,eligible[i]])
  if len(x):m2[i]=eligible[i]&(priorclose[i]<x[int(.75*len(x))])
 size=cap/10000
 m3=(size>=10)&(size<=1e8)&(g('income','n_income_attr_p')>0)&(g('income','n_income')>0)&(g('income','revenue')>1e8)
 base=q.rank(np.where(cap>0,-cap,np.nan))
 return [base+2*m for m in [m1,m2,m3]]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True)
 plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='three literal partial financial gates fixed before outcomes; no threshold tuning')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),lags=1,rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();ids=np.arange(128);cap=f['cap'][pos][:,ids];close=f['close'][pos-1][:,ids]
  full=values({k:v[:,ids] for k,v in fin.items()},cap,close);checks=[]
  for n in [35,79]:
   cutoff=dates[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='PIT-cutoff-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(dates[:n],stocks[ids],lags=1);cut=values(cf,cap[:n],close[:n])
    for sp,a,b in zip(SPECS,full,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6);checks.append(dict(key=sp['key'],test='raw_priorPIT_filing_cutoff_replay',passed=True))
  toy={'fina_indicator.netprofit_yoy.q0':np.array([[-10,10,10,10]],float),
       'balancesheet.total_hldr_eqy_exc_min_int.q0':np.full((1,4),5e8),
       'income.n_income_attr_p_ttm.q0':np.full((1,4),1e8),
       'income.n_income_attr_p.q0':np.full((1,4),1e8),
       'income.n_income.q0':np.full((1,4),1e8),
       'income.revenue.q0':np.array([[2e8,1e8,2e8,2e8]])}
  tc=np.full((1,4),1e5);base=q.rank(-tc);tv=values(toy,tc,np.array([[1.,2.,3.,4.]]))
  np.testing.assert_allclose(tv[0]-base,[[2,0,0,0]])
  np.testing.assert_allclose(tv[1]-base,[[2,2,2,0]])
  np.testing.assert_allclose(tv[2]-base,[[2,0,2,2]])
  checks.append(dict(test='literal_negativePEG_strict_conditional_quantile_and_YTDgates_toy',passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,f['cap'][pos],f['close'][pos-1])
  saved=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/signal_panels.pkl')
  assert saved['dates'].equals(grid) and saved['stocks'].equals(stocks)
  base=saved['panels']['membership144_size_control'].to_numpy()
  for x in vals:np.testing.assert_array_equal(np.isfinite(x),np.isfinite(base))
  checks.append(dict(test='same_support_as_saved_SIZE_control',passed=True))
  q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
  b=pd.read_csv(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/results.csv');r=pd.read_csv(OUT/'results.csv');deltas=[]
  for _,x in r[r.form.eq('raw')].iterrows():
   z=b[b.key.eq('membership144_size_control')&b.window.eq(x.window)&b.form.eq('raw')].iloc[0]
   deltas.append(dict(key=x.key,window=x.window,form='raw',delta_net_excess_pct=x.net_excess_pct-z.net_excess_pct,
    delta_held_daily_max_drawdown_pct=x.held_daily_max_drawdown_pct-z.held_daily_max_drawdown_pct,delta_turnover_pct=x.turnover_pct-z.turnover_pct))
  pd.DataFrame(deltas).to_csv(OUT/'matched_size_control_deltas.csv',index=False)
  q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED157',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
