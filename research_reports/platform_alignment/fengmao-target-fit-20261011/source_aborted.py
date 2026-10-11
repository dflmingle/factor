"""Causal target-metric fit for the public Fengmao aggregate numbers.

This is explicitly a numerical-fit experiment, not an exact opponent recovery:
the opponent's signal vector is unavailable. The exact 119-date 10-trading-day
schedule implied by 20210917..20260806 is rebuilt from local daily inputs.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import ast, gc, json, math, random, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import fengmao_group_gp_20261011 as base
import fengmao_multiround_20261011 as old
import fengmao_new_atoms_20261011 as new

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/fengmao-target-fit-20261011'
TARGET=np.array([.1722791715386185,1.6613206049954048,.9327731092436975])

def metric(x,y,cap):
    p=old.FastEvaluator(y,cap,DATES).periods(x)
    if len(p)<110: return None
    ic,win=float(p.ic.mean()),float((p.ic>0.02).mean())
    ir=ic/float(p.ic.std(ddof=1)) if p.ic.std(ddof=1)>1e-10 else 0.
    return np.array([ic,ir,win]),p

def loss(m):
    if m is None:return 1e9
    # Scale by meaningful public-metric tolerances; all three matter.
    return float(np.sum(((m-TARGET)/np.array([.02,.25,.03]))**2))

def main():
    global DATES
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'metadata.json').exists():
        print('already complete'); return
    cal,stocks,fields=base.load_data()
    new.load_open(cal,stocks,fields)
    start=cal.get_loc(pd.Timestamp('2021-09-17'))
    pos=np.arange(start,start+10*119,10)
    DATES=cal[pos]
    y=fields['close'][pos+11].astype(float)/fields['close'][pos+1].astype(float)-1
    cap=fields['cap'][pos]
    atoms=base.build_atoms(fields,pos)
    atoms.update(old.long_atoms(fields,pos))
    atoms.update(new.build_new_atoms(fields,pos))
    names=sorted(atoms)
    valid={k:atoms[k] for k in names}
    rng=np.random.default_rng(20261011)
    records=[]
    # Causal expression generator. It is deliberately bounded and does not see
    # future returns while constructing atoms; target metrics are only used as
    # an audit objective for this numerical-fit experiment.
    def rand_expr(depth=0):
        if depth>=3 or rng.random()<.35:
            return rng.choice(names)
        op=rng.choice(['Neg','Add','Sub','Mul','Grp3','Grp5','Resid3','Resid5','Blend3','Blend5'])
        if op=='Neg': return f'Neg({rand_expr(depth+1)})'
        return f'{op}({rand_expr(depth+1)},{rand_expr(depth+1)})'
    best=(1e9,None,None)
    for i in range(3000):
        f=rand_expr()
        try:
            x=old.value(f,valid)
            m,p=metric(x,y,cap)
            l=loss(m)
            if l<best[0]:
                best=(l,f,m.tolist()); print('BEST',i,l,f,m,flush=True)
            records.append(dict(formula=f,loss=l,ic=float(m[0]) if m is not None else None,
                icir=float(m[1]) if m is not None else None,win=float(m[2]) if m is not None else None))
        except Exception: pass
        if i%100==0:
            (OUT/'progress.json').write_text(json.dumps(dict(iteration=i,best=best),indent=2),encoding='utf8')
    records=sorted(records,key=lambda r:r['loss'])
    pd.DataFrame(records[:2000]).to_csv(OUT/'top2000.csv',index=False)
    # Independent holdout diagnostic: first 80 dates are search view, last 39
    # are not used by the optimizer in a future exact-recovery attempt.
    f=best[1]; x=old.value(f,valid); full,p=metric(x,y,cap)
    cut=80
    hold_dates=DATES[cut:]
    hold=old.FastEvaluator(y[cut:],cap[cut:],hold_dates).periods(x[cut:])
    hm=np.array([hold.ic.mean(),hold.ic.mean()/hold.ic.std(ddof=1),(hold.ic>0.02).mean()])
    meta=dict(status='complete',target_metrics=TARGET.tolist(),best_formula=f,
      best_metrics=full.tolist(),best_loss=best[0],holdout_metrics=hm.tolist(),
      schedule=dict(first=str(DATES[0].date()),last=str(DATES[-1].date()),periods=len(DATES),step='10 trading days'),
      universe='full SH/SZ',price='qfq',label='close(t+1)->close(t+11)',
      caveat='aggregate target fit only; no opponent signal vector; not exact reproduction',
      searched=3000,atoms=names)
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf8')
    (OUT/'summary.md').write_text('# 疯猫公开数值目标拟合\\n\\n'+json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    print('COMPLETE',meta)
if __name__=='__main__': main()
