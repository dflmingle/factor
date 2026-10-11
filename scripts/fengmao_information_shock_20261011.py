"""Raw daily information-shock and leave-one-out group return hypotheses.

Predeclared grammar, purged early/development selection and frozen historical
holdout. Uses qfq/full A/total_mv cached labels, no platform or remote models.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import gc
import hashlib
import json
from pathlib import Path
import threading
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import fengmao_literal_clue_20261011 as literal
from platform_alignment_rules import alignment_config_snapshot, validate_alignment_config

shared=literal.shared
ROOT=shared.ROOT
OUT=ROOT/'research_reports/platform_alignment/fengmao-information-shock-20261011'
shared.OUT=OUT


def recipes(c,v,o):
    r=c/c.shift(1)-1
    intraday=c/o-1
    overnight=o/c.shift(1)-1
    logv=np.log(v.where(v>0))
    surprise=v/v.rolling(20,min_periods=20).mean()
    values={'volsurprise':surprise,'volmean20':v.rolling(20,min_periods=20).mean(),
            'volcv20':v.rolling(20,min_periods=20).std()/v.rolling(20,min_periods=20).mean(),
            'volatility20':r.rolling(20,min_periods=20).std(),
            'logvolshock3':logv-logv.shift(3),
            'delta3close':c-c.shift(3),'return3':c/c.shift(3)-1,
            'corr6_d3c_volume':(c-c.shift(3)).rolling(6,min_periods=6).corr(v),
            'corr6_d3c_d3v':(c-c.shift(3)).rolling(6,min_periods=6).corr(logv-logv.shift(3)),
            'corr6_r_volume':r.rolling(6,min_periods=6).corr(v),
            'corr6_intraday_shock':intraday.rolling(6,min_periods=6).corr(logv.diff()),
            'corr6_rankd3c_rankv':(c-c.shift(3)).rolling(6,min_periods=6).rank(pct=True).rolling(6,min_periods=6).corr(v.rolling(6,min_periods=6).rank(pct=True))}
    shock_z=(logv-logv.rolling(60,min_periods=60).mean())/logv.rolling(60,min_periods=60).std()
    values['volshockz60']=shock_z
    for n in (3,6,20,60):
        mean=lambda x:x.rolling(n,min_periods=n).mean()
        total=lambda x:x.rolling(n,min_periods=n).sum()
        values.update({f'return{n}':c/c.shift(n)-1,
                       f'relvol{n}':mean(surprise),
                       f'weightedrev{n}':-total(r*surprise)/total(surprise),
                       f'highvolret{n}':total(r.where(surprise>1,0).where(r.notna()&surprise.notna())),
                       f'lowvolret{n}':total(r.where(surprise<=1,0).where(r.notna()&surprise.notna())),
                       f'intrarev{n}':-mean(intraday),
                       f'overnightmom{n}':mean(overnight),
                       f'tug{n}':mean(overnight-intraday),
                       f'disagreement{n}':mean(-intraday*overnight),
                       f'shockpressure{n}':-mean(r*shock_z)})
    return values


def build(cal,c,v,o,cap,positions):
    result=None; prefix_checks=[]
    for start in range(0,c.shape[1],96):
        shared.guard(); stop=min(start+96,c.shape[1])
        cs,vs,opens=[pd.DataFrame(x[:,start:stop],dtype=float) for x in (c,v,o)]
        values=recipes(cs,vs,opens)
        if result is None:
            result={name:np.full((len(positions),c.shape[1]),np.nan,np.float32) for name in values}
        for name,x in values.items(): result[name][:,start:stop]=x.iloc[positions].to_numpy(np.float32)
        if start==0:
            cutoff=cal.get_indexer([pd.Timestamp('2025-06-30')])[0]
            prefix=recipes(cs.iloc[:cutoff+1],vs.iloc[:cutoff+1],opens.iloc[:cutoff+1])
            for name in values:
                a=values[name].iloc[:cutoff+1].to_numpy(); b=prefix[name].to_numpy()
                assert np.array_equal(np.isfinite(a),np.isfinite(b)),name
                assert np.allclose(a,b,atol=0,rtol=0,equal_nan=True),name
                prefix_checks.append(dict(atom=name,cutoff='2025-06-30',max_difference=0.0))
        del cs,vs,opens,values
        gc.collect()
        if start%960==0: shared.log(f'raw causal recipes {stop}/{c.shape[1]}')
    active=np.isfinite(cap[positions])
    for name in result: result[name][~active|~np.isfinite(result[name])]=np.nan
    result['size']=cap[positions].copy()
    shared.write('daily_recipe_prefix_check.json',prefix_checks)
    return result


def specs():
    output=[]
    by=['volmean20','volsurprise','volshockz60','volcv20','volatility20','size']
    families={
        'literal_correlation':['corr6_d3c_volume','corr6_d3c_d3v','corr6_r_volume',
                               'corr6_intraday_shock','corr6_rankd3c_rankv'],
        'volume_information':[f'{stem}{n}' for n in (3,6,20,60) for stem in
                              ('weightedrev','highvolret','lowvolret','shockpressure')],
        'day_night_information':[f'{stem}{n}' for n in (3,6,20,60) for stem in
                                 ('intrarev','overnightmom','tug','disagreement')],
        'peer_return_difference':[f'return{n}' for n in (3,6,20,60)]}
    for family,signals in families.items():
        for name in signals:
            for sign in (1,-1):
                output.append(dict(family=family,signal=name,mode='plain',sign=sign))
            # Keep a compact predeclared grammar: 5 buckets; three observable
            # conditions per family. No adaptive expansion from holdout labels.
            conditions=by if family in ('literal_correlation','peer_return_difference') else ['volsurprise','volcv20','volatility20']
            modes=('peer_diff','peer_z','rank') if family=='peer_return_difference' else ('rank','peer_diff')
            for group in conditions:
                for mode in modes:
                    for sign in (1,-1):
                        output.append(dict(family=family,signal=name,group=group,buckets=5,mode=mode,sign=sign))
    return output


def expression(spec,atoms):
    a=atoms[spec['signal']]
    if spec['mode']=='plain': out=a.copy()
    else:
        b=atoms[spec['group']]; ok=np.isfinite(a)&np.isfinite(b)
        bins=np.minimum(np.floor((shared.rank(np.where(ok,b,np.nan))+.5)*spec['buckets']),spec['buckets']-1)
        out=np.full_like(a,np.nan)
        for g in range(spec['buckets']):
            mask=ok&(bins==g); bucket=np.where(mask,a,np.nan)
            if spec['mode']=='rank': z=shared.rank(bucket)
            else:
                # Observable same-date peer returns with self explicitly
                # removed. Never uses future labels or future peer selection.
                count=mask.sum(1,keepdims=True)
                peer=(np.nansum(bucket,axis=1,keepdims=True)-a)/np.maximum(count-1,1)
                z=a-peer
                if spec['mode']=='peer_z':
                    sd=np.nanstd(bucket,axis=1,keepdims=True)
                    z=z/np.maximum(sd,1e-8)
                z=np.where(count>1,z,np.nan)
            out[mask]=z[mask]
    return (spec['sign']*out).astype(np.float32)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen_candidates.json').exists(): raise RuntimeError('No post-freeze retuning')
    validate_alignment_config(alignment_config_snapshot())
    shared.OUT=OUT
    threading.Thread(target=shared.watchdog,daemon=True).start()
    start=time.monotonic()
    declared=specs()
    _,y,cap,dates,axes=shared.prior.load('target'); del _
    _,fy,fc,fd,fa=shared.prior.load('formal'); del _
    assert fa['symbols']==axes['symbols']
    exits=pd.DatetimeIndex(axes['exits'])
    early=(dates<shared.FINAL_START)&(exits<shared.FINAL_START)
    dev=early&(dates>=shared.DEVELOP_START)
    final=dates>=shared.FINAL_START
    shared.write('protocol.json',dict(rule=shared.ALIGNMENT_RULE_VERSION,
        hypotheses='raw volume shock, d3-price/r6-correlation and leave-one-out past peer returns',
        candidates=len(declared),specs=declared,selection_dates=dates[early].astype(str).tolist(),
        development_dates=dates[dev].astype(str).tolist(),final_dates=dates[final].astype(str).tolist(),
        selection_exit_dates=exits[early].astype(str).tolist(),final_used_for_selection=False,
        final_is_previously_exposed_history=True,platform_cost=0,memory_limits=dict(process_gib=2.25,available_floor_gib=1.25),
        date_source='119 inferred opponent dates; independent 120-date formal platform template',
        fidelity='proxy; daily qfq OHLCV and total_mv; volume-bucket peers are not text/industry peers',
        conditions_available_at_signal=True))
    shared.log(f'predeclared {len(declared)} hypotheses, loading daily history')
    cal,c,v,daily_cap=literal.load_prices(fa['symbols'])
    o=np.full_like(c,np.nan)
    stocks=pd.Index(fa['symbols'])
    paths=sorted((ROOT/'quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet'))
    for path in paths:
        f=pd.read_parquet(path,columns=['date','instrument','open'])
        i=cal.get_indexer(pd.to_datetime(f.date).dt.normalize()); k=stocks.get_indexer(f.instrument)
        ok=(i>=0)&(k>=0)
        o[i[ok],k[ok]]=f.open.to_numpy(np.float32)[ok]
        shared.guard()
    o[~np.isfinite(daily_cap)|(o<=0)]=np.nan
    union=pd.DatetimeIndex(sorted(set(dates)|set(fd)))
    atoms=build(cal,c,v,o,daily_cap,cal.get_indexer(union))
    del c,v,o,daily_cap,f
    gc.collect()
    shared.write('axes.json',dict(dates=union.astype(str).tolist(),symbols=fa['symbols']))
    np.savez_compressed(OUT/'atoms_raw.npz',**atoms)
    ix=union.get_indexer(dates); fi=union.get_indexer(fd)
    ev=literal.SelectionEvaluator(y[early],cap[early]); dv=literal.SelectionEvaluator(y[dev],cap[dev])
    records=[]
    with threadpool_limits(limits=1):
        for j,spec in enumerate(declared):
            try:
                sig=expression(spec,atoms)[ix]
                sig[~np.isfinite(cap)]=np.nan
                em=ev.evaluate(sig[early]); dm=dv.evaluate(sig[dev])
                loss=.5*shared.objective(em)+shared.objective(dm)+2*max(-dm['net_excess'],0)
                records.append(dict(index=j,spec=spec,selection_loss=loss,early=em,development=dm,status='evaluated'))
            except (ValueError,FloatingPointError) as exc:
                records.append(dict(index=j,spec=spec,selection_loss=1e9,error=str(exc),status='failed'))
            if (j+1)%100==0:
                shared.write('search_results.json',records); shared.log(f'new hypotheses {j+1}/{len(declared)}')
            shared.guard()
        shared.write('search_results.json',records)
        frozen=[]
        for family in dict.fromkeys(s['family'] for s in declared):
            rows=[r for r in records if r['spec']['family']==family and r['status']=='evaluated']
            if not rows: continue
            best=min(rows,key=lambda r:r['selection_loss'])
            frozen.append(dict(name='FM_SHOCK_'+family.upper(),spec=best['spec'],selection=best))
        shared.write('frozen_candidates.json',dict(frozen_before_final_labels=True,candidates=frozen))
        shared.write('freeze_hashes.json',dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     frozen=hashlib.sha256((OUT/'frozen_candidates.json').read_bytes()).hexdigest()))
        results=[]; corr_rows=[]; year_rows=[]
        for item in frozen:
            us=expression(item['spec'],atoms)
            for scope,sig,yy,cc,dd in [('target',us[ix],y,cap,dates),('formal',us[fi],fy,fc,fd)]:
                sig[~np.isfinite(cc)]=np.nan
                np.save(OUT/f'{item["name"]}_{scope}_signals.npy',sig)
                windows=[('target119',np.ones(len(dd),bool)),('historical_final24',final)] if scope=='target' else [
                    ('formal_5y',np.ones(len(dd),bool)),('recent_2026',dd>=pd.Timestamp('2026-01-01')),
                    ('formal_final',dd>=shared.FINAL_START)]
                for window,mask in windows:
                    m,p,g=shared.metrics(sig[mask],yy[mask],cc[mask],dd[mask])
                    p.to_csv(OUT/f'{item["name"]}_{window}_periods.csv',index=False)
                    g.to_csv(OUT/f'{item["name"]}_{window}_groups.csv',index=False)
                    results.append(dict(candidate=item['name'],window=window,**m))
                    shared.log(f'{item["name"]} {window}: IC {m["rank_ic"]:.6f}, IR {m["rank_ir"]:.3f}, wins {m["wins"]}/{m["periods"]}')
                if scope=='formal':
                    for year in sorted(set(dd.year)):
                        m,_,_=shared.metrics(sig[dd.year==year],yy[dd.year==year],cc[dd.year==year],dd[dd.year==year])
                        year_rows.append(dict(candidate=item['name'],year=int(year),**m))
                    for ref in ('rev3','rev20','lowturn','vol20','size'):
                        # References saved under the exact same formal axes.
                        with np.load(shared.prior.SOURCE/'atoms_formal.npz') as z: reference=z[ref]
                        ok=np.isfinite(sig)&np.isfinite(reference)&np.isfinite(cc)
                        rho=shared.rowcorr(shared.rank(np.where(ok,sig,np.nan)),shared.rank(np.where(ok,reference,np.nan)))
                        corr_rows.append(dict(candidate=item['name'],reference=ref,mean_signal_date_spearman=float(np.nanmean(rho)),
                                              fidelity='signal-date diagnostic; not all-daily correlation'))
                    mask=np.isfinite(cc)&((shared.rank(cc)+.5)>.20)
                    m,_,_=shared.metrics(np.where(mask,sig,np.nan),yy,cc,dd)
                    results.append(dict(candidate=item['name'],window='formal_exclude_smallest20_diagnostic',**m))
        pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
        pd.DataFrame(corr_rows).to_csv(OUT/'reference_correlations.csv',index=False)
        pd.DataFrame(year_rows).to_csv(OUT/'years.csv',index=False)
    shared.STOP.set()
    shared.write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,rule=shared.ALIGNMENT_RULE_VERSION,
        seconds=time.monotonic()-start,memory=shared.PEAK,candidates=len(declared),evaluated=sum(r['status']=='evaluated' for r in records),
        formal_config=alignment_config_snapshot(),holdout='historical and previously exposed; no final-label selection',
        public_target=dict(rank_ic=.1722791715386185,rank_ir=1.6613206049954048,wins=111,periods=119)))
    shared.log('complete; no exact recovery claim')


if __name__=='__main__': main()
