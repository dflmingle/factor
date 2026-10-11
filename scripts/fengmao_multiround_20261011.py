"""Six authorized GP rounds plus bounded TB-GFN and bundled AlphaPool.

All searches and weights use purged 2021-2023 training labels only. Historical
validation has already been viewed in earlier work and is not pristine OOS.
"""
from __future__ import annotations
import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
import argparse
import ast
import gc
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fengmao_group_gp_20261011 as base
from platform_alignment_rules import alignment_config_snapshot, validate_alignment_config
from search_field_policy import load_field_exclusion_policy

OUT = ROOT / 'research_reports/platform_alignment/fengmao-multiround2-20261011'
LONG_ATOMS = ['rev10', 'rev120', 'vol120', 'vol252', 'volshift20', 'volshift60',
              'lowvolume60', 'lowturn60', 'lowturn120', 'trel20long', 'vrel20long',
              'pressure20', 'pressure60', 'smoothvol20', 'smoothvstab20']
ROUNDS = [(f'{mechanism}_{seed}', mechanism, 20261020 + i * 2 + seed)
          for i, mechanism in enumerate(['continuous', 'slow', 'hybrid']) for seed in [0, 1]]


def rank(x):
    n = np.isfinite(x).sum(axis=1, keepdims=True)
    return (rankdata(x, axis=1, nan_policy='omit') / np.maximum(n, 1) - .5).astype(np.float32)


def rowcorr(x, y):
    valid = np.isfinite(x) & np.isfinite(y)
    a = np.where(valid, x, np.nan).astype(float)
    b = np.where(valid, y, np.nan).astype(float)
    a -= np.nanmean(a, axis=1, keepdims=True)
    b -= np.nanmean(b, axis=1, keepdims=True)
    return np.nansum(a * b, axis=1) / np.maximum(np.sqrt(np.nansum(a*a, axis=1) * np.nansum(b*b, axis=1)), 1e-15)


def group_transform(x, by, groups, mode):
    ok = np.isfinite(x) & np.isfinite(by)
    bins = np.minimum(np.floor((rank(np.where(ok, by, np.nan)) + .5) * groups).astype(np.float32), groups - 1)
    result = np.full_like(x, np.nan)
    for g in range(groups):
        mask = ok & (bins == g)
        bucket = np.where(mask, x, np.nan)
        if mode == 'rank':
            val = rank(bucket)
        else:
            mean = np.nanmean(bucket, axis=1, keepdims=True)
            val = x - mean
            if mode == 'z':
                std = np.nanstd(bucket, axis=1, keepdims=True)
                val = val / np.maximum(std, 1e-6)
        result[mask] = val[mask]
    if mode == 'residual':
        result = rank(result)
    if mode == 'blend':
        # Continuous within/between-group information, no date jitter.
        result = .75 * x + .25 * rank(result)
    return result.astype(np.float32)


def value(formula, atoms):
    tree = ast.parse(formula, mode='eval')
    if sum(isinstance(n, (ast.Name, ast.Call)) for n in ast.walk(tree)) > 51:
        raise ValueError('Expression complexity above bound')
    def visit(node):
        if isinstance(node, ast.Name):
            return atoms[node.id]
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError('Unsafe expression syntax')
        args = [visit(a) for a in node.args]
        name = node.func.id
        if name == 'Neg' and len(args) == 1:
            return -args[0]
        if name == 'Rank' and len(args) == 1:
            return rank(args[0])
        if name in ['Add', 'Sub', 'Mul'] and len(args) == 2:
            return {'Add': np.add, 'Sub': np.subtract, 'Mul': np.multiply}[name](*args)
        for prefix, mode in [('Grp', 'rank'), ('GZ', 'z'), ('Resid', 'residual'), ('Blend', 'blend')]:
            if name.startswith(prefix) and name[len(prefix):] in ['3', '5', '10'] and len(args) == 2:
                return group_transform(*args, int(name[len(prefix):]), mode)
        raise ValueError('Unknown operator or arity ' + name)
    return visit(tree.body)


