import sys,importlib.util,json,ast,time
from pathlib import Path
import numpy as np,pandas as pd
root=Path('research_reports/platform_alignment/bc-peer-pools-20261012');sys.path.insert(0,str(root));sp=importlib.util.spec_from_file_location('ms',root/'method_search_v3b.py');ms=importlib.util.module_from_spec(sp);sp.loader.exec_module(ms)
from platform_score_rules import raw_c_value
TARGET={'2026-09':{'raw_b':.1682133303820222,'raw_c':2.634661228043281,'rex':1.412057298880565,'sr':2.827223397434575,'max_dd':.017925197307789,'turnover':1.482668129875719},'2026-10':{'raw_b':.1126927543566361,'raw_c':89.20676601494793,'rex':13.019883659070862,'sr':2.712492691825157,'max_dd':.0047464116500837,'turnover':.3936381709741539}}
def parse(s):
 def r(n):
  if isinstance(n,ast.Name):return n.id
  if isinstance(n,ast.Constant):return n.value
  return (n.func.id,*(r(a) for a in n.args))
 return r(ast.parse(s,mode='eval').body)
def reprice(rows,daily):
 f=pd.DataFrame([{'date':d,'p':v[0]-1,'b':v[1]-1,'t':v[2]} for d,v in daily.items()]);out=[]
 for r in rows:
  q=f[f.date.astype('datetime64[ns]').dt.to_period('M').astype(str)==r['period']]
  if r['period']=='2026-09':q=q[q.date>=pd.Timestamp('2026-09-11')]
  p=q.p.to_numpy(float);b=q.b.to_numpy(float);n=len(p)
  if n<2:continue
  rp=np.prod(1+p)-1;rb=np.prod(1+b)-1;mr=(1+rp)**(21/n)-(1+rb)**(21/n);rex=(1+mr)**12-1;sr=p.mean()/p.std(ddof=1)*np.sqrt(252);nav=np.r_[1,np.cumprod(1+p)];dd=1-np.min(nav/np.maximum.accumulate(nav));turn=q.t.sum();rawc=raw_c_value(annual_excess_return=rex,annual_sharpe=sr,monthly_turnover=turn,monthly_max_drawdown=dd,sample_count=n)
  z={'period':r['period'],'C_days':n,'raw_b':r['raw_b'],'raw_c':rawc,'rex':rex,'sr':sr,'max_dd':dd,'turnover':turn,'seat_si':r['seat_si']};out.append(z)
 return out
def loss(rr):
 z=0
 for r in rr:
  t=TARGET[r['period']]
  for k in t:z+=(abs(r[k]-t[k])/max(abs(t[k]),.001))**2*(2 if k in ('raw_c','rex') else 1)
 return z
cal,stocks,fields,pos,dates,atoms=ms.load()
for f in ['original60_peer_atoms.npz','micro_atoms_20261013.npz']:
 with np.load(root/f) as z:atoms.update({k:z[k] for k in z.files})
ev=ms.Evaluator(cal,fields,pos,dates,atoms)
records=[];seen=set(); lines=open(root/'evaluations.jsonl').read().splitlines() if (root/'evaluations.jsonl').exists() else []
# actual methods-v3b evals path
lines=open(root/'methods-v3b/evaluations.jsonl').read().splitlines(); total=len(lines)
for j,l in enumerate(lines):
 r=json.loads(l)
 if r.get('status')!='evaluated':continue
 key=tuple(sorted(r['formulas']))
 if key in seen:continue
 seen.add(key)
 try:
  ids=tuple(ev.grammar.add(parse(s)) for s in r['formulas']); base,daily,_=ev.assess(ids); rr=reprice(base,daily)
  if len(rr)==2:
   records.append({'loss':loss(rr),'formulas':r['formulas'],'rows':rr})
 except Exception as e: pass
 if (j+1)%25==0: print('processed',j+1,'kept',len(records),flush=True)
records.sort(key=lambda x:x['loss']);out=root/'existing_corrected_20261013.json';out.write_text(json.dumps({'evaluated':len(records),'best':records[:100]},ensure_ascii=False,indent=2));
for z in records[:20]:print('LOSS',z['loss'],z['formulas'],[{k:round(r[k],5) for k in ['period','raw_b','raw_c','rex','sr','max_dd','turnover']} for r in z['rows']],flush=True)
