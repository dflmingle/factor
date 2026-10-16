"""Focused per-seat A/signature search; local, equal pool weights, no platform.

All public snapshots and A summaries are fitted evidence, never holdouts.
Shared engines/configuration and earlier experiments remain untouched.
"""
from pathlib import Path
import gc
import importlib.util
import itertools
import json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
PREV=OUT.parent/'star-coin-fidelity-focus-20261016-v6'
spec=importlib.util.spec_from_file_location('fidelity_v6',PREV/'revalidate.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
prior.OUT=OUT;prior.previous.OUT=OUT
ROOT=prior.ROOT
Expr=prior.Expr
Interpreter=prior.Interpreter
standardize=prior.standardize
correlation=prior.correlation
clean=prior.clean
save=prior.save
read=prior.read
Research=prior.Research
from grammar import field, const, op, paths, replace, formula


def metrics(x):
    x=np.array(x);mu=float(x.mean());ir=mu/max(float(x.std(ddof=1)),1e-12)
    win=float(np.mean(np.sign(mu)*x>.02))
    return dict(ic_mean=mu,icir=ir,ic_win_rate=win,s_i_a=abs(mu)*abs(ir)*win,valid_count=len(x))


def grid_audit(r,baseline):
    rows=[]
    for j,row in enumerate(baseline['selected_seats']):
        full=r.engines[row['proxy']].evaluate(Expr.from_json(row['tree']))
        public=row['A']['2026-10']['public'];key=(public['window_start'],public['window_end'],public['sample_count'])
        sig,_=r.grids[key]
        for offset in [-5,-1,0,1,5,6]:
            indices=sig+offset;y=r.m.prices[indices+r.e.cycle+1].astype(float)/r.m.prices[indices+1]-1
            xs=[correlation(np.where(r.m.capmask[p],full[p],np.nan),y[k],True) for k,p in enumerate(indices)]
            xs=[x for x in xs if np.isfinite(x)];m=metrics(xs)
            rows.append(dict(seat=j+1,offset=offset,local=m,public=public,
                A_ratio=m['s_i_a']/public['s_i_a'],
                mu_abs_delta=abs(abs(m['ic_mean'])-public['ic_mean']),
                ir_abs_delta=abs(abs(m['icir'])-public['icir']),
                win_delta=m['ic_win_rate']-public['ic_win_rate']))
        print(json.dumps(dict(stage='grid_audit',seat=j+1)),flush=True)
    save('grid_audit.json',dict(rows=rows,official_grid_changed=False,
        interpretation='global signal-grid shifts, same label1; sensitivity only, never per-seat fitted dates'))


def seat_loss(row):
    a=row['A']['2026-10'];local=a['local'];public=a['public']
    if local['s_i_a'] is None:return 1e9
    # Compare the three A components separately, not only their product.
    aloss=((abs(local['ic_mean'])-public['ic_mean'])/.015)**2
    aloss+=((abs(local['icir'])-public['icir'])/.10)**2
    aloss+=((local['ic_win_rate']-public['ic_win_rate'])/.05)**2
    return row['signature_loss']+.5*aloss


def proposals(r,base):
    """Bounded structural hypotheses; no fitted pool/stock weights."""
    c,v,lo,hi,opening,cap,cfp,amount,turn=[field(k) for k in ['close','volume','low','high','open','cap','cfp','amount','turnover']]
    rank=lambda x:op('rank',x)
    neg=lambda x:op('neg',x)
    capr=rank(neg(cap));pr=rank(neg(c));cashr=rank(cfp)
    # Seat1: map CFP structure, rank/sign and cash-price interaction.
    for proxy in ['baseline','annual']:
        for cash in [cfp,rank(cfp),rank(neg(cfp)),op('zscore',cfp)]:
            for join in ['add','mul']:
                yield 0,neg(op(join,capr,op('mean2',pr,cash))),proxy,'CFP sign/rank and size interaction'
        for shape in [neg(op('add',op('mean2',capr,pr),cashr)),
                      neg(op('mean2',capr,op('mul',pr,cashr))),
                      neg(op('mul',op('add',capr,pr),cashr)),
                      neg(op('add',capr,rank(op('div',cfp,c)))),
                      neg(op('add',capr,rank(op('mul',cfp,c)))),
                      neg(op('add',capr,rank(op('div',c,op('ts_mean',c,window=20)))))]:
            yield 0,shape,proxy,'CFP dimensional/subtree hypothesis'
    # Seat3: original expression mixed volume level with price level.
    # Replace level by activity or relative activity; test before/after EMA rank.
    for activity in [turn,op('div',v,op('ts_mean',v,window=20)),op('ts_mean',v,window=20),amount]:
        x=neg(op('add',rank(neg(activity)),rank(neg(lo))))
        for n in [3,5,10]:
            yield 2,op('ema',x,window=n),'baseline','activity semantics vs volume level'
    for join in ['mul','min2','max2']:
        for price in [c,lo]:
            x=neg(op(join,rank(neg(v)),rank(neg(price))))
            yield 2,op('ema',x,window=5),'baseline','nonadditive volume-price combination'
    # Seat8: causal price reversal denominator field/window/smoother.
    for price in [c,opening,lo]:
        for n in [3,5,10,20]:
            yield 7,op('div',c,op('ts_mean',price,window=n)),'baseline','price reversal trailing mean'
        for n in [3,5,10]:
            yield 7,op('div',c,op('ema',price,window=n)),'baseline','price reversal EMA'
    # Seat9: original subtracted <=1 rank from monetary cap (nearly pure size).
    # Test removal/relocation of cap, normalization, and smoothing duration.
    fin=base[8].args[0].args[1]
    for n in [10,20,40,60]:
        yield 8,op('ts_mean',cap,window=n),'baseline','pure smoothed cap control'
        yield 8,op('ts_mean',op('sub',rank(cap),fin),window=n),'baseline','rank-cap and financial difference'
        yield 8,op('ts_mean',op('mul',rank(cap),fin),window=n),'baseline','rank-cap financial interaction'
        yield 8,op('ts_mean',fin,window=n),'baseline','financial-only subtree'
    for shape in [op('logabs',cap),op('sqrtabs',cap),op('zscore',cap)]:
        yield 8,op('ts_mean',op('sub',shape,fin),window=20),'baseline','size scale hypothesis'


def main():
    (OUT/'panels').mkdir(exist_ok=True);(OUT/'A_cache').mkdir(exist_ok=True)
    baseline=read(PREV/'result.json');r=Research()
    save('protocol.json',dict(rule_reference=prior.LOCAL_RULE,platform_compute=0,strict_oos=False,
        all_dates_fitted=True,equal_pool_weights=True,focus_seats=[1,3,8,9],
        purpose='reduce per-seat IC/A component discrepancies; no returns maximization',
        A_screening='full five-year A for every structural hypothesis, no recent-IC prescreen',
        A_components='abs IC mean, abs ICIR, oriented win rate separately; no aggregate cancellation',
        grid='keep v6 return-end grid; global shifts diagnostic only',max_pool_changes=4))
    grid_audit(r,baseline)
    for j,row in enumerate(baseline['selected_seats']):
        ident=r.add(j,Expr.from_json(row['tree']),'v6 selected control',row['proxy'])
        r.A(ident);r.bank[ident]['seat_loss']=seat_loss(r.bank[ident])
    controls=tuple(range(10));control=r.measure(controls)
    candidates=list(proposals(r,r.base));save('proposals.json',[dict(seat=j+1,tree=x.json(),formula=formula(x),proxy=p,reason=reason) for j,x,p,reason in candidates])
    for k,(j,x,p,reason) in enumerate(candidates,1):
        ident=r.add(j,x,reason,p);r.A(ident);r.bank[ident]['seat_loss']=seat_loss(r.bank[ident])
        if k%5==0:
            r.export_bank();print(json.dumps(dict(stage='full_A_candidate',done=k,total=len(candidates),bank=len(r.bank))),flush=True)
    r.export_bank()
    focus=[0,2,7,8];eligible=[];frontiers=[]
    for j in focus:
        current=r.bank[j];rows=[b for b in r.bank if b['seat']==j]
        # Retain alternatives with bounded recent signature error plus per-seat fit.
        rows.sort(key=lambda b:b['seat_loss'])
        best=rows[:8];eligible.append(sorted({j}|{b['id'] for b in best}))
        frontiers.append(dict(seat=j+1,baseline=current['id'],ranked_ids=[b['id'] for b in rows],
            best_id=rows[0]['id']))
    save('seat_frontiers.json',frontiers)
    finalists=[]
    for combo in itertools.product(*eligible):
        state=list(controls)
        for j,b in zip(focus,combo):state[j]=b
        row=r.measure(state)
        # No per-seat recent IC can hide behind better IC at a different seat.
        ok=all(r.bank[b]['rankic_mae']<=max(r.bank[j]['rankic_mae']*1.25,r.bank[j]['rankic_mae']+.004)
            and r.bank[b]['ic_mae']<=max(r.bank[j]['ic_mae']*1.25,r.bank[j]['ic_mae']+.004)
            for j,b in zip(focus,combo))
        if not ok:continue
        # Keep board/membership drift bounded, but do not target high return.
        if row['mean_full_overlap']<control['mean_full_overlap']-.015:continue
        if any(abs(row['boards'][k]['relative_error'])>.035 for k in ['rex','robust']):continue
        sl=float(np.mean([r.bank[state[j]]['seat_loss'] for j in focus]))
        row=dict(row,focus_seat_loss=sl)
        finalists.append(row)
    finalists.sort(key=lambda x:(x['focus_seat_loss'],x['loss']))
    selected=finalists[0] if finalists else dict(control,focus_seat_loss=float(np.mean([r.bank[j]['seat_loss'] for j in focus])))
    save('result.json',dict(protocol=read(OUT/'protocol.json'),baselines=[control],baseline_labels=['v6'],
        selected=selected,selected_seats=[{k:v for k,v in r.bank[b].items() if k not in ['expr','z']}|dict(tree=r.bank[b]['expr'].json()) for b in selected['state']],
        finalists=finalists[:20],evaluated_states=len(r.cache),proposed=len(candidates),unique_legs=len(r.bank),platform_compute=0))
    r.export_bank()
    print(json.dumps(dict(stage='complete',path=[p['top20'] for p in selected['path']],state=selected['state'],
        loss=selected['loss'],focus_loss=selected['focus_seat_loss'],states=len(r.cache))),flush=True)


if __name__=='__main__':main()
