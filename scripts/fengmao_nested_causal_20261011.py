"""Local, purged temporal development and frozen evaluation of three families.

No platform calls. The final historical block was exposed by earlier research,
so it is not pristine OOS. Its labels never enter this run's selection logic.
Monthly C is computed from daily qfq holdings; no period/full-window C claim.
"""
from __future__ import annotations

import os
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_k] = '1'
import argparse
import gc
import hashlib
import json
import threading
import time
from pathlib import Path
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
from scipy.stats import rankdata
from threadpoolctl import threadpool_limits

import fengmao_rankboost_round2_20261011 as prior
from platform_alignment_rules import (ALIGNMENT_RULE_VERSION, alignment_config_snapshot,
                                      validate_alignment_config)
from platform_score_rules import raw_c_value, score_nc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/platform_alignment/fengmao-nested-causal-20261011'
FINAL_START = pd.Timestamp('2025-08-22')
DEVELOP_START = pd.Timestamp('2024-01-01')
TARGET = np.array([.1722791715386185, 1.6613206049954048, 111/119])
SCALE = np.array([.04, .5, .15])
PEAK = dict(rss_gib=0., private_gib=0., min_available_gib=100.)
STOP = threading.Event()
START = time.monotonic()
warnings.filterwarnings('ignore', category=RuntimeWarning)


def write(name, obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,
                                    allow_nan=False)+'\n',encoding='utf8')


def log(message):
    print(f'[{time.monotonic()-START:.1f}s] {message}',flush=True)


def guard():
    mi=psutil.Process().memory_info()
    rss=mi.rss/2**30
    private=getattr(mi,'private',mi.rss)/2**30
    avail=psutil.virtual_memory().available/2**30
    PEAK['rss_gib']=max(PEAK['rss_gib'],rss)
    PEAK['private_gib']=max(PEAK['private_gib'],private)
    PEAK['min_available_gib']=min(PEAK['min_available_gib'],avail)
    if max(rss,private)>2.25 or avail<1.25:
        raise MemoryError(f'RSS {rss:.3f}, private {private:.3f}, available {avail:.3f} GiB')


def watchdog():
    while not STOP.wait(.5):
        try:
            guard()
        except MemoryError as e:
            write('memory_stop.json',dict(error=str(e),memory=PEAK))
            log(str(e))
            os._exit(78)


def rank(a):
    n=np.isfinite(a).sum(axis=1,keepdims=True)
    return (rankdata(a,axis=1,method='average',nan_policy='omit')/np.maximum(n,1)-.5).astype(np.float32)


def rowcorr(a,b):
    ok=np.isfinite(a)&np.isfinite(b)
    a=np.where(ok,a,np.nan).astype(float)
    b=np.where(ok,b,np.nan).astype(float)
    a-=np.nanmean(a,axis=1,keepdims=True)
    b-=np.nanmean(b,axis=1,keepdims=True)
    d=np.sqrt(np.nansum(a*a,axis=1)*np.nansum(b*b,axis=1))
    return np.divide(np.nansum(a*b,axis=1),d,out=np.full(len(d),np.nan),where=d>1e-15)


def stats(rho):
    rho=np.asarray(rho,float)
    rho=rho[np.isfinite(rho)]
    m=float(rho.mean()); sd=float(rho.std(ddof=0))
    ir=m/sd if sd>0 else 0.
    win=float(np.mean(rho>.02))
    return dict(rank_ic=m,rank_ir=ir,wins=int((rho>.02).sum()),win_rate=win,
                s_i=abs(m*ir)*win,periods=len(rho))


