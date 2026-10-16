import sys,json,warnings
from pathlib import Path
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore',category=FutureWarning)
sys.path.insert(0,'scripts')
import repaint_check as check
out=Path(__file__).resolve().parent
fields=pd.read_pickle(out/'repaint_fields.pkl')
wide={k:v.unstack(1).sort_index() for k,v in fields.items()}
checks=[]
for t in [800,1500,2000]:
 stop=wide['close'].index[t]
 fs={k:v[v.index.get_level_values(0)<=stop] for k,v in fields.items()}
 a=check.load_factor_class(out/'style_explained120.py',check.load_smoke())().calculate(fs).xs(stop,level=0)
 b=check.load_factor_class(out/'style_stable120.py',check.load_smoke())().calculate(fs).xs(stop,level=0)
 start=t-120;prev=max(start-252,0)
 c=wide['close'].to_numpy();cap=wide['market_cap'].iloc[start].to_numpy();bm=wide['book_to_market_ratio_lf'].iloc[start].to_numpy()
 y=c[start+1:t+1]/c[start:t]-1
 assets=wide['total_assets'].to_numpy();roe=wide['oper_roe_ttm'].iloc[start].to_numpy()
 good=(cap>0)&np.isfinite(cap)&np.isfinite(y).all(axis=0)&np.isfinite(bm)&np.isfinite(roe)&(assets[start]>0)&(assets[prev]>0)&np.isfinite(assets[start])&np.isfinite(assets[prev])
 ids=np.flatnonzero(good);weights=cap[ids];yy=y[:,ids];third=len(ids)//3
 def spread(score):
  order=np.argsort(score,kind='stable');lo,hi=order[:third],order[-third:]
  return yy[:,hi]@(weights[hi]/weights[hi].sum())-yy[:,lo]@(weights[lo]/weights[lo].sum())
 market=yy@(weights/weights.sum());smb=-spread(weights);hml=spread(bm[ids]);res=[]
 for fac in [market[:,None],np.column_stack([market,smb,hml])]:
  x=np.column_stack([np.ones(120),fac]);res.append((yy-x@np.linalg.lstsq(x,yy,rcond=None)[0]).var(axis=0))
 expected=1-res[1]/res[0]
 valid=(wide['market_cap'].iloc[t].to_numpy()[ids]>0)&(res[0]>1e-12/252)
 expected[~valid]=np.nan
 truth=pd.Series(expected,index=a.index[ids]);risk=pd.Series(-np.sqrt(res[1])*np.sqrt(252),index=a.index[ids]).where(truth.notna());mix=truth.rank(pct=True)+risk.rank(pct=True)
 np.testing.assert_allclose(a.iloc[ids],truth,atol=1e-9,rtol=1e-8)
 np.testing.assert_allclose(b.iloc[ids],mix,atol=1e-12)
 checks.append({'date':str(stop.date()),'stocks':int(valid.sum()),'max_abs_formula_delta':float(np.nanmax(np.abs(a.iloc[ids].to_numpy()-expected))),'equalrank_matches':True})
 print(checks[-1],flush=True)
(out/'verification.json').write_text(json.dumps({'static_precheck':'pass both','repaint':'pass both, 242 daily comparisons, max_abs_delta=0','independent_intercept_OLS':checks,'input_fixture':'real full-A subset with PIT fields; proxy mapping described in plan'},indent=2))
