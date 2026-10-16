"""Actual source52 rolling top/bottom30day RETURN classifier, not ROA prediction.
Vendor/Barra inputs explicitly proxied/omitted; fullA stock research only.
"""
import sys,json,ast
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-xgboost-runtime-20261013'))
from xgboost import XGBClassifier,__version__ as XGB_VERSION
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/52机器学习滚动训练价投策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source90-20261013'
PARAM=dict(learning_rate=.01,max_depth=10,min_child_weight=17,n_estimators=100,nthread=1,subsample=.2,random_state=0,eval_metric='logloss',use_label_encoder=False)
SPECS=[]
for mode in ['technical4','technical4_turnproxy']:
 SPECS.append(spec('rolling_xgb30x9_'+mode,mode+'九期三十日极端收益分类',SRC,
 'monthly XGB P(label1) trained on9 nonoverlap30day intervals ending by monthlypriorclose; top/bottom10% train; source .01/depth10/child17/100trees/subsample.2; '+mode,
 'proxy: original target is next30d RETURN extremes classification; ROA is final sorting only, not trainingtarget. Monthly premarket snapshots carried to grid. VDIFF=EMA12V-EMA26V, VEMA26, WVAD24, moneyflow20=sum20(V*(C+H+L)/3) explicit vendor proxies. technical4 OMITS unsupported Barra liquidity; turnproxy adds(.35logsum21turn+.35logmean63turn+.30logmean252turn) disclosed NEW native approximation. Unknown training returns excluded AFTER source active-universe rank slicing (source NaN labels unsafe); deterministic symbol-order tie proxy; FullA replaces source mainboard; no ST/minute/listing gates; no original20stock portfolio'))
 SPECS.append(spec('rolling_xgb30x9_'+mode+'_qualified_roa',mode+'概率前两成内高ROA',SRC,
 'PITROA high within top20pct of monthly classifierprobability; '+mode,
 'proxy: source second-stage ROA ranking inside predictedtop20 retained, exact floor(N/5) probability slice, deterministic symbol-order tie proxy; original highest20 stocks generalized to qualified decile; restricted factor_valid benchmark; source ST/minute/listing/mainboard gates omitted, native technical proxies disclosed'))
 SPECS[-1]['gated']=True

def features(f):
 v=f['volume'].astype(float);c=f['close'];h=f['high'];l=f['low'];o=f['open']
 def ema(x,n):return pd.DataFrame(x).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy()
 a=ema(v,12);b=ema(v,26);w=q.rolling(q.ratio(c-o,h-l)*v,24,'sum');mf=q.rolling(v*(c+h+l)/3,20,'sum')
 tr=f['turnover'].astype(float)
 liq=.35*np.log(q.rolling(tr,21,'sum'))+.35*np.log(q.rolling(tr,63))+.30*np.log(q.rolling(tr,252))
 return np.stack([a-b,b,w,mf,liq],axis=-1)

def extreme_indices(sorted_ids):
 n=len(sorted_ids)
 return np.r_[sorted_ids[:int(n/10*1)],sorted_ids[int(n/10*9):]]

def fit_predict(feat,c,cap,t,cols,debug=False):
 dates=np.arange(t-270,t+1,30);xx=[];yy=[];detail=[]
 for a,b in zip(dates[:-1],dates[1:]):
  active=cap[a]>0;x=feat[a,:,cols].T.copy();x[~active]=np.nan
  med=np.nanmedian(x,axis=0);x=np.where(np.isfinite(x),x,med)
  r=c[b]/c[a]-1;ids=np.flatnonzero(active&np.isfinite(r)&np.isfinite(x).all(axis=1));ids=ids[np.argsort(-r[ids],kind='stable')]
  # Source boundaries floor(N/10) and floor(N/10*9) differ from9*floor(N/10).
  allids=np.flatnonzero(active);allids=allids[np.argsort(np.where(np.isfinite(r[allids]),-r[allids],np.inf),kind="stable")]
  sel=extreme_indices(allids)
  sel=sel[np.isfinite(r[sel])&np.isfinite(x[sel]).all(axis=1)]
  if not len(sel):continue
  label=(r[sel]>np.mean(r[sel])).astype(int);xx.append(x[sel]);yy.append(label);detail.append(dict(feature=int(a),label_exit=int(b),samples=len(sel)))
 if not xx:return np.full(c.shape[1],np.nan),detail
 x=feat[t,:,cols].T.copy();active=cap[t]>0;x[~active]=np.nan;med=np.nanmedian(x,axis=0);x=np.where(np.isfinite(x),x,med);good=active&np.isfinite(x).all(axis=1)
 X=np.vstack(xx);Y=np.concatenate(yy);out=np.full(len(x),np.nan)
 if len(np.unique(Y))<2:return out,detail
 model=XGBClassifier(**PARAM);model.fit(X,Y);out[good]=model.predict_proba(x[good])[:,1]
 assert all(z['label_exit']<=t for z in detail)
 return out,detail

