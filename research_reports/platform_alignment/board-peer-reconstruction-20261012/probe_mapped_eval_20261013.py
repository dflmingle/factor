import sys,importlib.util,json,ast
from pathlib import Path
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1]/'bc-peer-pools-20261012';sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('ms',root/'method_search_v3b.py');ms=importlib.util.module_from_spec(spec);spec.loader.exec_module(ms)
from platform_score_rules import raw_c_value
TARGET={'2026-09':{'raw_b':.1682133303820222,'raw_c':2.634661228043281,'rex':1.412057298880565,'sr':2.827223397434575,'max_dd':.017925197307789,'turnover':1.482668129875719},'2026-10':{'raw_b':.1126927543566361,'raw_c':89.20676601494793,'rex':13.019883659070862,'sr':2.712492691825157,'max_dd':.0047464116500837,'turnover':.3936381709741539}}
def parse(s):
 def r(n):
  if isinstance(n,ast.Name):return n.id
  if isinstance(n,ast.Constant):return n.value
  return (n.func.id,*(r(a) for a in n.args))
 return r(ast.parse(s,mode='eval').body)
def reprice(rows,daily):
 f=pd.DataFrame([{'date':d,'p':v[0]-1,'b':v[1]-1,'t':v[2]} for d,v in daily.items()])
 out=[]
 for r in rows:
  q=f[f.date.astype('datetime64[ns]').dt.to_period('M').astype(str)==r['period']]
  if r['period']=='2026-09':q=q[q.date>=pd.Timestamp('2026-09-11')]
  p=q.p.to_numpy(float);b=q.b.to_numpy(float);n=len(p)
  if n<2:continue
  rp=np.prod(1+p)-1;rb=np.prod(1+b)-1;mr=(1+rp)**(21/n)-(1+rb)**(21/n);rex=(1+mr)**12-1;sr=p.mean()/p.std(ddof=1)*np.sqrt(252);nav=np.r_[1,np.cumprod(1+p)];dd=1-np.min(nav/np.maximum.accumulate(nav));turn=q.t.sum();rawc=raw_c_value(annual_excess_return=rex,annual_sharpe=sr,monthly_turnover=turn,monthly_max_drawdown=dd,sample_count=n)
  z=dict(r);z.update(C_days=n,rex=rex,sr=sr,max_dd=dd,turnover=turn,raw_c=rawc);out.append(z)
 return out
def loss(rows):
 z=0
 for r in rows:
  t=TARGET[r['period']]
  for k in t:z+=(abs(r[k]-t[k])/max(abs(t[k]),.001))**2*(2 if k in ('raw_c','rex') else 1)
 return z
cal,stocks,fields,pos,dates,atoms=ms.load(); ev=ms.Evaluator(cal,fields,pos,dates,atoms)
sets={
'mapped2':['Mix(reversal30,amihud60,0.25)','Max(lowturn5,reversal5)','Mix(illiquidity5,momentum20,0.75)','Mul(bm,lowturn10)','Max(lowprice,lowresidual60)'],
'alt1':['Sub(reversal10,volume_trend60)','Max(lowturn5,reversal5)','Mix(illiquidity5,momentum20,0.75)','Sub(illiquidity5,illiquidity90)','Sub(reversal5,lowvol5)'],
'alt2':['Div(illiquidity90,amihud20)','Max(lowturn5,reversal5)','Mix(illiquidity5,momentum20,0.75)','Mul(bm,lowturn10)','Sub(reversal5,lowvol5)'],
'alt3':['Add(illiquidity10,reversal30)','Mul(a140turn10,lowturn5)','Mix(illiquidity5,momentum20,0.75)','Mul(bm,lowturn10)','Max(lowprice,lowresidual60)'],
}
for name,fs in sets.items():
 ids=tuple(ev.grammar.add(parse(s)) for s in fs); print(name,[float(np.isfinite(ev.grammar.get(i)[1]).sum(1).min()/np.isfinite(ev.cap).sum(1).min()) for i in ids]); rows,daily,_=ev.assess(ids); rr=reprice(rows,daily); print(name,fs, 'loss',loss(rr)); print([{k:(x[k] if k=='period' else round(x[k],6)) for k in ['period','C_days','raw_b','raw_c','rex','sr','max_dd','turnover']} for x in rr])
