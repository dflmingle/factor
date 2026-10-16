"""Distinct SVR source with default gamma and sign-log six financial inputs."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.svm import SVR
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2024年度精选策略1/12.致敬聚宽机器学习多因子50只持仓14年37倍.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source68-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-svr-signlog-schema-20261013'
FIELDS={'balancesheet':['total_assets','total_liab','r_and_d'],'income':['n_income','n_income_attr_p'],'fina_indicator':['or_yoy']}
SPECS=[spec('svr_signlog_default6_undervaluation','六财务符号对数SVR低估残差',SOURCE,
 '-(signlog(totalMV/10000)-SVR_RBF(gamma=scale,C1,epsilon.1).fit_predict(signlog([assets-liab,YTDnetincome,capitalizedRD,PE,assets/liab,revenue_yoy/100]))); assets>liab,YTDnetincome>0',
 'proxy: source default gamma scale, signlog all6 inputs, literal fillna0 AFTER positive-equity/profit filter; PIT totalMV target substitutes vendor亿元cap; PE uses PIT parentNI_TTM; industry dummies and index constituents missing explicitly omitted. Continuous residual replaces residual<0 top60 and 50stock buffer; current-CS estimation causal but no study OOS')]

def values(fin,cap,verbose=False):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 a=g('balancesheet','total_assets');li=g('balancesheet','total_liab');ni=g('income','n_income');pe=q.ratio(cap*10000,g('income','n_income_attr_p_ttm'))
 x=np.stack([a-li,ni,g('balancesheet','r_and_d'),pe,q.ratio(a,li),g('fina_indicator','or_yoy')/100],axis=-1)
 # Source fills original missing feature values with0 before sign-log. Infinite
 # feature values are rejected rather than silently clamped or zero-imputed.
 x=np.where(np.isnan(x),0,x);x=np.sign(x)*np.log1p(np.abs(x));y=np.log1p(cap/10000)
 res=np.full(cap.shape,np.nan)
 for i in range(len(cap)):
  good=(a[i]>li[i])&(ni[i]>0)&(cap[i]>0)&np.isfinite(x[i]).all(axis=1)&np.isfinite(y[i])
  if good.sum()<100:continue
  model=SVR(kernel='rbf');pred=model.fit(x[i,good],y[i,good]).predict(x[i,good]);res[i,good]=pred-y[i,good]
  if verbose and i%20==0:print('SVR_SIGNLOG',i,len(cap),int(good.sum()),flush=True)
 return [res]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();checks=[]
  ids=np.arange(768);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap)
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='svr-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=1);cut=values(cf,cap[:n])[0]
    np.testing.assert_allclose(whole[0][:n],cut,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(test='PIT_cutoff_and_entire_SVR_refit',cutoff=str(cutoff),nonempty=int(np.isfinite(cut).sum()),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,f['cap'][pos],True)
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='6availableinputs industry-omitted source proxy',statistics='exploratory no untouched OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED68',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
