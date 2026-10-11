"""Fengmao target RankIC fit with causal inputs and bounded GP/CEM search.

All 119 periods enter fitting. Temporal slices are in-sample diagnostics.
No future labels enter expression inputs; no platform calls occur.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import ast
import gc
import hashlib
import json
from pathlib import Path
import threading
import time
import warnings
import numpy as np
import pandas as pd
import fengmao_group_gp_20261011 as base
import fengmao_multiround_20261011 as old
import fengmao_new_atoms_20261011 as new
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from platform_score_rules import seat_stats, SCORE_RULE_VERSION
from search_field_policy import load_field_exclusion_policy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/platform_alignment/fengmao-target-rankic-20261011'
TARGET = np.array([.1722791715386185,1.6613206049954048,.9327731092436975])
SCALE = np.array([.02,.25,.03])
START = time.monotonic()
OPS = [('Neg',1),('Rank',1),('Add',2),('Sub',2),('Mul',2),('Grp3',2),('Grp5',2),
       ('Resid3',2),('Resid5',2),('Blend3',2),('Blend5',2)]
warnings.filterwarnings('ignore',category=RuntimeWarning)


def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf8')


def log(text):
    print(f'[{time.monotonic()-START:.1f}s] {text}',flush=True)


class Fit:
    def __init__(self,atoms,y,cap,dates):
        self.atoms,self.y,self.cap,self.dates = atoms,y,cap,dates
        self.valid = np.isfinite(y)&np.isfinite(cap)
        self.count = self.valid.sum(1)
        self.yrank = old.rank(np.where(self.valid,y,np.nan))
        self.records = {}
        self.origin = ''
        if (OUT/'search.jsonl').exists():
            for line in (OUT/'search.jsonl').read_text(encoding='utf8').splitlines():
                row = json.loads(line)
                self.records[row['formula']] = row

    def vector(self,x):
        valid = self.valid & np.isfinite(x)
        if np.any(valid.sum(1)<.95*self.count):
            raise ValueError('less than 95% per-period label-universe coverage')
        xx = np.where(valid,x,np.nan)
        yr = self.yrank if np.array_equal(valid,self.valid) else old.rank(np.where(valid,self.y,np.nan))
        rx = old.rank(xx)
        # old.rowcorr returns zero on a constant; explicitly reject that case.
        if np.any(np.nanstd(rx,axis=1)<=1e-9):
            raise ValueError('constant cross-section')
        rho = old.rowcorr(rx,yr)
        if not np.isfinite(rho).all():
            raise ValueError('non-finite RankIC')
        return rho

    def assess_panel(self,x):
        rho = self.vector(x)
        s = seat_stats(rho)
        v = np.array([s.ic_mean,s.icir,float(np.mean(rho>.02))])
        if not np.isfinite(v).all():
            raise ValueError('non-finite objective')
        return dict(loss=float(np.sum(((v-TARGET)/SCALE)**2)),rank_ic=float(v[0]),
                    rank_ic_ir=float(v[1]),rank_ic_win=float(v[2]),s_i=s.s_i_a,
                    periods=len(rho),min_period_coverage=float(((np.isfinite(x)&self.valid).sum(1)/self.count).min()))

    def assess(self,formula):
        if formula in self.records:
            return self.records[formula]
        base.memory_guard()
        row = dict(formula=formula,origin=self.origin,status='invalid',loss=1e9)
        try:
            x = old.value(formula,self.atoms)
            row.update(self.assess_panel(x),status='evaluated')
        except (ValueError,KeyError,SyntaxError,FloatingPointError) as exc:
            row['error'] = str(exc)
        self.records[formula] = row
        with (OUT/'search.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(row,allow_nan=False)+'\n')
        return row

    def best(self):
        return min(self.records.values(),key=lambda row:row['loss'])


def load():
    if (OUT/'atoms.npz').exists():
        axes = json.loads((OUT/'axes.json').read_text(encoding='utf8'))
        with np.load(OUT/'atoms.npz') as saved:
            atoms = {k:saved[k] for k in saved.files if k not in ('target','market_cap')}
            y,cap = saved['target'],saved['market_cap']
        return atoms,y,cap,pd.DatetimeIndex(axes['dates']),axes
    cal,stocks,fields = base.load_data()
    new.load_open(cal,stocks,fields)
    pos = np.arange(cal.get_loc(pd.Timestamp('2021-09-17')),cal.get_loc(pd.Timestamp('2026-08-06'))+1,10)
    dates = cal[pos]
    assert len(pos)==119 and dates[-1]==pd.Timestamp('2026-08-06')
    y = fields['close'][pos+11].astype(float)/fields['close'][pos+1].astype(float)-1
    cap = fields['cap'][pos]
    atoms = base.build_atoms(fields,pos)
    atoms.update(old.long_atoms(fields,pos))
    atoms.update(new.build_new_atoms(fields,pos))
    # Store the formal saved H03 grid independently; never merge with target fit.
    source = ROOT/'research_reports/platform_alignment/fengmao-new-signals-20261011'
    axis = json.loads((source/'axes.json').read_text(encoding='utf8'))
    assert axis['symbols']==stocks.tolist()
    formal_dates = pd.DatetimeIndex(axis['dates'])
    formal_pos = cal.get_indexer(formal_dates)
    formal = base.build_atoms(fields,formal_pos)
    formal.update(old.long_atoms(fields,formal_pos))
    formal.update(new.build_new_atoms(fields,formal_pos))
    fy = fields['close'][formal_pos+11].astype(float)/fields['close'][formal_pos+1].astype(float)-1
    fc = fields['cap'][formal_pos]
    np.savez_compressed(OUT/'atoms_formal.npz',**formal,target=fy,market_cap=fc)
    save('axes_formal.json',axis)
    axes = dict(dates=[str(d.date()) for d in dates],symbols=stocks.tolist(),
                exits=[str(d.date()) for d in cal[pos+11]],
                schedule_source='inferred every 10 local trading days; matches public start/end/count; intermediate dates not observed')
    save('axes.json',axes)
    np.savez_compressed(OUT/'atoms.npz',**atoms,target=y,market_cap=cap)
    del fields,formal,fy,fc
    gc.collect()
    return atoms,y,cap,dates,axes


def genetic(fit,seed):
    tag = f'gp_{seed}'
    if (OUT/(tag+'_result.json')).exists():
        return json.loads((OUT/(tag+'_result.json')).read_text(encoding='utf8'))
    rng = np.random.default_rng(seed)
    names = sorted(fit.atoms)
    def fresh(depth=0):
        if depth>=3 or rng.random()<.4:
            return str(rng.choice(names))
        op,arity = OPS[int(rng.integers(len(OPS)))]
        args = [fresh(depth+1) for _ in range(arity)]
        return op+'('+','.join(args)+')'
    def mutate(formula):
        tree = ast.parse(formula,mode='eval')
        nodes = [n for n in ast.walk(tree) if isinstance(n,(ast.Name,ast.Call))
                 and not any(isinstance(p,ast.Call) and n is p.func for p in ast.walk(tree))]
        chosen = nodes[int(rng.integers(len(nodes)))]
        replacement = ast.parse(fresh(1),mode='eval').body
        class Replace(ast.NodeTransformer):
            def visit(self,node):
                return replacement if node is chosen else super().visit(node)
        return ast.unparse(Replace().visit(tree)).replace(' ','')
    initial = [row['formula'] for row in sorted(fit.records.values(),key=lambda r:r['loss'])[:16]]
    population = initial+[fresh() for _ in range(64-len(initial))]
    history,seen = [],set()
    for generation in range(16):
        fit.origin = tag
        scored = [fit.assess(f) for f in population]
        seen.update(population)
        elites = sorted(scored,key=lambda row:row['loss'])[:16]
        checkpoint = dict(generation=generation+1,seen=len(seen),unique_total=len(fit.records),
                          best=elites[0],memory=dict(base.PEAK))
        history.append(checkpoint)
        save(tag+'_progress.json',history)
        log(f'{tag} generation {generation+1}/16, unique={len(fit.records)}, best RankIC={elites[0].get("rank_ic",0):.4f}, IR={elites[0].get("rank_ic_ir",0):.3f}, win={elites[0].get("rank_ic_win",0):.3f}')
        population = [row['formula'] for row in elites[:8]]
        while len(population)<64:
            u = rng.random()
            if u<.18:
                child = fresh()
            elif u<.82:
                child = mutate(elites[int(rng.integers(len(elites)))]['formula'])
            else:
                a,b = rng.choice([row['formula'] for row in elites],2)
                child = f'{rng.choice(["Add","Sub","Mul","Grp3","Grp5"])}({a},{b})'
            if sum(isinstance(n,(ast.Name,ast.Call)) for n in ast.walk(ast.parse(child)))<=45:
                population.append(child)
    best = min((fit.records[f] for f in seen),key=lambda row:row['loss'])
    result = dict(engine='elite genetic tree mutation and crossover',seed=seed,
                  generations=16,population=64,unique=len(seen),best=best)
    save(tag+'_result.json',result)
    return result


def sparse_cem(fit):
    if (OUT/'cem_result.json').exists():
        return json.loads((OUT/'cem_result.json').read_text(encoding='utf8'))
    picks,panels = [],[]
    for row in sorted(fit.records.values(),key=lambda r:r['loss']):
        if row['status']!='evaluated':
            continue
        x = old.rank(old.value(row['formula'],fit.atoms))
        if any(np.nanmean(np.abs(old.rowcorr(x,y)))>.97 for y in panels):
            continue
        picks.append(row); panels.append(x)
        if len(picks)==8:
            break
    # Continuous sparse mixtures; all components are causal formulas. Cross-
    # sectional rank sum is recalculated for Spearman rather than optimizing
    # Pearson covariance or using future targets as input leaves.
    rng = np.random.default_rng(20261014)
    k = len(picks)
    mean,std = np.zeros(k),np.ones(k)
    found,history = [],[]
    for generation in range(12):
        population = []
        for i in range(32):
            base.memory_guard()
            weights = rng.normal(mean,std)
            keep = np.argsort(-np.abs(weights),kind='stable')[:3]
            weights[np.setdiff1d(np.arange(k),keep)] = 0.
            weights /= max(np.abs(weights).sum(),1e-12)
            # Avoid different intersections across components: each panel was
            # separately required to preserve >=95% coverage and mixtures too.
            x = np.zeros_like(panels[0]); valid = np.ones_like(x,dtype=bool)
            for j in keep:
                x += weights[j]*np.nan_to_num(panels[j],nan=0.)
                valid &= np.isfinite(panels[j])
            x[~valid] = np.nan
            model = dict(engine='sparse_rank_mixture_CEM',components=[dict(formula=picks[j]['formula'],weight=float(weights[j])) for j in keep],
                         normalization='same-date average ranks, selected-component intersection')
            try:
                row = dict(generation=generation+1,draw=i,**fit.assess_panel(x),model=model)
            except ValueError as exc:
                row = dict(generation=generation+1,draw=i,loss=1e9,error=str(exc),model=model)
            found.append(row); population.append((row['loss'],weights,row))
            with (OUT/'mixtures.jsonl').open('a',encoding='utf8') as f:
                f.write(json.dumps(row,allow_nan=False)+'\n')
        elite = sorted(population,key=lambda row:row[0])[:8]
        w = np.array([r[1] for r in elite])
        mean = .4*mean+.6*w.mean(0)
        std = np.maximum(.4*std+.6*w.std(0),.08)
        best = min(found,key=lambda r:r['loss'])
        history.append(dict(generation=generation+1,draws=len(found),best=best,memory=dict(base.PEAK)))
        save('cem_progress.json',history)
        log(f'sparse CEM {generation+1}/12, loss={best["loss"]:.3f}')
    result = dict(engine='sparse_rank_mixture_CEM',draws=384,frontier=picks,best=min(found,key=lambda row:row['loss']))
    save('cem_result.json',result)
    return result


def model_value(model,atoms):
    if 'formula' in model:
        return old.value(model['formula'],atoms)
    panels = [old.rank(old.value(c['formula'],atoms)) for c in model['components']]
    x = np.zeros_like(panels[0]); valid = np.ones_like(x,dtype=bool)
    for c,p in zip(model['components'],panels):
        x += c['weight']*np.nan_to_num(p,nan=0.)
        valid &= np.isfinite(p)
    x[~valid] = np.nan
    return x


def evaluate(models,atoms,y,cap,dates,axes):
    results = []
    with np.load(OUT/'atoms_formal.npz') as saved:
        formal = {k:saved[k] for k in saved.files if k not in ('target','market_cap')}
        fy,fc = saved['target'],saved['market_cap']
    fax = json.loads((OUT/'axes_formal.json').read_text(encoding='utf8'))
    fd = pd.DatetimeIndex(fax['dates'])
    prefixes = []
    for i,m in enumerate(models,1):
        name = f'FM_TARGET_{i:02d}'
        x = model_value(m,atoms)
        xf = model_value(m,formal)
        np.save(OUT/(name+'_target_signals.npy'),x)
        np.save(OUT/(name+'_formal_signals.npy'),xf)
        mask = dates<='2024-06-28'
        cut = model_value(m,{k:v[mask] for k,v in atoms.items()})
        assert np.array_equal(cut,x[mask],equal_nan=True)
        prefixes.append(dict(candidate=name,cells=int(np.isfinite(cut).sum()),masks_equal=True,max_difference=0))
        windows = [('target_119_fit',x,y,cap,dates),
                   ('target_first80_diagnostic',x[:80],y[:80],cap[:80],dates[:80]),
                   ('target_last39_diagnostic',x[80:],y[80:],cap[80:],dates[80:]),
                   ('formal_5y',xf,fy,fc,fd)]
        for window,xx,yy,cc,dd in windows:
            if window=='formal_5y':
                xx,yy,cc,dd = xf,fy,fc,fd
            p = base.periods(xx,yy,dd,cc)
            stats = base.summarize(p)
            seat = seat_stats(p.rank_ic)
            row = dict(candidate=name,window=window,rank_ic_ir=seat.icir,
                       rank_ic_win=float(np.mean(p.rank_ic>.02)),s_i_rank=seat.s_i_a,
                       abs_size_corr=float(p.corr_size.abs().mean()),**stats)
            results.append(row)
            p.to_csv(OUT/f'{name}_{window}_periods.csv',index=False)
        recent = fd>='2026-01-01'
        p = base.periods(xf[recent],fy[recent],fd[recent],fc[recent])
        seat = seat_stats(p.rank_ic); stats = base.summarize(p)
        results.append(dict(candidate=name,window='recent_2026',rank_ic_ir=seat.icir,
            rank_ic_win=float(np.mean(p.rank_ic>.02)),s_i_rank=seat.s_i_a,
            abs_size_corr=float(p.corr_size.abs().mean()),**stats))
        p.to_csv(OUT/f'{name}_recent_2026_periods.csv',index=False)
        top = []
        for j,date in enumerate(dates):
            ids = np.flatnonzero(np.isfinite(x[j]))
            selected = ids[np.argsort(-x[j,ids],kind='stable')[:20]]
            top.extend(dict(date=str(date.date()),rank=k+1,symbol=axes['symbols'][at],value=float(x[j,at])) for k,at in enumerate(selected))
        pd.DataFrame(top).to_csv(OUT/f'{name}_top20.csv',index=False)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    save('expression_prefix_checks.json',prefixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resume',action='store_true')
    args = ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'metadata.json').exists():
        raise FileExistsError('Completed experiment; preserve artifacts')
    if (OUT/'plan.json').exists() and not args.resume:
        raise FileExistsError('Use --resume')
    validate_alignment_config(alignment_config_snapshot())
    policy = load_field_exclusion_policy(allow_version_mismatch=True)
    if policy['blocked_fields']:
        raise ValueError('Refresh exclusion registry before using blocked/stale fields')
    base.OUT = OUT
    threading.Thread(target=base.watchdog,daemon=True).start()
    save('plan.json',dict(target=TARGET.tolist(),metric='RankIC mean, RankIC IR population std, positive RankIC>.02 win',
        method='two elite GP seeds 64x16, sparse signed CEM 32x12; direction and length controls',
        platform_cost=0,finalists=3,objective_scales=SCALE.tolist(),
        fitting='all 119 public-window labels; no independent holdout claim',
        date_status='every 10 trading days inferred from public first/last/count, not exact opponent dates',
        alignment_rule_version=ALIGNMENT_RULE_VERSION,score_rule_version=SCORE_RULE_VERSION,
        policy=policy,minimum_per_period_universe_coverage=.95,
        memory=dict(process_gib=2.25,available_floor_gib=1.25,chunk_stocks=192,watchdog_seconds=.5),
        success='abs RankIC difference <= .001, IR <= .01, win equal 111/119; causal input audit',
        no_future_labels_as_features=True,no_per_date_label_tuned_weights=True))
    atoms,y,cap,dates,axes = load()
    fit = Fit(atoms,y,cap,dates)
    fit.origin = 'causal_atom_direction_controls'
    for name in sorted(atoms):
        fit.assess(name); fit.assess(f'Neg({name})')
    gp = [genetic(fit,seed) for seed in (20261012,20261013)]
    cem = sparse_cem(fit)
    # Fixed slots: two GP winners and one mixture, all selected solely by
    # public-target metric loss. They may overlap; don't cherry-pick after audit.
    models = [dict(engine=r['engine'],formula=r['best']['formula'],fit=r['best']) for r in gp]
    models.append(dict(**cem['best']['model'],fit={k:v for k,v in cem['best'].items() if k!='model'}))
    save('models_frozen.json',models)
    log('Frozen three target-fit finalists; independent reconstruction next')
    evaluate(models,atoms,y,cap,dates,axes)
    save('metadata.json',dict(status='complete',rule=ALIGNMENT_RULE_VERSION,score_rule=SCORE_RULE_VERSION,
        target=TARGET.tolist(),unique_formulas=len(fit.records),valid_formulas=sum(r['status']=='evaluated' for r in fit.records.values()),
        mixture_draws=cem['draws'],best_formula=fit.best(),memory=base.PEAK,seconds=time.monotonic()-START,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        feature_sha256=hashlib.sha256(Path(new.__file__).read_bytes()).hexdigest(),platform_cost=0,
        cautions=['full-window adaptive target fit, all slices in-sample','no private opponent vector/formula',
                  'public ic_mean is RankIC, not Pearson IC','inferred intermediate dates','proxy execution ties'],
        target_dates=[str(dates[0].date()),str(dates[-1].date())],last_target_exit=axes['exits'][-1],
        formal_nominal=['20210907','20260907'],recent=['20260101','20260907'],
        warmup='20180101',universe='full historical SH/SZ, no ST/IPO filter',prices='qfq',cap='total_mv',
        label='close(t+1)->close(t+11)',groups=10,benchmark='factor_valid',one_way_cost=.003))
    base.DONE.set()
    log('TARGET FIT COMPUTATION COMPLETE')


if __name__=='__main__':
    main()
