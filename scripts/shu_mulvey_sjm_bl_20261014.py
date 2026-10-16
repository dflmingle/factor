#!/usr/bin/env python3
"""Offline A-share adaptation of Shu & Mulvey (arXiv:2410.14841v1).

The author's sparse jump model implementation is vendored with its license.
Daily realized sleeve active returns, independent two-state models, causal
online inference, prequential model validation and Black--Litterman views.
The paper allocates among seven indices. Here allocation is also translated
into a stock-ranking composite, whose results are separately evaluated under
the project's full-A / qfq / label-1 / factor_valid / 0.30% contract.
"""
from __future__ import annotations
import os
for _name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[_name]='1'
import sys, json, hashlib, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import rankdata
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
LIT=ROOT/'research_reports/literature/shu-mulvey-dynamic-allocation-20261014'
sys.path.insert(0,str(LIT/'author_library'))
from jumpmodels.sparse_jump import SparseJumpModel
import jumpmodels.jump as author_jump
from numba import njit
import quant_corpus_local_20261012 as q
import regime_switch_all_factors_20261014 as old

OUT=ROOT/'research_reports/platform_alignment/shu-mulvey-sjm-bl-20261014'
VERSION='shu-mulvey-local-sjm-bl-v1'
PARAMS=[(10.,9.5),(50.,9.5),(100.,9.5)]
DELTA=2.5
MIN_TRAIN_DAYS=252
MAX_TRAIN_DAYS=756
VALIDATION_PERIODS=50
MIN_VALIDATION_PERIODS=12
FEATURE_NAMES=[f'{kind}{n}' for kind in ['active_ew','rsi','stoch'] for n in [8,21,63]]+['macd8_21','macd21_63','log_downside21','active_beta21','market_ew21','market_logvol_diff_ew21','market_breadth_ew21']

@njit(cache=True)
def dp_compiled(loss,penalty):
    n,k=loss.shape;values=np.empty((n,k));labels=np.empty(n,np.int64)
    for s in range(k):values[0,s]=loss[0,s] if np.isfinite(loss[0,s]) else np.inf
    for t in range(1,n):
        for s in range(k):
            best=np.inf
            for r in range(k):best=min(best,values[t-1,r]+penalty[r,s])
            values[t,s]=(loss[t,s] if np.isfinite(loss[t,s]) else np.inf)+best
    labels[-1]=np.argmin(values[-1])
    for t in range(n-2,-1,-1):
        best=np.inf;arg=0
        for s in range(k):
            v=values[t,s]+penalty[s,labels[t+1]]
            if v<best:best=v;arg=s
        labels[t]=arg
    return labels,values[-1,labels[-1]],values

def author_dp_fast(loss_mx,penalty_mx,return_value_mx=False):
    labels,value,values=dp_compiled(np.asarray(loss_mx,float),np.asarray(penalty_mx,float))
    return values if return_value_mx else (labels,value)

# This replaces only the numerical loop, not the model objective or solver.
# Check both smoothed paths and filtered DP values against the author's
# unmodified function, including exact ties and unreachable components.
DP_CHECKS=[]
for _seed in [0,1,2]:
    _loss=np.random.default_rng(_seed).normal(size=(87,2))**2
    if _seed==1:_loss[:]=1.
    if _seed==2:_loss[:,1]=np.nan
    _pen=np.array([[0.,50.],[50.,0.]])
    _l,_v=author_jump.dp(_loss,_pen);_ll,_vv=author_dp_fast(_loss,_pen)
    assert np.array_equal(_l,_ll) and abs(_v-_vv)<1e-10
    assert np.allclose(author_jump.dp(_loss,_pen,True),author_dp_fast(_loss,_pen,True),equal_nan=True)
    DP_CHECKS.append({'seed':_seed,'passed':True})
author_jump.dp=author_dp_fast

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def truth(v):
    if pd.isna(v): return False
    return str(v).strip().lower() in ['true','1','yes']

