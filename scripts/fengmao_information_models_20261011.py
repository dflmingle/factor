"""Test incremental predictive content of newly built causal information atoms.

Two predeclared regularized families. Choose on purged core/development only,
refit before holdout boundary, freeze weights/models, then report all windows.
"""
from __future__ import annotations
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import gc, hashlib, json, threading, time
from pathlib import Path
import numpy as np, pandas as pd
from threadpoolctl import threadpool_limits
import fengmao_information_shock_20261011 as info
import lightgbm as lgb

shared=info.shared
ROOT=info.ROOT
OUT=ROOT/'research_reports/platform_alignment/fengmao-information-models-20261011'


def matrix(scope):
    context,y,cap,dates,axes=shared.prior.load(scope)
    union=pd.DatetimeIndex(json.loads((info.OUT/'axes.json').read_text(encoding='utf8'))['dates'])
    ix=union.get_indexer(dates)
    names=['ctx_'+k for k in sorted(context)]
    with np.load(info.OUT/'atoms_raw.npz') as z:
        raw=[k for k in z.files if k not in ('size','delta3close')]
        names += ['raw_'+k for k in raw]
        x=np.zeros((len(dates),len(axes['symbols']),len(names)),np.float32)
        for j,k in enumerate(sorted(context)): x[:,:,j]=context[k]
        offset=len(context)
        for j,k in enumerate(raw): x[:,:,offset+j]=shared.rank(z[k][ix])
    np.nan_to_num(x,copy=False,nan=0.,posinf=0.,neginf=0.)
    del context
    gc.collect(); shared.guard()
    return x,names,y,cap,dates,axes


def fit(x,y,cap,mask,leaves,rounds):
    valid=np.isfinite(y)&np.isfinite(cap)&mask[:,None]
    target=shared.rank(np.where(valid,y,np.nan))[valid]
    w=np.broadcast_to(1/np.maximum(valid.sum(1),1)[:,None],valid.shape)[valid]
    w*=len(w)/w.sum()
    data=lgb.Dataset(x[valid],label=target,weight=w,free_raw_data=True)
    model=lgb.train(dict(objective='regression',learning_rate=.03,num_leaves=leaves,max_depth=5,
        max_bin=31,min_data_in_leaf=1000,lambda_l2=50,feature_fraction=.85,num_threads=1,
        seed=20261081,verbosity=-1,deterministic=True,force_col_wise=True),data,num_boost_round=rounds)
    del data,target,w
    gc.collect(); shared.guard()
    return model


