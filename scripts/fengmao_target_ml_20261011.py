"""Global supervised target-fit alternative; all target periods are in-sample.

Forward returns are training labels only. Inputs never contain dates, symbols,
future returns or fitted per-date weights. This cannot certify live performance.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import copy
import gc
import hashlib
import json
from pathlib import Path
import pickle
import threading
import time
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
import fengmao_target_rankic_20261011 as expression

ROOT = expression.ROOT
SOURCE = expression.OUT
OUT = ROOT/'research_reports/platform_alignment/fengmao-target-ml-20261011'
START = time.monotonic()
TARGET = expression.TARGET
NAMES = sorted(['rev3','rev6','rev10','rev20','rev60','rev120','size','lowvolume1','lowvolume3',
    'lowvolume20','lowturn','lowturn60','lowturn120','vrel3','vrel20','vrel20long','trel6',
    'vol6','vol20','vol60','vol120','vol252','volshift20','vstab20',
    'idrev20','onrev20','tug20','tug60','idvol20','idvol60','onvol20','onvol60',
    'asym20','asym60','downshare20','downshare60','rvbreak','gapbreak','macd','macdhist','signedflow60'])


def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf8')


def log(s):
    print(f'[{time.monotonic()-START:.1f}s] {s}',flush=True)


def matrix(atoms):
    # Fixed zero imputation of missing same-date centered ranks. Restore cap/
    # turnover universe after prediction; no learned time-series imputation.
    return np.stack([np.nan_to_num(atoms[k],nan=0.) for k in NAMES],axis=-1).reshape(-1,len(NAMES))


def predict(bundle,atoms):
    a = matrix(atoms)
    signal = bundle['estimator'].predict(a).reshape(atoms['size'].shape).astype(np.float32)
    signal[~np.isfinite(atoms['size'])] = np.nan
    weights = bundle.get('weights')
    if weights is not None:
        parts = [expression.old.rank(signal),-atoms['vol60'],atoms['rev6'],atoms['asym20']]
        result = np.zeros_like(signal)
        valid = np.ones_like(signal,dtype=bool)
        for w,p in zip(weights,parts):
            if w!=0:
                result += w*np.nan_to_num(p,nan=0.)
                valid &= np.isfinite(p)
        result[~valid] = np.nan
        signal = result
    return signal


def stats(fit,x):
    return fit.assess_panel(x)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'metadata.json').exists():
        raise FileExistsError('Completed experiment')
    expression.base.OUT = OUT
    threading.Thread(target=expression.base.watchdog,daemon=True).start()
    save('plan.json',dict(method='one global histogram gradient boosting regressor + fixed coefficient DE',
        target=TARGET.tolist(),training='all119 target-period labels; no holdout claim',
        inputs=NAMES,date_or_symbol_inputs=False,future_features=False,
        no_per_date_fitted_parameters=True,stages=400,stage_step=10,max_leaf_nodes=15,
        min_samples_leaf=500,max_bins=63,learning_rate=.06,seed=20261015,
        de_draw_budget='population24, 36 generations, max888 objective calls',
        platform_cost=0,memory=dict(process_gib=2.25,available_floor_gib=1.25,chunk_stocks=192),
        cautions=['explicit supervised full-window numerical fit','not causal parameter learning at historical dates',
                  'does not recover opponent formula','formal/recent windows overlap fitted target period']))
    axes = json.loads((SOURCE/'axes.json').read_text(encoding='utf8'))
    dates = pd.DatetimeIndex(axes['dates'])
    with np.load(SOURCE/'atoms.npz') as saved:
        atoms = {k:saved[k] for k in saved.files if k not in ('target','market_cap')}
        y,cap = saved['target'],saved['market_cap']
    fit = expression.Fit(atoms,y,cap,dates)
    a = matrix(atoms)
    valid = np.isfinite(y)&np.isfinite(cap)&np.isfinite(atoms['size'])
    target_ranks = expression.old.rank(np.where(valid,y,np.nan))
    training = valid.ravel()
    # Equalize each date's aggregate training weight. No per-date prediction
    # adjustments are fitted; model coefficients and splitting rules are global.
    weights = np.broadcast_to((1/valid.sum(1))[:,None],y.shape)[valid]
    weights *= len(weights)/weights.sum()
    model = HistGradientBoostingRegressor(max_iter=400,learning_rate=.06,max_leaf_nodes=15,
        min_samples_leaf=500,max_bins=63,l2_regularization=50.,early_stopping=False,
        random_state=20261015,verbose=0)
    log(f'Fitting one global nonlinear model; matrix={a.shape}, labels={training.sum()}')
    with threadpool_limits(limits=1):
        model.fit(a[training],target_ranks.ravel()[training],sample_weight=weights)
    log('Model fit complete; scanning fixed tree prefixes')
    history,best = [],None
    with threadpool_limits(limits=1):
        for stage,pred in enumerate(model.staged_predict(a),1):
            if stage%10:
                continue
            signal = pred.reshape(y.shape).astype(np.float32)
            signal[~np.isfinite(atoms['size'])] = np.nan
            row = dict(stage=stage,**stats(fit,signal))
            history.append(row)
            save('stage_progress.json',history)
            if best is None or row['loss']<best['loss']:
                best = row
            if stage%50==0:
                log(f'Stage {stage}/400, RankIC={row["rank_ic"]:.4f}, IR={row["rank_ic_ir"]:.3f}, win={row["rank_ic_win"]:.3f}')
    assert best is not None
    # Selecting a fixed prefix is equivalent to training that number of trees.
    chosen = copy.deepcopy(model)
    chosen._predictors = chosen._predictors[:best['stage']]
    bundle = dict(estimator=chosen,input_atoms=NAMES,weights=None,chosen_stage=best['stage'])
    with threadpool_limits(limits=1):
        signal = predict(bundle,atoms)
    assert abs(stats(fit,signal)['loss']-best['loss'])<1e-5
    del model,a,target_ranks,weights
    gc.collect()
    parts = [expression.old.rank(signal),-atoms['vol60'],atoms['rev6'],atoms['asym20']]
    history_de = []
    def objective(w):
        expression.base.memory_guard()
        coefs = np.array([1.,*w])
        x = sum(c*np.nan_to_num(p,nan=0.) for c,p in zip(coefs,parts))
        valid_parts = np.logical_and.reduce([np.isfinite(p) for p in parts])
        x[~valid_parts] = np.nan
        try:
            row = dict(weights=coefs.tolist(),**stats(fit,x))
        except ValueError as exc:
            row = dict(weights=coefs.tolist(),loss=1e9,error=str(exc))
        history_de.append(row)
        with (OUT/'coefficient_search.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(row,allow_nan=False)+'\n')
        if len(history_de)%100==0:
            log(f'Global blend draw {len(history_de)}, minimum loss={min(r["loss"] for r in history_de):.6f}')
        return row['loss']
    de = differential_evolution(objective,[(-2,2)]*3,seed=20261016,maxiter=36,popsize=8,
                                polish=False,tol=1e-7,workers=1,updating='immediate')
    best_de = min(history_de,key=lambda row:row['loss'])
    bundle['weights'] = best_de['weights']
    with (OUT/'model.pkl').open('wb') as f:
        pickle.dump(bundle,f)
    save('model_frozen.json',dict(engine='global_histogram_boosting_fixed_rank_blend',input_atoms=NAMES,
        trees=best['stage'],weights=best_de['weights'],raw_model_metrics=best,target_fit_metrics=best_de,
        checkpoint_sha256=hashlib.sha256((OUT/'model.pkl').read_bytes()).hexdigest(),
        fitting='all119 dates; no independent holdout',predictor_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    with threadpool_limits(limits=1):
        final = predict(bundle,atoms)
    np.save(OUT/'FM_ML_target_signals.npy',final)
    p = expression.base.periods(final,y,dates,cap)
    p.to_csv(OUT/'FM_ML_target_periods.csv',index=False)
    # Verify fixed-expression prefix equality across the full A stock grid.
    prefix = dates<='2024-06-28'
    with threadpool_limits(limits=1):
        cut = predict(bundle,{k:v[prefix] for k,v in atoms.items()})
    assert np.array_equal(final[prefix],cut,equal_nan=True)
    save('expression_prefix_checks.json',dict(status='passed',cells=int(np.isfinite(cut).sum()),max_difference=0,
        limit='frozen estimator input-causality only; training used all dates'))
    rawstats = expression.base.summarize(p)
    target_stats = stats(fit,final)
    save('metadata.json',dict(status='complete',**target_stats,target=TARGET.tolist(),
        errors=(np.array([target_stats['rank_ic'],target_stats['rank_ic_ir'],target_stats['rank_ic_win']])-TARGET).tolist(),
        memory=expression.base.PEAK,seconds=time.monotonic()-START,de_calls=len(history_de),
        checkpoint_sha256=hashlib.sha256((OUT/'model.pkl').read_bytes()).hexdigest(),
        platform_cost=0,net_excess=rawstats['net_excess'],turnover=rawstats['turnover'],
        source=str(SOURCE.relative_to(ROOT)),causal_features=True,causal_historical_model_training=False,
        admission='full-window supervised in-sample numeric fit; cannot claim live reproduction'))
    expression.base.DONE.set()
    log('GLOBAL MODEL TARGET FIT COMPLETE')


if __name__=='__main__':
    main()