def inventory(grid,stocks):
    cat=pd.read_csv(old.CAT)
    lookup={(str(r.output),str(r.key)):r.to_dict() for _,r in cat.iterrows()}
    entries=[];panels={};ledgers={}
    for path in sorted((ROOT/'research_reports/platform_alignment').glob('**/signal_panels.pkl')):
        obj=pd.read_pickle(path)
        if not isinstance(obj,dict) or 'panels' not in obj: continue
        if not obj['dates'].equals(grid) or not obj['stocks'].equals(stocks): continue
        md={m['key']:m for m in obj.get('metadata',[]) if isinstance(m,dict) and 'key' in m}
        folder=str(path.parent.relative_to(ROOT))
        for key,val in obj['panels'].items():
            m=md.get(key,{})
            cm=lookup.get((folder,key),{})
            pf=old.period_file(path.parent,key)
            audit_file=path.parent/'audit_complete.json'
            audited=truth(cm.get('research_audit_complete'))
            if audit_file.exists(): audited=audited or truth(json.loads(audit_file.read_text()).get('completed'))
            if path.parent==q.OUT: audited=True
            row={'record_id':folder+':'+key,'key':key,'name':m.get('name',cm.get('name',key)),
                 'panel_path':str(path.relative_to(ROOT)),'period_path':str(pf.relative_to(ROOT)) if pf else '',
                 'formula':m.get('formula',cm.get('formula','')),'fidelity':m.get('fidelity',cm.get('fidelity','')),
                 'source_paths':m.get('source_paths',cm.get('source_paths','')),
                 'gated':truth(m.get('gated')) or truth(cm.get('effective_gated')),
                 'superseded':truth(cm.get('superseded_unsafe')) or truth(cm.get('superseded_semantic')),
                 'audited':audited,'has_ledger':pf is not None}
            if not audited and (path.parent/'completion.json').exists():row['audited']=True
            entries.append(row)
            if pf:
                try:
                    df=pd.read_csv(pf,parse_dates=['date','entry_date','exit_date'])
                except pd.errors.EmptyDataError:
                    row['has_ledger']=False;row['periods']=0;row['mean_unique_fraction']=0.
                    continue
                if df.empty:
                    row['has_ledger']=False;row['periods']=0;row['mean_unique_fraction']=0.
                    continue
                row['periods']=len(df)
                row['mean_unique_fraction']=float(df.unique_pct.mean()) if len(df) else 0.
                # Sparse all-zero candle rows have no ranking. The minimum
                # is a structural availability check, never a return screen.
                panels[row['record_id']]=val.to_numpy(np.float32) if hasattr(val,'to_numpy') else np.asarray(val,np.float32)
                ledgers[row['record_id']]=df
    inv=pd.DataFrame(entries)
    inv['canonical']=False;inv['reason']=''
    for key,g in inv.groupby('key',sort=True):
        valid=g[g.has_ledger & ~g.superseded]
        if valid.empty:
            inv.loc[g.index,'reason']='superseded_or_missing_ledger';continue
        # Prefer the audited corrected/source implementation; the original
        # full-A corpus wins a purely duplicate tie. No outcome used.
        priority=valid.audited.astype(int)*10+valid.panel_path.str.contains('safe').astype(int)*5+valid.panel_path.str.contains('source-reproduction').astype(int)
        idx=priority.sort_values(ascending=False,kind='stable').index[0]
        inv.loc[idx,'canonical']=True
        inv.loc[g.index.difference([idx]),'reason']='duplicate_key_or_superseded'
    inv['main_eligible']=inv.canonical & inv.audited & ~inv.gated & ~inv.superseded & inv.has_ledger
    for idx,r in inv.iterrows():
        if r.canonical and not r.main_eligible:
            inv.at[idx,'reason']='gated' if r.gated else 'unaudited_or_missing'
    meta=inv[inv.main_eligible].copy().reset_index(drop=True)
    return inv,meta,[panels[k] for k in meta.record_id],{k:ledgers[k] for k in meta.record_id}

def ew(x,n): return pd.Series(x).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy()

