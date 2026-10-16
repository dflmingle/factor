"""Source low-idiosyncratic-risk mechanism with fixed start-date factor portfolios."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source10-20261012'
SOURCE='quant/2022年度精选策略/98.复现东方证券研报--特质波动率因子研究.txt'
SPECS=[{'key':f'fixed_{model.lower()}_ivol504','name':f'固定期初组合{model}低特质波动504',
 'source_paths':[SOURCE],'formula':f'-STD(OLS residuals(return ~ {model},504),ddof=0)*sqrt252; start-date total_mv factor portfolios',
 'fidelity':'source economic mechanism adaptation; intended24months mapped to504daily observations; source count24/month bug not copied',
 'gated':False} for model in ['CAPM','FF3','FF5']]

def one(f,eq,roe,assets,t,window=504,return_details=False):
 start=t-window
 if start<0:return [np.full(f['close'].shape[1],np.nan) for _ in SPECS]
 cap=f['cap'][start].astype(float)
 y=q.ratio(f['close'][start+1:t+1],f['close'][start:t])-1
 good=(cap>0)&np.isfinite(y).all(axis=0)&np.isfinite(eq[start])&np.isfinite(roe[start])&(assets[start]>0)
 # Prior-year assets observable by the window's formation date; no future statements.
 previous=max(start-252,0);growth=q.ratio(assets[start],assets[previous])
 good&=np.isfinite(growth)&(growth>0)
 ids=np.flatnonzero(good);out=[np.full(len(cap),np.nan,np.float32) for _ in SPECS]
 if len(ids)<100:return out
 weights=cap[ids];returns=y[:,ids].astype(float);n=len(ids)//3
 def spread(score):
  order=np.argsort(score,kind='stable');low=order[:n];high=order[-n:]
  lo=returns[:,low]@(weights[low]/weights[low].sum())
  hi=returns[:,high]@(weights[high]/weights[high].sum())
  return hi-lo
 market=returns@(weights/weights.sum());smb=-spread(weights)
 hml=spread(eq[start,ids]/(weights*10000));rmw=spread(roe[start,ids]);cma=-spread(np.log(growth[ids]))
 factors=np.column_stack([market,smb,hml,rmw,cma])
 for i,k in enumerate([1,3,5]):
  x=np.column_stack([np.ones(len(returns)),factors[:,:k]])
  coef=np.linalg.lstsq(x,returns,rcond=None)[0];res=returns-x@coef
  out[i][ids]=-np.std(res,axis=0,ddof=0)*np.sqrt(252)
 if return_details:return out,ids,factors,returns
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks)
 assets=q.daily_pit_field('balancesheet','total_assets',calendar,stocks)
 saved=OUT/'raw_arrays.pkl'
 if saved.exists():vals=pd.read_pickle(saved)
 else:
  vals=[np.full((len(pos),len(stocks)),np.nan,np.float32) for _ in SPECS]
  for i,t in enumerate(pos):
   results=one(f,eq,roe,assets,t)
   for k in range(3):vals[k][i]=results[k]
   if i%20==0:print('source10 build',i,len(pos),flush=True)
  pd.to_pickle(vals,saved)
 checks=[]
 for i in [31,77,len(pos)-1]:
  t=pos[i];stop=t+1
  full,ids,factors,returns=one(f,eq,roe,assets,t,return_details=True)
  cut=one({k:v[:stop] for k,v in f.items()},eq[:stop],roe[:stop],assets[:stop],t)
  for k in range(3):
   np.testing.assert_allclose(full[k],cut[k],equal_nan=True,atol=1e-6)
   np.testing.assert_allclose(full[k],vals[k][i],equal_nan=True,atol=1e-6)
  # Independent single-stock statsmodels regression for each factor count.
  import statsmodels.api as sm
  for k,num in enumerate([1,3,5]):
   fit=sm.OLS(returns[:,0],sm.add_constant(factors[:,:num])).fit()
   np.testing.assert_allclose(full[k][ids[0]],-fit.resid.std()*np.sqrt(252),rtol=1e-5)
  checks.append({'test':'prefix_recompute_and_independent_OLS','signal':str(grid[i]),'passed':True})
 run(OUT,SPECS,vals,calendar,stocks,f,checks,{'scope':'intended long-horizon source mechanism, not buggy source runtime',
  'proxy':'total_mv replaces circulating cap, book equity excludes minority; source equity definition differs;504days proxy for24months',
  'factor_formation':'fixed formation date t-504; thirds total_mv/BM/ROE/annual asset growth; cap-weighted portfolios',
  'universe':'common complete-window positive-cap, available accounting data; no ST filter; not source stocks',
  'missing_returns':'excluded, never set prelisting returns to0; rf constant absorbed by intercept',
  'source_bug':'get_tradeday_list(frequency=month,count=24) fetches24 DAILY observations before grouping months; cannot label literal source24months'})
if __name__=='__main__':main()