def predict(model,x,cap):
    if model['family']=='ridge':
        return shared.predict_linear(x,np.array(model['coefficients']),cap)
    booster=lgb.Booster(model_file=str(OUT/(model['name']+'.txt')))
    result=booster.predict(x.reshape(-1,x.shape[-1]),num_threads=1).reshape(cap.shape).astype(np.float32)
    result[~np.isfinite(cap)]=np.nan
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen_candidates.json').exists(): raise RuntimeError('No post-freeze tuning')
    shared.OUT=OUT
    threading.Thread(target=shared.watchdog,daemon=True).start()
    shared.validate_alignment_config(shared.alignment_config_snapshot())
    start=time.monotonic()
    with threadpool_limits(limits=1):
        x,names,y,cap,dates,axes=matrix('target')
        exits=pd.DatetimeIndex(axes['exits'])
        core=(dates<shared.DEVELOP_START)&(exits<shared.DEVELOP_START)
        dev=(dates>=shared.DEVELOP_START)&(dates<shared.FINAL_START)&(exits<shared.FINAL_START)
        refit=(dates<shared.FINAL_START)&(exits<shared.FINAL_START)
        shared.write('protocol.json',dict(rule=shared.ALIGNMENT_RULE_VERSION,features=names,feature_count=len(names),
            core_dates=dates[core].astype(str).tolist(),development_dates=dates[dev].astype(str).tolist(),
            refit_dates=dates[refit].astype(str).tolist(),refit_exit_dates=exits[refit].astype(str).tolist(),
            final_start=str(shared.FINAL_START),final_used_for_selection=False,final_previously_exposed=True,
            ridge_alphas=[.0001,.001,.01,.1,1.],tree_leaves=[3,7,15],tree_rounds=[100,200,400],
            seed=20261081,platform_cost=0,fixed_nan_fill='centered rank zero at each date',
            hypothesis='new raw information shock atoms add prediction beyond prior 60-feature causal basis',
            public_target='joint RankIC/population IR/win proxy; exact opponent IC provenance unavailable'))
        g,r=shared.normal_equations(x,y,cap,core)
        trials=[]
        for alpha in (.0001,.001,.01,.1,1.):
            w=shared.coefficients(g,r,alpha); s=shared.predict_linear(x[dev],w,cap[dev])
            m,_,_=shared.metrics(s,y[dev],cap[dev],dates[dev])
            trials.append(dict(alpha=alpha,selection_loss=shared.objective(m),**m))
            shared.log(f'information ridge {alpha}: development IC {m["rank_ic"]:.6f}, IR {m["rank_ir"]:.3f}')
        shared.write('ridge_trials.json',trials)
        best=min(trials,key=lambda m:m['selection_loss'])
        g,r=shared.normal_equations(x,y,cap,refit); w=shared.coefficients(g,r,best['alpha'])
        frozen=[dict(name='FM_INFO_RIDGE',family='ridge',features=names,coefficients=w.tolist(),selection=best)]
        trials=[]
        for leaves in (3,7,15):
            booster=fit(x,y,cap,core,leaves,400)
            for rounds in (100,200,400):
                s=booster.predict(x[dev].reshape(-1,len(names)),num_iteration=rounds,num_threads=1).reshape(cap[dev].shape).astype(np.float32)
                s[~np.isfinite(cap[dev])]=np.nan
                m,_,_=shared.metrics(s,y[dev],cap[dev],dates[dev])
                trials.append(dict(leaves=leaves,rounds=rounds,selection_loss=shared.objective(m),**m))
                shared.log(f'information tree {leaves}/{rounds}: development IC {m["rank_ic"]:.6f}, IR {m["rank_ir"]:.3f}')
            del booster
            gc.collect(); shared.guard()
        shared.write('tree_trials.json',trials)
        best=min(trials,key=lambda m:m['selection_loss'])
        booster=fit(x,y,cap,refit,best['leaves'],best['rounds'])
        booster.save_model(str(OUT/'FM_INFO_TREE.txt'))
        frozen.append(dict(name='FM_INFO_TREE',family='tree',features=names,selection=best))
        shared.write('frozen_candidates.json',dict(frozen_before_final_labels=True,candidates=frozen))
        shared.write('freeze_hashes.json',dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            frozen=hashlib.sha256((OUT/'frozen_candidates.json').read_bytes()).hexdigest(),
            tree=hashlib.sha256((OUT/'FM_INFO_TREE.txt').read_bytes()).hexdigest()))
        del booster
        rows=[]
        for scope in ('target','formal'):
            if scope=='formal':
                del x,y,cap; gc.collect()
                x,fn,y,cap,dates,axes=matrix(scope); assert fn==names
            for model in frozen:
                s=predict(model,x,cap)
                np.save(OUT/f'{model["name"]}_{scope}_signals.npy',s)
                windows=[('target119',np.ones(len(dates),bool)),('historical_final24',dates>=shared.FINAL_START)] if scope=='target' else [
                    ('formal_5y',np.ones(len(dates),bool)),('formal_final',dates>=shared.FINAL_START),('recent_2026',dates>=pd.Timestamp('2026-01-01'))]
                for window,mask in windows:
                    m,p,d=shared.metrics(s[mask],y[mask],cap[mask],dates[mask])
                    p.to_csv(OUT/f'{model["name"]}_{window}_periods.csv',index=False)
                    d.to_csv(OUT/f'{model["name"]}_{window}_groups.csv',index=False)
                    rows.append(dict(candidate=model['name'],window=window,**m))
                    shared.log(f'{model["name"]} {window}: IC {m["rank_ic"]:.6f}, IR {m["rank_ir"]:.3f}, wins {m["wins"]}/{m["periods"]}')
                # Test frozen inference prefixes; training causality is audited
                # separately via the purged refit exit dates above.
                for cutoff in ('2024-06-28','2025-06-30'):
                    prefix=dates<=cutoff
                    rebuilt=predict(model,x[prefix],cap[prefix])
                    assert np.array_equal(rebuilt,s[prefix],equal_nan=True)
            shared.guard()
        pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)
    shared.STOP.set()
    shared.write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,rule=shared.ALIGNMENT_RULE_VERSION,
        seconds=time.monotonic()-start,memory=shared.PEAK,candidate_checkpoints=14,
        final_previously_exposed=True,final_used_for_selection=False,causal_frozen_prefix_max_difference=0.))
    shared.log('information-content models complete; recovery not established')


if __name__=='__main__': main()
