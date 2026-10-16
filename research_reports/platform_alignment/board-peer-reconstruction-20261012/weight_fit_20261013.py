import sys,json,numpy as np,pandas as pd
sys.path.insert(0,'research_reports/platform_alignment/bc-peer-pools-20261012');import method_search_v3b as m
ROOT='research_reports/platform_alignment/board-peer-reconstruction-20261012';H=json.load(open(ROOT+'/public_holdings_20261013.json'));cal,stocks,fields,pos,dates,atoms=m.load();R={k:m.base.math.rank(v) for k,v in atoms.items()};D={pd.Timestamp(d).strftime('%Y%m%d'):i for i,d in enumerate(dates)};recs=[]
for trade,d in H.items():
 if d.get('data_status')=='ok':
  i=D[d['signal_trade_date']];recs.append((i,{r['symbol'] for r in d['rows']},np.isfinite(fields['cap'][pos[i]])&(fields['cap'][pos[i]]>0)&np.isfinite(fields['turnover'][pos[i]])))
combos=[['illiq_volscaled20','lowturn5','lowvol20','rsi14','lowamount10'],['illiq_volscaled20','lowturn5','lowvol20','rsi14','lowamount20'],['illiq_volscaled20','lowturn5','lowvol20','rsi14','smallsize'],['lowamount5','lowturn5','lowvol20','rsi14','smallsize'],['lowamount5','lowturn5','lowvol20','rsi14','lowamount120'],['lowamount10','lowturn5','lowvol20','rsi14','lowamount120']]
rng=np.random.default_rng(20261013);out=[]
for c in combos:
 best=(-1,None,None)
 Ws=[np.ones(5),np.array([100,61,53,34,13]),np.array([1,2,3,4,5]),np.array([5,3,2,1,1])]
 Ws += [rng.dirichlet(np.ones(5)*a)*5 for a in [.15,.3,.5,1,2,5] for _ in range(10000)]
 for w in Ws:
  ovs=[]
  for i,held,elig in recs:
   s=sum(ww*R[k][i] for ww,k in zip(w,c));ok=elig&np.isfinite(s);ids=np.flatnonzero(ok);n=len(held);sel=ids[np.argpartition(s[ok],-n)[-n:]];ovs.append(len(set(stocks[sel])&held)/n)
  score=np.mean(ovs)-.2*np.std(ovs)
  if score>best[0]:best=(score,w,ovs)
 out.append({'comb':c,'score':float(best[0]),'weights':best[1].tolist(),'overlap_mean':float(np.mean(best[2])),'overlaps':best[2]})
 print(out[-1])
json.dump(out,open(ROOT+'/weight_fit_20261013.json','w'),ensure_ascii=False,indent=2)
