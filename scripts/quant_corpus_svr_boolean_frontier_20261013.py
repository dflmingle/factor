"""Source 2024/66 literal five BOOLEAN query columns as SVR inputs."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.svm import SVR
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2024年度精选策略1/66.SVR机器学习上证综指择时中小板财务选股策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source77-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-svr-boolean-schema-20261013'
FIELDS={'balancesheet':['total_assets','total_liab','total_hldr_eqy_exc_min_int'],'income':['n_income'],'fina_indicator':['roe_dt','tr_yoy','netprofit_yoy','ocf_to_opincome']}
SPECS=[spec('svr_booleanquery5_undervaluation','五布尔查询列SVR估值残差',SOURCE,
 '-(log1p(totalMV/10000)-SVR_RBF(gamma=scale,C1,epsilon.1).fit_predict(log1p([PB>0,roe_dt>0,tr_yoy>0,netprofit_yoy>0,ocf_to_opincome>5])));assets>liab,YTDnetincome>0',
 'proxy: source query columns are five BOOLEAN comparison expressions, NOT five renamed continuous financial fields. Source NaN0 and signlog retained; Tushare roe_dt and ocf_to_opincome vendor ratio mappings not byte-equivalent. FullA replaces399101; PIT industry dummy columns omitted, indexRSRS/state/calendartrading and12stock buffer omitted explicitly. Not source full strategy')]
SPECS[0]['gated']=True

def values(fin,cap,verbose=False):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 a=g('balancesheet','total_assets');li=g('balancesheet','total_liab');ni=g('income','n_income')
 pb=q.ratio(cap*10000,g('balancesheet','total_hldr_eqy_exc_min_int'))
 # Comparisons are query columns, not query filters; unknown bool maps to source0.
 x=np.stack([pb>0,g('fina_indicator','roe_dt')>0,g('fina_indicator','tr_yoy')>0,g('fina_indicator','netprofit_yoy')>0,g('fina_indicator','ocf_to_opincome')>5],axis=-1).astype(float)
 x=np.log1p(x);y=np.log1p(np.where(cap>0,cap,np.nan)/10000)
 res=np.full(cap.shape,np.nan)
 for i in range(len(cap)):
  good=(a[i]>li[i])&(ni[i]>0)&(cap[i]>0)&np.isfinite(x[i]).all(axis=1)&np.isfinite(y[i])
  if good.sum()<100:continue
  model=SVR(kernel='rbf');pred=model.fit(x[i,good],y[i,good]).predict(x[i,good]);res[i,good]=pred-y[i,good]
  if verbose and i%20==0:print('SVR_BOOLEAN',i,len(cap),int(good.sum()),flush=True)
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
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='5boolean querycolumns industry-omitted source proxy',statistics='exploratory no untouched OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED77',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
