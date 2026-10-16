import sys,importlib.util,json,ast
from pathlib import Path
import numpy as np,pandas as pd
root=Path(__file__).resolve().parent;sys.path.insert(0,str(Path('research_reports/platform_alignment/bc-peer-pools-20261012')))
spec=importlib.util.spec_from_file_location('ms',Path('research_reports/platform_alignment/bc-peer-pools-20261012/method_search_v3b.py'));ms=importlib.util.module_from_spec(spec);spec.loader.exec_module(ms)
from platform_score_rules import raw_c_value
TARGET={'2026-09':{'raw_c':2.634661228043281,'rex':1.412057298880565,'sr':2.827223397434575,'max_dd':.017925197307789,'turnover':1.482668129875719},'2026-10':{'raw_c':89.20676601494793,'rex':13.019883659070862,'sr':2.712492691825157,'max_dd':.0047464116500837,'turnover':.3936381709741539}}
def parse(s):
 def r(n):
  if isinstance(n,ast.Name):return n.id
  if isinstance(n,ast.Constant):return n.value
  return (n.func.id,*(r(a) for a in n.args))
 return r(ast.parse(s,mode='eval').body)
def reprice(rows,daily,start):
 f=pd.DataFrame([{'date':d,'p':v[0]-1,'b':v[1]-1,'t':v[2]} for d,v in daily.items()]);out=[]
 for r in rows:
  q=f[f.date.astype('datetime64[ns]').dt.to_period('M').astype(str)==r['period']]
  if r['period']=='2026-09':q=q[q.date>=pd.Timestamp(start)]
  p=q.p.to_numpy(float);b=q.b.to_numpy(float);n=len(p)
  if n<2:continue
  rp=np.prod(1+p)-1;rb=np.prod(1+b)-1;mr=(1+rp)**(21/n)-(1+rb)**(21/n);rex=(1+mr)**12-1;sr=p.mean()/p.std(ddof=1)*np.sqrt(252);nav=np.r_[1,np.cumprod(1+p)];dd=1-np.min(nav/np.maximum.accumulate(nav));turn=q.t.sum();rawc=raw_c_value(annual_excess_return=rex,annual_sharpe=sr,monthly_turnover=turn,monthly_max_drawdown=dd,sample_count=n)
  z={'period':r['period'],'n':n,'raw_c':rawc,'rex':rex,'sr':sr,'max_dd':dd,'turnover':turn};out.append(z)
 return out
cal,stocks,fields,pos,dates,atoms=ms.load();
for f in ['original60_peer_atoms.npz','micro_atoms_20261013.npz']:
 with np.load(root/'../bc-peer-pools-20261012'/f) as z: atoms.update({k:z[k] for k in z.files})
ev=ms.Evaluator(cal,fields,pos,dates,atoms)
x=json.load(open(Path('research_reports/platform_alignment/bc-peer-pools-20261012/crossover_corrected_search_20261013.json'))); arr=x['top']
# choose 20 distinct pools with oct rawc near target and sep rex/sr plausible
sel=[]
for z in sorted(arr,key=lambda z:abs(z['rows'][1]['raw_c']-89.2)):
 if z['formulas'] not in [q['formulas'] for q in sel]:sel.append(z)
 if len(sel)>=20:break
starts=['2026-09-07','2026-09-08','2026-09-09','2026-09-10','2026-09-11','2026-09-14','2026-09-15']
rows=[]
for pi,z in enumerate(sel):
 ids=tuple(ev.grammar.add(parse(s)) for s in z['formulas']); base,day,_=ev.assess(ids)
 for st in starts:
  rr=reprice(base,day,st); dd={r['period']:r for r in rr}
  if '2026-09' not in dd or '2026-10' not in dd:continue
  score=0
  for per in TARGET:
   for k in TARGET[per]:
    val=dd[per][k];tar=TARGET[per][k];score+=(abs(val-tar)/max(abs(tar),.001))**2*(2 if k in ('raw_c','rex') else 1)
  rows.append({'pool':pi,'start':st,'score':score,'formulas':' | '.join(z['formulas']),**{f'{per}_{k}':dd[per][k] for per in TARGET for k in TARGET[per]}})
out=pd.DataFrame(rows).sort_values('score');out.to_csv(Path('research_reports/platform_alignment/bc-peer-pools-20261012/activation_scan_20261013.csv'),index=False);print(out.head(20).to_string(index=False))