def features(active,market,environment):
    a=np.asarray(active,float); nav=np.cumprod(1+np.nan_to_num(a,nan=0.))
    out=[]
    for n in [8,21,63]: out.append(ew(a,n))
    up=np.maximum(a,0);dn=np.maximum(-a,0)
    for n in [8,21,63]:
        u,d=ew(up,n),ew(dn,n);den=u+d
        out.append(np.divide(100*u,den,out=np.full(len(a),50.),where=den>1e-12))
    for n in [8,21,63]:
        lo=pd.Series(nav).rolling(n).min().to_numpy();hi=pd.Series(nav).rolling(n).max().to_numpy();den=hi-lo
        out.append(np.divide((nav-lo)*100,den,out=np.full(len(a),50.),where=den>1e-12))
    out.extend([ew(nav,8)/ew(nav,21)-1,ew(nav,21)/ew(nav,63)-1])
    out.append(np.log(np.maximum(np.sqrt(ew(dn**2,21)),1e-8)))
    m=ew(market,21);cov=ew(a*market,21)-ew(a,21)*m;var=ew(market**2,21)-m**2
    out.append(np.divide(cov,var,out=np.zeros(len(a)),where=var>1e-12))
    out.extend([m,environment[:,0],environment[:,1]])
    x=np.column_stack(out); x[~np.isfinite(a),:]=np.nan
    return x

def make_daily(meta,ledger,cal,fields,grid):
    start=cal.get_loc(grid[0])+1;last=cal.get_loc(grid[-1])+11
    daily=cal[start:last+1];N=len(meta);T=len(daily)
    asset=np.full((T,N),np.nan);active=asset.copy();benchmark=asset.copy();valid=asset.copy().astype(bool);valid[:]=False
    for j,r in meta.iterrows():
        p=ROOT/r.period_path.replace('.periods.csv','.daily_nav.csv')
        d=pd.read_csv(p,parse_dates=['date']).drop_duplicates('date',keep='last').set_index('date')
        # Each stored index holds cash during gaps. Discard the entry anchor;
        # only differences between recorded daily values are observed returns.
        raw=d[['nav','benchmark_nav']].pct_change(fill_method=None).reindex(daily)
        observed=raw.nav.notna().to_numpy()
        asset[:,j]=raw.nav.to_numpy();benchmark[:,j]=raw.benchmark_nav.to_numpy();active[:,j]=asset[:,j]-benchmark[:,j];valid[:,j]=observed
    rr=q.ratio(fields['close'],q.delay(fields['close']))-1
    full=pd.DataFrame(np.where(fields['cap']>0,rr,np.nan)).mean(axis=1).to_numpy()
    m=full[start:last+1]
    vol=pd.Series(full).rolling(20,min_periods=20).std();logchange=np.log(vol.clip(lower=1e-8)).diff()
    breadth=pd.DataFrame(rr).rolling(20,min_periods=20).mean().gt(0).mean(axis=1)
    env=np.column_stack([logchange.ewm(span=21,adjust=False,min_periods=21).mean().to_numpy()[start:last+1],breadth.ewm(span=21,adjust=False,min_periods=21).mean().to_numpy()[start:last+1]])
    # Broad market is solely an exogenous training input / relative view
    # reference, never a substitute for the formal factor_valid benchmark.
    return daily,asset,active,benchmark,valid,m,env