def metrics(signal,y,cap,dates):
    ok=np.isfinite(signal)&np.isfinite(y)&np.isfinite(cap)
    coverage=(ok.sum(1)/np.maximum((np.isfinite(y)&np.isfinite(cap)).sum(1),1))
    if np.any(coverage<.95):
        raise ValueError('Coverage below 95%; cannot shrink universe to match scores')
    sr=rank(np.where(ok,signal,np.nan)); yr=rank(np.where(ok,y,np.nan))
    ric=rowcorr(sr,yr)
    if not np.isfinite(ric).all():
        raise ValueError('Constant or missing factor cross section')
    pearson=rowcorr(np.where(ok,signal,np.nan),np.where(ok,y,np.nan))
    sizecorr=rowcorr(sr,rank(np.where(ok,cap,np.nan)))
    rows=[]; previous=None; groups=[]
    for i,date in enumerate(dates):
        ids=np.flatnonzero(ok[i])
        ordered=ids[np.argsort(signal[i,ids],kind='stable')]
        bins=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
        held=ordered[bins==10]
        members=set(held.tolist())
        t=np.nan if previous is None else 1-len(previous&members)/len(members)
        previous=members
        gross=float(y[i,held].mean()-y[i,ids].mean())
        rows.append(dict(date=str(date.date()),rank_ic=float(ric[i]),ic=float(pearson[i]),
                         gross_excess=gross,turnover=t,corr_size=float(sizecorr[i]),
                         stocks=len(ids)))
        for g in range(1,11):
            selected=ordered[bins==g]
            groups.append(dict(date=str(date.date()),group=g,
                               gross_excess=float(y[i,selected].mean()-y[i,ids].mean())))
    p=pd.DataFrame(rows)
    s=stats(ric)
    pic=stats(pearson)
    s.update(gross_excess=float(p.gross_excess.mean()*25.2),turnover=float(p.turnover.mean()),
             net_excess=float(p.gross_excess.mean()*25.2-p.turnover.mean()*.006*25.2),
             corr_size=float(np.mean(sizecorr)),min_coverage=float(coverage.min()),
             pearson_ic=pic['rank_ic'],pearson_ir_population=pic['rank_ir'],
             pearson_ir_sample=float(np.mean(pearson)/np.std(pearson,ddof=1)),
             pearson_wins=pic['wins'],pearson_win_rate=pic['win_rate'],
             rule_s_i_proxy=float(abs(np.mean(ric)*np.mean(pearson)/np.std(pearson,ddof=1))*pic['win_rate']))
    return s,p,pd.DataFrame(groups)


def objective(s):
    v=np.array([s['rank_ic'],s['rank_ir'],s['win_rate']])
    gap=float(np.sum(((v-TARGET)/SCALE)**2))
    return gap+25*max(-s['net_excess'],0)+5*max(abs(s['corr_size'])-.5,0)


def feature_matrix(atoms,augmented=False):
    names=sorted(atoms)
    parts=[np.nan_to_num(atoms[n],nan=0.) for n in names]
    if augmented:
        # Fixed low-order conditional basis, not a date-specific model.
        for a,b in prior.PAIRS:
            parts.extend([np.nan_to_num(prior.prior.old.group_transform(atoms[a],atoms[b],5,'rank'),nan=0.),
                          np.nan_to_num(atoms[a]*atoms[b],nan=0.)])
            names.extend([f'Grp5({a},{b})',f'Mul({a},{b})'])
        for a in ('rev3','rev6','rev20','vol20','vol60','lowturn','lowvolume20','vstab20'):
            parts.extend([np.nan_to_num(atoms[a]**2,nan=0.),np.nan_to_num(atoms[a]**3,nan=0.)])
            names.extend([f'Square({a})',f'Cube({a})'])
    x=np.stack(parts,axis=2).astype(np.float32)
    del parts
    guard()
    return x,names


def normal_equations(x,y,cap,mask):
    nfeat=x.shape[-1]
    gram=np.zeros((nfeat,nfeat)); rhs=np.zeros(nfeat)
    for i in np.flatnonzero(mask):
        ok=np.isfinite(y[i])&np.isfinite(cap[i])
        z=x[i,ok].astype(float)
        label=rank(np.where(ok,y[i],np.nan)[None,:])[0,ok].astype(float)
        z-=z.mean(axis=0); label-=label.mean()
        gram+=z.T@z/len(z); rhs+=z.T@label/len(z)
        guard()
    return gram/max(mask.sum(),1),rhs/max(mask.sum(),1)


