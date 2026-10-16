"""Independent checks of source state length and qualified peer correlations."""
import ast,hashlib
import numpy as np
import pandas as pd
from numba import set_num_threads
import quant_corpus_local_20261012 as q
import quant_corpus_divergence_corrected_20261013 as d
import quant_corpus_weightedcorr_frontier_20261013 as w
OUT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012/semantic_supplement_20261013'

def main():
 OUT.mkdir(exist_ok=True);set_num_threads(4);cal,stocks,f=q.load_market();checks=[]
 source=q.ROOT/d.SOURCE;tree=ast.parse(source.read_text());names={'ema','macdx','barslast','core_ssdd'}
 defs=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
 assert len(defs)==4
 # Execute only four reviewed pure math definitions, never module statements,
 # imports, initialize(), source portfolio code or trading API calls.
 ns={'np':np,'print':lambda *a,**k:None};exec(compile(ast.Module(body=defs,type_ignores=[]),str(source),'exec'),ns)
 ids=np.flatnonzero(np.isfinite(f['close']).all(axis=0))[:6];c=f['close'][:,ids].astype(float);actual=d.state(c);count=0;events=0
 for j in range(len(ids)):
  flags=[[False]*199 for _ in range(4)]
  for t in range(199,len(cal)):
   y=c[t-199:t+1,j];dif,_,hist=ns['macdx'](y)
   deads=ns['barslast']([hist[k]<0 and hist[k-1]>=0 for k in range(1,200)])
   golds=ns['barslast']([hist[k]>0 and hist[k-1]<=0 for k in range(1,200)])
   if len(deads)<3 or len(golds)<3:
    flags=[z[1:]+[False] for z in flags];ref=np.nan
   else:
    flags=ns['core_ssdd'](deads,golds,y,*flags)
    ref=2*flags[3][-1]+flags[2][-1]-2*flags[1][-1]-flags[0][-1]
   assert all(len(z)==199 for z in flags)
   assert actual[t,j]==ref or (np.isnan(actual[t,j]) and np.isnan(ref)),(t,j,actual[t,j],ref)
   count+=1;events+=int(np.isfinite(ref) and ref!=0)
 checks.append(dict(test='independent_original_four_pure_functions_199list_state',passed=True,observations=count,nonzero=events,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_full_module_executed=False))
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:512].astype(float)
 tr=w.trendrank(small,pos);a,b=w.peer(small,pos,tr)
 assert np.isfinite(b).sum()>0
 for stop in [1200,len(cal)-31]:
  use=pos<stop;ta,tb=w.peer(small[:stop],pos[use],w.trendrank(small[:stop],pos[use]))
  np.testing.assert_allclose(a[use],ta,equal_nan=True,atol=1e-8);np.testing.assert_allclose(b[use],tb,equal_nan=True,atol=1e-8)
  checks.append(dict(test='nonvacuous_qualified_peercorr_prefix_recompute',passed=True,stop=stop,finite_qualified=int(np.isfinite(tb).sum())))
 for i in range(0,len(pos),31):
  t=pos[i];qualified=np.flatnonzero(np.isfinite(b[i]));hist=pd.DataFrame(small[t-244:t+1,qualified]);ref=np.log(hist).diff().iloc[1:].corr().abs();np.fill_diagonal(ref.values,np.nan)
  np.testing.assert_allclose(b[i,qualified],-ref.mean().to_numpy(),equal_nan=True,atol=1e-8)
 checks.append(dict(test='independent_qualified_pandas_paircorr',passed=True,finite_qualified=int(np.isfinite(b).sum())))
 q.dump(OUT/'verification.json',checks);print('SUPPLEMENT_PASSED',checks,flush=True)
if __name__=='__main__':main()
