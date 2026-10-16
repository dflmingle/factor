"""Exhaustive per-stock causal SVC adaptation of source98, resumable chunks."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
from sklearn.svm import SVC
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
from quant_corpus_sweep_20261013 import tie_diagnostic
SOURCE='quant/2020年度精选策略/98 机器学习SVM用法示例策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source47-20261013'
SPECS=[
 spec('svm22_source_stale_binary','SVM22源码滞后五日分类',SOURCE,'per-stock SVC_RBF(C1,gamma1/7); X dates signal-229..signal-6; y=C(xdate+5)>C(xdate); predict hard class at signal-5',
      'proxy: preserves stale source x_all[-1], label already known at signal, hence NOT future forecast; old sklearn gamma=auto explicit; fullA stock adaptation of source single-stock600085'),
 spec('svm22_current_decision','SVM22当日因果决策值',SOURCE,'same trained model, decision_function on CURRENT 22bar features(C/MA22,V/MA22,H/MA22H,L/MA22L,V/lag21V,C/lag21C,STD22C)',
      'proxy: repaired current feature timing and continuous SVC margin; no feature standardization per source; all 5day training labels known through signal-1; fullA rather than single-stock timing'),
]
FEATURES=CLOSE=CAP=POSITIONS=None

def features(f):
 c,v,h,l=[f[k] for k in ['close','volume','high','low']]
 return np.stack([q.ratio(c,q.rolling(c,22)),q.ratio(v,q.rolling(v,22)),q.ratio(h,q.rolling(h,22)),q.ratio(l,q.rolling(l,22)),q.ratio(v,q.delay(v,21)),q.ratio(c,q.delay(c,21)),q.rolling(c,22,'std')*np.sqrt(21/22)],axis=-1)

def predict_symbol(j,ft,c,cap,positions):
 out=np.full((2,len(positions)),np.nan,np.float32);fits=0
 for i,t in enumerate(positions):
  if not cap[t,j]>0:continue
  train=np.arange(t-229,t-5);x=ft[train,j];future=c[train+5,j];past=c[train,j]
  valid=np.isfinite(x).all(axis=1)&np.isfinite(future)&(past>0)&(cap[train,j]>0)
  # Source training requires complete224rows. Partial histories are not imputed.
  if not valid.all():continue
  y=future>past
  if np.unique(y).size!=2:continue
  model=SVC(kernel='rbf',C=1,gamma='auto').fit(x,y);fits+=1
  if np.isfinite(ft[t-5,j]).all():out[0,i]=model.predict(ft[t-5,j].reshape(1,-1))[0]
  if np.isfinite(ft[t,j]).all():out[1,i]=model.decision_function(ft[t,j].reshape(1,-1))[0]
 return out,fits

def chunk(task):
 start,end=task;a=np.full((2,len(POSITIONS),end-start),np.nan,np.float32);fits=0
 for j in range(start,end):
  value,n=predict_symbol(j,FEATURES,CLOSE,CAP,POSITIONS);a[:,:,j-start]=value;fits+=n
 return start,end,a,fits

def main():
 global FEATURES,CLOSE,CAP,POSITIONS
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='fixed source98 before outcomes',platform_compute=0,gamma='auto=1/7',chunks=128)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];POSITIONS=cal.get_indexer(grid)
 FEATURES=features(f);CLOSE=f['close'];CAP=f['cap'];checks=[]
 # Independent data truncation, feature reconstruction, and actual SVC retraining.
 for stop in [POSITIONS[34]+1,POSITIONS[78]+1]:
  ids=np.flatnonzero(np.isfinite(FEATURES[stop-250:stop]).all(axis=(0,2)))[:4]
  p=POSITIONS[POSITIONS<stop];small={k:v[:stop,ids] for k,v in f.items()};ft=features(small)
  for k,j in enumerate(ids):
   a,_=predict_symbol(j,FEATURES,CLOSE,CAP,p)
   b,n=predict_symbol(k,ft,small['close'],small['cap'],p)
   np.testing.assert_allclose(a,b,equal_nan=True,rtol=1e-6,atol=1e-6);assert n>0
   checks.append(dict(test='truncated_prices_reconstruct_features_retrain_SVC',stop=stop,symbol=str(stocks[j]),fits=n,passed=True))
 q.dump(OUT/'verification.json',checks)
 tasks=[];chunks=OUT/'chunks';chunks.mkdir(exist_ok=True)
 for s in range(0,len(stocks),128):
  e=min(s+128,len(stocks));p=chunks/f'{s:04d}-{e:04d}.npz'
  if not p.exists():tasks.append((s,e))
 with ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('fork')) as pool:
  jobs=[pool.submit(chunk,t) for t in tasks]
  for done in as_completed(jobs):
   s,e,a,n=done.result();np.savez_compressed(chunks/f'{s:04d}-{e:04d}.npz',values=a,fits=n)
   print('chunk',s,e,'fits',n,flush=True)
 values=np.full((2,len(grid),len(stocks)),np.nan,np.float32);totalfits=0
 for s in range(0,len(stocks),128):
  e=min(s+128,len(stocks));a=np.load(chunks/f'{s:04d}-{e:04d}.npz');values[:,:,s:e]=a['values'];totalfits+=int(a['fits'])
 q.dump(OUT/'model_training_audit.json',dict(fits=totalfits,training_features='t-229..t-6',latest_training_target='t-1',source_prediction_feature='t-5',source_prediction_target_end='t already known',repaired_prediction_feature='t',future_labels_used=False))
 run(OUT,SPECS,list(values),cal,stocks,f,checks,dict(fidelity='source98 single-stock model adapted independently to fullA; gamma old-runtime proxy',statistics='exploratory causal rolling fit; not independent study OOS'))
 audit(OUT,cal,stocks,f);tie_diagnostic(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED47',flush=True)
if __name__=='__main__':main()
