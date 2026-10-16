"""Actual causal reconstruction of the corpus 12-horizon/25-week model."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import spec,audit
from quant_corpus_offline_batch_20261012 import run

SOURCE='quant/2020年度精选策略/15 基于多期限的选股策略（一）.txt'
SPECS=[
 spec('weekly_multihorizon_literal','多期限周模型源码标签',SOURCE,
      'OLS25 calendar weekly pairs of 12 MA_n/C features at date-7d*(i+1), y=open[p-3]/open[p-2]-1; current feature prediction',
      'proxy: literal source iloc[1,-1]/iloc[2,1] target preserved (reverse adjacent opens); fullA, sklearn deprecated predict shape repaired'),
 spec('weekly_multihorizon_forward_repair','多期限周模型因果周收益修复',SOURCE,
      'same source feature grid; y=C(target_date)/C(feature_date)-1; all target dates<=signal; OLS intercept, no regularization',
      'proxy: explicit corrected weekly-return hypothesis, different from original erroneous positional target; no future labels'),
]
HORIZONS=[3,5,10,20,30,60,90,120,180,240,270,300]

def predict(f,cal,grid):
 c=f['close'];o=f['open'];features=np.stack([q.ratio(q.rolling(c,n),c) for n in HORIZONS],axis=-1)
 vals=[np.full((len(grid),c.shape[1]),np.nan,np.float32) for _ in SPECS];datechecks=[]
 for i,date in enumerate(grid):
  p=cal.get_indexer([date])[0]
  targetdates=pd.DatetimeIndex([date-pd.Timedelta(days=7*k) for k in range(25)])
  featdates=targetdates-pd.Timedelta(days=7)
  yp=cal.searchsorted(targetdates,side='right')-1;xp=cal.searchsorted(featdates,side='right')-1
  if xp.min()<299 or yp.min()<4:continue
  # A week-long exchange holiday can map both calendar endpoints to the same
  # last trading day. Preserve source calendar stepping (zero forward return).
  assert (xp<=yp).all() and (yp<=p).all()
  x=features[xp];now=features[p]
  y=np.stack([q.ratio(o[yp-3],o[yp-2])-1,q.ratio(c[yp],c[xp])-1],axis=-1)
  valid=np.isfinite(x).all(axis=(0,2))&np.isfinite(y).all(axis=(0,2))&np.isfinite(now).all(axis=1)
  for j in np.flatnonzero(valid):
   # Centering matches sklearn LinearRegression(fit_intercept=True), including
   # the minimum-norm solution when the moving-average features are collinear.
   xx=x[:,j];yy=y[:,j];xm=xx.mean(axis=0);ym=yy.mean(axis=0)
   beta=np.linalg.lstsq(xx-xm,yy-ym,rcond=None)[0]
   pred=(now[j]-xm)@beta+ym
   for k in range(2):vals[k][i,j]=pred[k]
  datechecks.append(dict(signal=str(date),latest_training_target=str(cal[yp.max()]),latest_training_feature=str(cal[xp.max()]),valid_stocks=int(valid.sum()),targets_known=True,holiday_zero_intervals=int(np.sum(xp==yp))))
 return vals,datechecks

def main():
 out=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source37-20261013';out.mkdir(exist_ok=True)
 plan=dict(specs=SPECS,horizons=HORIZONS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0)
 path=out/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('plan mismatch')
 q.dump(path,plan)
 if (out/'audit_complete.json').exists():print('SKIP COMPLETE37');return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates']
 ids=np.flatnonzero(np.isfinite(f['close'][-650:]).all(axis=0))[:8]
 small={k:v[:,ids] for k,v in f.items()};full,_=predict(small,cal,grid);checks=[]
 for n in [35,79]:
  stop=cal.get_indexer([grid[n-1]])[0]+1
  cut,_=predict({k:v[:stop] for k,v in small.items()},cal[:stop],grid[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-6,atol=1e-6)
   checks.append(dict(key=sp['key'],test='truncate_prices_and_retrain_entire_model',stop=stop,passed=True))
 vals,training=predict(f,cal,grid);q.dump(out/'training_date_audit.json',training)
 run(out,SPECS,vals,cal,stocks,f,checks,dict(fidelity='local causal model source proxy; not platform validated',
   training='source25 calendar weeks, 12 MA/C inputs, intercept OLS',statistics='exploratory, no independent OOS',
   missing='require complete training samples and live input; no imputation',source_label_warning='first recipe preserves erroneous reverse open-to-open source target'))
 audit(out,cal,stocks,f);q.dump(out/'audit_complete.json',dict(completed=True,platform_compute=0))
 print('AUDIT FINISHED37',flush=True)

if __name__=='__main__':main()