def monthly_scores(feat,f,cal,pos,roa,checkpoint=True):
 first={}
 for i,d in enumerate(cal):first.setdefault((d.year,d.month),i)
 trainpos=np.array([first[(cal[t].year,cal[t].month)]-1 for t in pos]);out=np.full((4,len(pos),feat.shape[1]),np.nan);stats=[]
 for t in np.unique(trainpos):
  use=trainpos==t;cache=OUT/f'month_{cal[t].strftime("%Y%m%d")}.npz'
  if checkpoint and cache.exists():vv=np.load(cache)['values']
  else:
   vv=[]
   for cols in [np.arange(4),np.arange(5)]:
    prob,detail=fit_predict(feat,f['close'],f['cap'],t,cols);good=np.isfinite(prob);gate=np.zeros_like(good);ids=np.flatnonzero(good);ids=ids[np.argsort(-prob[ids],kind="stable")];gate[ids[:int(len(ids)//5)]]=True
    rr=np.where(gate,roa[t],np.nan);vv.extend([prob,rr]);stats.append(dict(month=str(cal[t]),features=len(cols),train_periods=detail))
   vv=np.array(vv)
   if checkpoint:np.savez_compressed(cache,values=vv)
  out[:,use,:]=vv[:,None,:]
  print('XGB_MONTH',str(cal[t].date()),flush=True)
 return out,stats

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,params=PARAM,xgboost_version=XGB_VERSION,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='same four source89 hypotheses, semantic correction only; no tuning',supersedes='quant-corpus-semantic-source89-20261013',corrections='floor(.9*N), sorted active-universe slice before finite-label exclusion, floor(N/5) top probability gate with deterministic ties')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:512] for k,v in f.items()};featuresmall=features(sf);checks=[]
 for n in [101,107,512,5456]:
  ids=np.arange(n);frame=pd.DataFrame({'id':ids})
  expected=pd.concat([frame.iloc[:int(len(frame['id'])/10*1)],frame.iloc[int(len(frame['id'])/10*9):]])['id'].to_numpy()
  np.testing.assert_array_equal(extreme_indices(ids),expected)
  checks.append(dict(test='independent_literal_pandas_source_extreme_decile_slicing',universe=n,selected=expected.tolist(),passed=True))
 for stop in [1200,len(cal)-31]:
  cut=features({k:v[:stop] for k,v in sf.items()});np.testing.assert_allclose(featuresmall[:stop],cut,equal_nan=True,rtol=1e-8,atol=1e-8)
  t=stop-1
  for cols in [np.arange(4),np.arange(5)]:
   a,details=fit_predict(featuresmall,sf['close'],sf['cap'],t,cols);b,_=fit_predict(cut,sf['close'][:stop],sf['cap'][:stop],t,cols);np.testing.assert_array_equal(a,b)
   checks.append(dict(test='independent_full_vs_raw_cutoff_features_retrained_XGB_no_future30label',cutoff=str(cal[t]),features=len(cols),training=details,passed=True))
 tree=ast.parse(read_text(q.ROOT/SRC));classifier=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='XGBClassifier');actual={k.arg:ast.literal_eval(k.value) for k in classifier.keywords};assert all(PARAM[k]==v for k,v in actual.items());checks.append(dict(test='actual_source_AST_classifier_hyperparameters_not_summary_ROA_regressor',source_params=actual,passed=True))
 old=q.OUT
 try:q.OUT=OUT;roa=q.daily_pit_field('fina_indicator','roa',cal,stocks)
 finally:q.OUT=old
 # Per-field loader uses actual publication max(ann,f_ann), latest report-period event replay.
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC),'vendor_assumptions':SPECS[0]['fidelity'],'library_version':XGB_VERSION,'platform_compute':0})
 cache=OUT/'model_scores.pkl'
 if cache.exists():values=pd.read_pickle(cache)
 else:values,stats=monthly_scores(features(f),f,cal,pos,roa);pd.to_pickle(values,cache);q.dump(OUT/'training_period_manifest.json',stats)
 run(OUT,SPECS,list(values),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='actual rolling futureRETURN classifier with explicit supportednative field proxies and omissions',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED90',flush=True)
if __name__=='__main__':main()