def fit_predict_one(task):
    j,x,a,grididx,grid,params=task
    with threadpool_limits(limits=1):
        candidates=[];fits=[]
        for lam,kappa2 in params:
            forecast=np.full(len(grid),np.nan);states=np.full(len(grid),-1,int);selected=np.zeros((len(grid),x.shape[1]));maxdate=np.full(len(grid),-1,int)
            model=None;last_month=None;mean=None;std=None;train_idx=None
            for i,t in enumerate(grididx):
                if t<0:continue
                # All training observations strictly precede the signal close.
                ok=np.isfinite(x[:t]).all(axis=1)&np.isfinite(a[:t]);ids=np.flatnonzero(ok)[-MAX_TRAIN_DAYS:]
                if len(ids)<MIN_TRAIN_DAYS: continue
                month=str(pd.Timestamp(grid[i]).to_period('M'))
                if model is None or month!=last_month:
                    z=x[ids];mean=z.mean(axis=0);std=z.std(axis=0);std=np.maximum(std,1e-8)
                    z=np.clip((z-mean)/std,-8,8)
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore')
                            model=SparseJumpModel(n_components=2,jump_penalty=lam,max_feats=kappa2,max_iter=8,max_iter_jm=50,n_init_jm=2,random_state=47347).fit(z,ret_ser=a[ids],sort_by='ret')
                        labs=np.asarray(model.labels_,int)
                        means=np.array([a[ids][labs==s].mean() if np.sum(labs==s)>=15 else np.nan for s in range(2)])
                        counts=np.bincount(labs,minlength=2)
                        # A one-state fit is legitimate evidence of weak
                        # state separation, not a forced bull/bear signal.
                        train_idx=ids;last_month=month
                        fits.append({'j':j,'signal_i':i,'lambda':lam,'max_feats':kappa2,'last_train_daily':int(ids[-1]),'training_days':len(ids),'state0_n':int(counts[0]),'state1_n':int(counts[1]),'mu0':means[0],'mu1':means[1],'sparse_iterations':int(getattr(model,'n_iter_',0))})
                    except (ValueError,AssertionError,FloatingPointError):
                        model=None;continue
                # Recompute the endpoint of the DP on the fixed train prefix
                # plus all observations available at this signal. Historical
                # online decisions are saved, never replaced with smoothed labels.
                upto=np.flatnonzero(np.isfinite(x[:t+1]).all(axis=1)&np.isfinite(a[:t+1]))
                upto=upto[upto>=train_idx[0]]
                if not len(upto) or upto[-1]<t:continue
                z=np.clip((x[upto]-mean)/std,-8,8)
                labs_now=np.asarray(model.predict_online(z),int);s=int(labs_now[-1])
                forecast[i]=means[s];states[i]=s;selected[i]=np.asarray(model.w);maxdate[i]=int(train_idx[-1])
            candidates.append((forecast,states,selected,maxdate))
    return j,candidates,fits

def choose_predictions(meta, candidates, daily,active,ledgers,grid):
    n=len(grid);m=len(meta);V=np.full((n,m),np.nan);state=np.full((n,m),-1,int);param=np.full((n,m),-1,int);quality=np.full((n,m),np.nan);F=[];A=[]
    for j,r in meta.iterrows():
        p=ledgers[r.record_id].set_index('date').reindex(grid)
        end=pd.DatetimeIndex(p.exit_date);net=p.net_excess_path.to_numpy(float)
        chosen=1;half=None
        for i,date in enumerate(grid):
            hist=np.flatnonzero((end<date)&np.isfinite(net))[-VALIDATION_PERIODS:]
            h=f'{date.year}-H{1 if date.month<=6 else 2}'
            if h!=half:
                half=h
                scores=[]
                for k,(v,st,feat,cutoff) in enumerate(candidates[j]):
                    valid=hist[np.isfinite(v[hist])]
                    if len(valid)<MIN_VALIDATION_PERIODS:scores.append(np.nan);continue
                    b=np.clip(v[valid]*252/.05,-1,1)
                    # Hypothetical timing strategy is solely a validation
                    # device.  Actual allocation stays nonnegative.
                    ret=b*net[valid]-.006*np.r_[0.,np.abs(np.diff(b))]
                    sd=ret.std(ddof=1);scores.append(float(ret.mean()/sd) if sd>1e-8 else np.nan)
                if np.isfinite(scores).any():chosen=int(np.nanargmax(scores))
            v,st,feat,cutoff=candidates[j][chosen];V[i,j]=v[i];state[i,j]=st[i];param[i,j]=chosen
            valid=hist[np.isfinite(v[hist])]
            if len(valid)>=MIN_VALIDATION_PERIODS:
                b=np.clip(v[valid]*252/.05,-1,1);ret=b*net[valid]-.006*np.r_[0.,np.abs(np.diff(b))];sd=ret.std(ddof=1)
                if sd>1e-8:quality[i,j]=ret.mean()/sd
            if np.isfinite(v[i]):
                A.append({'date':date,'key':r.key,'parameter':chosen,'lambda':PARAMS[chosen][0],'forecast_daily':v[i],'state':int(st[i]),'last_training_return':daily[cutoff[i]],'validation_max_exit':end[hist[-1]] if len(hist) else pd.NaT,'validation_observations':len(valid),'validation_timing_score':quality[i,j]})
                F.append({'date':date,'key':r.key,**dict(zip(FEATURE_NAMES,feat[i]))})
    return V,state,param,quality,pd.DataFrame(A),pd.DataFrame(F)

