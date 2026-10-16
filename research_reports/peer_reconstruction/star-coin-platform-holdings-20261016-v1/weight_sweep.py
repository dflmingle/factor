from pathlib import Path
import json,sys,itertools
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[3]
V2=ROOT/'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'
SEARCH=ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1'
sys.path.insert(0,str(SEARCH)); sys.path.insert(0,str(V2))
from grammar import Expr
from engine import Market
from evidence import read,extract,PUBLIC
import objective
from holdings_diff import build_pool
OUT=Path(__file__).resolve().parent
pool=build_pool(); market=Market(); market.cache_dir=V2/'platform_weight_panels'; market.cache_dir.mkdir(exist_ok=True)
target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0]; e=objective.Objective(market,extract(target,market),OUT/'weight_eval',pool)
# z panels by signal date, active lifecycle. Use public holdings as target.
legs=[e.leg(x,j)['z'] for j,x in enumerate(pool)]; z=np.array(legs)
records=e.records; stocks=e.stocks
# target top20 sets and ranks
def score(weights):
    checks=[]; rankcorr=[]; top_hits=[]; held_ov=[]
    for r in records:
        i=e.index[pd.Timestamp(r['signal'])]; active=np.flatnonzero(e.active[:,i]); w=np.asarray(weights)[active]; w=w/w.sum()
        comp=np.average(z[active,i],axis=0,weights=w)
        valid=np.flatnonzero(e.mask[i]&np.isfinite(comp)); order=valid[np.argsort(comp[valid],kind='stable')][::-1]
        pred20=list(map(str,stocks[order[:20]])); pub=[x['symbol'] for x in r['rows']]; pubset=set(pub); pub20=set(pub[:20])
        top_hits.append(len(set(pred20)&pub20)); held=set(pub); chosen=set(map(str,stocks[order[:int(np.ceil(len(order)/10))]])); held_ov.append(len(chosen&held)/len(held))
        by={s:k+1 for k,s in enumerate(pub)}; common=[s for s in pred20 if s in by]
        if len(common)>=3:
            a=np.array([pred20.index(s)+1 for s in common]); b=np.array([by[s] for s in common]); rankcorr.append(float(pd.Series(a).corr(pd.Series(b),method='spearman')))
        checks.append({'trade':r['trade'],'top20':top_hits[-1],'held_overlap':held_ov[-1],'pred_top1':pred20[0],'peer_top1':pub[0]})
    # favor latest and all dates, with rank order; avoid extreme sparse weights
    return {'objective':float(np.mean(top_hits)+0.35*top_hits[-1]+0.8*np.nanmean(rankcorr)+0.5*np.mean(held_ov)),'mean_top20':float(np.mean(top_hits)),'latest_top20':int(top_hits[-1]),'mean_rankcorr':float(np.nanmean(rankcorr)),'mean_hold_overlap':float(np.mean(held_ov)),'checks':checks}
base=np.ones(10)/10
rows=[{'weights':base.tolist(),**score(base)}]
# one-leg tilts and paired structured tilts
cands=[]
for j in range(10):
  for mult in [0.5,0.75,1.25,1.5,2.0]:
    w=np.ones(10);w[j]*=mult;cands.append((f'w{j}x{mult}',w/w.sum()))
for group in [[0,1,8],[0,1,4,8,9],[1,2,3],[4,8,9],[0,8],[1,8],[0,4,9]]:
  for mult in [0.5,0.75,1.25,1.5,2.0]:
    w=np.ones(10);w[group]*=mult;cands.append((f'group{group}x{mult}',w/w.sum()))
# coarse random simplex around equal; deterministic
rng=np.random.default_rng(20261016)
for n in [5000]:
  for k in range(n):
    # Dirichlet concentration keeps weights near equal, include sparse possibilities
    a=rng.choice([8.,20.,40.],p=[.25,.5,.25]); w=rng.dirichlet(np.ones(10)*a); cands.append((f'rand{k}',w))
for name,w in cands:
  r=score(w); rows.append({'name':name,'weights':w.tolist(),**r})
rows.sort(key=lambda x:x['objective'],reverse=True)
(OUT/'weight_sweep_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'name':x.get('name','base'),'objective':x['objective'],'mean_top20':x['mean_top20'],'latest_top20':x['latest_top20'],'rankcorr':x['mean_rankcorr'],'held':x['mean_hold_overlap'],'weights':x['weights']} for x in rows[:20]],ensure_ascii=False))
