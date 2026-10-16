"""Strict quarterly walk-forward control: original frozen shallow tree contract.

Preserves the original 60 raw features and LightGBM parameters (3 leaves,
200 trees selected from the original 400-round training configuration). Only
training is changed: each quarter is fitted using labels whose exit date is
strictly before that quarter's first signal. No platform calls.
"""
from __future__ import annotations
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import ast, gc, hashlib, json, pickle, sys, time, importlib.util
from types import SimpleNamespace
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
from scipy.stats import rankdata

EXPERIMENT=Path(__file__).resolve().parent; ROOT=EXPERIMENT.parents[2]
HERE=EXPERIMENT/'train94-impute0'
sys.path.insert(0,str(ROOT/'scripts'))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from platform_score_rules import raw_c_value, score_nc
_simple_path=ROOT/'research_reports/platform_alignment/nonlinear-walkforward-20261012/run.py'
_spec=importlib.util.spec_from_file_location('simple_wf',_simple_path); simple=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(simple)

MARKET=ROOT/'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl'
SOURCE=ROOT/'research_reports/platform_alignment/fengmao-nested-causal-20261011'
START=time.monotonic()
FEATURES=tuple(json.loads((SOURCE/'frozen_candidates.json').read_text())['candidates'][1]['features'])
PARAMS=dict(objective='regression',learning_rate=.03,num_leaves=3,max_depth=3,max_bin=31,
            min_data_in_leaf=1000,lambda_l2=50.,feature_fraction=.85,seed=20261023,
            num_threads=1,verbosity=-1,deterministic=True,force_col_wise=True)
TREES=200