def coefficients(gram,rhs,alpha):
    return np.linalg.solve(gram+alpha*np.eye(len(rhs)),rhs)


def predict_linear(x,w,cap):
    out=np.einsum('ijk,k->ij',x,w,optimize=True).astype(np.float32)
    out[~np.isfinite(cap)]=np.nan
    return out


def select_ridge(atoms,y,cap,dates,core,dev,refit):
    x,names=feature_matrix(atoms,True)
    g,r=normal_equations(x,y,cap,core)
    trials=[]
    for alpha in (.0001,.001,.01,.1,1.):
        w=coefficients(g,r,alpha)
        pred=predict_linear(x[dev],w,cap[dev])
        m,_,_=metrics(pred,y[dev],cap[dev],dates[dev])
        trials.append(dict(alpha=alpha,selection_loss=objective(m),**m))
        log(f'ridge alpha={alpha}: internal IC={m["rank_ic"]:.4f}, IR={m["rank_ir"]:.3f}')
    best=min(trials,key=lambda t:t['selection_loss'])
    write('ridge_internal_trials.json',trials)
    g,r=normal_equations(x,y,cap,refit)
    w=coefficients(g,r,best['alpha'])
    del x
    gc.collect()
    return dict(family='ridge',name='FM_CAUSAL_RIDGE',alpha=best['alpha'],features=names,
                coefficients=w.tolist(),selection=best)


def fit_shallow(x,y,cap,mask,leaves,rounds):
    ok=np.isfinite(y)&np.isfinite(cap)&mask[:,None]
    label=rank(np.where(ok,y,np.nan))[ok]
    weights=np.broadcast_to(1/np.maximum(ok.sum(1),1)[:,None],ok.shape)[ok]
    weights*=len(weights)/weights.sum()
    data=lgb.Dataset(x[ok],label=label,weight=weights,free_raw_data=True)
    params=dict(objective='regression',learning_rate=.03,num_leaves=leaves,max_depth=3,
                max_bin=31,min_data_in_leaf=1000,lambda_l2=50.,feature_fraction=.85,
                seed=20261023,num_threads=1,verbosity=-1,deterministic=True,force_col_wise=True)
    model=lgb.train(params,data,num_boost_round=rounds)
    del data,label,weights
    gc.collect()
    guard()
    return model


def select_shallow(atoms,y,cap,dates,core,dev,refit):
    x,names=feature_matrix(atoms,False)
    trials=[]
    for leaves in (3,7):
        model=fit_shallow(x,y,cap,core,leaves,400)
        for trees in (100,200,400):
            pred=model.predict(x[dev].reshape(-1,len(names)),num_iteration=trees,num_threads=1).reshape(y[dev].shape)
            pred[~np.isfinite(cap[dev])]=np.nan
            m,_,_=metrics(pred,y[dev],cap[dev],dates[dev])
            trials.append(dict(leaves=leaves,trees=trees,selection_loss=objective(m),**m))
            log(f'shallow leaves={leaves}, trees={trees}: internal IC={m["rank_ic"]:.4f}, IR={m["rank_ir"]:.3f}')
        del model
        gc.collect()
    best=min(trials,key=lambda t:t['selection_loss'])
    write('shallow_internal_trials.json',trials)
    model=fit_shallow(x,y,cap,refit,best['leaves'],best['trees'])
    model.save_model(str(OUT/'FM_CAUSAL_SHALLOW.txt'))
    del x,model
    gc.collect()
    return dict(family='shallow',name='FM_CAUSAL_SHALLOW',features=names,
                leaves=best['leaves'],trees=best['trees'],selection=best)


