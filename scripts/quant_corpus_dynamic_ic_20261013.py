"""Source five matured 10-day IC blocks with PIT fundamental exposures."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata,spearmanr
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2022年度精选策略/81.有脑子，会调整权重的动态多因子模型.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source54-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-dynamic-ic-schema-20261013'
FIELDS={'fina_indicator':['roe','tr_yoy'],'income':['n_income_attr_p'],'balancesheet':['total_hldr_eqy_exc_min_int']}
SPECS=[spec('dynamic_ic5_source7','五期显著IC动态七因子',''+SOURCE,
 'mean5(IC_j if p<=.1 else0); >=3 nonzero (turnover>=4); normalized signed weights on current7 ranks; features logMV,PE,BM,ROE,turnover,tr_yoy,RET20; PEpositive current gate',
 'proxy: literal source most recent5 of6computed10day IC rows; training labels fully matured at signal; allA intercept replaces unavailable PIT industry dummies; original train/current ROE neutralization difference retained; PE/BM from PIT accounting, total_mv, parentNI_TTM, YTDroe; source current ST/pause/index filtering omitted')]
SPECS[0]['gated']=True

def residual(y,logcap):
 x=np.column_stack([np.ones(len(y)),logcap]);return y-x@np.linalg.lstsq(x,y,rcond=None)[0]

def exposures(t,fin,where,f,current=False):
 idx=where[t];mv=f['cap'][t].astype(float)*10000
 ni=fin['income.n_income_attr_p_ttm.q0'][idx].astype(float);eq=fin['balancesheet.total_hldr_eqy_exc_min_int.q0'][idx].astype(float)
 roe=fin['fina_indicator.roe.q0'][idx].astype(float);growth=fin['fina_indicator.tr_yoy.q0'][idx].astype(float)
 pe=q.ratio(mv,ni).astype(float);bm=q.ratio(eq,mv).astype(float);turn=f['turnover'][t].astype(float)
 mom=q.ratio(f['close'][t],f['close'][t-20]).astype(float)-1
 good=(mv>0)&np.isfinite(np.stack([pe,bm,roe,growth,turn,mom])).all(axis=0)
 if current:good&=pe>0
 else:pe=np.where(pe<0,200,pe)
 x=np.full((len(mv),7),np.nan)
 if good.sum()<100:return x
 lc=np.log(mv[good]);lc0=lc-lc.mean()
 x[good,0]=lc0
 for k,a in [(1,pe),(2,bm),(3,roe),(5,growth),(6,mom)]:
  x[good,k]=a[good]-a[good].mean() if k==3 and current else residual(a[good],lc)
 x[good,4]=turn[good]
 return x

def calculate(fin,dates,cal,pos,f):
 where={cal.get_indexer([d])[0]:i for i,d in enumerate(dates)};out=np.full((len(pos),f['close'].shape[1]),np.nan);weights=[]
 for i,t in enumerate(pos):
  ic=[]
  for k in range(5):
   end=t-10*k;start=end-10;x=exposures(start,fin,where,f)
   y=q.ratio(f['close'][end],f['close'][start])-1
   good=np.isfinite(x).all(axis=1)&np.isfinite(y);row=np.zeros(7)
   if good.sum()>=100:
    for j in range(7):
     rho,p=spearmanr(x[good,j],y[good]);row[j]=rho if np.isfinite(rho) and p<=.1 else 0.
   ic.append(row)
  a=np.asarray(ic);w=a.mean(axis=0);need=np.array([3,3,3,3,4,3,3]);w[np.sum(a!=0,axis=0)<need]=0
  z=exposures(t,fin,where,f,current=True);good=np.isfinite(z).all(axis=1);scale=np.abs(w).sum()
  if scale>1e-12 and good.sum()>=100:
   out[i,good]=np.column_stack([rankdata(z[good,j],method='average') for j in range(7)])@(w/scale)
  weights.append(dict(signal=str(cal[t].date()),training_latest_label=str(cal[t].date()),training_earliest_feature=str(cal[t-50].date()),nonzero_features=int((w!=0).sum()),weight=w.tolist(),valid_current_stocks=int(good.sum())))
 return out,weights

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True)
 plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source fixed before outcome evaluation',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 dates=pd.DatetimeIndex(sorted(set(cal[t-10*k] for t in pos for k in range(6))))
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=[str(d) for d in dates],lags=1,rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();checks=[]
  ids=np.arange(512);small={k:v[:,ids] for k,v in f.items()};sf={k:v[:,ids] for k,v in fin.items()}
  whole,_=calculate(sf,dates,cal,pos,small)
  for n in [35,79]:
   cutoff=grid[n-1];use=dates<=cutoff;sub={ep:tab[(tab.ann_date<=cutoff)&tab.instrument.isin(stocks[ids])] for ep,tab in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='PIT-prefix-',dir=OUT) as temp:
    q.OUT=Path(temp);replay=q.financial_snapshot(dates[use],stocks[ids],lags=1)
    stop=cal.get_indexer([cutoff])[0]+1
    cut,_=calculate(replay,dates[use],cal[:stop],pos[:n],{k:v[:stop] for k,v in small.items()})
    np.testing.assert_allclose(whole[:n],cut,equal_nan=True,rtol=1e-5,atol=1e-5);assert np.isfinite(cut).any()
    checks.append(dict(key=SPECS[0]['key'],test='raw_PIT_cutoff_and_price_truncation_retrain_all_IC_weights',cutoff=str(cutoff),stocks=len(ids),passed=True))
  q.OUT=oldout;q.pit_tables=loader
  x,w=calculate(fin,dates,cal,pos,f);q.dump(OUT/'training_weights.json',w)
  run(OUT,SPECS,[x],cal,stocks,f,checks,dict(fidelity='PIT seven-feature dynamic IC fullA proxy; industry omitted explicitly',statistics='causal weights; exploratory no independent study OOS',benchmark_warning='current positivePE qualification subset factor_valid benchmark',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED54',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
