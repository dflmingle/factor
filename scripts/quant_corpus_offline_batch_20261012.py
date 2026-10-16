"""Persist every fixed hypothesis and both windows, including failed recipes."""
import hashlib
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual

def run(out,specs,values,calendar,stocks,fields,verification,notes,residualizer=None):
 out.mkdir(parents=True,exist_ok=True);q.dates_all=calendar
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 cap=fields['cap'][pos];rev=-(q.ratio(fields['close'],q.delay(fields['close'],20))-1)[pos]
 q.dump(out/'verification.json',verification)
 q.dump(out/'config.json',{'version':q.ALIGNMENT_RULE_VERSION+'-'+out.name+'-arithmetic-fullA',
  'warmup':'20180101','formal_window':['20210907','20260907'],'recent_window':['20260101',str(calendar.max().date())],
  'cycle':10,'groups':10,'label_offset':1,'benchmark':'factor_valid','one_way_cost':.003,'qfq':True,
  'universe':'SH/SZ fullA','market_cap':'total_mv','platform_net_filter':'all','oos':False,
  'platform_compute_spent':0,'hypotheses':len(specs),'parameter_selection':'fixed before outcome evaluation',**notes})
 rows=[];meta=[];panels={}
 for spec,x in zip(specs,values):
  m=dict(spec);key=m['key'];m['direction']=1
  m['source_sha256']=[hashlib.sha256((q.ROOT/p).read_bytes()).hexdigest() for p in m['source_paths']]
  meta.append(m);x=np.where((cap>0)&np.isfinite(x),x,np.nan).astype(np.float32)
  panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  forms=[('raw',x),('size_reversal_rank_residual',(residualizer or dual_residual)(x,-cap,rev))]
  for form,score in forms:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    dest=out/win;dest.mkdir(exist_ok=True)
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],fields)
    a.update(key=key,name=m['name'],window=win,form=form,gated=m.get('gated',False),coverage_pct=a['periods']/mask.sum()*100)
    rows.append(a);q.dump(dest/f'{key}.{form}.json',a)
    p.to_csv(dest/f'{key}.{form}.periods.csv',index=False);d.to_csv(dest/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['window'],r['form'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
  pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(out/'results.csv',index=False)
  q.dump(out/'recipe_manifest.json',meta)
 pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},out/'signal_panels.pkl')
 q.dump(out/'completion.json',{'completed':True,'hypotheses':len(specs),'rows':len(rows),'platform_compute_spent':0,
  'formal_last_signal':grid.max(),'last_exit':calendar[pos[-1]+11],'pool_test_done':False})
