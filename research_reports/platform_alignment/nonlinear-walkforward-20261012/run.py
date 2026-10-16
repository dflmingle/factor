"""Three predeclared, low-complexity quarterly walk-forward experiments.

Offline only. Writes exclusively to this isolated experiment directory.
No parameter search, full-window refit/backfill, platform calls or pool edits.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from platform_score_rules import raw_c_value, score_nc

CLUSTERS = ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2'
MARKET = ROOT/'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl'
SEATS = ['size_only', 'impact60', 't10_size_plus_impact_bm',
         'book_to_market_lf_minus_size', 'book_to_market_lf_plus_impact']
SPECS = [
    dict(name='NL01', mechanism='Reversal conditional on volatility and trading activity',
         features=['rev6','rev20','vol20','vol60','lowturn','vrel3'], target='rank_return'),
    dict(name='NL02', mechanism='Intraday/overnight disagreement conditional on overnight risk and flow',
         features=['rev20','idrev20','onrev20','tug20','onvol60','signedflow20','lowturn'], target='rank_return'),
    dict(name='NL03', mechanism='Learn return information beyond within-date size buckets',
         features=['rev6','rev20','vol20','vol60','lowturn','vrel3','tug20','signedflow20'],
         target='size_bucket_residual_rank_return'),
]
PARAMS = dict(objective='regression', learning_rate=.03, num_leaves=3, max_depth=2,
              max_bin=15, min_data_in_leaf=2500, lambda_l2=100., feature_fraction=1.,
              bagging_fraction=1., seed=20261012, num_threads=1, verbosity=-1,
              deterministic=True, force_col_wise=True)
TREES=60
STARTED=time.monotonic()


def log(message):
    print(f'[{time.monotonic()-STARTED:.1f}s] {message}', flush=True)


def write(name, value):
    def clean(x):
        if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)): return [clean(v) for v in x]
        if isinstance(x,(np.integer,np.bool_)): return x.item()
        if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
        if isinstance(x,(pd.Timestamp,pd.Period)): return str(x)
        return x
    (HERE/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def rank(x):
    n=np.isfinite(x).sum(1,keepdims=True)
    return (rankdata(x,axis=1,method='average',nan_policy='omit')/np.maximum(n,1)-.5).astype(np.float32)


def rowcorr(a,b):
    ok=np.isfinite(a)&np.isfinite(b)
    x=np.where(ok,a,np.nan).astype(float); y=np.where(ok,b,np.nan).astype(float)
    n=ok.sum(1)
    x-=np.nansum(x,axis=1)[:,None]/np.maximum(n[:,None],1)
    y-=np.nansum(y,axis=1)[:,None]/np.maximum(n[:,None],1)
    den=np.sqrt(np.nansum(x*x,axis=1)*np.nansum(y*y,axis=1))
    return np.divide(np.nansum(x*y,axis=1),den,out=np.full(len(a),np.nan),where=(den>0)&(n>=100))


def spearman(a,b):
    ok=np.isfinite(a)&np.isfinite(b)
    return rowcorr(rank(np.where(ok,a,np.nan)),rank(np.where(ok,b,np.nan)))


def features(fields, positions, wanted):
    """Daily causal recipes, then same-day ranks over currently active stocks."""
    result={k:np.full((len(positions),fields['close'].shape[1]),np.nan,np.float32) for k in wanted}
    for begin in range(0, fields['close'].shape[1], 192):
        sl=slice(begin,begin+192)
        c,o,v,t=[pd.DataFrame(fields[k][:,sl],dtype=float) for k in ('close','open','volume','turnover')]
        r=c/c.shift(1)-1; intra=c/o-1; night=o/c.shift(1)-1
        raw={
            'rev6':-(c/c.shift(6)-1), 'rev20':-(c/c.shift(20)-1),
            'vol20':r.rolling(20,min_periods=20).std(), 'vol60':r.rolling(60,min_periods=60).std(),
            'lowturn':-t.rolling(20,min_periods=20).mean(),
            'vrel3':v.rolling(3,min_periods=3).mean()/v.rolling(60,min_periods=60).mean(),
            'idrev20':-intra.rolling(20,min_periods=20).mean(),
            'onrev20':-night.rolling(20,min_periods=20).mean(),
            'tug20':(night-intra).rolling(20,min_periods=20).mean(),
            'onvol60':night.rolling(60,min_periods=60).std(),
            'signedflow20':-(r*np.log(v).diff()).rolling(20,min_periods=20).mean(),
        }
        for k in wanted: result[k][:,sl]=raw[k].iloc[positions].to_numpy(np.float32)
    active=np.isfinite(fields['cap'][positions])
    for k in result:
        result[k][~active|~np.isfinite(result[k])]=np.nan
        result[k]=rank(result[k])
    return result


def size_neutral(signal, cap, buckets=20):
    """Bucket-local rank centering, not mean subtraction on heavy-tailed values."""
    result=np.full_like(signal,np.nan,np.float32)
    for i in range(len(signal)):
        ids=np.flatnonzero(np.isfinite(signal[i])&np.isfinite(cap[i]))
        if len(ids)<100: continue
        ordered=ids[np.argsort(cap[i,ids],kind='stable')]
        groups=np.minimum(np.arange(len(ordered))*buckets//len(ordered),buckets-1)
        for b in range(buckets):
            selected=ordered[groups==b]
            result[i,selected]=(rankdata(signal[i,selected],method='average')-.5)/len(selected)-.5
    return result


def residual_label(y, cap):
    result=y.copy()
    for i in range(len(y)):
        ids=np.flatnonzero(np.isfinite(y[i])&np.isfinite(cap[i]))
        ordered=ids[np.argsort(cap[i,ids],kind='stable')]
        groups=np.minimum(np.arange(len(ordered))*20//len(ordered),19)
        for b in range(20):
            selected=ordered[groups==b]
            result[i,selected]-=result[i,selected].mean()
    return result


def fit(x,target,cap,train):
    ok=np.isfinite(target)&np.isfinite(cap)&train[:,None]
    rows=np.nan_to_num(x[ok],nan=0.0)
    weights=np.broadcast_to(1/np.maximum(ok.sum(1),1)[:,None],ok.shape)[ok]
    weights*=len(weights)/weights.sum()
    model=lgb.train(PARAMS,lgb.Dataset(rows,label=target[ok],weight=weights),num_boost_round=TREES)
    # Fixed ridge control, same features/target/training observations; no tuning.
    design=np.column_stack((np.ones(len(rows)), rows)).astype(float)
    gram=design.T@(design*weights[:,None])/weights.sum()
    rhs=design.T@(target[ok]*weights)/weights.sum()
    penalty=np.eye(design.shape[1])*.01; penalty[0,0]=0
    linear=np.linalg.solve(gram+penalty,rhs)
    return model,linear


def causal_training_mask(dates,exits,boundary):
    train=(dates<boundary)&(exits<boundary)
    ids=np.flatnonzero(train)[-72:]
    assert len(ids)>=48 and np.all(exits[ids]<boundary)
    result=np.zeros(len(dates),bool); result[ids]=True
    return result


def walkforward(x,target,cap,dates,exits,evaluation,spec):
    signal=np.full(cap.shape,np.nan,np.float32); linear_signal=signal.copy(); folds=[]
    for quarter in sorted(dates[evaluation].to_period('Q').unique()):
        tests=evaluation&(dates.to_period('Q')==quarter)
        boundary=dates[tests].min()
        train=causal_training_mask(dates,exits,boundary)
        model,linear=fit(x,target,cap,train)
        xx=np.nan_to_num(x[tests],nan=0.0)
        signal[tests]=model.predict(xx.reshape(-1,x.shape[-1]),num_threads=1).reshape(xx.shape[:2]).astype(np.float32)
        linear_signal[tests]=(linear[0]+xx@linear[1:]).astype(np.float32)
        signal[tests&~np.isfinite(cap).any(1)]=np.nan
        path=HERE/'models'/f'{spec["name"]}_{quarter}.txt'; model.save_model(str(path))
        info=dict(candidate=spec['name'],fold=str(quarter),test_first=dates[tests].min(),test_last=dates[tests].max(),
                  test_periods=int(tests.sum()),train_periods=int(train.sum()),train_first=dates[train].min(),
                  train_last=dates[train].max(),latest_training_label_exit=exits[train].max(),
                  model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        folds.append(info)
        # Counterfactual perturbation of all unavailable labels must leave the
        # first model unchanged. This tests the training path, not just inference.
        if len(folds)==1:
            altered=target.copy(); altered[~train]=12345.
            check,_=fit(x,altered,cap,train)
            pred=check.predict(xx.reshape(-1,x.shape[-1]),num_threads=1).astype(np.float32)
            assert np.array_equal(pred,signal[tests].ravel())
            info['unavailable_label_perturbation']='PASS: bitwise equal'
        log(f'{spec["name"]} {quarter}: train {train.sum()} periods through label exit {exits[train].max().date()}; test {tests.sum()}')
    signal[~np.isfinite(cap)]=np.nan; linear_signal[~np.isfinite(cap)]=np.nan
    return signal[evaluation],linear_signal[evaluation],folds


def metrics(signal,y,cap,dates):
    rows=[];prev=None
    rho=spearman(signal,y); size=spearman(signal,cap); ic=rowcorr(signal,y)
    groups=[]
    for i,date in enumerate(dates):
        valid=np.isfinite(signal[i])&np.isfinite(y[i])&np.isfinite(cap[i]); ids=np.flatnonzero(valid)
        assert len(ids)>=100
        ordered=ids[np.argsort(signal[i,ids],kind='stable')]
        bins=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
        chosen=ordered[bins==10]; members=set(chosen)
        turn=np.nan if prev is None else 1-len(prev&members)/len(members);prev=members
        ret=float(y[i,chosen].mean()); bench=float(y[i,ids].mean())
        rows.append(dict(date=date,rank_ic=rho[i],ic=ic[i],corr_size=size[i],turnover=turn,
                         gross_excess=ret-bench,held=ret,benchmark=bench,stocks=len(ids),
                         coverage=len(ids)/max(1,int((np.isfinite(y[i])&np.isfinite(cap[i])).sum()))))
        for b in range(1,11):
            selected=ordered[bins==b]
            groups.append(dict(date=date,group=b,gross_excess=float(y[i,selected].mean()-bench)))
    frame=pd.DataFrame(rows)
    ir=np.nanmean(rho)/np.nanstd(rho,ddof=0); win=float(np.nanmean(rho>.02))
    gross=frame.gross_excess.mean()*25.2; turn=frame.turnover.mean()
    out=dict(periods=len(frame),rank_ic=float(np.nanmean(rho)),rank_ir=float(ir),rank_win=win,
             s_i=float(abs(np.nanmean(rho)*ir)*win),pearson_ic=float(np.nanmean(ic)),
             gross_excess=float(gross),turnover=float(turn),net_excess=float(gross-turn*.006*25.2),
             corr_size=float(np.nanmean(size)),min_coverage=float(frame.coverage.min()))
    return out,frame,pd.DataFrame(groups)


def daily_path(signal,y,cap,dates,calendar,close):
    """Buy-and-hold weights drift; cost at t+1; factor-valid benchmark."""
    records=[]; turns=[]; previous=np.zeros(close.shape[1]);previous_end=None
    for i,date in enumerate(dates):
        start=calendar.get_loc(date)+1; end=start+10
        assert end<len(calendar)
        if previous_end is not None: assert start==previous_end
        previous_end=end
        ids=np.flatnonzero(np.isfinite(signal[i])&np.isfinite(y[i])&np.isfinite(cap[i]))
        order=ids[np.argsort(signal[i,ids],kind='stable')]
        bins=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
        held=order[bins==10]; new=np.zeros(close.shape[1]);new[held]=1/len(held)
        buys=np.maximum(new-previous,0).sum(); sells=np.maximum(previous-new,0).sum()
        fee=.003*(buys+sells);turn=(buys+sells)/2
        block=close[start:end+1].astype(float)
        np.testing.assert_allclose(block[-1,ids]/block[0,ids]-1,y[i,ids],rtol=2e-6,atol=1e-7)
        pp=np.mean(block[:,held]/block[0,held],axis=1); bb=np.mean(block[:,ids]/block[0,ids],axis=1)
        records.append(dict(date=calendar[start],portfolio=-fee,benchmark=0.,turnover=turn))
        for step in range(10):
            records.append(dict(date=calendar[start+step+1],portfolio=pp[step+1]/pp[step]-1,
                                benchmark=bb[step+1]/bb[step]-1,turnover=0.))
        previous[:]=0; values=block[-1,held]/block[0,held];previous[held]=values/values.sum()
        turns.append(dict(date=date,entry_date=calendar[start],turnover=turn,buy=buys,sell=sells,cost=fee))
    daily=pd.DataFrame(records).groupby('date',sort=True).agg(
        portfolio=('portfolio',lambda x:np.prod(1+x)-1),
        benchmark=('benchmark',lambda x:np.prod(1+x)-1),turnover=('turnover','sum'))
    months=[]
    for month,frame in daily.groupby(daily.index.to_period('M')):
        p=frame.portfolio.to_numpy();b=frame.benchmark.to_numpy();n=len(p)
        rex=float(np.prod(1+p)**(252/n)-np.prod(1+b)**(252/n))
        sr=float(p.mean()/p.std(ddof=1)*np.sqrt(252)) if p.std(ddof=1)>0 else 0.
        nav=np.r_[1.,np.cumprod(1+p)];dd=float(1-np.min(nav/np.maximum.accumulate(nav)))
        t=float(frame.turnover.sum())
        raw=raw_c_value(annual_excess_return=rex,annual_sharpe=sr,monthly_turnover=t,
                        monthly_max_drawdown=dd,sample_count=n)
        months.append(dict(month=str(month),days=n,rex=rex,sr=sr,max_dd=dd,turnover=t,
                           raw_c=raw,nc=score_nc(raw),
                           partial=str(month) in (str(daily.index.min().to_period('M')),str(daily.index.max().to_period('M')))))
    return daily,pd.DataFrame(months),pd.DataFrame(turns)


def nav_metrics(daily):
    p=daily.portfolio.to_numpy();b=daily.benchmark.to_numpy();nav=np.r_[1.,np.cumprod(1+p)]
    return dict(daily_net_nav_max_dd=float(1-np.min(nav/np.maximum.accumulate(nav))),
                daily_net_nav_sharpe=float(p.mean()/p.std(ddof=1)*np.sqrt(252)),
                daily_net_compound_excess=float(np.prod(1+p)**(252/len(p))-np.prod(1+b)**(252/len(p))))


def normalized(signal):
    lo=np.nanquantile(signal,.01,axis=1)[:,None];hi=np.nanquantile(signal,.99,axis=1)[:,None]
    x=np.clip(signal,lo,hi)
    return ((x-np.nanmean(x,axis=1)[:,None])/np.nanstd(x,axis=1)[:,None]).astype(np.float32)


def baseline_panels(dates,stocks):
    with (ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl').open('rb') as f:
        sf,*_=pickle.load(f)
    with (ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl').open('rb') as f:
        cache=pickle.load(f)
    scores=cache['scores'][SEATS];sf=sf.reset_index(drop=True)
    result={}
    for name in SEATS:
        p=sf.copy();p['value']=scores[name].to_numpy()
        wide=p.pivot(index='date',columns='instrument',values='value').reindex(index=dates,columns=stocks)
        result[name]=normalized(wide.to_numpy(np.float32))
    return result


def main():
    HERE.mkdir(parents=True,exist_ok=True)
    if (HERE/'protocol.json').exists(): raise RuntimeError('Refuse overwrite existing experiment')
    (HERE/'models').mkdir()
    config=alignment_config_snapshot();validate_alignment_config(config)
    protocol=dict(specs=SPECS,lightgbm_params=PARAMS,trees=TREES,train_last_periods=72,
                  min_training_periods=48,retrain='quarterly at first actual test signal',
                  purge='label exit strictly earlier than first test signal',direction=1,
                  local_candidate_count=3,fixed_linear_controls=3,parameter_search=False,
                  formal_window=['20210907','20260907'],recent_window=['20260101','latest local data'],
                  pre_formal_training_start='20190101',data_start='20180101',cost=.003,
                  no_size_input=True,platform_runs=0,historical_data_previously_viewed=True,
                  method_version=ALIGNMENT_RULE_VERSION+'-nonlinear-wf-fullA-arithmetic-v1',
                  core_alignment=config,universe='Full SH/SZ A shares, active total_mv/turnover; no ST filter',
                  headline='arithmetic annualised excess minus observed member-overlap turnover cost',
                  method_boundary='User full-A/arithmetic contract; distinct from legacy qualitygate3 filtered/compound comparisons.',
                  pool_boundary='Saved five-seat signal cache, aligned to new dates/stocks; require all seats valid. Archived-seat common-universe diagnostic, not new formal platform pool reproduction.',
                  controls='Same feature sets, target and folds; fixed ridge alpha=.01; no control selection.',
                  decision_gate=dict(min_s_i=.035,min_net=.15,max_turnover=.40,
                      max_abs_size_rho=.30,max_abs_existing_cluster_rho=.80,
                      pool_size_neutral_net_must_not_decrease=True,pool_size_exposure_must_not_increase=True,
                      mean_monthly_delta_comb_must_be_positive=True),
                  multiple_testing='3 fixed tree hypotheses + 3 fixed linear controls in this new round; historical 475 comparisons already exposed these recipes. No pristine blind holdout claim.')
    write('protocol.json',protocol)  # before labels/results are scored
    with MARKET.open('rb') as f:calendar,stocks,fields=pickle.load(f)
    calendar=pd.DatetimeIndex(calendar);stocks=pd.Index(stocks)
    fields={k:fields[k] for k in ('close','open','volume','turnover','cap')}
    active=(fields['cap']>0)&np.isfinite(fields['turnover']);fields['cap'][~active]=np.nan
    for k in ('close','open','volume'):fields[k][~active|(fields[k]<=0)]=np.nan
    fields['close']=pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    assert all(str(s).endswith(('.SH','.SZ')) for s in stocks)
    cluster_meta=json.loads((CLUSTERS/'metadata.json').read_text())
    assert cluster_meta['rule_version']==ALIGNMENT_RULE_VERSION
    formal=pd.DatetimeIndex(cluster_meta['signal_dates'])
    anchor=calendar.get_loc(formal[0]); positions=np.arange(anchor%10,len(calendar)-11,10)
    positions=positions[calendar[positions]>=pd.Timestamp('2019-01-01')]
    dates=calendar[positions]; exits=calendar[positions+11]
    evaluation=(dates>='2021-09-07')&(dates<='2026-09-07')
    assert dates[evaluation].equals(formal)
    cap=fields['cap'][positions].copy()
    y=(fields['close'][positions+11].astype(float)/fields['close'][positions+1]-1).astype(np.float32)
    y[~np.isfinite(cap)|~np.isfinite(y)]=np.nan
    label=rank(y)
    all_features=sorted(set(k for s in SPECS for k in s['features']))
    log(f'Loaded {len(calendar)} daily dates / {len(stocks)} stocks; {evaluation.sum()} formal tests')
    atoms=features(fields,positions,all_features)
    # Feature history must be identical if the raw daily panel is truncated.
    verification=dict(prefix_features=[],fold_purge=True,label_exit_offset=11)
    for cutoff in ('2023-06-30','2025-06-30'):
        last=calendar.searchsorted(pd.Timestamp(cutoff),side='right')
        selected=positions[positions<last][-3:]
        part=features({k:v[:last] for k,v in fields.items()},selected,all_features)
        at=np.flatnonzero(np.isin(positions,selected))
        for k in all_features: np.testing.assert_array_equal(part[k],atoms[k][at])
        verification['prefix_features'].append(dict(cutoff=cutoff,dates=len(at),features=len(all_features),max_abs_delta=0.))
    log('Daily feature prefix checks passed')
    eval_dates=dates[evaluation];eval_cap=cap[evaluation];eval_y=y[evaluation]
    baseline=baseline_panels(eval_dates,stocks)
    common=np.logical_and.reduce([np.isfinite(v) for v in baseline.values()])&np.isfinite(eval_cap)
    base=sum(baseline.values())/5;base[~common]=np.nan
    write('axes.json',dict(calendar_first=str(calendar.min().date()),calendar_last=str(calendar.max().date()),
                          stocks=stocks.tolist(),signal_dates=eval_dates.astype(str).tolist(),
                          training_signal_dates=dates[~evaluation].astype(str).tolist(),
                          pool_common_coverage_min=float(np.min(common.sum(1)/np.isfinite(eval_cap).sum(1)))))
    all_signals={};folds=[];rows=[];fold_stats=[]
    for spec in SPECS:
        x=np.stack([atoms[k] for k in spec['features']],axis=-1)
        target=residual_label(label,cap) if spec['target']!='rank_return' else label
        signal,linear,fs=walkforward(x,target,cap,dates,exits,evaluation,spec);folds+=fs
        all_signals[spec['name']]=signal;all_signals[spec['name']+'_LINEAR']=linear
        for name,value in ((spec['name'],signal),(spec['name']+'_LINEAR',linear)):
            np.save(HERE/f'{name}_signal.npy',value)
            for window,mask in (('formal_5y',np.ones(len(eval_dates),bool)),('recent_2026',eval_dates>='2026-01-01')):
                stats,p,g=metrics(value[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])
                p.to_csv(HERE/f'{name}_{window}_periods.csv',index=False);g.to_csv(HERE/f'{name}_{window}_groups.csv',index=False)
                if not name.endswith('_LINEAR'):
                    daily,monthly,turns=daily_path(value[mask],eval_y[mask],eval_cap[mask],eval_dates[mask],calendar,fields['close'])
                    daily.to_csv(HERE/f'{name}_{window}_daily.csv');monthly.to_csv(HERE/f'{name}_{window}_monthly.csv',index=False)
                    turns.to_csv(HERE/f'{name}_{window}_weight_turnover.csv',index=False)
                    stats.update(nav_metrics(daily))
                rows.append(dict(candidate=name,window=window,**stats))
            for quarter in eval_dates.to_period('Q').unique():
                mask=eval_dates.to_period('Q')==quarter
                stats,_,_=metrics(value[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])
                fold_stats.append(dict(candidate=name,fold=str(quarter),**stats))
        pd.DataFrame(rows).to_csv(HERE/'single_results.csv',index=False)
        write('folds.json',folds)
        log(f'{spec["name"]} metrics complete')
        del x;gc.collect()
    # Direct nonlinearity-vs-linear comparison without choosing parameters.
    pd.DataFrame(fold_stats).to_csv(HERE/'fold_results.csv',index=False)
    correlations=[]
    refs=pd.read_csv(CLUSTERS/'references.csv')
    u=pd.read_csv(CLUSTERS/'new_unanchored_clusters.csv').rename(columns={'new_cluster':'cluster'})
    refs=pd.concat([refs,u[['name','cluster','panel_id']]],ignore_index=True)
    old_stocks=pd.Index(cluster_meta['stock_ids']);mapped=stocks.get_indexer(old_stocks)
    assert np.all(mapped>=0)
    for _,ref in refs.iterrows():
        path=CLUSTERS/'panels'/f'{ref.panel_id}.npy'
        if not path.exists(): continue
        old=np.load(path,mmap_mode='r')
        for spec in SPECS:
            for window,mask in (('formal_5y',np.ones(len(eval_dates),bool)),('recent_2026',eval_dates>='2026-01-01')):
                r=spearman(all_signals[spec['name']][mask][:,mapped],old[mask])
                correlations.append(dict(candidate=spec['name'],window=window,cluster=ref.cluster,
                                         reference=ref['name'],panel_id=ref.panel_id,
                                         rho=float(np.nanmean(r)),valid_dates=int(np.isfinite(r).sum()),
                                         scope='saved rebalance-date daily cross-sectional Spearman; not every trading day'))
    pd.DataFrame(correlations).to_csv(HERE/'cluster_correlations.csv',index=False)
    nearest=[]
    for (name,window),g in pd.DataFrame(correlations).groupby(['candidate','window']):
        g=g.assign(abs_rho=g.rho.abs()).sort_values('abs_rho',ascending=False).drop_duplicates('cluster').head(5)
        nearest.extend(g.to_dict('records'))
    pd.DataFrame(nearest).to_csv(HERE/'nearest_other_clusters.csv',index=False)
    pool_rows=[];monthly_pairs=[];seat_corr=[]
    for spec in SPECS:
        for seat,value in baseline.items():
            r=spearman(all_signals[spec['name']],value)
            seat_corr.append(dict(candidate=spec['name'],seat=seat,rho=float(np.nanmean(r))))
    pd.DataFrame(seat_corr).to_csv(HERE/'seat_correlations.csv',index=False)
    for window,mask in (('formal_5y',np.ones(len(eval_dates),bool)),('recent_2026',eval_dates>='2026-01-01')):
        bstats,_,_=metrics(base[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])
        bd,bm,bt=daily_path(base[mask],eval_y[mask],eval_cap[mask],eval_dates[mask],calendar,fields['close'])
        bstats.update(nav_metrics(bd));bd.to_csv(HERE/f'BASE_{window}_daily.csv');bm.to_csv(HERE/f'BASE_{window}_monthly.csv',index=False)
        bneu,_,_=metrics(size_neutral(base[mask],eval_cap[mask]),eval_y[mask],eval_cap[mask],eval_dates[mask])
        # A terms use this run's common archived-seat universe consistently.
        base_seat_si=[metrics(v[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])[0]['s_i'] for v in baseline.values()]
        base_na=min(np.mean(base_seat_si)/.08,.70)
        pool_rows.append(dict(candidate='BASE',window=window,**bstats,size_neutral_net=bneu['net_excess']))
        for spec in SPECS:
            value=all_signals[spec['name']].copy();value[~common]=np.nan
            added=(base*5+normalized(value))/6
            stats,p,_=metrics(added[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])
            neu,_,_=metrics(size_neutral(added[mask],eval_cap[mask]),eval_y[mask],eval_cap[mask],eval_dates[mask])
            daily,monthly,turns=daily_path(added[mask],eval_y[mask],eval_cap[mask],eval_dates[mask],calendar,fields['close'])
            stats.update(nav_metrics(daily))
            daily.to_csv(HERE/f'ADD_{spec["name"]}_{window}_daily.csv');monthly.to_csv(HERE/f'ADD_{spec["name"]}_{window}_monthly.csv',index=False)
            turns.to_csv(HERE/f'ADD_{spec["name"]}_{window}_weight_turnover.csv',index=False)
            candidate_si=metrics(value[mask],eval_y[mask],eval_cap[mask],eval_dates[mask])[0]['s_i']
            new_na=min((sum(base_seat_si)+candidate_si)/6/.08,.70)
            dna=float(new_na-base_na)
            paired=bm.merge(monthly,on='month',suffixes=('_base','_new'))
            paired=paired[~paired.partial_base&~paired.partial_new].copy()
            paired['candidate']=spec['name'];paired['window']=window
            paired['delta_E']=paired.rex_new-paired.rex_base
            paired['delta_T']=paired.turnover_new-paired.turnover_base
            paired['delta_NC']=paired.nc_new-paired.nc_base
            paired['delta_A_proxy']=dna
            paired['delta_B']=np.nan
            paired['delta_Comb_AC_proxy']=.20*dna+.45*paired.delta_NC
            monthly_pairs.append(paired)
            pool_rows.append(dict(candidate=spec['name'],window=window,**stats,
                                  size_neutral_net=neu['net_excess'],delta_net=stats['net_excess']-bstats['net_excess'],
                                  delta_turnover=stats['turnover']-bstats['turnover'],
                                  delta_dd=stats['daily_net_nav_max_dd']-bstats['daily_net_nav_max_dd'],
                                  delta_abs_size_rho=abs(stats['corr_size'])-abs(bstats['corr_size']),
                                  delta_size_neutral_net=neu['net_excess']-bneu['net_excess'],
                                  size_guard=abs(stats['corr_size'])<=abs(bstats['corr_size'])+1e-9 and neu['net_excess']>=bneu['net_excess']-1e-9,
                                  months=len(paired),mean_delta_E=float(paired.delta_E.mean()),
                                  mean_delta_T=float(paired.delta_T.mean()),mean_delta_NC=float(paired.delta_NC.mean()),
                                  mean_delta_Comb_AC_proxy=float(paired.delta_Comb_AC_proxy.mean()),delta_A_proxy=dna,
                                  delta_B=None,full_delta_Comb=None,
                                  note='B and official pool ledger unavailable. A+C is explicitly a diagnostic; never rank as full official deltaComb.'))
            log(f'{spec["name"]} add-six {window}: dNet {(stats["net_excess"]-bstats["net_excess"])*100:+.2f}pp')
    pd.DataFrame(pool_rows).to_csv(HERE/'pool_results.csv',index=False)
    pd.concat(monthly_pairs).to_csv(HERE/'pool_monthly_deltas.csv',index=False)
    verification['unavailable_labels_perturbation']='PASS all three first folds; no unavailable labels used'
    verification['folds']=len(folds)
    verification['all_latest_label_exits_strictly_before_first_test']=all(pd.Timestamp(f['latest_training_label_exit'])<pd.Timestamp(f['test_first']) for f in folds)
    verification['elapsed_seconds']=time.monotonic()-STARTED
    verification['rss_gib']=psutil.Process().memory_info().rss/2**30
    verification['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    write('verification.json',verification)
    write('complete.json',dict(status='complete',paid_platform_runs=0,candidates=3,linear_controls=3))
    log('Finished fixed local round; no platform calls')


if __name__=='__main__': main()