def select_symbolic(atoms,y,cap,dates,core,dev,refit):
    # Only early/development arrays enter the evaluator. No final labels here.
    signal_names=('rev3','rev6','rev20','rev60','lowvolume1','lowvolume3','lowvolume20',
                  'lowturn','vstab20','vol6','vol20','vol60','pressure20','macdhist')
    group_names=('vol6','vol20','vol60','vrel3','vrel6','vrel20','lowturn','vstab20')
    early=core|dev
    small={k:v[early] for k,v in atoms.items()}
    ey,ec,ed=y[early],cap[early],dates[early]
    trials=[]
    formulas=list(signal_names)
    formulas += [f'Grp{n}({a},{b})' for n in (3,5) for a in signal_names for b in group_names if a!=b]
    formulas += [f'Add(rev6,Neg({b}))' for b in ('vol20','vol60','vrel3','vrel6')]
    for j,formula in enumerate(formulas):
        raw=prior.prior.old.value(formula,small)
        for sign in (1,-1):
            f=formula if sign==1 else f'Neg({formula})'
            try:
                m,_,_=metrics(sign*raw,ey,ec,ed)
                ds=ed>=DEVELOP_START
                inner,_,_=metrics(sign*raw[ds],ey[ds],ec[ds],ed[ds])
                loss=.5*objective(m)+objective(inner)
                trials.append(dict(formula=f,selection_loss=loss,**m,internal=inner))
            except ValueError as e:
                trials.append(dict(formula=f,selection_loss=1e9,error=str(e)))
        if j%25==0:
            pd.DataFrame(trials).drop(columns=['internal'],errors='ignore').to_csv(OUT/'symbolic_search.csv',index=False)
            log(f'symbolic {j+1}/{len(formulas)}; best {min(trials,key=lambda t:t["selection_loss"])["formula"]}')
        guard()
    best=min(trials,key=lambda t:t['selection_loss'])
    write('symbolic_internal_trials.json',trials)
    return dict(family='symbolic',name='FM_CAUSAL_SYMBOLIC',formula=best['formula'],selection=best)


def signal_for(frozen,atoms,cap):
    if frozen['family']=='symbolic':
        signal=prior.prior.old.value(frozen['formula'],atoms)
    elif frozen['family']=='ridge':
        x,names=feature_matrix(atoms,True)
        assert names==frozen['features']
        signal=predict_linear(x,np.asarray(frozen['coefficients']),cap)
        del x
    else:
        x,names=feature_matrix(atoms,False)
        assert names==frozen['features']
        model=lgb.Booster(model_file=str(OUT/(frozen['name']+'.txt')))
        signal=model.predict(x.reshape(-1,len(names)),num_threads=1).reshape(cap.shape).astype(np.float32)
        del model,x
    signal=np.asarray(signal,np.float32)
    signal[~np.isfinite(cap)]=np.nan
    gc.collect()
    return signal


def load_close(symbols):
    cache=ROOT/'quantlab/.quantlab/cache/research/cn_equity'
    frames=[pd.read_parquet(p,columns=['trade_date','is_open']) for p in (cache/'trade_calendar').glob('*.parquet')]
    f=pd.concat(frames,ignore_index=True)
    d=pd.to_datetime(f.trade_date.astype(str),format='mixed').dt.normalize()
    cal=pd.DatetimeIndex(sorted(d[f.is_open.eq(1)&d.between('2018-01-01','2026-09-07')].unique()))
    columns=pd.Index(symbols)
    close=np.full((len(cal),len(columns)),np.nan,np.float32)
    files=sorted((cache/'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet'))
    for j,path in enumerate(files):
        f=pd.read_parquet(path,columns=['date','instrument','close'])
        i=cal.get_indexer(pd.to_datetime(f.date).dt.normalize()); c=columns.get_indexer(f.instrument)
        ok=(i>=0)&(c>=0)
        old=close[i[ok],c[ok]]; new=f.close.to_numpy(np.float32)[ok]
        if np.any(np.isfinite(old)&(old!=new)):
            raise ValueError('Conflicting qfq cache '+path.name)
        close[i[ok],c[ok]]=new
        if (j+1)%50==0:
            log(f'daily close {j+1}/{len(files)}')
        guard()
    # Match the original label source exactly: only price observations with
    # positive daily total_mv and nonmissing turnover survive before ffill.
    active=np.zeros(close.shape,bool)
    capfiles=sorted((cache/'tushare_factor_recheck/daily_basic_full_a').glob('daily_basic_*.parquet'))
    for j,path in enumerate(capfiles):
        f=pd.read_parquet(path,columns=['date','instrument','total_mv','turnover'])
        i=cal.get_indexer(pd.to_datetime(f.date).dt.normalize()); c=columns.get_indexer(f.instrument)
        ok=(i>=0)&(c>=0)&f.total_mv.gt(0).to_numpy()&f.turnover.notna().to_numpy()
        active[i[ok],c[ok]]=True
        if (j+1)%600==0:
            log(f'daily cap eligibility {j+1}/{len(capfiles)}')
        guard()
    close[~active|(close<=0)]=np.nan
    del active
    close=pd.DataFrame(close).ffill().to_numpy(np.float32)
    del f,frames
    gc.collect()
    return cal,close


