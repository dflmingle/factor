"""Predeclared daily cross-sectional rank THEN rolling correlation hypotheses.

Distinguishes Alpha101-like Rank->Correlation from TS_RANK->Correlation;
literal d3c/r6 clue only, not claiming the opponent used Alpha101.
"""
from __future__ import annotations
import gc, hashlib, json, threading, time
from pathlib import Path
import numpy as np, pandas as pd
import fengmao_information_shock_20261011 as info
from fengmao_literal_clue_20261011 import SelectionEvaluator

shared=info.shared
ROOT=info.ROOT
OUT=ROOT/'research_reports/platform_alignment/fengmao-daily-rankcorr-20261011'
PAIRS=[('d3close','d3logv'),('d3close','volume'),('ret3','d3logv'),
       ('intraday','d2logv'),('intraday','d3logv'),('close','volume')]


def crossrank(a):
    # Bound temporary rank allocations by 16 dates; never materialize an
    # O(stocks^2) correlation matrix.
    out=np.full(a.shape,np.nan,np.float32)
    for i in range(0,len(a),16):
        out[i:i+16]=shared.rank(a[i:i+16]); shared.guard()
    return out


def specs():
    rows=[]
    signals=[f'{a}_{b}_corr{n}' for a,b in PAIRS for n in (3,6,20)]
    for name in signals:
        for sign in (1,-1): rows.append(dict(signal=name,mode='plain',sign=sign))
        for by in ('volume6','volatility6','volatility20'):
            for mode in ('rank','peer_diff'):
                for sign in (1,-1): rows.append(dict(signal=name,group=by,mode=mode,buckets=5,sign=sign))
    return rows


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen_candidates.json').exists(): raise RuntimeError('No post-freeze retuning')
    shared.OUT=OUT
    threading.Thread(target=shared.watchdog,daemon=True).start()
    shared.validate_alignment_config(shared.alignment_config_snapshot())
    start=time.monotonic()
    _,y,cap,dates,axes=shared.prior.load('target'); del _
    _,fy,fc,fd,fa=shared.prior.load('formal'); del _
    union=pd.DatetimeIndex(sorted(set(dates)|set(fd)))
    exits=pd.DatetimeIndex(axes['exits'])
    early=(dates<shared.FINAL_START)&(exits<shared.FINAL_START)
    dev=early&(dates>=shared.DEVELOP_START)
    declared=specs()
    shared.write('protocol.json',dict(rule=shared.ALIGNMENT_RULE_VERSION,candidates=len(declared),specs=declared,
        hypotheses='daily cross-sectional RANK before six-day rolling correlation, not TS_RANK',
        selection_dates=dates[early].astype(str).tolist(),selection_exit_dates=exits[early].astype(str).tolist(),
        development_dates=dates[dev].astype(str).tolist(),final_start=str(shared.FINAL_START),
        final_used_for_selection=False,final_previously_exposed=True,platform_cost=0,
        pairs=PAIRS,rolling_windows=[3,6,20],rank_axis='entire same-date historical eligible universe',
        fidelity='local diagnostic; private formula and actual signal schedule unknown'))
    cal,c,v,dc=info.literal.load_prices(fa['symbols'])
    o=np.full_like(c,np.nan); symbols=pd.Index(fa['symbols'])
    for p in sorted((ROOT/'quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet')):
        f=pd.read_parquet(p,columns=['date','instrument','open'])
        di=cal.get_indexer(pd.to_datetime(f.date).dt.normalize()); si=symbols.get_indexer(f.instrument)
        valid=(di>=0)&(si>=0); o[di[valid],si[valid]]=f.open.to_numpy(np.float32)[valid]
        shared.guard()
    o[~np.isfinite(dc)|(o<=0)]=np.nan
    positions=cal.get_indexer(union)
    # Causal differences are computed in bounded chunks before same-date rank.
    ranked={}
    definitions=['d3close','d3logv','ret3','intraday','d2logv','close','volume']
    for name in definitions:
        a=np.full_like(c,np.nan)
        if name=='d3close': a[3:]=c[3:]-c[:-3]
        elif name=='ret3': a[3:]=c[3:]/c[:-3]-1
        elif name in ('d3logv','d2logv'):
            lag=3 if name=='d3logv' else 2
            a[lag:]=np.log(v[lag:]/v[:-lag])
        elif name=='intraday': a=c/o-1
        elif name=='close': a=c.copy()
        else: a=v.copy()
        a[~np.isfinite(dc)|~np.isfinite(a)]=np.nan
        ranked[name]=crossrank(a); del a; gc.collect()
        shared.log(f'daily cross ranks {name}')
    atoms={f'{a}_{b}_corr{n}':np.full((len(union),len(symbols)),np.nan,np.float32)
           for a,b in PAIRS for n in (3,6,20)}
    for name in ('volume6','volatility6','volatility20'): atoms[name]=np.full_like(next(iter(atoms.values())),np.nan)
    checks=[]; cutoff=cal.get_indexer([pd.Timestamp('2025-06-30')])[0]
    for begin in range(0,len(symbols),96):
        end=min(begin+96,len(symbols))
        for a,b in PAIRS:
            aa=pd.DataFrame(ranked[a][:,begin:end],dtype=float); bb=pd.DataFrame(ranked[b][:,begin:end],dtype=float)
            for n in (3,6,20):
                z=aa.rolling(n,min_periods=n).corr(bb)
                atoms[f'{a}_{b}_corr{n}'][:,begin:end]=z.iloc[positions].to_numpy(np.float32)
                if begin==0:
                    prefix=aa.iloc[:cutoff+1].rolling(n,min_periods=n).corr(bb.iloc[:cutoff+1])
                    assert np.array_equal(z.iloc[:cutoff+1].to_numpy(),prefix.to_numpy(),equal_nan=True)
                    checks.append(dict(atom=f'{a}_{b}_corr{n}',cutoff='2025-06-30',max_difference=0.))
        cc=pd.DataFrame(c[:,begin:end],dtype=float); vv=pd.DataFrame(v[:,begin:end],dtype=float)
        r=cc/cc.shift(1)-1
        atoms['volume6'][:,begin:end]=vv.rolling(6,min_periods=6).mean().iloc[positions].to_numpy(np.float32)
        for n in (6,20): atoms[f'volatility{n}'][:,begin:end]=r.rolling(n,min_periods=n).std().iloc[positions].to_numpy(np.float32)
        gc.collect(); shared.guard()
    del ranked,c,v,o,dc,aa,bb,cc,vv,r,z,prefix,f
    gc.collect()
    shared.write('daily_recipe_prefix_check.json',checks)
    shared.write('axes.json',dict(dates=union.astype(str).tolist(),symbols=fa['symbols']))
    np.savez_compressed(OUT/'atoms_raw.npz',**atoms)
    ix=union.get_indexer(dates); fi=union.get_indexer(fd)
    ev=SelectionEvaluator(y[early],cap[early]); dv=SelectionEvaluator(y[dev],cap[dev])
    records=[]
    for j,spec in enumerate(declared):
        try:
            s=info.expression(spec,atoms)[ix]; s[~np.isfinite(cap)]=np.nan
            em=ev.evaluate(s[early]); dm=dv.evaluate(s[dev])
            loss=.5*shared.objective(em)+shared.objective(dm)+2*max(-dm['net_excess'],0)
            records.append(dict(spec=spec,selection_loss=loss,early=em,development=dm,status='evaluated'))
        except (ValueError,FloatingPointError) as exc:
            records.append(dict(spec=spec,selection_loss=1e9,status='failed',error=str(exc)))
        if (j+1)%50==0: shared.log(f'rankcorr hypotheses {j+1}/{len(declared)}')
        shared.guard()
    shared.write('search_results.json',records)
    frozen=[]
    for category in ('plain','rank','peer_diff'):
        rows=[r for r in records if r['spec']['mode']==category and r['status']=='evaluated']
        best=min(rows,key=lambda r:r['selection_loss'])
        frozen.append(dict(name='FM_RANKCORR_'+category.upper(),spec=best['spec'],selection=best))
    shared.write('frozen_candidates.json',dict(frozen_before_final_labels=True,candidates=frozen))
    shared.write('freeze_hashes.json',dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        frozen=hashlib.sha256((OUT/'frozen_candidates.json').read_bytes()).hexdigest()))
    results=[]
    for model in frozen:
        s=info.expression(model['spec'],atoms)
        for scope,sig,yy,cp,dt in [('target',s[ix],y,cap,dates),('formal',s[fi],fy,fc,fd)]:
            sig[~np.isfinite(cp)]=np.nan
            np.save(OUT/f'{model["name"]}_{scope}_signals.npy',sig)
            windows=[('target119',np.ones(len(dt),bool)),('historical_final24',dt>=shared.FINAL_START)] if scope=='target' else [
                ('formal_5y',np.ones(len(dt),bool)),('formal_final',dt>=shared.FINAL_START),('recent_2026',dt>=pd.Timestamp('2026-01-01'))]
            for window,mask in windows:
                m,p,g=shared.metrics(sig[mask],yy[mask],cp[mask],dt[mask])
                p.to_csv(OUT/f'{model["name"]}_{window}_periods.csv',index=False)
                g.to_csv(OUT/f'{model["name"]}_{window}_groups.csv',index=False)
                results.append(dict(candidate=model['name'],window=window,**m))
                shared.log(f'{model["name"]} {window}: IC {m["rank_ic"]:.6f}, IR {m["rank_ir"]:.3f}, net {m["net_excess"]:.3f}')
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    shared.STOP.set()
    shared.write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,rule=shared.ALIGNMENT_RULE_VERSION,
        candidates=len(declared),evaluated=sum(r['status']=='evaluated' for r in records),memory=shared.PEAK,
        seconds=time.monotonic()-start,final_used_for_selection=False,final_previously_exposed=True))


if __name__=='__main__': main()
