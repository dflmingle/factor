"""Explicit available-input conformal valuation adaptation; no original claim."""
import sys,json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from threadpoolctl import threadpool_limits
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-xgboost-runtime-20261013'))
from xgboost import XGBRegressor
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/聚宽2025年精选/70动态保形回归小市值策略改进.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source63-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-conformal-schema-20261013'
FIELDS={'fina_indicator':['netprofit_yoy','grossprofit_margin','tr_yoy','roa'],'balancesheet':['total_cur_assets','total_cur_liab','total_liab','total_assets','total_hldr_eqy_exc_min_int'],'income':['total_profit','n_income_attr_p','total_revenue'],'cashflow':['n_cashflow_act']}
FN=['actual_profit_growth','workingcapital','liab_minus_assets','liab_equity','actual_grossmargin','noncurrentasset_fraction','equity_fraction','YTDtotalprofit','revenuegrowth','turnover','PEproxy','PBproxy','PSproxy','ROA']
TN=['amount','MTM10','volume','EMA10','MA10','BIAS10']
SPECS=[spec('conformal_available20_valuation_residual','二十输入保形估值相对残差',SOURCE,
 'sourceXGBselection5financial+5technical->4features; minmaxCS;GMM1..10BIC largestcluster;3fold(train/cal/test);XGB12trees,AbsError95interval; high -(actual-prediction)/abs(actual) ifmeanwidth<1.4 else highpositive, remove3IQRresidualoutliers',
 'proxy:20/25availableinputs, omit directcap explanatory feature becausecircMV->totalMV creates self-prediction, omit4unverifiedvendor technical kernels(KDJ,BRAR,OBV,DMA); actual mislabeled source financial fields preserved; totalMV target replacescircMV; fullA replaces sizebottom10% audit/dividend qualified subset; missing external audit/dividends omitted explicitly; allsymbol joins keyed; fixedGMMseed42 replaces unspecific state; standard daily EMA/MTM proxies, versionXGBoost1.7.6; per-current-CS past20calendar-day selection label, crossfit targetcurrentMV does NOT establish future-return OOS')]
SPECS[0]['gated']=True

