"""Causal local proxy replication of Liang, Zohren & Cucuringu (2026).

The paper uses U.S. daily residual signals, custom Sharpe-optimised XGB/FFN
allocation functions, and feature-level attribution propagation. Here we keep
the attribution-guided intervention and temporal/cross-model regularisation,
but use the existing Chinese full-A factor panel, 10-trading-day signal grid,
LightGBM (TreeSHAP-style pred_contrib) and a small PyTorch FFN. This is a
research proxy, never a platform submission.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import hashlib, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
import torch
from torch import nn
from scipy.stats import rankdata

import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import simultaneous_residual

ROOT=q.ROOT
OUT=ROOT/'research_reports/literature/economic-explanation-ml-portfolios-20261016'
PANEL=ROOT/'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/signal_panels.pkl'
PAPER='From Economic Explanation to Performance Improvement in Machine-Learning Portfolios (Liang, Zohren & Cucuringu, arXiv:2610.15144, 2026)'
FEATURES=['small_size','reversal20','momentum120','low_vol20','low_turn20','volume_low_std20','amount_low_std20','pv_corr20','cgo100_low','capm_residual_vol120_low','book_market','roe','roic','asset_turnover','growth_sales','cash_accrual_quality','ebit_ev','fear_std20_low']
N_TRAIN=24                 # 2 years on the 10-day grid; paper's 4 years is unavailable pre-2018
N_VALID=12                 # 1 year validation
BLOCK=12                   # annual OOS blocks
ETA=.5
LAM_MIN,LAM_MAX=0.,3.
PAPER_COST=.0005           # 5bp per unit L1 turnover, paper convention
LOCAL_COST=.003            # separate project sensitivity
TOP_CAP=1500               # large/liquid proxy, analogous to paper's 346 U.S. stocks
SEED=20261016

def dump(path,obj):
 def c(x):
  if isinstance(x,dict):return {str(k):c(v) for k,v in x.items()}
  if isinstance(x,(list,tuple)):return [c(v) for v in x]
  if isinstance(x,(np.integer,)):return int(x)
  if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
  if isinstance(x,(pd.Timestamp,)):return str(x)
  return x
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(c(obj),ensure_ascii=False,indent=2)+'\n')

def cross_zscore(x):
 out=np.full_like(x,np.nan,dtype=np.float32)
 for i,row in enumerate(x):
  ok=np.isfinite(row)
  if ok.sum()<100:continue
  m=np.nanmean(row);s=np.nanstd(row)
  if s>1e-12:out[i,ok]=(row[ok]-m)/s
 return out

def build_features():
 """Build an extended 10-day grid and verify the formal overlap bytewise."""
 cached=OUT/'extended_features.pkl'
 if cached.exists():return pd.read_pickle(cached)
 cal,stocks,fields=q.load_market();q.dates_all=cal
 formal=pd.read_pickle(PANEL);fd=pd.DatetimeIndex(formal['dates']);fp=cal.get_indexer(fd)
 # 36 pre-formal periods permit 24 train + 12 validation. The grid remains
 # anchored to saved platform dates and uses full daily warm-up internally.
 first=max(0,int(fp[0])-360);positions=np.arange(first,int(fp[-1])+1,10,dtype=int)
 dates=cal[positions]
 oldout=q.OUT
 try:
  q.OUT=OUT/'feature_cache';q.OUT.mkdir(parents=True,exist_ok=True)
  fin=q.financial_snapshot(dates,stocks,lags=6)
  vals={}
  for meta,x in q.recipes(fields,positions):
   if meta['key'] in FEATURES:vals[meta['key']]=x
  for meta,x in q.additional_market_recipes(fields,positions):
   if meta['key'] in FEATURES:vals[meta['key']]=x
  for meta,x in q.financial_recipes(fin,fields,positions):
   if meta['key'] in FEATURES:vals[meta['key']]=x
 finally:q.OUT=oldout
 missing=[k for k in FEATURES if k not in vals]
 if missing:raise RuntimeError(f'missing features: {missing}')
 # Explicit source reproduction check on the 120 formal signal dates.
 ix=np.arange(len(positions))[dates.isin(fd)]
 for k in FEATURES:
  ref=formal['panels'][k].reindex(columns=stocks).to_numpy(dtype=np.float32)
  got=vals[k][ix]
  np.testing.assert_allclose(got,ref,equal_nan=True,rtol=2e-5,atol=2e-5,err_msg=k)
 pd.to_pickle({'dates':dates,'positions':positions,'stocks':stocks,'fields':fields,'values':vals,
               'formal_overlap_checked':True,'features':FEATURES},cached)
 print('FEATURES_READY',len(dates),len(stocks),len(vals),flush=True)
 return pd.read_pickle(cached)

def target_matrix(bundle):
 cal,stocks,fields=bundle['dates'],bundle['stocks'],bundle['fields']
 # positions are positions in original market calendar, not bundle date ordinals.
 pos=bundle['positions'];close=fields['close'];y=np.full((len(pos),len(stocks)),np.nan,np.float32)
 for i,p in enumerate(pos):
  if p+11<len(close):y[i]=q.ratio(close[p+11],close[p+1])-1
 return y

def rows_for(idx,X,y,cap,training=True):
 xs=[];ys=[];ds=[]
 for i in idx:
  ok=np.isfinite(X[i]).all(axis=1)&np.isfinite(y[i])&(cap[i]>0)
  ids=np.flatnonzero(ok)
  if len(ids)>TOP_CAP:
   ids=ids[np.argsort(-cap[i,ids],kind='stable')[:TOP_CAP]]
  if len(ids)<200:continue
  xs.append(X[i,ids]);ys.append(y[i,ids]);ds.extend([(i,int(j)) for j in ids])
 if not xs:return np.empty((0,X.shape[2])),np.empty(0),[]
 return np.vstack(xs).astype(np.float32),np.concatenate(ys).astype(np.float32),ds

class FFN(nn.Module):
 def __init__(self,p):
  super().__init__();self.net=nn.Sequential(nn.Linear(p,32),nn.ReLU(),nn.Linear(32,16),nn.ReLU(),nn.Linear(16,1))
 def forward(self,x):return self.net(x).squeeze(-1)

def train_models(X,y,cap,train_idx):
 xtr,ytr,_=rows_for(train_idx,X,y,cap)
 if len(ytr)<10000:raise RuntimeError(f'too few train rows {len(ytr)}')
 lgbm=lgb.LGBMRegressor(objective='regression',n_estimators=120,num_leaves=15,max_depth=4,
     learning_rate=.03,min_child_samples=150,subsample=.85,colsample_bytree=.85,
     reg_lambda=2.,random_state=SEED,verbosity=-1,n_jobs=4)
 lgbm.fit(xtr,ytr)
 torch.manual_seed(SEED);model=FFN(X.shape[2]);opt=torch.optim.Adam(model.parameters(),lr=.002,weight_decay=1e-4)
 tx=torch.from_numpy(xtr);ty=torch.from_numpy(ytr)
 model.train()
 batch=8192
 for epoch in range(18):
  order=torch.randperm(len(ty))
  for st in range(0,len(ty),batch):
   ids=order[st:st+batch];pred=model(tx[ids]);loss=((pred-ty[ids])**2).mean()
   opt.zero_grad();loss.backward();opt.step()
 return lgbm,model

def model_pred_attr(model,x,kind):
 if kind=='lgb':
  z=model.predict(x,pred_contrib=True);return z[:,:-1].astype(np.float32),z[:,-1].astype(np.float32)
 model.eval();tx=torch.tensor(x,dtype=torch.float32,requires_grad=True)
 out=model(tx);g=torch.autograd.grad(out.sum(),tx)[0].detach().numpy();pred=out.detach().numpy();return (g*x).astype(np.float32),pred.astype(np.float32)

def weights_from_pred(pred,mask):
 u=pred.copy();u[~mask]=np.nan
 m=np.nanmean(u);u=u-m;u[~mask]=0.;den=np.sum(np.abs(u))
 return u/den if den>1e-12 else np.zeros_like(u)

def weight_derivative(pred,attr,mask):
 u=pred.copy();u[~mask]=np.nan;m=np.nanmean(u);u=u-m;u[~mask]=0.;L=np.sum(np.abs(u))
 if L<=1e-12:return np.zeros_like(attr)
 a=attr.copy();a[~mask]=0.;a=a-np.nanmean(a[mask]);
 s=np.sign(u);dL=np.sum(s*a);return (a*L-u*dL)/(L*L)

def block_eval(model,kind,X,y,cap,pos,idx,lambdas=None,cost=PAPER_COST,prev_w=None,prev_dw=None,need_attr=False):
 rows=[];daily=[];attrs=[];prev=np.zeros(X.shape[1],np.float32) if prev_w is None else prev_w.copy();prev_der=np.zeros((X.shape[1],X.shape[2]),np.float32) if prev_dw is None else prev_dw.copy();nav=1.
 for i in idx:
  mask=np.isfinite(X[i]).all(axis=1)&np.isfinite(y[i])&(cap[i]>0);ids=np.flatnonzero(mask)
  if len(ids)>TOP_CAP:
   ids=ids[np.argsort(-cap[i,ids],kind='stable')[:TOP_CAP]]
   mask=np.zeros_like(mask);mask[ids]=True
  if mask.sum()<200:continue
  xx=X[i].copy();
  if lambdas is not None:xx=xx*lambdas[None,:]
  pred_all=model_pred_attr(model,xx[ids],kind);attr=np.zeros((X.shape[1],X.shape[2]),np.float32);pred=np.zeros(X.shape[1],np.float32);attr[ids]=pred_all[0];pred[ids]=pred_all[1]
  w=weights_from_pred(pred,mask);turn=np.sum(np.abs(w-prev));
  # Invalid names carry NaN labels. Their weights are zero, but NumPy still
  # propagates 0*NaN through a full-vector dot product, so restrict every
  # return/attribution calculation to the valid cross-section explicitly.
  gross=float(np.dot(w[mask],y[i,mask]));net=gross-cost*turn
  dw=np.zeros((X.shape[1],X.shape[2]),np.float32)
  for j in range(X.shape[2]):dw[:,j]=weight_derivative(pred,attr[:,j],mask)
  dturn=np.zeros(X.shape[2]);
  for j in range(X.shape[2]):dturn[j]=np.sum(np.sign(w-prev)*(dw[:,j]-prev_der[:,j]))
  dret=np.array([np.dot(dw[mask,j],y[i,mask])-cost*dturn[j] for j in range(X.shape[2])])
  rows.append(dict(index=int(i),date=str(pos[i]),gross=gross,net=net,turnover=turn));attrs.append((dret,w,dw))
  p=pos[i]
  for step in range(1,11):
   if p+1+step>=len(cap):break
   rr=q.ratio(bundle_fields['close'][p+1+step,ids],bundle_fields['close'][p+step,ids])-1
   rok=np.isfinite(rr)
   dgross=float(np.dot(w[ids][rok],rr[rok])) if rok.any() else np.nan
   daily.append(dict(index=int(i),step=step,date=str(all_calendar[p+1+step]),gross=dgross,net=float(dgross-(cost*turn if step==1 else 0)) if np.isfinite(dgross) else np.nan))
  prev=w;prev_der=dw;nav*=1+net
 return pd.DataFrame(rows),pd.DataFrame(daily),attrs,prev,prev_der

def sharpe_attr(rows,attrs):
 r=rows.net.to_numpy(float);mu=r.mean();sig=r.std(ddof=0);out=np.full(len(FEATURES),np.nan)
 if sig<=1e-12:return out
 phi=np.array([a[0] for a in attrs]);m=phi.mean(axis=0)
 for j in range(len(FEATURES)):
  ps=np.mean((r-mu)*(phi[:,j]-m[j]))/sig
  out[j]=math.sqrt(25.2)*(m[j]*sig-mu*ps)/(sig*sig)
 return out

def metrics(rows,daily):
 r=rows.net.to_numpy(float);g=rows.gross.to_numpy(float);t=rows.turnover.to_numpy(float)
 sr=math.sqrt(25.2)*r.mean()/r.std(ddof=1) if len(r)>1 and r.std(ddof=1)>0 else np.nan
 srg=math.sqrt(25.2)*g.mean()/g.std(ddof=1) if len(g)>1 and g.std(ddof=1)>0 else np.nan
 nav=np.cumprod(1+r);dd=float(-np.min(nav/np.maximum.accumulate(nav)-1)) if len(nav) else np.nan
 return dict(periods=len(rows),sharpe_net=sr,sharpe_gross=srg,mean_net_annual_pct=r.mean()*25.2*100,mean_gross_annual_pct=g.mean()*25.2*100,turnover_period_pct=t.mean()*100,drawdown_pct=dd)

def main():
 global bundle_fields,all_calendar
 OUT.mkdir(parents=True,exist_ok=True);bundle=build_features();bundle_fields=bundle['fields'];all_calendar=pd.DatetimeIndex(bundle_fields['close'].shape[0] and q.load_market()[0]);
 # q.load_market calendar is immutable and corresponds to fields axis.
 dates=pd.DatetimeIndex(bundle['dates']);pos=bundle['positions'];stocks=bundle['stocks'];cap=bundle_fields['cap'][pos]
 vals=bundle['values'];X=np.stack([cross_zscore(vals[k]) for k in FEATURES],axis=2);y=target_matrix(bundle)
 np.savez_compressed(OUT/'ml_feature_tensor.npz',X=X,y=y,cap=cap)
 plan=dict(paper=PAPER,features=FEATURES,grid_start=str(dates[0]),grid_end=str(dates[-1]),periods=len(dates),
   train_periods=N_TRAIN,validation_periods=N_VALID,oos_block_periods=BLOCK,eta=ETA,lambda_bounds=[LAM_MIN,LAM_MAX],
   paper_cost=PAPER_COST,local_cost=LOCAL_COST,top_cap=TOP_CAP,universe='daily full-A source panel, top-total_mv 1500 per date for ML proxy',
   model_proxy={'xgb':'LightGBM regression with pred_contrib, not custom Sharpe objective','ffn':'PyTorch 2xReLU regression, gradient-times-input attribution'},
   adaptation='10-trading-day labels/holding periods; 24 train + 12 validation due local 2018 data; annual blocks',
   no_platform_calls=True,parameter_selection='frozen from paper; no outcome grid search',alignment='feature overlap exact on saved 120 formal dates')
 dump(OUT/'frozen_plan.json',plan)
 allout=[];attrlog=[];blocklog=[]
 # OOS starts after 24 train + 12 validation, then annual 12-period blocks.
 for test_start in range(N_TRAIN+N_VALID,len(dates)-BLOCK+1,BLOCK):
  train_idx=np.arange(test_start-N_VALID-N_TRAIN,test_start-N_VALID);val_idx=np.arange(test_start-N_VALID,test_start);test_idx=np.arange(test_start,test_start+BLOCK)
  print('BLOCK',test_start,dates[test_start],flush=True)
  lgbm,ffn=train_models(X,y,cap,train_idx)
  val_results={};val_attrs={};
  for kind,model in [('lgb',lgbm),('ffn',ffn)]:
   vr,vd,va,_,_=block_eval(model,kind,X,y,cap,pos,val_idx,lambdas=None,cost=PAPER_COST,need_attr=True)
   phi=sharpe_attr(vr,va);val_results[kind]=vr;val_attrs[kind]=phi
   attrlog.append(dict(test_start=str(dates[test_start]),model=kind,**{FEATURES[j]:float(phi[j]) for j in range(len(FEATURES))}))
  # Cross-model averaging uses every available model attribution.  In a
  # validation block where one model has zero return dispersion its Sharpe
  # attribution is undefined; dropping that model is preferable to turning
  # the whole cross-model signal into NaN.
  with np.errstate(invalid='ignore'):
   phi_cm=np.nanmean(np.vstack([val_attrs['lgb'],val_attrs['ffn']]),axis=0)
  lambdas={}
  for kind,phi in [('lgb',val_attrs['lgb']),('ffn',val_attrs['ffn']),('cm',phi_cm)]:
   sd=np.nanstd(phi)
   if not np.isfinite(sd) or sd<1e-12:
    step=np.ones(len(FEATURES))
   else:
    z=np.where(np.isfinite(phi),phi/sd,0.)
    step=1+ETA*np.tanh(z)
   lambdas[kind]={'unstabilised':np.clip(step,LAM_MIN,LAM_MAX),'stabilised':None}
  # Carry state across OOS blocks, separately for model-specific and CM rules.
  if not blocklog:state={k:np.ones(len(FEATURES)) for k in ['lgb','ffn','cm']}
  for kind,model in [('lgb',lgbm),('ffn',ffn)]:
   for rule in ['baseline','unstabilised','stabilised']:
    lam=None if rule=='baseline' else (lambdas[kind]['unstabilised'] if rule=='unstabilised' else state[kind]*lambdas[kind]['unstabilised'])
    tr,td,ta,_,_=block_eval(model,kind,X,y,cap,pos,test_idx,lambdas=lam,cost=PAPER_COST,need_attr=False)
    if rule=='stabilised':state[kind]=np.clip(lam,LAM_MIN,LAM_MAX)
    if rule=='baseline':state[kind]=state[kind]
    allout.append((kind,rule,test_start,tr,td))
  for rule in ['unstabilised','stabilised']:
   lam=lambdas['cm']['unstabilised'] if rule=='unstabilised' else state['cm']*lambdas['cm']['unstabilised']
   # The same cross-model exposure rule is evaluated on both allocation
   # models, matching the paper's cross-model intervention tables.
   for kind,model in [('lgb_cm',lgbm),('ffn_cm',ffn)]:
    base_kind='lgb' if kind=='lgb_cm' else 'ffn'
    tr,td,ta,_,_=block_eval(model,base_kind,X,y,cap,pos,test_idx,lambdas=lam,cost=PAPER_COST,need_attr=False)
    allout.append((kind,rule,test_start,tr,td))
   if rule=='stabilised':state['cm']=np.clip(lam,LAM_MIN,LAM_MAX)
  blocklog.append(dict(test_start=str(dates[test_start]),test_end=str(dates[test_idx[-1]]),train_start=str(dates[train_idx[0]]),train_end=str(dates[train_idx[-1]]),validation_start=str(dates[val_idx[0]]),validation_end=str(dates[val_idx[-1]]),**{f'lambda_{k}_{j}':float(v) for k in ['lgb','ffn','cm'] for j,v in enumerate(lambdas[k]['unstabilised'])}))
 # aggregate and save each model/rule; also run local cost sensitivity on the
 # saved period gross/turnover paths without retraining or refitting lambdas.
 rows=[];period_sets={}
 for model,rule,st,pr,dr in allout:
  folder=OUT/'results';folder.mkdir(exist_ok=True)
  pr=pr.copy();pr['model']=model;pr['rule']=rule;pr['block']=st;dr=dr.copy();dr['model']=model;dr['rule']=rule;dr['block']=st
  pr.to_csv(folder/f'{model}.{rule}.{st}.periods.csv',index=False);dr.to_csv(folder/f'{model}.{rule}.{st}.daily.csv',index=False)
  period_sets.setdefault((model,rule),[]).append(pr)
 # Report pooled OOS statistics as the primary result.  Averaging annual
 # block Sharpes can overweight short/high-volatility blocks, so retain that
 # quantity separately for diagnostics rather than presenting it as the
 # overall portfolio Sharpe.
 for (model,rule),plist in period_sets.items():
  pooled=pd.concat(plist,ignore_index=True)
  pm=metrics(pooled,pd.DataFrame())
  block_sr=[metrics(x,pd.DataFrame())['sharpe_net'] for x in plist]
  pm.update(model=model,rule=rule,block_sharpe_net_mean=float(np.nanmean(block_sr)),
            local_cost_sensitivity_net_annual_pct=float((pooled.gross-pooled.turnover*LOCAL_COST).mean()*25.2*100))
  rows.append(pm)
 result=pd.DataFrame(rows).sort_values(['model','rule']).reset_index(drop=True)
 result.to_csv(OUT/'results.csv',index=False);pd.DataFrame(attrlog).to_csv(OUT/'validation_net_sharpe_attributions.csv',index=False);pd.DataFrame(blocklog).to_csv(OUT/'block_log.csv',index=False)
 dump(OUT/'verification.json',dict(completed=True,formal_overlap_checked=True,feature_prefix_recompute='source panel overlap exact within tolerance',lookahead='train/validation/test periods disjoint; attribution lagged one block; lambda only before test block',platform_compute_spent=0,shap='LightGBM pred_contrib used as tree attribution proxy; FFN gradient-times-input; no sampled Shapley benchmark',
   daily_path='period return metrics are 10-day rebalance proxy; daily held path saved for each block',failed_claims=['not paper byte-replication','not custom Sharpe objective','not U.S. Fama-French residual universe']))
 print(result.to_string(index=False),flush=True)

if __name__=='__main__':main()