def ew_cov(R,halflife=126):
    if len(R)<2:return np.eye(R.shape[1])*1e-4
    R=np.nan_to_num(R,nan=0.);w=np.power(.5,np.arange(len(R)-1,-1,-1)/halflife);w/=w.sum();mu=w@R
    S=((R-mu)*w[:,None]).T@(R-mu)
    # A few hundred local sleeves have more covariance dimensions than
    # independent regimes. Diagonal shrinkage is an explicit A-share addition.
    S=.75*S+.25*np.diag(np.diag(S));S+=np.eye(len(S))*1e-8
    return S

def capped_simplex(x,cap=.20):
    x=np.maximum(np.asarray(x,float),0);n=len(x)
    if n*cap<1-1e-9:raise ValueError('infeasible weight cap')
    lo=float(x.min()-1);hi=float(x.max())
    for _ in range(80):
        mid=(lo+hi)/2;z=np.clip(x-mid,0,cap)
        if z.sum()>1:lo=mid
        else:hi=mid
    z=np.clip(x-hi,0,cap);z/=z.sum();return z

def allocate(V,quality,asset,active,market,daily,grid,meta,te=.02,adjust_penalty=0.):
    n,m=V.shape;W=np.zeros((n,m));logs=[];prev=np.zeros(m)
    for i,date in enumerate(grid):
        t=int(daily.searchsorted(date,side='left'));h=asset[max(0,t-756):t]
        avail=np.isfinite(V[i])&(np.isfinite(h).sum(axis=0)>=252)
        ids=np.flatnonzero(avail)
        if len(ids)<5:
            # Neutral equal-weight, normalized, no future state fallback.
            live=np.flatnonzero(np.isfinite(h).sum(axis=0)>=20) if len(h) else np.arange(m)
            if not len(live):live=np.arange(m)
            W[i,live]=1/len(live);prev=W[i].copy();continue
        # Correlation redundancy control and model reliability use only
        # pre-signal observed active returns. No full-window return screen.
        hist=active[max(0,t-504):t];C=np.corrcoef(np.nan_to_num(hist,nan=0.),rowvar=False)
        priority=np.nan_to_num(quality[i],nan=0.)+.01*np.nan_to_num(V[i])*252
        selected=[]
        for j in ids[np.argsort(-priority[ids],kind='stable')]:
            if selected and np.nanmax(np.abs(C[j,selected]))>.90:continue
            selected.append(int(j))
            if len(selected)>=24:break
        if len(selected)<5:
            selected+= [int(j) for j in ids if j not in selected][:5-len(selected)]
        ids=np.array(selected);K=len(ids)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');ew_asset=np.nanmean(asset[max(0,t-756):t],axis=1)
        # Keep a fixed all-factor EW sleeve in the asset universe. The prior
        # and TE reference remain that sleeve even as the 24 view portfolios
        # change; changing the reference to EW of today's selected winners
        # would fail to constrain deviation from the static benchmark.
        R=np.column_stack([asset[max(0,t-756):t,ids],ew_asset,market[max(0,t-756):t]])
        S=ew_cov(R);b=np.r_[np.zeros(K),1.,0.]
        P=np.column_stack([np.eye(K),np.zeros(K),-np.ones(K)]);Pi=DELTA*S@b
        v=V[i,ids];view_var=np.maximum(np.diag(P@S@P.T),1e-9)
        # View confidence is calibrated from current covariance and TE, not
        # realized future tracking error. Long-only factor weights sum to 1;
        # no market sleeve is translated to an inert score constant.
        def solve(c):
            omega=np.diag(view_var*c)
            post=Pi+S@P.T@np.linalg.solve(P@S@P.T+omega,v-P@Pi)
            cov=S[:K+1,:K+1];mu=post[:K+1]
            # Reconstruct previous exposure in this reduced universe. The
            # EW sleeve supplies a common baseline across every factor.
            base_weight=float(np.min(prev))*m
            p=np.r_[np.maximum(prev[ids]-base_weight/m,0),base_weight]
            if p.sum()>0:p=p/p.sum()
            else:p=b[:K+1]
            scale=252
            def obj(w):return scale*(DELTA/2*w@cov@w-mu@w)+adjust_penalty*np.sqrt((w-p)**2+1e-8).sum()
            def jac(w):return scale*(DELTA*cov@w-mu)+adjust_penalty*(w-p)/np.sqrt((w-p)**2+1e-8)
            upper=.20-1/m
            res=minimize(obj,b[:K+1],jac=jac,method='SLSQP',bounds=[(0,upper)]*K+[(0,1.)],constraints=[{'type':'eq','fun':lambda w:w.sum()-1,'jac':lambda w:np.ones(K+1)}],options={'ftol':1e-10,'maxiter':150})
            w=np.maximum(res.x,0) if res.success else b[:K+1]
            w=w/w.sum()
            err=float(np.sqrt(max((w-b[:K+1])@cov@(w-b[:K+1])*252,0)))
            return w,err,res.success
        # Bisection on uncertainty: larger c approaches the EW prior. Keep
        # the most active solution whose predicted TE meets the bound.
        low,high=-4.,6.;w,err,ok=solve(10**high)
        for _ in range(20):
            mid=(low+high)/2;z,e,success=solve(10**mid)
            if e<=te+1e-8:w,err,ok=z,e,success;high=mid
            else:low=mid
        W[i]=w[-1]/m;W[i,ids]+=w[:-1]
        logs.append({'date':date,'selected_sleeves':K,'ew_baseline_sleeve_weight':w[-1],'predicted_te':err,'target_te':te,'confidence_inverse':10**high,'solver_success':ok,'allocation_l1_change':float(np.abs(W[i]-prev).sum()),'max_weight':W[i].max(),'training_daily_max':daily[t-1] if t else pd.NaT})
        prev=W[i].copy()
    return W,pd.DataFrame(logs)

