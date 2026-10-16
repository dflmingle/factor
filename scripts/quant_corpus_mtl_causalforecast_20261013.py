"""NEW causal pooled risk forecast inspired by reviewed MTL auxiliary task.
Not the author LSTM; labels must mature21days before training.
"""
import json,hashlib,gc
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_multitask_features_20261013 import roll,z21
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略1/91.【复现】多任务时序动量策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source110-20261013'
COMMON='proxy NEW research: source15 causal21zfeatures used in pooledRidge(alpha1) auxiliaryriskforecast, NOT original4ETFhfq LSTM. Training dates every21days in trailing756 endingt-21, future21return volatility target strictly matured by t. Fixed no hypersearch, exclude missing rather than zero fill. Historicalprefix checked; no source validation leakage or stockaxisLSTM; signedvolprediction is research ranking only.'
SPECS=[
 spec('mtl_causal_ridge_vol21_low','因果预测未来波动率低值',SRC,'-predicted populationfuture21logreturnSTD from source15 causal21zfeatures; pooledRidge756/21',COMMON),
 spec('mtl_causal_ridge_vol21_decline','预测波动相对历史波动下降',SRC,'currentSTD21(logret)-predictedfutureSTD21(logret)',COMMON+' NEW change ranking; historicallevel controlled by subtracting fittedtarget, absolute units.'),
 spec('mtl_causal_ridge_vol21_logratio','预测未来波动率相对当前低比',SRC,'log(currentSTD21logret / predictedfutureSTD21logret), both>0',COMMON+' NEW normalizedrisk forecast diagnostic, negativepredictions excluded rather than clipped.')]

def features(f):
 c=f['close'].astype(float);r=np.log(c/q.delay(c));raw=[roll(r,n-1,'std')*np.sqrt(252) for n in [5,21,63,126,252]]
 vov=[roll(x,21,'std',ddof=0) for x in raw]
 ret=[np.log(c/q.delay(c,n)) for n in [1,5,21,126,252]]
 # Exact fifteen source predictors; all transformation windows backwardlooking.
 x=np.stack([z21(v) for v in ret+vov+raw],axis=2).astype(np.float32)
 current=roll(r,21,'std',ddof=0);return x,current

def predict(x,vol,cap,pos):
 panels=[np.full((len(pos),x.shape[1]),np.nan) for _ in SPECS];records=[]
 for i,t in enumerate(pos):
  train=np.arange(max(300,t-756),t-20,21);assert len(train) and train.max()+21<=t
  xx=x[train].reshape(-1,15).astype(float);yy=vol[train+21].reshape(-1);cc=cap[train].reshape(-1)
  good=np.isfinite(xx).all(axis=1)&np.isfinite(yy)&(yy>0)&(cc>0)
  use=np.isfinite(x[t]).all(axis=1)&(cap[t]>0)&np.isfinite(vol[t])&(vol[t]>0)
  if good.sum()<200 or use.sum()<100:continue
  model=Ridge(alpha=1.,fit_intercept=True,solver='cholesky').fit(xx[good],yy[good]);pred=model.predict(x[t,use].astype(float));current=vol[t,use]
  panels[0][i,use]=-pred;panels[1][i,use]=current-pred
  with np.errstate(invalid='ignore',divide='ignore'):panels[2][i,use]=np.where(pred>0,np.log(current/pred),np.nan)
  records.append(dict(signal=t,latest_training_feature=int(train.max()),latest_label_known=int(train.max()+21),examples=int(good.sum()),prediction_count=int(use.sum()),coef=model.coef_.tolist(),intercept=float(model.intercept_)))
 return panels,records

def main():
 OUT.mkdir(exist_ok=True);dep=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012/external_dependency_evidence_20261013'
 plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='3 fixed derivedforecasts, no outcome/horizon/model search',dependencies={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dep.glob('MTL_*.py')})
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:32] for k,v in f.items()};x,v=features(small);base,logs=predict(x,v,small['cap'],pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;xx,vv=features({k:a[:stop] for k,a in small.items()});cut,records=predict(xx,vv,small['cap'][:stop],pos[:n])
  for sp,a,b in zip(SPECS,base,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_rollingfeature_labelmaturity_refit_prefix',stop=stop,passed=True))
 # 32 stocks insufficient for predictioncontract, compare fit numerically on 200syntheticobservations.
 rng=np.random.default_rng(11091);xx=rng.normal(size=(200,15));yy=rng.normal(size=200);xm=xx.mean(axis=0);ym=yy.mean();xc=xx-xm
 coef=np.linalg.solve(xc.T@xc+np.eye(15),xc.T@(yy-ym));fit=Ridge(alpha=1.,solver='cholesky').fit(xx,yy)
 np.testing.assert_allclose(fit.coef_,coef,atol=1e-12);np.testing.assert_allclose(fit.intercept_,ym-xm@coef,atol=1e-12)
 checks.append(dict(test='independent_centered_normal_equations_ridge',passed=True))
 # Prefix forecast needs >=100symbols, independently repeat on first256 stocks for two grids.
 medium={k:a[:,:256] for k,a in f.items()};xx,vv=features(medium);bp,lr=predict(xx,vv,medium['cap'],pos[:3])
 assert lr and all(r['latest_label_known']<=r['signal'] for r in lr)
 stop=pos[2]+1;xc,vc=features({k:a[:stop] for k,a in medium.items()});cp,_=predict(xc,vc,medium['cap'][:stop],pos[:3])
 for a,b in zip(bp,cp):np.testing.assert_allclose(a,b,equal_nan=True,atol=1e-8)
 checks.append(dict(test='256stock_actual_fits_rawdaily_prefix_and_training21day_embargo',fittedsignals=len(lr),passed=True))
 del medium,xx,vv,xc,vc,x,v;gc.collect()
 x,v=features(f);vals,records=predict(x,v,f['cap'],pos);q.dump(OUT/'training_cutoffs.json',records);del x,v;gc.collect()
 q.dump(OUT/'source_evidence.json',{SRC:'\n'.join(l for l in read_text(q.ROOT/SRC).splitlines() if len(l)<700),'model_fidelity':'NEW pooled causal Ridge, not original LSTM model','original_model_audit':'author temporalaxis is stockaxis due batch_first input[date,stock,feature]; randomhiddenstates everycall; no21daylabelpurge; predict_data not expliciteval; source weights not certified'})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='NEWforecast inspiredbyriskauxiliary, no claim originalnetwork'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED110',flush=True)
if __name__=='__main__':main()
