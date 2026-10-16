from pathlib import Path
import sys,json,itertools
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[3]; V2=ROOT/'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'; SEARCH=ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1'; sys.path[:0]=[str(SEARCH),str(V2)]
from grammar import Expr,field,const,op,paths,replace,formula
from engine import Market
from evidence import read,extract,PUBLIC
import objective
from holdings_diff import build_pool
OUT=Path(__file__).resolve().parent
base=list(build_pool()); market=Market();market.cache_dir=OUT/'variant_panels';market.cache_dir.mkdir(exist_ok=True);target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0];e=objective.Objective(market,extract(target,market),OUT/'variant_eval_out',tuple(base)); legsbase=[e.leg(x,j)['z'] for j,x in enumerate(base)]

def metrics(pool):
 legs=[e.leg(x,j)['z'] for j,x in enumerate(pool)]; z=np.array(legs); ts=[]; held=[]; ranks=[]
 for r in e.records:
  i=e.index[pd.Timestamp(r['signal'])];a=np.flatnonzero(e.active[:,i]); comp=z[a,i].sum(axis=0)/len(a); ids=np.flatnonzero(e.mask[i]&np.isfinite(comp)); order=ids[np.argsort(comp[ids],kind='stable')][::-1];pub=[x['symbol'] for x in r['rows']]; pub20=set(pub[:20]); p20=set(map(str,e.stocks[order[:20]])); ts.append(len(p20&pub20)); chosen=set(map(str,e.stocks[order[:int(np.ceil(len(order)/10))]]));held.append(len(chosen&set(pub))/len(pub)); by={s:k+1 for k,s in enumerate(pub)}; common=[s for s in map(str,e.stocks[order[:20]]) if s in by]; ranks.append(pd.Series([by[s] for s in common],index=range(len(common))).corr(pd.Series(range(1,len(common)+1)),method='spearman') if len(common)>2 else np.nan)
 return {'mean_top20':float(np.mean(ts)),'latest_top20':int(ts[-1]),'top20_path':ts,'mean_hold':float(np.mean(held)),'latest_hold':float(held[-1]),'mean_rankcorr':float(np.nanmean(ranks))}

def win(expr,which):
 p=list(base); p[which]=expr; return p
cands=[]
# baseline
cands.append(('control_v2',base.copy()))
# M02 window neighbourhoods
m02=base[8]
for path,node in paths(m02):
 if node.op=='ts_kurt' and 'sp' in node.fields:
  for n in [16,18,20,22,24,30]: cands.append((f'm02_kurt{n}',win(replace(m02,path,Expr(node.op,node.args,n)),8)))
# M03 cap/cfp simple variants
cap,cfp,close=field('cap'),field('cfp'),field('close')
for label,x in [('m03_rankcap_cfp',op('neg',op('add',op('rank',op('neg',cap)),cfp))),('m03_mean_rankcap_cfp',op('neg',op('mean2',op('rank',op('neg',cap)),cfp))),('m03_zcap_zcfp',op('neg',op('add',op('zscore',op('neg',cap)),op('zscore',cfp)))),('m03_rankcap_rankcfp',op('neg',op('add',op('rank',op('neg',cap)),op('rank',cfp))))]: cands.append((label,win(x,0)))
# V01 variants
ret=op('sub',op('div',close,op('delay',close,window=1)),const(1))
for n in [18,19,21,22,24]: cands.append((f'v01_std{n}',win(op('rank',op('ts_std',ret,window=n)),1)))
# X01 windows
for n in [8,9,11,12,15]: cands.append((f'x01_open{n}',win(op('div',close,op('ts_mean',field('open'),window=n)),7)))
rows=[]
for name,p in cands:
 m=metrics(p); rows.append({'name':name,'formulas':[formula(x) for x in p],**m})
rows.sort(key=lambda x:(x['latest_top20'],x['mean_top20'],x['mean_hold']),reverse=True);(OUT/'variant_eval_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(json.dumps([{k:r[k] for k in ['name','mean_top20','latest_top20','top20_path','mean_hold','latest_hold','mean_rankcorr']} for r in rows],ensure_ascii=False))
