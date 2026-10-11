"""Independent pandas/NumPy audits of frozen local results and daily ledgers."""
from __future__ import annotations
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import argparse
import gc
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import fengmao_nested_causal_20261011 as task

ROOT=task.ROOT
SOURCE=task.prior.SOURCE


def audit(out):
    results=pd.read_csv(out/'results.csv')
    protocol=json.loads((out/'protocol.json').read_text(encoding='utf8'))
    frozen=json.loads((out/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
    checks=[]; tops=[]; errors=[]
    for scope in ('target','formal'):
        axisfile='axes.json' if scope=='target' else 'axes_formal.json'
        npzfile='atoms.npz' if scope=='target' else 'atoms_formal.npz'
        axes=json.loads((SOURCE/axisfile).read_text(encoding='utf8'))
        dt=pd.DatetimeIndex(axes['dates'])
        with np.load(SOURCE/npzfile) as data:
            y=data['target']; cap=data['market_cap']
        if scope=='target':
            exits=pd.DatetimeIndex(axes['exits'])
            names=protocol.get('purged_refit',protocol.get('selection_dates'))
            use=dt.isin(pd.DatetimeIndex(names))
            assert np.all(exits[use]<task.FINAL_START)
            assert not np.any(use&(dt>=task.FINAL_START))
            checks.append(dict(check='training_labels_before_final_boundary',passed=True,periods=int(use.sum()),
                               latest_exit=str(exits[use].max()),first_final=str(task.FINAL_START)))
        for model in frozen:
            signal=np.load(out/(model['name']+'_'+scope+'_signals.npy'),mmap_mode='r')
            actual=[]
            for i,date in enumerate(dt):
                ok=np.isfinite(signal[i])&np.isfinite(y[i])&np.isfinite(cap[i])
                ids=np.flatnonzero(ok)
                f=pd.DataFrame(dict(signal=signal[i,ids].astype(float),label=y[i,ids].astype(float),cap=cap[i,ids].astype(float)),index=ids)
                # pandas average ranks are independent of the pipeline's scipy ranks.
                ric=f.signal.corr(f.label,method='spearman'); pic=f.signal.corr(f.label)
                order=f.signal.sort_values(kind='stable').index.to_numpy()
                held=order[np.ceil(np.arange(1,len(order)+1)*10/len(order)).astype(int)==10]
                gross=float(f.loc[held,'label'].mean()-f.label.mean())
                actual.append(dict(date=str(date.date()),rank_ic=ric,ic=pic,gross_excess=gross,held=set(held)))
                if i==len(dt)-1:
                    for j,k in enumerate(f.signal.sort_values(ascending=False,kind='stable').index[:20]):
                        tops.append(dict(candidate=model['name'],scope=scope,date=str(date.date()),rank=j+1,
                                         symbol=axes['symbols'][k],value=float(signal[i,k])))
            windows=results[results.candidate.eq(model['name'])]
            windows=windows[~windows.window.str.startswith(('formal','recent'))] if scope=='target' else windows[windows.window.str.startswith(('formal','recent'))]
            for _,row in windows.iterrows():
                saved=pd.read_csv(out/f'{model["name"]}_{row.window}_periods.csv')
                keys=set(saved.date)
                pp=[a.copy() for a in actual if a['date'] in keys]
                prev=None
                for a in pp:
                    a['turnover']=np.nan if prev is None else 1-len(a['held']&prev)/len(a['held'])
                    prev=a.pop('held')
                p=pd.DataFrame(pp)
                assert p.date.tolist()==saved.date.tolist()
                differences={k:float(np.nanmax(np.abs(p[k]-saved[k]))) for k in ('rank_ic','ic','gross_excess','turnover')}
                assert max(differences.values())<1e-7,(model['name'],row.window,differences)
                rho=p.rank_ic.to_numpy(); pic=p.ic.to_numpy()
                m=float(rho.mean()); ir=m/float(rho.std(ddof=0)); wins=int((rho>.02).sum())
                net=float(p.gross_excess.mean()*25.2-p.turnover.mean()*.006*25.2)
                # Pipeline stores percentile ranks as float32; pandas ranks
                # remain float64. Measured IR rounding difference is 1.05e-9.
                assert abs(m-row.rank_ic)<1e-8
                assert abs(ir-row.rank_ir)<1e-8
                assert wins==row.wins
                assert abs(net-row.net_excess)<1e-7
                errors.append(dict(candidate=model['name'],window=row.window,**{k+'_max_error':v for k,v in differences.items()},
                                   rank_ic=m,rank_ir=ir,wins=wins,net_excess=net,
                                   summary_mean_error=abs(m-row.rank_ic),summary_ir_error=abs(ir-row.rank_ir)))
                if 'pearson_ir_sample' in row:
                    assert abs(float(pic.mean()/pic.std(ddof=1))-row.pearson_ir_sample)<1e-9
        # Reload causal atoms and reconstruct frozen inference on true time
        # prefixes. This is separate from the label-boundary training audit.
        if 'purged_refit' in protocol:
            with np.load(SOURCE/npzfile) as z:
                atoms={k:z[k] for k in z.files if k not in ('target','market_cap')}
            task.OUT=out
            predictor=lambda m,a,cp:task.signal_for(m,a,cp)
        else:
            import fengmao_literal_clue_20261011 as literal
            task.OUT=out
            la=json.loads((out/'literal_axes.json').read_text(encoding='utf8'))
            ix=pd.DatetimeIndex(la['dates']).get_indexer(dt)
            with np.load(out/'literal_atoms.npz') as z:
                atoms={k:z[k][ix] for k in z.files}
            def predictor(m,a,cp):
                s=literal.expression(m['spec'],a)
                s[~np.isfinite(cp)]=np.nan
                return s
        for cutoff in ('2024-06-28','2025-06-30'):
            mask=dt<=cutoff
            for m in frozen:
                rebuilt=predictor(m,{k:a[mask] for k,a in atoms.items()},cap[mask])
                cached=np.load(out/(m['name']+'_'+scope+'_signals.npy'),mmap_mode='r')[mask]
                assert np.array_equal(np.isfinite(rebuilt),np.isfinite(cached))
                diff=float(np.nanmax(np.abs(rebuilt-cached)))
                assert diff<1e-7,(m['name'],scope,cutoff,diff)
                checks.append(dict(check='frozen_inference_time_prefix',candidate=m['name'],scope=scope,
                                   cutoff=cutoff,passed=True,max_difference=diff,
                                   limitation='frozen inference and cached causal atoms; does not prove pristine holdout'))
                del rebuilt,cached
        del atoms,y,cap
        gc.collect()
    # Verify monthly formulas from actual saved daily cost-adjusted returns.
    ledgers=list(out.glob('*_monthly_c_proxy.csv'))
    for path in ledgers:
        name=path.name.removesuffix('_monthly_c_proxy.csv')
        daily=pd.read_csv(out/(name+'_daily_proxy.csv'))
        monthly=pd.read_csv(path)
        assert not daily.date.duplicated().any()
        dm=pd.to_datetime(daily.date).dt.strftime('%Y-%m')
        largest=0.
        for _,r in monthly.iterrows():
            d=daily[dm.eq(r.month)]
            p=d.portfolio.to_numpy(); b=d.benchmark.to_numpy(); n=len(d)
            rp=np.prod(1+p)-1; rb=np.prod(1+b)-1
            rex=(1+rp)**(252/n)-(1+rb)**(252/n)
            sr=p.mean()/p.std(ddof=1)*np.sqrt(252) if n>1 and p.std(ddof=1)>0 else 0.
            nav=np.r_[1.,np.cumprod(1+p)]
            dd=-(nav/np.maximum.accumulate(nav)-1).min()
            turn=d.turnover.sum()
            raw=max(rex,0)/max(turn,.3)*sr*(1-1.2*dd) if n>=2 else 0.
            nc=float(np.clip(raw/.6,0,1))
            for field,value in dict(r_p=rp,r_b=rb,annual_rex=rex,annual_sr=sr,max_dd=dd,
                                    turnover_month=turn,raw_c=raw,nc=nc).items():
                difference=abs(float(value)-r[field]); largest=max(largest,difference)
                assert np.isclose(value,r[field],rtol=1e-9,atol=1e-10),(name,r.month,field,value,r[field])
        checks.append(dict(check='monthly_daily_C_algebra',candidate=name,passed=True,months=len(monthly),max_error=largest,
                           limitation='validates monthly algebra; factor_valid benchmark and local holdings remain proxies'))
    if 'purged_refit' in protocol:
        hashes=json.loads((out/'freeze_hashes.json').read_text(encoding='utf8'))
        assert hashes['script']==hashlib.sha256((ROOT/'scripts/fengmao_nested_causal_20261011.py').read_bytes()).hexdigest()
        assert hashes['shallow_model']==hashlib.sha256((out/'FM_CAUSAL_SHALLOW.txt').read_bytes()).hexdigest()
        for m in frozen:
            assert hashes[m['name']]==hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()
    else:
        hashes=json.loads((out/'freeze_hashes.json').read_text(encoding='utf8'))
        assert hashes['frozen']==hashlib.sha256((out/'frozen_candidates.json').read_bytes()).hexdigest()
        assert hashes['script']==hashlib.sha256((ROOT/'scripts/fengmao_literal_clue_20261011.py').read_bytes()).hexdigest()
    checks.append(dict(check='freeze_hashes_unchanged',passed=True))
    pd.DataFrame(tops).to_csv(out/'top20_raw.csv',index=False)
    pd.DataFrame(errors).to_csv(out/'independent_metrics.csv',index=False)
    (out/'verification.json').write_text(json.dumps(dict(status='passed',checks=checks,
        metric_windows=len(errors),scope='independent metric and monthly algebra audit; historical final already exposed',
        opponent_exact_recovery_verified=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'{out.name}: {len(errors)} windows and {len(ledgers)} monthly ledgers independently verified',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('directories',nargs='+')
    for name in parser.parse_args().directories:
        audit(ROOT/'research_reports/platform_alignment'/name)