def long_atoms(fields, pos):
    atoms = {k: np.full((len(pos), fields['close'].shape[1]), np.nan, np.float32) for k in LONG_ATOMS}
    for begin in range(0, fields['close'].shape[1], 192):
        base.memory_guard()
        sl = slice(begin, begin + 192)
        c, v, t = [pd.DataFrame(fields[k][:, sl], dtype=float) for k in ['close', 'volume', 'turnover']]
        r = c / c.shift(1) - 1
        vols = {n: r.rolling(n, min_periods=n).std() for n in [20, 60, 120, 252]}
        vm252, tm252 = v.rolling(252, min_periods=252).mean(), t.rolling(252, min_periods=252).mean()
        rel = v / v.rolling(60, min_periods=60).mean()
        recipes = dict(rev10=-(c/c.shift(10)-1), rev120=-(c/c.shift(120)-1),
            vol120=vols[120], vol252=vols[252], volshift20=vols[20]/vols[120], volshift60=vols[60]/vols[252],
            lowvolume60=-v.rolling(60, min_periods=60).mean(), lowturn60=-t.rolling(60, min_periods=60).mean(),
            lowturn120=-t.rolling(120, min_periods=120).mean(), trel20long=t.rolling(20, min_periods=20).mean()/tm252,
            vrel20long=v.rolling(20, min_periods=20).mean()/vm252,
            pressure20=-(r*rel).rolling(20, min_periods=20).sum()/rel.rolling(20, min_periods=20).sum(),
            pressure60=-(r*rel).rolling(60, min_periods=60).sum()/rel.rolling(60, min_periods=60).sum(),
            smoothvol20=vols[20].rolling(60, min_periods=60).mean(),
            smoothvstab20=-(v.rolling(20, min_periods=20).std()/v.rolling(20, min_periods=20).mean()).rolling(60, min_periods=60).mean())
        for key, data in recipes.items():
            atoms[key][:, sl] = data.iloc[pos].to_numpy(dtype=np.float32)
        del recipes, vols, c, v, t, r, rel, vm252, tm252
        gc.collect()
    active = np.isfinite(fields['cap'][pos])
    for key in atoms:
        atoms[key][~active | ~np.isfinite(atoms[key])] = np.nan
        atoms[key] = rank(atoms[key])
    return atoms


class FastEvaluator:
    def __init__(self, target, cap, dates):
        self.target, self.cap, self.dates = target, cap, dates

    def periods(self, x):
        valid = np.isfinite(x) & np.isfinite(self.target) & np.isfinite(self.cap)
        xx = np.where(valid, x, np.nan)
        yy = np.where(valid, self.target, np.nan)
        ic = rowcorr(xx, yy)
        ric = rowcorr(rank(xx), rank(yy))
        sizecorr = rowcorr(rank(xx), rank(np.where(valid, self.cap, np.nan)))
        rows, previous = [], None
        for i, date in enumerate(self.dates):
            ids = np.flatnonzero(valid[i])
            if len(ids) < 100 or np.std(x[i, ids]) < 1e-10:
                continue
            order = ids[np.argsort(x[i, ids], kind='stable')]
            held = order[int(np.floor(.9 * len(ids))):]
            members = set(held)
            turn = np.nan if previous is None else 1 - len(members & previous)/len(members)
            previous = members
            rows.append(dict(date=str(date.date()), stocks=len(ids), ic=float(ic[i]), rank_ic=float(ric[i]),
                turnover=turn, gross_excess=float(self.target[i, held].mean()-self.target[i, ids].mean()),
                corr_size=float(sizecorr[i])))
        return pd.DataFrame(rows)

    def assess(self, x):
        p = self.periods(x)
        s = base.summarize(p.assign(tied_fraction=0.))
        # Three chronological training segments prevent a single regime from
        # winning the search. This is a training objective, not heldout tuning.
        split_nets = []
        for inds in np.array_split(np.arange(len(p)), 3):
            b = p.iloc[inds]
            split_nets.append(float(b.gross_excess.mean()*25.2 - b.turnover.mean()*.006*25.2))
        s['train_worst_third_net'] = min(split_nets)
        # Avoid rediscovering the size sleeve under a volatility label.  A
        # candidate with |size correlation| above .30 is heavily penalized;
        # this is a training guard, not an ex-post validation filter.
        s['fitness'] = (s['s_i_proxy'] + .20*s['net_excess'] + .15*min(split_nets)
                        - .10*max(s['turnover']-.30, 0)
                        - .20*max(abs(s['corr_size'])-.30, 0))
        return s