def daily_monthly_c(signal,y,cap,dates,cal,close):
    """Daily equal-capital buy-and-hold path; factor-valid benchmark proxy.

    Equal weights at entry drift within each holding period. Cost uses both
    actual buys and sells; first entry pays 0.003, no artificial final exit.
    PIT eligibility, platform stops and official index data are unavailable.
    """
    rows=[]; turn_rows=[]; previous_weights={}; previous_end=None
    for i,date in enumerate(dates):
        pos=cal.get_loc(date)+1; end=pos+10
        if end>=len(cal):
            continue
        if previous_end is not None and pos!=previous_end:
            raise ValueError('Monthly path requires contiguous ten-trading-day holdings')
        previous_end=end
        ok=np.isfinite(signal[i])&np.isfinite(y[i])&np.isfinite(cap[i])
        ids=np.flatnonzero(ok)
        ordered=ids[np.argsort(signal[i,ids],kind='stable')]
        bins=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
        held=ordered[bins==10]
        block=close[pos:end+1].astype(float)
        # Verify the qfq label equals the saved source used for IC scoring.
        rebuilt=block[-1,ids]/block[0,ids]-1
        if not np.allclose(rebuilt,y[i,ids],rtol=1e-6,atol=1e-7,equal_nan=True):
            raise ValueError('Saved label versus daily qfq price mismatch')
        new_weights={int(k):1/len(held) for k in held}
        union=set(previous_weights)|set(new_weights)
        buys=sum(max(new_weights.get(k,0)-previous_weights.get(k,0),0) for k in union)
        sells=sum(max(previous_weights.get(k,0)-new_weights.get(k,0),0) for k in union)
        turnover=(buys+sells)/2
        pp=np.mean(block[:,held]/block[0,held],axis=1)
        bb=np.mean(block[:,ids]/block[0,ids],axis=1)
        pr=pp[1:]/pp[:-1]-1; br=bb[1:]/bb[:-1]-1
        # Transaction is at t+1; include fee on entry day in daily accounting.
        fee=.003*(buys+sells)
        rows.append(dict(date=str(cal[pos].date()),portfolio=-fee,benchmark=0.,turnover=turnover))
        for step in range(10):
            rows.append(dict(date=str(cal[pos+step+1].date()),portfolio=float(pr[step]),
                             benchmark=float(br[step]),turnover=0.))
        values=block[-1,held]/block[0,held]
        previous_weights={int(k):float(v/values.sum()) for k,v in zip(held,values)}
        turn_rows.append(dict(signal_date=str(date.date()),entry_date=str(cal[pos].date()),
                              turnover=turnover,buy_fraction=buys,sell_fraction=sells,cost=fee))
    daily=pd.DataFrame(rows)
    # Exit and next entry share a close date. Combine their return/cost events.
    daily=daily.groupby('date',sort=True).agg(portfolio=('portfolio',lambda a:np.prod(1+a)-1),
                     benchmark=('benchmark',lambda a:np.prod(1+a)-1),turnover=('turnover','sum')).reset_index()
    dt=pd.to_datetime(daily.date)
    months=[]
    for month,ix in daily.groupby(dt.dt.to_period('M')).groups.items():
        block=daily.loc[ix]; p=block.portfolio.to_numpy(); b=block.benchmark.to_numpy(); n=len(p)
        rp=float(np.prod(1+p)-1); rb=float(np.prod(1+b)-1)
        rex=float((1+rp)**(252/n)-(1+rb)**(252/n))
        sd=p.std(ddof=1) if n>1 else 0
        sr=float(p.mean()/sd*np.sqrt(252)) if sd>0 else 0.
        eq=np.r_[1.,np.cumprod(1+p)]
        dd=float(-(eq/np.maximum.accumulate(eq)-1).min())
        t=float(block.turnover.sum())
        raw=raw_c_value(annual_excess_return=rex,annual_sharpe=sr,
                        monthly_turnover=t,monthly_max_drawdown=dd,sample_count=n)
        nc=score_nc(raw)
        months.append(dict(month=str(month),days=n,r_p=rp,r_b=rb,annual_rex=rex,annual_sr=sr,
                           max_dd=dd,turnover_month=t,raw_c=raw,nc=nc,c_contribution=.45*nc,
                           partial_month=(str(month) in [str(dt.min().to_period('M')),str(dt.max().to_period('M'))])))
    return daily,pd.DataFrame(months),pd.DataFrame(turn_rows)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--monthly-only',action='store_true')
    args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    threading.Thread(target=watchdog,daemon=True).start()
    validate_alignment_config(alignment_config_snapshot())
    with threadpool_limits(limits=1):
        atoms,y,cap,dates,axes=prior.load('target')
        exits=pd.DatetimeIndex(axes['exits'])
        core=(dates<DEVELOP_START)&(exits<DEVELOP_START)
        dev=(dates>=DEVELOP_START)&(dates<FINAL_START)&(exits<FINAL_START)
        refit=(dates<FINAL_START)&(exits<FINAL_START)
        final=dates>=FINAL_START
        log(f'core={core.sum()}, development={dev.sum()}, purged refit={refit.sum()}, historical final={final.sum()}')
        write('protocol.json',dict(rule=ALIGNMENT_RULE_VERSION,train=dates[core].astype(str).tolist(),
              internal_development=dates[dev].astype(str).tolist(),purged_refit=dates[refit].astype(str).tolist(),
              final_historical_validation=dates[final].astype(str).tolist(),
              removed_crossing_labels=dates[(dates<FINAL_START)&(exits>=FINAL_START)].astype(str).tolist(),
              final_was_exposed_in_prior_research=True,final_used_in_current_selection=False,
              target_dates_inferred=True,platform_cost=0,c_ledger='monthly daily path proxy, factor_valid benchmark',
              public_ic_field='ic_mean; exact Pearson-versus-RankIC provenance unavailable',
              rank_based_target_match_is_a_proxy=True,
              c_public_target=dict(month='2026-10',raw_c=97.90807355538628,nc=1,scope='six-factor opponent pool'),
              c_same_scope_comparison_available=False))
        if args.monthly_only:
            frozen=json.loads((OUT/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
        else:
            if (OUT/'frozen_candidates.json').exists():
                raise RuntimeError('Refuse to retune after final validation; frozen configuration exists')
            frozen=[]
            frozen.append(select_ridge(atoms,y,cap,dates,core,dev,refit))
            frozen.append(select_shallow(atoms,y,cap,dates,core,dev,refit))
            frozen.append(select_symbolic(atoms,y,cap,dates,core,dev,refit))
            write('frozen_candidates.json',dict(frozen_before_final_labels=True,candidates=frozen))
            hashes={m['name']:hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest() for m in frozen}
            hashes['script']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            if (OUT/'FM_CAUSAL_SHALLOW.txt').exists():
                hashes['shallow_model']=hashlib.sha256((OUT/'FM_CAUSAL_SHALLOW.txt').read_bytes()).hexdigest()
            write('freeze_hashes.json',hashes)
        rows=[]
        for m in frozen:
            s=signal_for(m,atoms,cap)
            np.save(OUT/(m['name']+'_target_signals.npy'),s)
            for window,mask in [('refit',refit),('historical_final24',final),('target119',np.ones(len(dates),bool))]:
                stat,periods,groups=metrics(s[mask],y[mask],cap[mask],dates[mask])
                periods.to_csv(OUT/f'{m["name"]}_{window}_periods.csv',index=False)
                groups.to_csv(OUT/f'{m["name"]}_{window}_groups.csv',index=False)
                rows.append(dict(candidate=m['name'],window=window,**stat))
                log(f'{m["name"]} {window}: RankIC={stat["rank_ic"]:.6f}, IR={stat["rank_ir"]:.3f}, win={stat["wins"]}/{stat["periods"]}')
            del s
        pd.DataFrame(rows).to_csv(OUT/'results_target.csv',index=False)
        del atoms,y,cap
        gc.collect()
        fatoms,fy,fc,fd,fa=prior.load('formal')
        for m in frozen:
            s=signal_for(m,fatoms,fc)
            np.save(OUT/(m['name']+'_formal_signals.npy'),s)
            for window,mask in [('formal_5y',np.ones(len(fd),bool)),('recent_2026',fd>='2026-01-01'),
                                ('formal_final',fd>=FINAL_START)]:
                stat,periods,groups=metrics(s[mask],fy[mask],fc[mask],fd[mask])
                periods.to_csv(OUT/f'{m["name"]}_{window}_periods.csv',index=False)
                groups.to_csv(OUT/f'{m["name"]}_{window}_groups.csv',index=False)
                rows.append(dict(candidate=m['name'],window=window,**stat))
            del s
        pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)
        del fatoms
        gc.collect()
        cal,close=load_close(fa['symbols'])
        monthly_rows=[]
        for m in frozen:
            s=np.load(OUT/(m['name']+'_formal_signals.npy'),mmap_mode='r')
            daily,monthly,turns=daily_monthly_c(s,fy,fc,fd,cal,close)
            daily.to_csv(OUT/f'{m["name"]}_daily_proxy.csv',index=False)
            monthly.to_csv(OUT/f'{m["name"]}_monthly_c_proxy.csv',index=False)
            turns.to_csv(OUT/f'{m["name"]}_weight_turnover.csv',index=False)
            full=monthly[~monthly.partial_month]
            last=full[full.month>='2025-09']
            monthly_rows.append(dict(candidate=m['name'],full_months=len(full),nc_mean=float(full.nc.mean()),
                 nc_full_months=int((full.nc==1).sum()),nc_zero_months=int((full.nc==0).sum()),
                 final_months=len(last),final_nc_mean=float(last.nc.mean()),
                 final_full_months=int((last.nc==1).sum()),final_zero_months=int((last.nc==0).sum())))
        # Correct the old whole-window C claim using a proper monthly daily proxy.
        old=ROOT/'research_reports/platform_alignment/fengmao-rankboost-round2-20261011/FM_RB_BLEND_formal_signals.npy'
        s=np.load(old,mmap_mode='r')
        daily,monthly,turns=daily_monthly_c(s,fy,fc,fd,cal,close)
        daily.to_csv(OUT/'OLD_FULLFIT_daily_proxy.csv',index=False)
        monthly.to_csv(OUT/'OLD_FULLFIT_monthly_c_proxy.csv',index=False)
        full=monthly[~monthly.partial_month]
        monthly_rows.append(dict(candidate='OLD_FULLFIT_noncausal',full_months=len(full),nc_mean=float(full.nc.mean()),
               nc_full_months=int((full.nc==1).sum()),nc_zero_months=int((full.nc==0).sum())))
        pd.DataFrame(monthly_rows).to_csv(OUT/'monthly_c_summary.csv',index=False)
    STOP.set()
    write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,memory=PEAK,
         seconds=time.monotonic()-START,rule=ALIGNMENT_RULE_VERSION,
         formal_rules=alignment_config_snapshot(),c_fidelity='proxy: local daily path and factor_valid benchmark; opponent pool signals and October data unavailable',
         success_requires='same scope public metrics; no independent opponent subwindow C or B target available'))
    log('complete; results saved; reproduction goal remains unachieved')


if __name__=='__main__':
    main()
