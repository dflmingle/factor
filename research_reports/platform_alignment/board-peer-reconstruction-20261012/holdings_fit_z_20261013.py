import sys,json,itertools,numpy as np,pandas as pd
sys.path.insert(0,'research_reports/platform_alignment/bc-peer-pools-20261012');import method_search_v3b as m
ROOT='research_reports/platform_alignment/board-peer-reconstruction-20261012';H=json.load(open(ROOT+'/public_holdings_20261013.json'));cal,stocks,fields,pos,dates,atoms=m.load();Z={k:m.base.norm(v) for k,v in atoms.items()};D={pd.Timestamp(d).strftime('%Y%m%d'):i for i,d in enumerate(dates)};recs=[]
for trade,d in H.items():
 if d.get('data_status')=='ok':
  i=D[d['signal_trade_date']];recs.append((i,{r['symbol'] for r in d['rows']},np.isfinite(fields['cap'][pos[i]])&(fields['cap'][pos[i]]>0)&np.isfinite(fields['turnover'][pos[i]])))
sets={
'illiq':['illiq_volscaled20','illiq_ratio20','illiquidity5','illiquidity10','illiquidity20','illiquidity60','lowamount5','lowamount10','lowamount20'],
'lowturn':['lowturn5','lowturn10','lowturn20','lowturn30'],
'lowvol':['lowvol10','lowvol20','lowvol30','lowvol60','lowrange10','lowrange20','lowrange30','rangevol20'],
'rsi':['rsi10','rsi14','rsi24','rsi30','rsi60','reversal20','reversal60'],
'size':['smallsize','lowamount10','lowamount20','lowamount60','lowamount120','lowprice']}
rows=[]
for comb in itertools.product(*[sets[g] for g in ['illiq','lowturn','lowvol','rsi','size']]):
 ovs=[]
 for i,held,elig in recs:
  s=sum(Z[k][i] for k in comb);ok=elig&np.isfinite(s);ids=np.flatnonzero(ok);n=len(held);sel=ids[np.argpartition(s[ok],-n)[-n:]];ovs.append(len(set(stocks[sel])&held)/n)
 rows.append({'comb':comb,'overlap_mean':float(np.mean(ovs)),'overlap_min':float(np.min(ovs)),'overlaps':ovs})
rows.sort(key=lambda x:(x['overlap_mean'],x['overlap_min']),reverse=True);json.dump(rows[:500],open(ROOT+'/holdings_fit_z_20261013.json','w'),ensure_ascii=False,indent=2)
for x in rows[:100]:print(x)
