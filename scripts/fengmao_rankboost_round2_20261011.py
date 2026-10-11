"""Three bounded LightGBM methods, global numerical fit and temporal controls.

Labels enter training/objective only. No dates, symbols or future returns are
predictor inputs; full-window fitted models are NOT historical tradable factors.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
import hashlib
import json
from pathlib import Path
import threading
import time
import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy.optimize import differential_evolution
from threadpoolctl import threadpool_limits
import fengmao_target_rankic_20261011 as prior
from platform_score_rules import seat_stats
from platform_alignment_rules import ALIGNMENT_RULE_VERSION

ROOT, SOURCE = prior.ROOT, prior.OUT
OUT = ROOT/'research_reports/platform_alignment/fengmao-rankboost-round2-20261011'
PEER = ROOT/'research_reports/platform_alignment/peer-return-gap-local-20261010'
START = time.monotonic()
STAGES = (300, 600, 900, 1200, 1500, 1800, 2100, 2400)
KINDS = ('rank_regression', 'listwise_ranking', 'peer_group_regression')
FEATURES = sorted(set(prior.base.ATOMS + prior.old.LONG_ATOMS + prior.new.NEW_NAMES))
PAIRS = [('rev6','vol20'),('rev20','vol60'),('rev6','lowturn'),
         ('rev20','size'),('vstab20','asym20'),('idrev20','onvol20'),
         ('rev6','volshift20'),('pressure20','lowturn'),('rev10','rvcor20')]


def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str,
                                   allow_nan=False)+'\n', encoding='utf8')


def log(s):
    print(f'[{time.monotonic()-START:.1f}s] {s}', flush=True)


def load(family):
    axes = json.loads((SOURCE/('axes.json' if family=='target' else 'axes_formal.json')).read_text(encoding='utf8'))
    with np.load(SOURCE/('atoms.npz' if family=='target' else 'atoms_formal.npz')) as data:
        atoms = {k:data[k] for k in data.files if k not in ('target','market_cap')}
        y, cap = data['target'], data['market_cap']
    return atoms, y, cap, pd.DatetimeIndex(axes['dates']), axes


def matrix(atoms, dates, axes, augmented):
    names = list(FEATURES)
    shape = atoms['size'].shape
    count = len(names)+(len(PAIRS)*2+5 if augmented else 0)
    x = np.empty((shape[0],shape[1],count), np.float32)
    for j, name in enumerate(names):
        x[:,:,j] = atoms[name]
    if augmented:
        for a,b in PAIRS:
            j = len(names)
            names += [f'grp5_{a}_by_{b}', f'product_{a}_{b}']
            x[:,:,j] = prior.old.group_transform(atoms[a],atoms[b],5,'rank')
            x[:,:,j+1] = atoms[a]*atoms[b]
        peeraxes = json.loads((PEER/'signal_axes.json').read_text(encoding='utf8'))
        assert peeraxes['symbols'] == axes['symbols']
        positions = pd.DatetimeIndex(peeraxes['dates']).get_indexer(dates)
        assert np.all(positions>=0)
        raw = np.load(PEER/'signal_panels.npy',mmap_mode='r')
        prg = prior.old.rank(raw[0,positions,:])
        peer = prior.old.rank(raw[1,positions,:])
        j = len(names)
        names += ['prg20','peer20','prg20_x_vol20','prg20_x_lowturn','grp5_prg20_by_vol20']
        x[:,:,j],x[:,:,j+1] = prg,peer
        x[:,:,j+2] = prg*atoms['vol20']
        x[:,:,j+3] = prg*atoms['lowturn']
        x[:,:,j+4] = prior.old.group_transform(prg,atoms['vol20'],5,'rank')
    assert len(names)==count
    # Centered-rank zero imputation is fixed a priori, not fitted over time.
    np.nan_to_num(x,copy=False,nan=0.,posinf=0.,neginf=0.)
    prior.base.memory_guard()
    return x.reshape(-1,count), names


def metric(signal,y,cap):
    valid = np.isfinite(signal)&np.isfinite(y)&np.isfinite(cap)
    coverage = valid.sum(1)/np.maximum((np.isfinite(y)&np.isfinite(cap)).sum(1),1)
    assert np.all(coverage >= .95)
    rho = prior.old.rowcorr(prior.old.rank(np.where(valid,signal,np.nan)),
                            prior.old.rank(np.where(valid,y,np.nan)))
    assert np.all(np.nanstd(np.where(valid,signal,np.nan),axis=1)>1e-9)
    s = seat_stats(rho)
    v = np.array([s.ic_mean,s.icir,s.win_rate])
    return dict(rank_ic=float(v[0]),rank_ir=float(v[1]),wins=int((rho>.02).sum()),
                win_rate=float(v[2]),s_i=s.s_i_a,periods=len(rho),
                loss=float(np.sum(((v-prior.TARGET)/np.array([.001,.01,1/119]))**2))),rho


def predict(model, x, cap, trees=None):
    result = model.predict(x,num_iteration=trees,num_threads=1).reshape(cap.shape).astype(np.float32)
    result[~np.isfinite(cap)] = np.nan
    return result


def fit_model(kind, x, y, cap, dates, axes, full):
    valid = np.isfinite(y)&np.isfinite(cap)
    if not full:
        # Purge forward returns crossing the declared training cutoff.
        exits = pd.DatetimeIndex(axes['exits'])
        take = (dates<='2023-12-31')&(exits<='2023-12-31')
        valid &= take[:,None]
    ix = valid.ravel()
    target = prior.old.rank(np.where(valid,y,np.nan))[valid]
    weights = np.broadcast_to(1/np.maximum(valid.sum(1),1)[:,None],valid.shape)[valid]
    weights *= len(weights)/weights.sum()
    params = dict(learning_rate=.035, max_bin=63, num_threads=1,verbosity=-1,
                  seed=20261017, deterministic=True,force_col_wise=True,
                  feature_fraction=.85,lambda_l2=15.,min_data_in_leaf=300,
                  num_leaves=63 if kind=='rank_regression' else 31)
    if kind=='listwise_ranking':
        params.update(objective='rank_xendcg',metric='None',label_gain=list(range(16)))
        labels = np.minimum(np.floor((target+.5)*16),15).astype(int)
        counts = valid.sum(1)
        groups = counts[counts>0].tolist()
    else:
        params.update(objective='regression',metric='None')
        labels,groups = target,None
    rounds = 2400 if full else 800
    dataset = lgb.Dataset(x[ix],label=labels,weight=weights,group=groups,free_raw_data=True)
    def progress(env):
        if (env.iteration+1)%300==0:
            prior.base.memory_guard()
            log(f'{kind} {"full fit" if full else "temporal control"} trees {env.iteration+1}/{rounds}')
    model = lgb.train(params,dataset,num_boost_round=rounds,callbacks=[progress])
    del dataset,weights,target,labels
    gc.collect()
    return model


def output_periods(candidate,family,signal,y,cap,dates):
    windows = [(family, np.ones(len(dates),bool))]
    if family=='formal_5y':
        windows += [('recent_2026', dates>='2026-01-01')]
    if candidate.startswith('TEMP_'):
        windows += [(family+'_temporal_validation_2024_2025', (dates>='2024-01-01')&(dates<'2026-01-01')),
                    (family+'_temporal_2026', dates>='2026-01-01')]
    rows=[]
    for window,mask in windows:
        p = prior.base.periods(signal[mask],y[mask],dates[mask],cap[mask])
        p.to_csv(OUT/f'{candidate}_{window}_periods.csv',index=False)
        s = seat_stats(p.rank_ic)
        rows.append(dict(candidate=candidate,window=window,rank_ic=float(p.rank_ic.mean()),
            rank_ir=s.icir,wins=int((p.rank_ic>.02).sum()),win_rate=s.win_rate,s_i=s.s_i_a,
            **{k:v for k,v in prior.base.summarize(p).items() if k!='rank_ic'}))
    return rows


def blend(parts,y,cap):
    valid = np.isfinite(y)&np.isfinite(cap)
    ranked_y = prior.old.rank(np.where(valid,y,np.nan))
    panels = [prior.old.rank(p) for p in parts]
    trace=[]
    def assess(w):
        signal = sum(float(c)*np.nan_to_num(p,nan=0.) for c,p in zip(w,panels))
        signal[~np.isfinite(cap)] = np.nan
        rho = prior.old.rowcorr(prior.old.rank(np.where(valid,signal,np.nan)),ranked_y)
        m,std=float(rho.mean()),float(rho.std(ddof=0))
        wins=int((rho>.02).sum()); ir=m/max(std,1e-10)
        v=np.array([m,ir,wins/len(rho)])
        loss=float(np.sum(((v-prior.TARGET)/np.array([.001,.01,1/119]))**2))
        row=dict(call=len(trace)+1,weights=np.asarray(w).tolist(),loss=loss,rank_ic=m,rank_ir=ir,wins=wins)
        trace.append(row)
        if len(trace)%100==0:
            prior.base.memory_guard()
            save('blend_progress.json',dict(calls=len(trace),best=min(trace,key=lambda r:r['loss']),memory=prior.base.PEAK))
            log(f'Global coefficient search {len(trace)}, best {min(trace,key=lambda r:r["loss"])}')
        return loss
    # All coefficients are shared by all dates/stocks. No date-conditioned
    # label weights or post-hoc manipulation of individual periods.
    def objective(w):
        return assess(np.array([*w[:3],w[3],w[4],w[5]]))
    result=differential_evolution(objective,[(0,2)]*3+[(-2,2)]*3,
        seed=20261018,maxiter=24,popsize=5,polish=False,tol=1e-6,workers=1)
    best=min(trace,key=lambda r:r['loss'])
    # Preserve every sampled vector, including failed-to-match outcomes.
    with (OUT/'blend_trials.jsonl').open('w',encoding='utf8') as f:
        for row in trace:
            f.write(json.dumps(row)+'\n')
    final=sum(w*np.nan_to_num(p,nan=0.) for w,p in zip(best['weights'],panels)).astype(np.float32)
    final[~np.isfinite(cap)]=np.nan
    return final,best


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'metadata.json').exists():
        raise FileExistsError('Preserve completed experiment')
    prior.base.OUT=OUT
    threading.Thread(target=prior.base.watchdog,daemon=True).start()
    save('plan.json',dict(methods=KINDS,target=prior.TARGET.tolist(),stages=STAGES,
        full_fit='all119 historical labels; numerical fit only',temporal_control='train labels exit<=20231231, fixed800trees',
        blend='six global coefficients; 30x25 draws; full-window numerical fitting',
        rule=ALIGNMENT_RULE_VERSION,platform_cost=0,finalists=3,
        no_date_or_symbol_inputs=True,no_future_inputs=True,no_per_date_label_fitted_weights=True,
        memory=dict(process_gib=2.25,available_floor_gib=1.25,threads=1),
        success='RankIC abs error<=.001, IR abs error<=.01 and wins111/119; predictor audit required',
        counterfactual_only='temporal controls use researched historical data, not pristine OOS'))
    atoms,y,cap,dates,axes=load('target')
    progress,chosen,rawparts,rows,controls=[],[],[],[],[]
    for kind in KINDS:
        aug=kind=='peer_group_regression'
        x,names=matrix(atoms,dates,axes,aug)
        log(f'Train {kind}, input {x.shape}')
        checkpoint=OUT/f'{kind}_full2400.txt'
        if checkpoint.exists():
            model=lgb.Booster(model_file=str(checkpoint))
        else:
            model=fit_model(kind,x,y,cap,dates,axes,True)
            model.save_model(str(checkpoint))
        cumulative=np.zeros(len(x),float)
        previous=0
        for trees in STAGES:
            # Each tree is predicted only once. Regression and rank_xendcg
            # have identity prediction links, so tree chunks are additive.
            cumulative += model.predict(x,start_iteration=previous,
                num_iteration=trees-previous,raw_score=True,num_threads=1)
            previous=trees
            signal=cumulative.reshape(cap.shape).astype(np.float32)
            signal[~np.isfinite(cap)]=np.nan
            stat,_=metric(signal,y,cap)
            progress.append(dict(kind=kind,trees=trees,**stat))
            log(f'{kind} {trees}: RankIC={stat["rank_ic"]:.6f}, IR={stat["rank_ir"]:.6f}, wins={stat["wins"]}/119')
            save('stages.json',progress)
        del cumulative
        best=max([r for r in progress if r['kind']==kind],key=lambda r:r['rank_ir'])
        trees=best['trees']
        model.save_model(str(OUT/f'{kind}.txt'),num_iteration=trees)
        signal=predict(model,x,cap,trees)
        rawparts.append(signal)
        chosen.append(dict(kind=kind,trees=trees,features=names,augmented=aug,raw_metrics=best))
        rows+=output_periods(kind,'target_119_fit',signal,y,cap,dates)
        np.save(OUT/f'{kind}_target_signals.npy',signal)
        # Separate, fixed-budget chronological model; not initialized from
        # all-window trained model, and never trained on 2024+ labels.
        del model
        gc.collect()
        temp=fit_model(kind,x,y,cap,dates,axes,False)
        temp.save_model(str(OUT/f'TEMP_{kind}.txt'))
        tx=predict(temp,x,cap)
        rows+=output_periods('TEMP_'+kind,'target_119_fit',tx,y,cap,dates)
        np.save(OUT/f'TEMP_{kind}_target_signals.npy',tx)
        controls.append(dict(kind=kind,trees=800,training_cutoff='2023-12-31'))
        del temp,x,tx
        gc.collect()
    fitted,best=blend(rawparts+[-atoms['vol60'],atoms['rev6'],atoms['size']],y,cap)
    np.save(OUT/'FM_RB_BLEND_target_signals.npy',fitted)
    rows+=output_periods('FM_RB_BLEND','target_119_fit',fitted,y,cap,dates)
    save('models_frozen.json',dict(models=chosen,temporal_controls=controls,
        blend=best,blend_order=list(KINDS)+['-vol60','rev6','size'],
        statement='full models and blend in-sample; temporal controls use cutoff-only model training'))
    del atoms,y,cap,fitted,rawparts
    gc.collect()
    atoms,y,cap,dates,axes=load('formal')
    formal_parts=[]
    for m in chosen:
        x,names=matrix(atoms,dates,axes,m['augmented'])
        assert names==m['features']
        model=lgb.Booster(model_file=str(OUT/f'{m["kind"]}.txt'))
        signal=predict(model,x,cap)
        np.save(OUT/f'{m["kind"]}_formal_signals.npy',signal)
        formal_parts.append(signal)
        rows+=output_periods(m['kind'],'formal_5y',signal,y,cap,dates)
        temp=lgb.Booster(model_file=str(OUT/f'TEMP_{m["kind"]}.txt'))
        tx=predict(temp,x,cap)
        np.save(OUT/f'TEMP_{m["kind"]}_formal_signals.npy',tx)
        rows+=output_periods('TEMP_'+m['kind'],'formal_5y',tx,y,cap,dates)
        log(f'Formal and recent output saved: {m["kind"]}')
        del model,temp,x,tx
        gc.collect()
    pparts=formal_parts+[-atoms['vol60'],atoms['rev6'],atoms['size']]
    fitted=sum(w*np.nan_to_num(prior.old.rank(p),nan=0.) for w,p in zip(best['weights'],pparts)).astype(np.float32)
    fitted[~np.isfinite(cap)]=np.nan
    np.save(OUT/'FM_RB_BLEND_formal_signals.npy',fitted)
    rows+=output_periods('FM_RB_BLEND','formal_5y',fitted,y,cap,dates)
    pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)
    save('metadata.json',dict(status='complete',rule=ALIGNMENT_RULE_VERSION,seconds=time.monotonic()-START,
        memory=prior.base.PEAK,platform_cost=0,target=prior.TARGET.tolist(),best=best,
        success=abs(best['rank_ic']-prior.TARGET[0])<=.001 and abs(best['rank_ir']-prior.TARGET[1])<=.01 and best['wins']==111,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        warning='fit labels used full window; cannot submit or claim historical tradability',
        original_formula_recovered=False,inferred_target_dates=True))
    prior.base.DONE.set()
    log('ROUND TWO FIT AND TEMPORAL CONTROLS COMPLETE')


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()