def log(x): print(f'[{time.monotonic()-START:.1f}s] {x}',flush=True)
def write(name,obj):
    def c(x):
        if isinstance(x,dict): return {str(k):c(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)): return [c(v) for v in x]
        if isinstance(x,(np.integer,np.bool_)): return x.item()
        if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
        if isinstance(x,(pd.Timestamp,pd.Period)): return str(x)
        return x
    (HERE/name).write_text(json.dumps(c(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def extract_original():
    """Extract only the three original atom builders; never run their mains."""
    def one(filename,names):
        tree=ast.parse((ROOT/'scripts'/filename).read_text())
        nodes=[n for n in tree.body if
            (isinstance(n,ast.FunctionDef) and n.name in names) or
            (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)) or
            (isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id in names)]
        env=dict(np=np,pd=pd,gc=gc,rankdata=rankdata,memory_guard=lambda:None,
                 base=type('B',(),{'memory_guard':staticmethod(lambda:None)})())
        exec(compile(ast.Module(body=nodes,type_ignores=[]),filename,'exec'),env)
        return env
    b=one('fengmao_group_gp_20261011.py',{'ATOMS','rank','build_atoms'})
    l=one('fengmao_multiround_20261011.py',{'LONG_ATOMS','rank','long_atoms'})
    n=one('fengmao_new_atoms_20261011.py',{'NEW_NAMES','build_new_atoms'})
    n['old']=SimpleNamespace(rank=l['rank'],base=l['base'])
    return b,l,n


def build_atoms(fields,positions):
    b,l,n=extract_original()
    out=b['build_atoms'](fields,positions); out.update(l['long_atoms'](fields,positions)); out.update(n['build_new_atoms'](fields,positions))
    missing=set(FEATURES)-set(out)
    if missing: raise RuntimeError(f'missing original features: {sorted(missing)}')
    return {k:out[k] for k in FEATURES}


def fit(x,y,cap,train):
    ok=np.isfinite(y)&np.isfinite(cap)&train[:,None]
    label=simple.rank(np.where(ok,y,np.nan))[ok]
    w=np.broadcast_to(1/np.maximum(ok.sum(1),1)[:,None],ok.shape)[ok];w*=len(w)/w.sum()
    model=lgb.train(PARAMS,lgb.Dataset(x[ok],label=label,weight=w),num_boost_round=TREES)
    return model


def train_mask(dates,exits,boundary):
    eligible=(dates<boundary)&(exits<boundary)
    ids=np.flatnonzero(eligible)[-94:]
    if len(ids)<48: raise RuntimeError('insufficient causal history')
    out=np.zeros(len(dates),bool);out[ids]=True;return out


def walk(x,y,cap,dates,exits,evaluation):
    sig=np.full(cap.shape,np.nan,np.float32);folds=[]
    for q in sorted(dates[evaluation].to_period('Q').unique()):
        test=evaluation&(dates.to_period('Q')==q); boundary=dates[test].min();train=train_mask(dates,exits,boundary)
        model=fit(x,y,cap,train); pred=model.predict(np.nan_to_num(x[test],nan=0.).reshape(-1,x.shape[-1]),num_threads=1).reshape((test.sum(),cap.shape[1])).astype(np.float32)
        pred[~np.isfinite(cap[test])]=np.nan; sig[test]=pred
        path=HERE/'models'/f'FM_SHALLOW_{q}.txt';model.save_model(str(path))
        info=dict(fold=str(q),test_first=dates[test].min(),test_last=dates[test].max(),test_periods=int(test.sum()),
                  train_periods=int(train.sum()),train_first=dates[train].min(),train_last=dates[train].max(),
                  latest_training_label_exit=exits[train].max(),model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if len(folds)==0:
            altered=y.copy();altered[~train]=12345.;check=fit(x,altered,cap,train)
            chk=check.predict(np.nan_to_num(x[test],nan=0.).reshape(-1,x.shape[-1]),num_threads=1).astype(np.float32)
            chk=chk.reshape(pred.shape);chk[~np.isfinite(cap[test])]=np.nan
            np.testing.assert_array_equal(chk,pred)
            info['unavailable_label_perturbation']='PASS: bitwise equal including active-stock mask'
        folds.append(info);log(f'{q}: train={train.sum()} through {exits[train].max().date()} test={test.sum()}')
    return sig[evaluation],folds


def main():
    (HERE/'models').mkdir(parents=True,exist_ok=True)
    if (HERE/'protocol.json').exists(): raise RuntimeError('refuse overwrite')
    config=alignment_config_snapshot();validate_alignment_config(config)
    protocol=dict(model='original FM_CAUSAL_SHALLOW',registered_features=60,features=list(FEATURES),
                  leaves=3,trees=200,training_parameters=PARAMS,quarterly_refit=True,
                  train_history_periods=94,min_train_periods=48,label_exit_strict=True,
                  formal=['20210907','20260907'],recent=['20260101','latest local'],data_start='20180101',
                  no_parameter_search=True,platform_runs=0,paid_compute=0,rule_version=ALIGNMENT_RULE_VERSION,
                  caveat='Historical window was previously viewed; this is strict temporal validation, not a pristine blind holdout.')
    write('protocol.json',protocol)
    with MARKET.open('rb') as f: calendar,stocks,fields=pickle.load(f)
    calendar=pd.DatetimeIndex(calendar);stocks=pd.Index(stocks)
    fields={k:fields[k] for k in ('close','open','volume','turnover','cap')}
    active=(fields['cap']>0)&np.isfinite(fields['turnover']);fields['cap'][~active]=np.nan
    for k in ('close','open','volume'):fields[k][~active|(fields[k]<=0)]=np.nan
    fields['close']=pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    formal=pd.DatetimeIndex(json.loads((ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2/metadata.json').read_text())['signal_dates'])
    anchor=calendar.get_loc(formal[0]);positions=np.arange(anchor%10,len(calendar)-11,10);positions=positions[calendar[positions]>='2019-01-01']
    dates=calendar[positions];exits=calendar[positions+11];evaluation=(dates>='2021-09-07')&(dates<='2026-09-07');assert dates[evaluation].equals(formal)
    cap=fields['cap'][positions];y=(fields['close'][positions+11].astype(float)/fields['close'][positions+1]-1).astype(np.float32);y[~np.isfinite(cap)|~np.isfinite(y)]=np.nan
    log(f'building exact original 60 atoms: {len(dates)} training/test signal periods x {len(stocks)} stocks')
    atoms=build_atoms(fields,positions)
    # Causal feature prefix check using the original builders.
    for cutoff in ('2023-06-30','2025-06-30'):
        last=calendar.searchsorted(pd.Timestamp(cutoff),side='right');sel=positions[positions<last][-3:];part={k:v[:last] for k,v in fields.items()};small=build_atoms(part,sel);idx=np.flatnonzero(np.isin(positions,sel))
        for k in FEATURES:np.testing.assert_array_equal(small[k],atoms[k][idx])
    write('verification.json',dict(prefix_feature_check='PASS',prefix_cutoffs=['2023-06-30','2025-06-30'],feature_count=60))
    x=np.nan_to_num(np.stack([atoms[k] for k in FEATURES],axis=-1),nan=0.)
    # Verify the unchanged feature pipeline reproduces original frozen scores.
    frozen=lgb.Booster(model_file=str(SOURCE/'FM_CAUSAL_SHALLOW.txt'))
    frozen_sig=frozen.predict(x[evaluation].reshape(-1,len(FEATURES)),num_threads=1).reshape(cap[evaluation].shape).astype(np.float32)
    frozen_sig[~np.isfinite(cap[evaluation])]=np.nan
    frozen_stats,_,_=simple.metrics(frozen_sig,y[evaluation],cap[evaluation],dates[evaluation])
    write('frozen_reproduction.json',frozen_stats)
    sig,folds=walk(x,y,cap,dates,exits,evaluation)
    np.save(HERE/'signal.npy',sig)
    eval_dates=dates[evaluation];eval_cap=cap[evaluation];eval_y=y[evaluation]
    rows=[]
    for window,mask in (('formal_5y',np.ones(len(eval_dates),bool)),('recent_2026',eval_dates>='2026-01-01')):
        stats,p,g=simple.metrics(sig[mask],eval_y[mask],eval_cap[mask],eval_dates[mask]);p.to_csv(HERE/f'periods_{window}.csv',index=False);g.to_csv(HERE/f'groups_{window}.csv',index=False)
        daily,monthly,turns=simple.daily_path(sig[mask],eval_y[mask],eval_cap[mask],eval_dates[mask],calendar,fields['close']);daily.to_csv(HERE/f'daily_{window}.csv');monthly.to_csv(HERE/f'monthly_{window}.csv',index=False);turns.to_csv(HERE/f'turnover_{window}.csv',index=False);stats.update(simple.nav_metrics(daily));rows.append(dict(window=window,**stats))
    pd.DataFrame(rows).to_csv(HERE/'results.csv',index=False);write('folds.json',folds)
    # Compare against the saved shallow tree's 60-feature contract, linearity,
    # existing pool seats and nearest historical clusters.
    baseline=simple.baseline_panels(eval_dates,stocks)
    common=np.logical_and.reduce([np.isfinite(v) for v in baseline.values()])&np.isfinite(eval_cap)
    base=sum(baseline.values())/5; base[~common]=np.nan
    pool_rows=[]
    for window,mask in (('formal_5y',np.ones(len(eval_dates),bool)),('recent_2026',eval_dates>='2026-01-01')):
        bstats,_,_=simple.metrics(base[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])
        bneu,_,_=simple.metrics(simple.size_neutral(base[mask],eval_cap[mask]),eval_y[mask],eval_cap[mask],eval_dates[mask])
        bd,bm,_=simple.daily_path(base[mask],eval_y[mask],eval_cap[mask],eval_dates[mask],calendar,fields['close'])
        value=sig.copy();value[~common]=np.nan;added=(base*5+simple.normalized(value))/6
        stats,_,_=simple.metrics(added[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])
        neu,_,_=simple.metrics(simple.size_neutral(added[mask],eval_cap[mask]),eval_y[mask],eval_cap[mask],eval_dates[mask])
        daily,monthly,_=simple.daily_path(added[mask],eval_y[mask],eval_cap[mask],eval_dates[mask],calendar,fields['close'])
        pair=bm.merge(monthly,on='month',suffixes=('_base','_new'));pair=pair[~pair.partial_base&~pair.partial_new]
        pair['delta_E']=pair.rex_new-pair.rex_base;pair['delta_T']=pair.turnover_new-pair.turnover_base;pair['delta_NC']=pair.nc_new-pair.nc_base
        pair.to_csv(HERE/f'pool_monthly_{window}.csv',index=False)
        pool_rows.append(dict(window=window,base_net=bstats['net_excess'],added_net=stats['net_excess'],delta_net=stats['net_excess']-bstats['net_excess'],
            base_turn=bstats['turnover'],added_turn=stats['turnover'],base_corr_size=bstats['corr_size'],added_corr_size=stats['corr_size'],
            base_size_neutral_net=bneu['net_excess'],added_size_neutral_net=neu['net_excess'],
            size_guard=abs(stats['corr_size'])<=abs(bstats['corr_size']) and neu['net_excess']>=bneu['net_excess'],
            delta_E_mean=float(pair.delta_E.mean()),delta_T_mean=float(pair.delta_T.mean()),delta_NC_mean=float(pair.delta_NC.mean()),
            base_daily_max_dd=simple.nav_metrics(bd)['daily_net_nav_max_dd'],added_daily_max_dd=simple.nav_metrics(daily)['daily_net_nav_max_dd'],
            B='unavailable; no full deltaComb claim',scope='Archived-seat common-universe diagnostic only'))
    pd.DataFrame(pool_rows).to_csv(HERE/'pool_results.csv',index=False)
    corr=[]
    for name,v in baseline.items(): corr.append(dict(reference=name,rho=float(np.nanmean(simple.spearman(sig,v)))))
    pd.DataFrame(corr).to_csv(HERE/'seat_correlations.csv',index=False)
    refs=pd.read_csv(ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2/references.csv')
    u=pd.read_csv(ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2/new_unanchored_clusters.csv').rename(columns={'new_cluster':'cluster'});refs=pd.concat([refs,u[['name','cluster','panel_id']]])
    oldstocks=pd.Index(json.loads((ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2/metadata.json').read_text())['stock_ids']);mapped=stocks.get_indexer(oldstocks);out=[]
    for _,r in refs.iterrows():
        p=ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2/panels'/f'{r.panel_id}.npy'
        if not p.exists():continue
        old=np.load(p,mmap_mode='r');rho=simple.spearman(sig[:,mapped],old);out.append(dict(reference=r['name'],cluster=r['cluster'],panel_id=r.panel_id,rho=float(np.nanmean(rho)),abs_rho=float(abs(np.nanmean(rho)))))
    pd.DataFrame(out).sort_values('abs_rho',ascending=False).to_csv(HERE/'cluster_correlations.csv',index=False)
    verification=json.loads((HERE/'verification.json').read_text());verification.update(dict(folds=len(folds),all_training_exits_strictly_before_tests=all(pd.Timestamp(f['latest_training_label_exit'])<pd.Timestamp(f['test_first']) for f in folds),
        unavailable_labels_perturbation='PASS',elapsed_seconds=time.monotonic()-START,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    write('verification.json',verification);write('complete.json',dict(status='complete',platform_runs=0))
    log('complete')

if __name__=='__main__':main()