def composite(panels,W):
    n,m=W.shape;nstocks=panels[0].shape[1];result=np.zeros((n,nstocks));den=np.zeros_like(result)
    for i in range(n):
        for j in np.flatnonzero(W[i]>1e-12):
            x=panels[j][i];ok=np.isfinite(x)
            if ok.sum()<100 or np.nanstd(x)==0:continue
            rank=(rankdata(x[ok],method='average')-.5)/ok.sum()
            result[i,ok]+=W[i,j]*rank;den[i,ok]+=W[i,j]
    # A stock with almost none of the selected information cannot be ranked
    # on one tiny remaining sleeve. No forward return involved in this mask.
    np.divide(result,den,out=result,where=den>0);result[den<.80]=np.nan
    return result.astype(np.float32)

def old_causal_weights(meta,ledgers,grid,states,cap=.20):
    n=len(grid);m=len(meta);W=np.zeros((n,m));ret=np.full((n,m),np.nan);ex=np.full((n,m),np.datetime64('NaT'),dtype='datetime64[ns]')
    for j,r in meta.iterrows():
        p=ledgers[r.record_id].set_index('date').reindex(grid);ret[:,j]=p.net_excess_path;ex[:,j]=pd.to_datetime(p.exit_date).to_numpy()
    for i,date in enumerate(grid):
        vals=np.zeros(m)
        for j in range(m):
            hist=np.flatnonzero((ex[:,j]<date.to_datetime64())&np.isfinite(ret[:,j])&(states==states[i]))[-25:]
            if len(hist)<8:continue
            z=ret[hist,j];sd=z.std(ddof=1)
            if sd>1e-8:vals[j]=max(z.mean()/sd,0)
        if vals.sum()<=0:W[i]=1/m
        else:
            # Proper upper-bound projection, never clip then renormalize.
            W[i]=capped_simplex(vals/vals.sum(),cap)
    return W

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'verification.json').exists():raise RuntimeError('Completed output already exists; choose a new version/output')
    cal,stocks,fields=q.load_market();q.dates_all=cal
    base=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=base['dates'];pos=cal.get_indexer(grid)
    inv,meta,panels,ledgers=inventory(grid,stocks)
    inv.to_csv(OUT/'all_panel_inventory.csv',index=False);meta.to_csv(OUT/'factor_metadata.csv',index=False)
    print('INVENTORY',len(inv),'canonical',int(inv.canonical.sum()),'eligible',len(meta),flush=True)
    daily,asset,active,bench,valid,market,environment=make_daily(meta,ledgers,cal,fields,grid)
    idx=daily.get_indexer(grid);idx=np.where(idx>=0,idx,daily.searchsorted(grid)-1)
    xs=[features(active[:,j],market,environment) for j in range(len(meta))]
    cache=OUT/'models_predictions.pkl'
    if cache.exists():
        cached=pd.read_pickle(cache);assert cached['keys']==meta.key.tolist();candidates=cached['candidates'];fits=cached['fits']
    else:
        candidates={};fits=[]
        tasks=[(j,xs[j],active[:,j],idx,grid,PARAMS) for j in range(len(meta))]
        # Parallel numerical workers only; no agent delegation or remote call.
        with ProcessPoolExecutor(max_workers=8) as pool:
            fut=[pool.submit(fit_predict_one,task) for task in tasks]
            for count,f in enumerate(as_completed(fut),1):
                j,c,log=f.result();candidates[j]=c;fits.extend(log)
                if count%25==0: print('FITTED',count,'/',len(meta),flush=True)
        pd.to_pickle({'keys':meta.key.tolist(),'candidates':candidates,'fits':fits},cache)
    V,state,params,quality,audit,fw=choose_predictions(meta,candidates,daily,active,ledgers,grid)
    audit.to_csv(OUT/'prediction_audit.csv',index=False);fw.to_parquet(OUT/'feature_weights.parquet',index=False);pd.DataFrame(fits).to_csv(OUT/'model_fits.csv',index=False)
    # Fail closed if a training return or a validation exit was not yet known.
    assert (pd.to_datetime(audit.last_training_return)<pd.to_datetime(audit.date)).all()
    assert (pd.to_datetime(audit.validation_max_exit.dropna())<pd.to_datetime(audit.loc[audit.validation_max_exit.notna(),'date'])).all()
    n,m=V.shape;W_eq=np.full((n,m),1/m)
    st,_=old.market_states(cal,fields,grid);W_old=old_causal_weights(meta,ledgers,grid,st)
    spec={'SJM_BL_TE2':(.02,0.),'SJM_BL_TE4':(.04,0.),'SJM_BL_TE2_TURN':(.02,.003)}
    W_all={};sigs={'ALL_EQUAL':composite(panels,W_eq),'COMMON_STATE_CORRECTED':composite(panels,W_old)}
    for key,(te,pen) in spec.items():
        W,log=allocate(V,quality,asset,active,market,daily,grid,meta,te,pen)
        assert np.allclose(W.sum(axis=1),1.,atol=1e-8) and W.max()<=.20+1e-7 and W.min()>=0
        W_all[key]=W;sigs[key]=composite(panels,W)
        log.to_csv(OUT/f'{key}.allocation_audit.csv',index=False)
        pd.DataFrame(W,index=grid,columns=meta.key).rename_axis('date').to_parquet(OUT/f'{key}.weights.parquet')
        print('ALLOCATED',key,flush=True)
    # Known local baseline and archived five-seat pool are references. The
    # five-seat archive is a proxy, not a claim of live platform equivalence.
    lookup={key:j for j,key in enumerate(meta.key)}
    sigs['IDIO_BASE']=panels[lookup['idio_vroc_size']]
    sf,*_=pd.read_pickle(ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
    stored=pd.read_pickle(ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
    seats=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact'];z=[]
    for key in seats:
        frame=sf[['date','instrument']].copy();frame['value']=stored['scores'][key].to_numpy();frame.date=pd.to_datetime(frame.date)
        x=frame.pivot(index='date',columns='instrument',values='value').reindex(index=grid,columns=stocks).to_numpy(np.float32);z.append(q.zscore(x))
    pool_score=sum(z)/5;sigs['ARCHIVED_MINGLE']=pool_score
    # Fixed 20% diagnostic overlay: preserve the archived core, express the
    # research sleeve on a comparable cross-sectional score scale.
    for key in spec:sigs[key+'_POOL20']=.8*q.zscore(pool_score)+.2*q.zscore(sigs[key])
    results=[];years=[];paths={}
    for key,score in sigs.items():
        for win,mask in [('five_year',np.ones(n,bool)),('recent',grid>='2026-01-01')]:
            r,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],fields);r.update(key=key,window=win);years.extend([{'key':key,'window':win,'year':yr,**val} for yr,val in r.get('years',{}).items()]);r.pop('years',None);r.pop('group_arithmetic_annual_pct',None);results.append(r)
            p.to_csv(OUT/f'{key}.{win}.periods.csv',index=False);d.to_csv(OUT/f'{key}.{win}.daily_nav.csv',index=False);paths[(key,win)]=p
        print('EVALUATED',key,flush=True)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False);pd.DataFrame(years).to_csv(OUT/'year_results.csv',index=False)
    # A genuinely useful causality test: mutate every observation after a
    # cutoff, refit the same prefixes, and demand unchanged historical views.
    checks=[]
    for j in [lookup['reversal20'],lookup['idio_vroc_size'],lookup['turn_long_short60_20']]:
        for stop in [75,100]:
            t=idx[stop];xx=xs[j].copy();aa=active[:,j].copy();xx[t+1:]=123.;aa[t+1:]=-.7
            _,new,_=fit_predict_one((j,xx,aa,idx[:stop+1],grid[:stop+1],PARAMS))
            diffs=[]
            for k in range(len(PARAMS)):
                a=candidates[j][k][0][:stop+1];b=new[k][0]
                assert np.array_equal(np.isnan(a),np.isnan(b));dif=float(np.nanmax(np.abs(a-b))) if np.isfinite(a).any() else 0.;diffs.append(dif)
            assert max(diffs)<1e-12
            checks.append({'key':meta.iloc[j].key,'cutoff':grid[stop],'future_mutation_max_forecast_delta':max(diffs),'passed':True})
    # Allocation recomputation with truncated inputs also checks parameter
    # validation, correlation pruning, covariance and confidence calibration.
    stop=75;t=idx[stop];Vr,sr,pr,qr,ar,fr=choose_predictions(meta,candidates,daily,active,ledgers,grid[:stop+1])
    assert np.allclose(Vr,V[:stop+1],equal_nan=True)
    Wcut,_=allocate(Vr,qr,asset[:t+1],active[:t+1],market[:t+1],daily[:t+1],grid[:stop+1],meta,.02,.003)
    delta=float(np.max(np.abs(Wcut-W_all['SJM_BL_TE2_TURN'][:stop+1])));assert delta<1e-8
    checks.append({'test':'truncated_model_selection_and_allocation','cutoff':grid[stop],'max_weight_delta':delta,'passed':True})
    old.dump(OUT/'protocol.json',{'experiment_version':VERSION,'alignment_rule':q.ALIGNMENT_RULE_VERSION,'paper':'https://arxiv.org/abs/2410.14841','journal_doi':'10.3905/jpm.2024.1.649','paper_sha256':sha(LIT/'paper-arxiv-2410.14841v1.pdf'),'author_library_wheel_sha256':sha(LIT/'jumpmodels-0.1.1-py3-none-any.whl'),'candidate_configs':spec,'model_hyperparameters':PARAMS,'feature_names':FEATURE_NAMES,'paper_deviations':['A-share local proxies instead of six US factor indices','saved five-year signal histories; min252 daily training, max756, not paper8-12years','prequential last50 completed periods for validation, at least12; not paper6years','monthly refits at available signal dates','US VIX/2Y/10Y2Y unavailable; omit, substitute separately labelled local vol and breadth','24-sleeve historical-correlation pruning and covariance diagonal shrink25%','allocation is factor-only; market used for relative views but not invested','main results are bottom-up stock ranking; paper is top-down ETF allocation','weight cap20%, predicted TE2/4%, adjustment penalty added locally','original daily ledgers have factor_valid benchmarks, possible tie/field proxies','entire factor library was discovered on this historical window; replay is exploratory, not untouched OOS'],'platform_compute':0,'formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'actual_last_signal':str(grid.max().date()),'actual_last_exit':str(cal[pos[-1]+11].date()),'weight_sum':1.,'future_return_training':'strictly before signal close; completed exits before validation selection'})
    old.dump(OUT/'verification.json',{'completed':True,'author_dp_equivalence':DP_CHECKS,'future_mutation_and_truncation':checks,'training_and_validation_date_checks':True,'weights_normalized_and_capped':True,'all_saved_panels':len(inv),'canonical_keys':int(inv.canonical.sum()),'eligible_models':m,'platform_calls':0,'daily_feature_model_count':m*len(PARAMS)})
    print(pd.DataFrame(results)[['key','window','net_excess_pct','turnover_pct','held_daily_max_drawdown_pct']].to_string(index=False),flush=True)

if __name__=='__main__':main()
