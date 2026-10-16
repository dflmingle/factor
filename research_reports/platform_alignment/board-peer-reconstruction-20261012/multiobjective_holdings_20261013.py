import sys,json,itertools,numpy as np,pandas as pd
sys.path.insert(0,'research_reports/platform_alignment/bc-peer-pools-20261012');import method_search_v3b as m
ROOT='research_reports/platform_alignment/board-peer-reconstruction-20261012'; H=json.load(open(ROOT+'/public_holdings_20261013.json'))
cal,stocks,fields,pos,dates,atoms=m.load(); complete=pos+4<len(cal); y=np.full((len(pos),len(stocks)),np.nan); y[complete]=fields['close'][pos[complete]+4]/fields['close'][pos[complete]+1]-1
mask=complete&(dates<=pd.Timestamp('20260904'))
targ=pd.read_csv(ROOT+'/factor_targets.csv');targ=targ[targ.period=='2026-09'].set_index('factor_name')
# date rank arrays
R={k:m.base.math.rank(v) for k,v in atoms.items()}
# A stats for all atoms
stats={}
for k,x in R.items():
 rho=m.base.math.corr(m.base.math.rank(np.where(np.isfinite(y),x,np.nan)),m.base.math.rank(np.where(np.isfinite(x),y,np.nan)))[mask];rho=rho[np.isfinite(rho)]
 if len(rho):
  ic=rho.mean(); ir=ic/rho.std(ddof=0); win=(rho>.02).mean(); stats[k]=(ic,ir,win,abs(ic*ir)*win)
# target semantic groups
sets={
'illiq':[k for k in atoms if k.startswith(('illiquidity','illiq_','amihud','lowmaxret','lowamount','turnimpact'))],
'lowturn':[k for k in atoms if k.startswith(('lowturn','a140turn10','a120vol70'))],
'lowvol':[k for k in atoms if k.startswith(('lowvol','lowrange','downside','rangevol','a140turn10','a120vol70'))],
'rsi':[k for k in atoms if k.startswith(('rsi','a078rev','reversal'))],
'size':[k for k in atoms if k in ('smallsize','lowamount5','lowamount10','lowamount20','lowamount60','lowamount90','lowamount120','lowprice')]
}
for g,ks in sets.items():
 target={'illiq':'probe-illiquidity','lowturn':'probe-lowturn','lowvol':'probe-lowvol','rsi':'probe-rsi_rev','size':'probe-size'}[g]; tv=targ.loc[target,['ic_mean','icir','ic_win_rate']].to_numpy(float)
 arr=[]
 for k in ks:
  if k not in stats:continue
  v=np.array(stats[k][:3]);dist=float(np.sum(((v-tv)/np.array([.02,.2,.1]))**2))
  arr.append((dist,k,stats[k]))
 print('\n',g)
 for x in sorted(arr)[:20]:print(x)
# choose top 15 each by A distance, optimize equal and random weights
best={}
for g,ks in sets.items():
 target={'illiq':'probe-illiquidity','lowturn':'probe-lowturn','lowvol':'probe-lowvol','rsi':'probe-rsi_rev','size':'probe-size'}[g];tv=targ.loc[target,['ic_mean','icir','ic_win_rate']].to_numpy(float)
 vals=[]
 for k in ks:
  if k in stats:
   dist=np.sum(((np.array(stats[k][:3])-tv)/np.array([.02,.2,.1]))**2);vals.append((dist,k))
 best[g]=[k for _,k in sorted(vals)[:6]]
D={pd.Timestamp(d).strftime('%Y%m%d'):i for i,d in enumerate(dates)};recs=[]
for trade,d in H.items():
 if d.get('data_status')=='ok':recs.append((trade,D[d['signal_trade_date']],{r['symbol'] for r in d['rows']},np.isfinite(fields['cap'][pos[D[d['signal_trade_date']]]])&(fields['cap'][pos[D[d['signal_trade_date']]]]>0)&np.isfinite(fields['turnover'][pos[D[d['signal_trade_date']]]])))
def overlap(comb,ws):
 o=[]
 for _,i,held,elig in recs:
  s=sum(w*R[k][i] for w,k in zip(ws,comb));ok=elig&np.isfinite(s);ids=np.flatnonzero(ok);n=len(held);sel=ids[np.argpartition(s[ok],-n)[-n:]];o.append(len(set(stocks[sel])&held)/n)
 return float(np.mean(o)),float(np.min(o)),o
rows=[]
for comb in itertools.product(*[best[g] for g in ['illiq','lowturn','lowvol','rsi','size']]):
 tvdist=0
 for g,k in zip(['illiq','lowturn','lowvol','rsi','size'],comb):
  target={'illiq':'probe-illiquidity','lowturn':'probe-lowturn','lowvol':'probe-lowvol','rsi':'probe-rsi_rev','size':'probe-size'}[g];tv=targ.loc[target,['ic_mean','icir','ic_win_rate']].to_numpy(float);tvdist+=np.sum(((np.array(stats[k][:3])-tv)/np.array([.02,.2,.1]))**2)
 ov=overlap(comb,[1]*5)
 rows.append({'comb':comb,'a_dist':float(tvdist),'overlap_mean':ov[0],'overlap_min':ov[1],'overlaps':ov[2],'objective':ov[0]-0.03*tvdist})
rows.sort(key=lambda x:x['objective'],reverse=True);json.dump(rows[:500],open(ROOT+'/multiobjective_holdings_20261013.json','w'),ensure_ascii=False,indent=2)
for x in rows[:100]:print(x)