class Search:
    def __init__(self, atoms, ev, records):
        self.atoms, self.ev, self.records, self.origin = atoms, ev, records, ''
    def assess(self, formula):
        if formula in self.records:
            return self.records[formula]
        base.memory_guard()
        row = dict(formula=formula, origin=self.origin, fitness=-10., status='invalid')
        try:
            if not any(s in formula for s in ['Grp', 'GZ', 'Resid', 'Blend']):
                raise ValueError('No grouping mechanism')
            x = value(formula, self.atoms)
            stats = self.ev.assess(x)
            if stats['periods'] < .95*len(self.ev.dates):
                raise ValueError('Insufficient training coverage')
            row.update(stats)
            row['status'] = 'evaluated'
        except (ValueError, KeyError, SyntaxError) as exc:
            row['error'] = str(exc)
        self.records[formula] = row
        with (OUT/'search_progress.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, allow_nan=False)+'\n')
        return row


def train_gp(search, name, mechanism, seed):
    search.origin = name
    common = [('Neg',1), ('Rank',1), ('Add',2), ('Sub',2), ('Mul',2)]
    if mechanism == 'continuous':
        ops = common + [('GZ3',2), ('GZ5',2), ('Resid5',2), ('Blend5',2)]
    elif mechanism == 'slow':
        ops = common + [('GZ5',2), ('Resid3',2), ('Blend3',2)]
    else:
        ops = common + [('Grp5',2), ('GZ10',2), ('Resid10',2), ('Blend5',2)]
    names = [k for k in search.atoms if k != 'size']
    if mechanism == 'slow':
        names = [k for k in names if k in LONG_ATOMS or k in ['size','lowturn','vstab20','rev60','vol60','vrel20']]
    seen = set()
    def score(_y, f, _w):
        formula = str(np.asarray(f).flat[0])
        seen.add(formula)
        return search.assess(formula)['fitness']
    logs = []
    def callback():
        winner = max((search.records[f] for f in seen), key=lambda r:r['fitness'])
        row = dict(generation=len(logs)+1, round=name, unique=len(seen), global_unique=len(search.records), best=winner, memory=dict(base.PEAK))
        logs.append(row)
        base.dump(OUT/(name+'_generations.json'), logs)
        print(name, 'generation', len(logs), '/10', 'unique',len(seen),'bestS',round(winner.get('s_i_proxy',0),4),
              'net',round(winner.get('net_excess',0)*100,2),'turn',round(winner.get('turnover',0)*100,1),flush=True)
    estimator = base.SymbolicRegressor(population_size=96, generations=10, tournament_size=12,
        init_depth=(1,3), const_range=None, function_set=[base.symbol_function(n,a) for n,a in ops],
        metric=base._Fitness(score, greater_is_better=True), stopping_criteria=1.,
        parsimony_coefficient=.0005, random_state=seed, n_jobs=1,
        p_crossover=.4,p_subtree_mutation=.3,p_hoist_mutation=.1,p_point_mutation=.1,
        max_samples=1.,low_memory=True,verbose=0)
    estimator.fit(np.asarray([names],object),np.asarray([1.]),callback=callback)
    winner = max((search.records[f] for f in seen), key=lambda r:r['fitness'])
    result = dict(round=name,seed=seed,mechanism=mechanism,unique_formulas=len(seen),best=winner)
    base.dump(OUT/(name+'_result.json'),result)
    return result


def diverse_frontier(search, count=8):
    picks, panels = [], []
    for r in sorted(search.records.values(),key=lambda r:r['fitness'],reverse=True):
        if r['status'] != 'evaluated':
            continue
        x = value(r['formula'],search.atoms)
        rx = rank(x)
        if any(abs(float(np.mean(rowcorr(rx, rank(p)))))>.95 for p in panels):
            continue
        picks.append(r)
        panels.append(x)
        if len(picks)==count:
            break
    return picks, panels


def train_gfn(search, frontier):
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(20261031)
    search.origin = 'native_TB_GFN'
    names = [r['formula'] for r in frontier]
    k = len(names)
    policy = torch.nn.Sequential(torch.nn.Linear(2*k,48),torch.nn.Tanh(),torch.nn.Linear(48,2*k+1))
    logz = torch.nn.Parameter(torch.zeros(()))
    opt = torch.optim.Adam(list(policy.parameters())+[logz],lr=.003)
    found, logs = {}, []
    for iteration in range(128):
        states = torch.zeros(16,2*k)
        active = torch.ones(16,dtype=torch.bool)
        lpf, lpb = torch.zeros(16),torch.zeros(16)
        for _ in range(4):
            used = states[:,:k].bool() | states[:,k:].bool()
            mask = torch.cat((~used,~used,torch.ones(16,1,dtype=torch.bool)),1)
            mask[:,-1] = states.sum(1)>0
            mask[states.sum(1)>=3,:-1] = False
            logits = policy(states).masked_fill(~mask,-1e9)
            probs = .9*torch.softmax(logits,1)+.1*mask.float()/mask.sum(1,keepdim=True)
            dist = torch.distributions.Categorical(probs=probs)
            action = dist.sample()
            lpf = lpf+torch.where(active,dist.log_prob(action),0.)
            added = active & (action<2*k)
            ids = torch.nonzero(added).flatten()
            nextstate = states.clone()
            nextstate[ids,action[ids]]=1
            lpb=lpb+torch.where(added,-torch.log(nextstate.sum(1).clamp_min(1)),0.)
            active=active & (action<2*k)
            states=nextstate
            if not active.any():
                break
        rewards=[]
        for state in states.numpy():
            selected=np.flatnonzero(state)
            parts=[names[j] if j<k else f'Neg({names[j-k]})' for j in selected]
            expr=parts[0]
            for part in parts[1:]:
                expr=f'Add({expr},{part})'
            result=search.assess(expr)
            found[expr]=result
            rewards.append(float(np.clip(20*result['fitness'],-12,8)))
        loss=(logz+lpf-lpb-torch.tensor(rewards)).square().mean()
        opt.zero_grad();loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(),5.)
        opt.step()
        if (iteration+1)%16==0:
            best=max(found.values(),key=lambda r:r['fitness'])
            logs.append(dict(batch=iteration+1,trajectories=(iteration+1)*16,unique=len(found),loss=float(loss.detach()),best=best))
            base.dump(OUT/'gfn_progress.json',logs)
            print('GFN',iteration+1,'/128','unique',len(found),'best fitness',round(best['fitness'],5),flush=True)
    best=max(found.values(),key=lambda r:r['fitness'])
    base.dump(OUT/'gfn_engine.json',dict(engine='native torch trajectory balance, not full torchgfn package',
        trajectories=2048,frontier=names,grammar='signed subsets max3, uniform backward removals',unique=len(found),seed=20261031,loss=float(loss.detach())))
    return dict(engine='native_TB_GFN',formula=best['formula'],training=best)


