"""Independent saved-signal metric and frozen-inference checks, no refitting."""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import gc
import hashlib
import json
import time
import threading
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import lightgbm as lgb
import fengmao_rankboost_round2_20261011 as task


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    started=time.monotonic()
    out,source=task.OUT,task.SOURCE
    meta=json.loads((out/'metadata.json').read_text(encoding='utf8'))
    frozen=json.loads((out/'models_frozen.json').read_text(encoding='utf8'))
    assert meta['status']=='complete'
    task.prior.base.OUT=out
    threading.Thread(target=task.prior.base.watchdog,daemon=True).start()
    prefixes=[]
    independent,deciles,years,top20,checks=[],[],[],[],[]
    names=list(task.KINDS)+['TEMP_'+k for k in task.KINDS]+['FM_RB_BLEND']
    for family in ('target','formal'):
        atoms,y,cap,dates,axes=task.load(family)
        yfinite=np.isfinite(y)&np.isfinite(cap)
        signals={name:np.load(out/f'{name}_{family}_signals.npy',mmap_mode='r') for name in names}
        assert all(x.shape==y.shape for x in signals.values())
        blend_inputs=[signals[k] for k in task.KINDS]+[-atoms['vol60'],atoms['rev6'],atoms['size']]
        rebuilt=sum(w*np.nan_to_num(task.prior.old.rank(p),nan=0.)
                    for w,p in zip(frozen['blend']['weights'],blend_inputs)).astype(np.float32)
        rebuilt[~np.isfinite(cap)]=np.nan
        assert np.array_equal(rebuilt,signals['FM_RB_BLEND'],equal_nan=True)
        for cutoff in ('2024-06-28','2025-06-30'):
            mask=dates<=cutoff
            cut=sum(w*np.nan_to_num(task.prior.old.rank(p[mask]),nan=0.)
                    for w,p in zip(frozen['blend']['weights'],blend_inputs)).astype(np.float32)
            cut[~np.isfinite(cap[mask])]=np.nan
            assert np.array_equal(cut,rebuilt[mask],equal_nan=True)
            prefixes.append(dict(family=family,candidate='FM_RB_BLEND',cutoff=cutoff,
                finite_cells=int(np.isfinite(cut).sum()),max_difference=0,
                scope='global frozen coefficients reconstructed; component tree prefixes audited separately'))
        del rebuilt,cut,blend_inputs
        # Recompute inputs and frozen tree outputs on truncated full-stock
        # panels; this checks date-axis and grouped/peer-feature causality.
        for m in frozen['models']:
            name=m['kind']
            for cutoff in ('2024-06-28','2025-06-30'):
                mask=dates<=cutoff
                cut,nm=task.matrix({k:v[mask] for k,v in atoms.items()},dates[mask],axes,m['augmented'])
                assert nm==m['features']
                for prefix in ('','TEMP_'):
                    model=lgb.Booster(model_file=str(out/f'{prefix}{name}.txt'))
                    xx=task.predict(model,cut,cap[mask])
                    cached=signals[prefix+name][mask]
                    assert np.array_equal(xx,cached,equal_nan=True)
                    prefixes.append(dict(family=family,candidate=prefix+name,cutoff=cutoff,
                        finite_cells=int(np.isfinite(xx).sum()),max_difference=0,
                        scope='frozen inference only; temporal/full training status separate'))
                    del model,xx,cached
                del cut
                gc.collect()
        for name,x in signals.items():
            windows=[('target_119_fit' if family=='target' else 'formal_5y',np.ones(len(dates),bool))]
            if family=='formal':
                windows.append(('recent_2026',dates>='2026-01-01'))
            if name.startswith('TEMP_'):
                fam='target_119_fit' if family=='target' else 'formal_5y'
                windows += [(fam+'_temporal_validation_2024_2025',(dates>='2024-01-01')&(dates<'2026-01-01')),
                            (fam+'_temporal_2026',dates>='2026-01-01')]
            for window,mask in windows:
                periods,groups,prev=[],[],{}
                for at in np.flatnonzero(mask):
                    task.prior.base.memory_guard()
                    ok=yfinite[at]&np.isfinite(x[at])
                    ids=np.flatnonzero(ok)
                    f=pd.DataFrame(dict(signal=x[at,ids].astype(float),forward=y[at,ids].astype(float),
                        cap=cap[at,ids].astype(float)),index=ids)
                    assert len(f)>=.95*yfinite[at].sum()
                    rho=f.signal.corr(f.forward,method='spearman')
                    ic=f.signal.corr(f.forward)
                    buckets=np.ceil(f.signal.rank(method='first')*10/len(f)).astype(int).clip(1,10)
                    turn,gross=None,None
                    for g in range(1,11):
                        members=set(f.index[buckets==g])
                        t=np.nan if g not in prev else 1-len(members&prev[g])/len(members)
                        prev[g]=members
                        e=float(f.loc[list(members),'forward'].mean()-f.forward.mean())
                        groups.append(dict(candidate=name,window=window,date=str(dates[at].date()),
                            group=g,gross_excess=e,turnover=t,stocks=len(members)))
                        if g==10:
                            turn,gross=t,e
                    periods.append(dict(date=str(dates[at].date()),rank_ic=rho,ic=ic,
                        gross_excess=gross,turnover=turn,size_corr=f.signal.corr(f.cap,method='spearman')))
                    if window in ('target_119_fit','formal_5y'):
                        chosen=f.signal.sort_values(ascending=False,kind='stable').index[:20]
                        top20 += [dict(candidate=name,window=window,date=str(dates[at].date()),
                            rank=j+1,symbol=axes['symbols'][i],value=float(x[at,i])) for j,i in enumerate(chosen)]
                p=pd.DataFrame(periods)
                # Record the actual per-period sequence (not only matching
                # aggregate scores), so win-count boundary cases are reviewable.
                p.to_csv(out/f'{name}_{window}_independent_periods.csv',index=False)
                saved=pd.read_csv(out/f'{name}_{window}_periods.csv')
                errors={k:float(np.nanmax(np.abs(p[k].to_numpy()-saved[k].to_numpy())))
                        for k in ('rank_ic','ic','gross_excess','turnover')}
                assert all(v<1e-7 for v in errors.values()),(name,window,errors)
                assert p.date.tolist()==saved.date.tolist()
                assert np.isnan(p.turnover.iloc[0])
                r=p.rank_ic.to_numpy()
                mean,ir=float(r.mean()),float(r.mean()/r.std(ddof=0))
                wins=int((r>.02).sum())
                gross,turn=float(p.gross_excess.mean()*25.2),float(p.turnover.mean())
                independent.append(dict(candidate=name,window=window,periods=len(p),rank_ic=mean,rank_ir=ir,
                    wins=wins,win_rate=wins/len(p),s_i=abs(mean*ir)*wins/len(p),
                    pearson_ic=float(p.ic.mean()),gross_excess=gross,turnover=turn,net_excess=gross-turn*.006*25.2))
                checks.append(dict(candidate=name,window=window,max_errors=errors))
                gd=pd.DataFrame(groups)
                if window in ('target_119_fit','formal_5y','recent_2026'):
                    gd.to_csv(out/f'{name}_{window}_independent_group_periods.csv',index=False)
                    for g,b in gd.groupby('group'):
                        gg,tt=float(b.gross_excess.mean()*25.2),float(b.turnover.mean())
                        deciles.append(dict(candidate=name,window=window,group=int(g),gross_excess=gg,
                                            turnover=tt,net_excess=gg-tt*.006*25.2))
                    for year,b in p.groupby(p.date.str[:4]):
                        rr=b.rank_ic.to_numpy()
                        years.append(dict(candidate=name,window=window,year=year,periods=len(b),
                            rank_ic=float(rr.mean()),rank_ir=float(rr.mean()/rr.std(ddof=0)),
                            wins=int((rr>.02).sum()),net_excess=float(b.gross_excess.mean()*25.2-b.turnover.mean()*.006*25.2)))
        task.log(f'Independent {family} metrics complete')
        del atoms,y,cap,signals
        gc.collect()
    pd.DataFrame(independent).to_csv(out/'independent_results.csv',index=False)
    pd.DataFrame(deciles).to_csv(out/'deciles.csv',index=False)
    pd.DataFrame(years).to_csv(out/'years.csv',index=False)
    pd.DataFrame(top20).to_csv(out/'top20.csv',index=False)
    models=list(out.glob('*.txt'))
    audit=dict(status='passed',independent_pandas_metrics=checks,frozen_input_prefix_checks=prefixes,
        checkpoint_sha256={p.name:digest(p) for p in models},seconds=time.monotonic()-started,
        memory=task.prior.base.PEAK,upstream_actual_input_audits=[
            str((source/'raw_causality_checks.json').relative_to(task.ROOT)),
            str((task.PEER/'causality_checks.json').relative_to(task.ROOT))],
        historical_training={'full_models':'NONCAUSAL all119 supervised labels',
            'TEMP_models':'fresh training only label exits<=20231231; no later labels',
            'blend':'NONCAUSAL full119 global coefficient search'},
        limitation='frozen input checks do not remove all-window training/selection leakage or public date uncertainty')
    task.save('verification.json',audit)
    task.prior.base.DONE.set()
    print(pd.DataFrame(independent).to_string(index=False),flush=True)
    task.log('INDEPENDENT AUDIT PASSED')


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()
