import sys,json,ast,numpy as np,pandas as pd
sys.path.insert(0,'research_reports/platform_alignment/bc-peer-pools-20261012');import method_search_v3b as m
ROOT='research_reports/platform_alignment/board-peer-reconstruction-20261012';H=json.load(open(ROOT+'/public_holdings_20261013.json'));cal,stocks,fields,pos,dates,atoms=m.load();e=m.Evaluator(cal,fields,pos,dates,atoms);R=e.grammar
# parse existing formula render grammar names

def parse(s):
 def r(n):
  if isinstance(n,ast.Name):return n.id
  if isinstance(n,ast.Constant):return n.value
  return (n.func.id,*(r(a) for a in n.args))
 return r(ast.parse(s,mode='eval').body)
# map signal dates
didx={pd.Timestamp(d).strftime('%Y%m%d'):i for i,d in enumerate(e.dates)};recs=[]
for trade,d in H.items():
 if d.get('data_status')=='ok':
  i=didx[d['signal_trade_date']]; held={r['symbol'] for r in d['rows']}; elig=np.isfinite(fields['cap'][pos[i]])&(fields['cap'][pos[i]]>0)&np.isfinite(fields['turnover'][pos[i]]);recs.append((i,held,elig))
records=[]
for line in open('research_reports/platform_alignment/bc-peer-pools-20261012/methods-v3b/evaluations.jsonl'):
 try:
  x=json.loads(line)
  if x.get('status')!='evaluated':continue
  records.append(x)
 except:pass
# unique by formulas, prioritize metric loss
uniq={tuple(x['formulas']):x for x in records}; candidates=sorted(uniq.values(),key=lambda x:x.get('loss',99))[:500]
out=[]
for no,x in enumerate(candidates):
 try:
  ids=[R.add(parse(s)) for s in x['formulas']]
  ovs=[]
  for i,held,elig in recs:
   pool=sum(R.get(j)[1][i] for j in ids)/5;ok=elig&np.isfinite(pool);ii=np.flatnonzero(ok);n=len(held);sel=ii[np.argpartition(pool[ok],-n)[-n:]];ovs.append(len(set(stocks[sel])&held)/n)
  ov=float(np.mean(ovs));loss=x.get('loss',99);out.append({'metric_loss':loss,'overlap_mean':ov,'overlap_min':float(np.min(ovs)),'overlaps':ovs,'formulas':x['formulas'],'rows':x['rows']})
 except Exception:pass
# metric normalized not directly comparable, combine rank
out.sort(key=lambda z:(z['overlap_mean']-.03*z['metric_loss']),reverse=True)
json.dump(out,open(ROOT+'/existing_holdings_rank_20261013.json','w'),ensure_ascii=False,indent=2)
for z in out[:100]:print(round(z['overlap_mean'],4),round(z['overlap_min'],4),round(z['metric_loss'],4),z['formulas'])