def normalize(x):
    mean=np.nanmean(x,axis=1,keepdims=True)
    std=np.nanstd(x,axis=1,keepdims=True)
    return np.nan_to_num((x-mean)/np.maximum(std,1e-6),nan=0).astype(np.float32)


def train_alphapool(search, picks, panels):
    import torch
    from alphagen.models.alpha_pool import AlphaPool
    torch.set_num_threads(1)
    class PanelExpression:
        def __init__(self,name,x): self.name,self.x=name,torch.from_numpy(x)
        def evaluate(self,data,period=slice(0,1)): return self.x
        def __str__(self): return self.name
    data=type('SignalPanel',(),{'device':torch.device('cpu')})()
    n=min(6,len(picks))
    pool=AlphaPool(n,data,PanelExpression('label1_train',search.ev.target.astype(np.float32)))
    exprs=[PanelExpression(r['formula'],x.copy()) for r,x in zip(picks[:n],panels[:n])]
    pool.force_load_exprs(exprs)
    weights=pool._optimize(alpha=.005,lr=.0005,n_iter=300)
    weights=weights/max(np.abs(weights).sum(),1e-12)
    model=dict(engine='bundled_AlphaPool',components=[dict(formula=r['formula'],weight=float(w)) for r,w in zip(picks[:n],weights)],
        normalization='same-date population zscore, union vendor NaN fill zero, final intersection validity restored')
    x=model_value(model,search.atoms)
    model['training']=search.ev.assess(x)
    base.dump(OUT/'alphapool_model.json',model)
    print('AlphaPool train net',round(model['training']['net_excess']*100,2),flush=True)
    return model


