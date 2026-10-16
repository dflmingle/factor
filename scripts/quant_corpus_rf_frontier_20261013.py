"""Causal source RF16 available-feature proxy, no invented main-money-flow."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2024年度精选策略2/72.随机森林 - 多因子模型.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source59-safe-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-rf16-schema-20261013'
FIELDS={'fina_indicator':['roe','roa'],'balancesheet':['money_cap','total_cur_liab','total_assets','total_hldr_eqy_exc_min_int'],'income':['total_revenue','total_cogs'],'cashflow':['n_cashflow_act']}
NAMES=['CASH_RATIO','GROSSPROFITABILITY','mom120','mom60','mom10','close','PCF','BP','SP','ROA','logtotalMV','VSTD20','ROE','std20','std40','std120']
SPECS=[spec('rf16_source_available','源码可用十六特征随机森林',SOURCE,
 'RF50trees(sqrtfeatures,seed47347) on9matured30bar blocks within source300dates[::30]; target SUM(dailyreturn), train top/bottom30%; winsor5MAD,sizeOLS,zscore16inputs; current probability, refit every60elapsedtradedays',
 'proxy:20sourcefeatures reduced16; omit unavailable main-money-flow and3ambiguous quarter-alias growth features explicitly; PIT industry neutralization omitted, total_mv replacescirc_mv; totalMV logsize neutralized on itself has identicallyzero residual, standardized constant explicitly set0 as causal repair rather than floating-point-noise signal; YTDgrossprofit/assets replaces vendor singlequarter accounting; fullA replacesHS300;10day saved evaluation replaces source15day trade interval; deterministic RF seed replaces unspecified random state')]

def features(fin,dates,cal,stocks,f):
 where=cal.get_indexer(dates);cap=f['cap'][where].astype(float);mv=cap*10000;c=f['close'].astype(float)
 def a(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 rv=a('income','total_revenue');eq=a('balancesheet','total_hldr_eqy_exc_min_int')
 values=[q.ratio(a('balancesheet','money_cap'),a('balancesheet','total_cur_liab')),
 q.ratio(rv-a('income','total_cogs'),a('balancesheet','total_assets')),
 *[(q.ratio(c,q.delay(c,n-2))-1)[where] for n in [120,60,10]],c[where],
 q.ratio(a('cashflow','n_cashflow_act_ttm'),mv),q.ratio(eq,mv),q.ratio(fin['income.total_revenue_ttm.q0'],mv),a('fina_indicator','roa'),
 np.where(cap>0,np.log(np.where(cap>0,cap,np.nan)),np.nan),q.rolling(f['volume'],20,'std')[where],a('fina_indicator','roe'),
 *[q.rolling(c,n,'std')[where] for n in [20,40,120]]]
 x=np.stack(values,axis=-1).astype(float)
 for i in range(len(dates)):
  active=cap[i]>0
  for k in range(len(NAMES)):
   v=x[i,:,k];good=active&np.isfinite(v)
   if good.sum()<100:x[i,:,k]=np.nan;continue
   y=v[good];median=np.median(y);mad=np.median(np.abs(y-median))*1.4826
   if mad>1e-12:y=np.clip(y,median-5*mad,median+5*mad)
   design=np.column_stack([np.ones(good.sum()),np.log(cap[i,good])]);res=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
   x[i,:,k]=np.nan
   if np.std(res)>1e-7:x[i,good,k]=(res-res.mean())/res.std(ddof=1)
   else:x[i,good,k]=0. # Explicit repaired constant feature contributes no split.
 return x

def predict(x,dates,cal,pos,f):
 index={cal.get_indexer([d])[0]:i for i,d in enumerate(dates)};out=np.full((len(pos),x.shape[1]),np.nan);training=[];model=None;bucket=-1
 r=q.ratio(f['close'],q.delay(f['close']))-1
 for i,t in enumerate(pos):
  # Current factor remains causal while the trained RF is held for60tradedays.
  b=(t-pos[0])//60
  if model is None or b!=bucket:
   times=np.arange(t-299,t+1,30);xs=[];ys=[];details=[]
   for start,end in zip(times[:-1],times[1:]):
    feat=x[index[start]];y=np.sum(r[start+1:end+1].astype(float),axis=0);good=np.isfinite(feat).all(axis=1)&np.isfinite(y)&(f['cap'][start]>0)
    if good.sum()<100:continue
    lo,hi=np.quantile(y[good],[.3,.7]);keep=good&((y<lo)|(y>hi));xs.append(feat[keep]);ys.append((y[keep]>hi).astype(int))
    details.append(dict(feature=str(cal[start].date()),label_known=str(cal[end].date()),samples=int(keep.sum())))
   if not xs:continue
   xx=np.concatenate(xs);yy=np.concatenate(ys)
   if len(np.unique(yy))<2:continue
   model=RandomForestClassifier(n_estimators=50,max_features='sqrt',n_jobs=1,random_state=47347);model.fit(xx,yy);bucket=b
   training.append(dict(signal=str(cal[t].date()),latest_training_end=str(cal[times[-1]].date()),samples=len(yy),blocks=details,features=NAMES))
  now=x[index[t]];good=np.isfinite(now).all(axis=1)&(f['cap'][t]>0)
  if good.any():out[i,good]=model.predict_proba(now[good])[:,1]
  if i%12==0:print('RF_SIGNAL',i+1,'/',len(pos),'valid',int(good.sum()),flush=True)
 return out,training

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,features=NAMES,seed=47347,rule=q.ALIGNMENT_RULE_VERSION,selection='source hyperparameters and feature omission frozen before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 dates=pd.DatetimeIndex(sorted(set([*grid,*[cal[t-299+30*k] for t in pos for k in range(10)]])))
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=[str(d) for d in dates],lags=1,rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();checks=[];ids=np.arange(512);small={k:v[:,ids] for k,v in f.items()};sf={k:v[:,ids] for k,v in fin.items()}
  sx=features(sf,dates,cal,stocks[ids],small);whole,_=predict(sx,dates,cal,pos,small)
  for n in [35,79]:
   cutoff=grid[n-1];use=dates<=cutoff;stop=pos[n-1]+1;sub={ep:tab[(tab.ann_date<=cutoff)&tab.instrument.isin(stocks[ids])] for ep,tab in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='RF-PIT-prefix-',dir=OUT) as tmp:
    q.OUT=Path(tmp);replay=q.financial_snapshot(dates[use],stocks[ids],lags=1);sf2={k:v[:stop] for k,v in small.items()}
    cutx=features(replay,dates[use],cal[:stop],stocks[ids],sf2);cut,_=predict(cutx,dates[use],cal[:stop],pos[:n],sf2)
    np.testing.assert_allclose(whole[:n],cut,equal_nan=True,rtol=1e-5,atol=1e-5);assert np.isfinite(cut).any()
    checks.append(dict(key=SPECS[0]['key'],test='raw_PIT_cutoff_price_truncation_feature_rebuild_and_RF_retrain',cutoff=str(cutoff),stocks=len(ids),passed=True))
  q.OUT=oldout;q.pit_tables=loader
  x=features(fin,dates,cal,stocks,f);v,training=predict(x,dates,cal,pos,f);q.dump(OUT/'training_date_audit.json',training)
  run(OUT,SPECS,[v],cal,stocks,f,checks,dict(statistics='causal walk-forward training; no independent study OOS',fidelity='16/20input explicit RF adaptation, not original strategy',missing='no imputation,16inputs required',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED59',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
