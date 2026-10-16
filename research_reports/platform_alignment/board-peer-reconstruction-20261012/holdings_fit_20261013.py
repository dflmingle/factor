import sys,json,itertools, numpy as np,pandas as pd
sys.path.insert(0,'research_reports/platform_alignment/bc-peer-pools-20261012')
import method_search_v3b as m
ROOT='research_reports/platform_alignment/board-peer-reconstruction-20261012'
H=json.load(open(ROOT+'/public_holdings_20261013.json'))
cal,stocks,fields,pos,dates,atoms=m.load()
# date index to local signal array
D={pd.Timestamp(d).strftime('%Y%m%d'):i for i,d in enumerate(dates)}
# public target rows and cap eligible base; platform selected rows are top 10 composite, use actual list
recs=[]
for trade,d in H.items():
 if d.get('data_status')!='ok':continue
 sig=d['signal_trade_date'];
 if sig not in D: print('missing sig',trade,sig);continue
 i=D[sig]; held={r['symbol'] for r in d['rows']};
 # rank eligible based on cap; local symbols can include all; public universe count ~5022
 eligible=np.isfinite(fields['cap'][pos[i]]) & (fields['cap'][pos[i]]>0) & np.isfinite(fields['turnover'][pos[i]])
 recs.append((trade,sig,i,held,eligible))
print('dates',[(x[0],x[1],len(x[3]),x[2]) for x in recs])
# oriented factor candidate sets
sets={
'illiq':[k for k in atoms if k.startswith(('illiquidity','illiq_','amihud'))],
'lowturn':[k for k in atoms if k.startswith('lowturn')],
'lowvol':[k for k in atoms if k.startswith(('lowvol','downside','lowrange','rangevol'))],
'rsi':[k for k in atoms if k.startswith('rsi')],
'size':[k for k in atoms if k in ('smallsize','lowprice','lowamount10','lowamount20','lowamount60','lowamount90','lowamount120')]
}
print({k:v for k,v in sets.items()})
# cross-sec rank; handle low/higher direction all atoms are oriented except some candidates like lowrange etc yes

def rankrow(x):
 out=np.full_like(x,np.nan,float)
 for j in range(x.shape[0]):
  z=x[j];ok=np.isfinite(z); n=ok.sum()
  if n: out[j,ok]=(np.argsort(np.argsort(z[ok],kind='stable'),kind='stable')+1)/n
 return out
# cache ranks
R={k:rankrow(atoms[k]) for k in atoms}
# single-factor orientation diagnostics
for group,ks in sets.items():
  out=[]
  for k in ks:
    ovs=[]
    for trade,sig,i,held,eligible in recs:
      score=R[k][i];ok=eligible&np.isfinite(score);ord=np.flatnonzero(ok)[np.argsort(score[ok],kind='stable')[-len(held):]];ovs.append(len(set(stocks[ord])&held)/len(held))
    out.append((np.mean(ovs),np.min(ovs),k,ovs))
  print(group)
  for x in sorted(out,reverse=True)[:20]:print(x)
# weighted composite search over a reduced high-overlap proxy set
cand={
'illiq':['illiq_volscaled20','illiq_ratio20','illiquidity5','illiquidity20','illiquidity10'],
'lowturn':['lowturn5','lowturn10','lowturn20'],
'lowvol':['lowvol20','lowvol10','lowrange10','lowrange20','rangevol20','lowvol30'],
'rsi':['rsi14','rsi60','rsi10','rsi30'],
'size':['lowamount10','lowamount20','lowamount120','smallsize']}
weights_list=[[100,61,53,34,13],[1,1,1,1,1],[5,3,2,1,1],[10,6,5,3,1],[100,61,53,34,13]]
outs=[]
for comb in itertools.product(*[cand[k] for k in ['illiq','lowturn','lowvol','rsi','size']]):
 for ws in weights_list:
  ovs=[];mins=[]
  for trade,sig,i,held,eligible in recs:
   score=sum(w*R[k][i] for w,k in zip(ws,comb));ok=eligible&np.isfinite(score)
   ord=np.flatnonzero(ok)[np.argpartition(score[ok],-len(held))[-len(held):]];pred=set(stocks[ord]); inter=len(pred&held);ovs.append(inter/len(held))
  outs.append({'comb':comb,'weights':ws,'overlap_mean':float(np.mean(ovs)),'overlap_min':float(np.min(ovs)),'overlaps':ovs})
outs.sort(key=lambda x:(x['overlap_mean'],x['overlap_min']),reverse=True)
json.dump(outs[:500],open(ROOT+'/holdings_fit_weighted_20261013.json','w'),ensure_ascii=False,indent=2)
print('COMPOSITE BEST')
for x in outs[:50]:print(x)