def model_value(model,atoms):
    if 'formula' in model:
        return value(model['formula'],atoms)
    pieces=[value(p['formula'],atoms) for p in model['components']]
    result=sum(normalize(x)*p['weight'] for x,p in zip(pieces,model['components']))
    valid=np.logical_and.reduce([np.isfinite(x) for x in pieces])
    result[~valid]=np.nan
    return result


def finish(models,atoms,target,cap,dates,calendar,pos,fields,started,round_results,records):
    base.dump(OUT/'frozen_models.json',models)
    print('ALL MODELS FROZEN; beginning historical validation',flush=True)
    cutoff=calendar.get_loc(pd.Timestamp('2024-06-28'))
    prefix=dates<=calendar[cutoff]
    cutfields={k:v[:cutoff+1] for k,v in fields.items()}
    cutatoms=base.build_atoms(cutfields,pos[prefix]);cutatoms.update(long_atoms(cutfields,pos[prefix]))
    exits=calendar[pos+11]
    masks={'formal_5y':np.ones(len(dates),bool),
           'training':(dates<='2023-12-29') & (exits<='2023-12-29'),
           'validation_2024_2025':(dates>='2024-01-01') & (dates<='2025-12-31') & (exits<='2025-12-31'),
           'recent_2026':dates>='2026-01-01'}
    results,checks=[],[]
    for i,model in enumerate(models,1):
        name=f'FM_MULTI_{i:02d}'
        x=model_value(model,atoms)
        truncated=model_value(model,cutatoms)
        valid=np.isfinite(truncated)
        diff=float(np.max(np.abs(x[prefix][valid]-truncated[valid])))
        same=bool(np.array_equal(np.isfinite(x[prefix]),valid))
        assert same and diff==0, 'Prefix repaint failure '+name
        checks.append(dict(candidate=name,cutoff='20240628',dates=int(prefix.sum()),cells=int(valid.sum()),masks_equal=same,max_difference=diff))
        np.save(OUT/(name+'_signals.npy'),x)
        for window,mask in masks.items():
            p=FastEvaluator(target[mask],cap[mask],dates[mask]).periods(x[mask])
            ties=[]
            for xx,cc in zip(x[mask],cap[mask]):
                xx=xx[np.isfinite(xx)&np.isfinite(cc)]
                ties.append(float(pd.Series(xx).duplicated(keep=False).mean()))
            p['tied_fraction']=ties
            stats=base.summarize(p)
            results.append(dict(candidate=name,engine=model['engine'],window=window,**stats))
            p.to_csv(OUT/f'{name}_{window}_periods.csv',index=False)
            print(name,window,'ICIR',round(stats['icir'],3),'net',round(stats['net_excess']*100,2),'turn',round(stats['turnover']*100,1),flush=True)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    pd.DataFrame(records.values()).to_csv(OUT/'search_registry.csv',index=False)
    base.dump(OUT/'causality_checks.json',checks)
    base.dump(OUT/'round_results.json',round_results)
    base.dump(OUT/'metadata.json',dict(status='complete',method='fengmao-multiround-causal-full-a-arithmetic-v2',
        alignment_reference=base.ALIGNMENT_RULE_VERSION,GP_rounds=6,GP_population=96,GP_generations=10,GP_calls=5760,
        unique_formulas=len(records),valid_formulas=sum(r['status']=='evaluated' for r in records.values()),
        GFN_trajectories=2048,platform_cost=0,memory=base.PEAK,seconds=time.perf_counter()-started,
        nominal_window=['20210907','20260907'],warmup='20180101',latest=str(calendar[-1].date()),
        last_signal=str(dates[-1].date()),last_realized_end=str(exits[-1].date()),fields=['qfq close','volume','turnover','total_mv'],
        signal_dates=str(base.REFERENCE.relative_to(ROOT)),label='close(t+1)->close(t+11)',groups=10,one_way_cost=.003,
        universe='full historical SH/SZ, no ST/subnew overlays',direction=1,annualization='arithmetic, factor_valid benchmark',
        training_purge='exclude labels ending after 20231229',validation_purge='exclude labels ending after 20251231',
        freeze='all seeds, expressions and weights selected using purged training labels only',
        limitation='validation has previously been researched; no pristine holdout or official score claim',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check',action='store_true')
    args=parser.parse_args()
    if args.self_check:
        x=np.asarray([[1.,2.,3.,4.],[4.,3.,2.,1.]],np.float32)
        by=np.asarray([[1.,1.,2.,2.]]*2,np.float32)
        for mode in ['rank','z','residual','blend']:
            full=group_transform(x,by,3,mode)
            cut=group_transform(x[:1],by[:1],3,mode)
            assert np.array_equal(full[:1],cut)
        assert np.isfinite(value('GZ3(x,by)',{'x':x,'by':by})).all()
        print('causal cross-section transforms and safe syntax passed')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'search_progress.jsonl').exists() or (OUT/'metadata.json').exists():
        raise RuntimeError('Refuse overwrite completed or checkpointed research')
    started=time.perf_counter()
    base.OUT=OUT
    validate_alignment_config(alignment_config_snapshot())
    policy=load_field_exclusion_policy(allow_version_mismatch=True)
    assert not {'close','volume','turnover','market_cap'}.intersection(policy['blocked_fields'])
    base.dump(OUT/'plan.json',dict(rounds=ROUNDS,population=96,generations=10,maxGPcalls=5760,
        GFNtrajectories=2048,alphapool_components=6,finalists=3,cost=0,training='purged2021..2023',
        memory_limits={'process_gib':2.25,'system_available_min_gib':1.25},field_policy=policy,
        formula_families=['GZ3/5/10(x,g)','Resid3/5/10(x,g)','Blend3/5/10(x,g)','Grp5(x,g)'],
        new_atoms=LONG_ATOMS,selection='training reward only, no per-round heldout inspection'))
    threading.Thread(target=base.watchdog,daemon=True).start()
    calendar,stocks,fields=base.load_data()
    saved=base.read_platform_run(base.REFERENCE)
    dates=pd.DatetimeIndex(sorted(d for d in set(saved['dates']) if d in calendar and calendar.get_loc(d)+11<len(calendar)))
    pos=calendar.get_indexer(dates)
    target=fields['close'][pos+11].astype(float)/fields['close'][pos+1].astype(float)-1
    cap=fields['cap'][pos]
    atoms=base.build_atoms(fields,pos);atoms.update(long_atoms(fields,pos))
    np.savez_compressed(OUT/'atoms.npz',**atoms,target=target,market_cap=cap)
    base.dump(OUT/'axes.json',dict(dates=[str(d.date()) for d in dates],symbols=stocks.tolist()))
    training=(dates<='2023-12-29') & (calendar[pos+11]<='2023-12-29')
    search=Search({k:v[training] for k,v in atoms.items()},FastEvaluator(target[training],cap[training],dates[training]),{})
    round_results=[]
    for name,mechanism,seed in ROUNDS:
        print('START ROUND',name,'seed',seed,flush=True)
        round_results.append(train_gp(search,name,mechanism,seed))
        base.dump(OUT/'round_results.json',round_results)
    picks,panels=diverse_frontier(search)
    best=picks[0]
    gpmodel=dict(engine='best_of_six_GP_rounds',formula=best['formula'],training=best)
    gfnmodel=train_gfn(search,picks)
    alphamodel=train_alphapool(search,picks,panels)
    finish([gpmodel,gfnmodel,alphamodel],atoms,target,cap,dates,calendar,pos,fields,started,round_results,search.records)
    base.DONE.set()
    print('COMPLETE',OUT,'memory',base.PEAK,'seconds',round(time.perf_counter()-started,1),flush=True)


if __name__=='__main__':
    import warnings
    warnings.filterwarnings('ignore',category=RuntimeWarning)
    main()