def inputs(fin,grid,cal,f):
 pos=cal.get_indexer(grid);mv=f['cap'][pos].astype(float)*10000
 def a(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 A=a('balancesheet','total_assets');L=a('balancesheet','total_liab');E=a('balancesheet','total_hldr_eqy_exc_min_int');CA=a('balancesheet','total_cur_assets');CL=a('balancesheet','total_cur_liab')
 finance=np.stack([a('fina_indicator','netprofit_yoy'),CA-CL,L-A,q.ratio(L,E),a('fina_indicator','grossprofit_margin'),q.ratio(A-CA,A),q.ratio(E,A),a('income','total_profit'),a('fina_indicator','tr_yoy'),f['turnover'][pos],q.ratio(mv,fin['income.n_income_attr_p_ttm.q0']),q.ratio(mv,E),q.ratio(mv,fin['income.total_revenue_ttm.q0']),a('fina_indicator','roa')],axis=-1)
 c=f['close'].astype(float);ema=pd.DataFrame(c).ewm(span=10,adjust=False,min_periods=10).mean().to_numpy();ma=q.rolling(c,10)
 tech=np.stack([f['amount'][pos],(c-q.delay(c,10))[pos],f['volume'][pos],ema[pos],ma[pos],(q.ratio(c,ma)-1)[pos]],axis=-1)
 old=cal.searchsorted(grid-pd.Timedelta(days=19),side='right')-1
 ret=q.ratio(c[pos],c[old])-1;y=np.where(np.isfinite(ret),(ret>=0).astype(float),np.nan)
 return finance,tech,mv,y

def minmax(x):
 low=np.nanmin(x,axis=0);high=np.nanmax(x,axis=0);den=high-low
 out=np.full(x.shape,np.nan);good=den>1e-12;out[:,good]=(x[:,good]-low[good])/den[good]
 return out

def select(x,y,n):
 cols=np.flatnonzero(np.isnan(x).mean(axis=0)<=.05)
 if not len(cols):return []
 good=np.isfinite(x[:,cols]).all(axis=1)&np.isfinite(y)
 if good.sum()<100:return []
 m=XGBRegressor(n_estimators=n,gamma=.8,learning_rate=.1,max_depth=3,random_state=42,n_jobs=1,tree_method='hist');m.fit(x[good][:,cols],y[good])
 return cols[np.argsort(-m.feature_importances_,kind='stable')[:5]].tolist()

def predict(data):
 fin,tech,mv,y=data;out=np.full(mv.shape,np.nan);notes=[]
 for i in range(len(mv)):
  active=(mv[i]>0)&np.isfinite(y[i]);ids=np.flatnonzero(active)
  if len(ids)<100:continue
  xf=minmax(fin[i,ids]);xt=minmax(tech[i,ids]);target=minmax(mv[i,ids,None])[:,0];sy=y[i,ids]
  af=select(xf,sy,10);at=select(xt,sy,9)
  if not af or not at:continue
  merged=np.concatenate([xf[:,af],xt[:,at]],axis=1);chosen=select(merged,sy,10)[:4]
  if not chosen:continue
  X=merged[:,chosen];cols=np.column_stack([X,target]);lo=np.nanquantile(cols,.25,axis=0);hi=np.nanquantile(cols,.75,axis=0);good=np.isfinite(cols).all(axis=1)&((cols>=lo-1.5*(hi-lo))&(cols<=hi+1.5*(hi-lo))).all(axis=1)
  X=X[good];Y=target[good];local=ids[good]
  if len(X)<100:continue
  bics=[]
  for k in range(1,11):
   g=GaussianMixture(n_components=k,covariance_type='full',random_state=42);g.fit(X);bics.append(g.bic(X))
  best=int(np.argmin(bics)+1);g=GaussianMixture(n_components=best,covariance_type='full',random_state=42).fit(X);label=g.predict(X);largest=np.argmax(np.bincount(label));take=label==largest;X=X[take];Y=Y[take];local=local[take]
  if len(X)<100:notes.append(dict(signal=i,largestcluster=len(X),skipped='less100'));continue
  # pandas.sample fixed seed is used by source; preserve its permutation.
  order=pd.Series(np.arange(len(X))).sample(frac=1,random_state=42).to_numpy();third=len(X)//3;groups=[order[:third],order[third:2*third],order[2*third:]]
  pred=np.full(len(X),np.nan);width=np.full(len(X),np.nan)
  for a,b,c in [(0,1,2),(2,0,1),(1,2,0)]:
   ca,tr,te=groups[a],groups[b],groups[c];m=XGBRegressor(n_estimators=12,random_state=42,n_jobs=1,tree_method='hist');m.fit(X[tr],Y[tr]);err=np.sort(np.abs(m.predict(X[ca])-Y[ca]))[::-1];border=min(max(int(np.floor(.05*(len(err)+1)))-1,0),len(err)-1);pred[te]=m.predict(X[te]);width[te]=2*err[border]
  valid=(Y!=0)&np.isfinite(pred);dist=q.ratio(Y-pred,np.abs(Y));ql,qh=np.nanquantile(dist[valid],[.25,.75]);valid&=(dist>=ql-3*(qh-ql))&(dist<=qh+3*(qh-ql));sign=-1 if np.nanmean(width)<1.4 else 1;out[i,local[valid]]=sign*dist[valid]
  names=[FN[k] for k in af]+[TN[k] for k in at];notes.append(dict(signal=i,features=[names[k] for k in chosen],gmm=best,largestcluster=len(X),meanwidth=float(np.nanmean(width)),sign=sign,valid=int(valid.sum())))
  if i%12==0:print('CONFORMAL',i+1,'/',len(mv),'valid',int(valid.sum()),flush=True)
 return out,notes

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,financial=FN,technical=TN,selection='source architecture and explicit omissions fixed before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;fin=q.financial_snapshot(grid,stocks,lags=1);tables=q.pit_tables();checks=[];ids=np.arange(1024);small={k:v[:,ids] for k,v in f.items()};sf={k:v[:,ids] for k,v in fin.items()}
  # Validate entire model on a prefix independently rebuilt from raw filings.
  cutoff=grid[9];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
  with tempfile.TemporaryDirectory(prefix='conformal-PIT-prefix-',dir=OUT) as temp:
   q.OUT=Path(temp);cf=q.financial_snapshot(grid[:10],stocks[ids],lags=1);cutfields={k:v[:pos[9]+1] for k,v in small.items()}
   with threadpool_limits(limits=1):
    whole,_=predict(inputs({k:v[:10] for k,v in sf.items()},grid[:10],cal,small));cut,_=predict(inputs(cf,grid[:10],cal[:pos[9]+1],cutfields))
   np.testing.assert_allclose(whole,cut,equal_nan=True,rtol=1e-6,atol=1e-6);assert np.isfinite(cut).any();checks.append(dict(test='raw_filing_cutoff_price_prefix_and_entire_XGB_GMM_conformal_retrain',stocks=len(ids),signals=10,passed=True))
  q.OUT=oldout;q.pit_tables=loader
  with threadpool_limits(limits=1):v,trace=predict(inputs(fin,grid,cal,f))
  q.dump(OUT/'model_selection_trace.json',trace)
  run(OUT,SPECS,[v],cal,stocks,f,checks,dict(statistics='currentCS crossfit not independent study OOS',fidelity='available-input fullA adaptation; source audit/dividend/small10% gates absent',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED63',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
