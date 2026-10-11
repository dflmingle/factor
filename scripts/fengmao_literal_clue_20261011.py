"""Predeclared literal d3c/r6/grpvol interpretations, local and purged.

Select formulas using only core and internal development labels. Frozen
historical validation is already exposed by prior research, not a blind test.
No platform access and no recovery claim from aggregate similarity alone.
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
import fengmao_nested_causal_20261011 as shared

ROOT=shared.ROOT
OUT=ROOT/'research_reports/platform_alignment/fengmao-literal-clue-20261011'
shared.OUT=OUT
SIGNALS=('delta3close','delta6close','delay3close','rev6raw',
         'delta3rel','delta3volscaled','tsrank6close','tsrank6delta3',
         'delay3tsrank6','rev6delay3','delta3rank6','delta3minusrev6')
GROUPS=('volume1','volume3','volume6','volume20','volume60',
        'returnvol6','returnvol20','returnvol60')


def load_prices(symbols):
    # This loader exactly replicates the price eligibility used for saved y.
    cal,c=shared.load_close(symbols)
    columns=pd.Index(symbols)
    v=np.full(c.shape,np.nan,np.float32)
    paths=sorted((ROOT/'quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet'))
    for j,path in enumerate(paths):
        f=pd.read_parquet(path,columns=['date','instrument','volume'])
        i=cal.get_indexer(pd.to_datetime(f.date).dt.normalize()); k=columns.get_indexer(f.instrument)
        ok=(i>=0)&(k>=0)
        v[i[ok],k[ok]]=f.volume.to_numpy(np.float32)[ok]
        shared.guard()
    # Volume observations must have active daily_basic rows, as in source.
    daily_cap=np.full(c.shape,np.nan,np.float32)
    paths=sorted((ROOT/'quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a').glob('daily_basic_*.parquet'))
    for path in paths:
        f=pd.read_parquet(path,columns=['date','instrument','total_mv','turnover'])
        i=cal.get_indexer(pd.to_datetime(f.date).dt.normalize()); k=columns.get_indexer(f.instrument)
        ok=(i>=0)&(k>=0)&f.total_mv.gt(0).to_numpy()&f.turnover.notna().to_numpy()
        daily_cap[i[ok],k[ok]]=f.total_mv.to_numpy(np.float32)[ok]
        shared.guard()
    v[~np.isfinite(daily_cap)|(v<=0)]=np.nan
    del f
    gc.collect()
    return cal,c,v,daily_cap


def recipes(c,v):
    r=c/c.shift(1)-1
    d3=c-c.shift(3)
    vol={n:r.rolling(n,min_periods=n).std() for n in (6,20,60)}
    rank6=lambda a:a.rolling(6,min_periods=6).rank(method='average',pct=True)
    return dict(delta3close=d3,delta6close=c-c.shift(6),delay3close=c.shift(3),
         rev6raw=-(c/c.shift(6)-1),delta3rel=d3/c.shift(3),
         delta3volscaled=(d3/c.shift(3))/vol[20],tsrank6close=rank6(c),
         tsrank6delta3=rank6(d3),delay3tsrank6=rank6(c).shift(3),
         rev6delay3=-(c.shift(3)/c.shift(9)-1),delta3rank6=rank6(d3/c.shift(3)),
         delta3minusrev6=d3/c.shift(3)-(c/c.shift(6)-1),
         **{f'volume{n}':v.rolling(n,min_periods=n).mean() for n in (1,3,6,20,60)},
         **{f'returnvol{n}':a for n,a in vol.items()})


def build(c,v,positions):
    atoms={k:np.full((len(positions),c.shape[1]),np.nan,np.float32) for k in SIGNALS+GROUPS}
    check=[]
    for start in range(0,c.shape[1],160):
        end=min(start+160,c.shape[1])
        cc=pd.DataFrame(c[:,start:end],dtype=float)
        vv=pd.DataFrame(v[:,start:end],dtype=float)
        values=recipes(cc,vv)
        for k,a in values.items():
            atoms[k][:,start:end]=a.iloc[positions].to_numpy(np.float32)
        if start==0:
            # Recompute daily recipes on a real prefix, not sliced signal dates.
            cut=int(positions[len(positions)//2])
            prefix=recipes(cc.iloc[:cut+1],vv.iloc[:cut+1])
            for k in atoms:
                aa=values[k].iloc[:cut+1].to_numpy()
                bb=prefix[k].to_numpy()
                assert np.array_equal(np.isfinite(aa),np.isfinite(bb)),k
                assert np.allclose(aa,bb,rtol=0,atol=0,equal_nan=True),k
                check.append(dict(atom=k,cutoff_position=cut,max_abs_difference=0.))
        del cc,vv,values
        gc.collect()
        shared.guard()
    shared.write('daily_recipe_prefix_check.json',check)
    return atoms


def expression(spec,atoms):
    a=atoms[spec['signal']]
    if spec['mode']=='plain':
        result=shared.rank(a)
    else:
        result=shared.prior.prior.old.group_transform(a,atoms[spec['group']],spec['buckets'],spec['mode'])
    return (spec['sign']*result).astype(np.float32)


class SelectionEvaluator:
    """Cache fixed label ranks; selection needs only the top decile ledger."""
    def __init__(self,y,cap):
        self.y,self.cap=y,cap
        self.valid=np.isfinite(y)&np.isfinite(cap)
        self.yrank=shared.rank(np.where(self.valid,y,np.nan))
        self.crank=shared.rank(np.where(self.valid,cap,np.nan))

    def evaluate(self,signal):
        ok=self.valid&np.isfinite(signal)
        coverage=ok.sum(1)/np.maximum(self.valid.sum(1),1)
        if np.any(coverage<.95):
            raise ValueError('Coverage below 95%')
        sr=shared.rank(np.where(ok,signal,np.nan))
        yr=self.yrank if np.array_equal(ok,self.valid) else shared.rank(np.where(ok,self.y,np.nan))
        cr=self.crank if np.array_equal(ok,self.valid) else shared.rank(np.where(ok,self.cap,np.nan))
        rho=shared.rowcorr(sr,yr)
        if not np.isfinite(rho).all():
            raise ValueError('Constant cross section')
        m=shared.stats(rho)
        returns=[]; turns=[]; previous=None
        for i in range(len(signal)):
            ids=np.flatnonzero(ok[i])
            ordered=ids[np.argsort(signal[i,ids],kind='stable')]
            held=ordered[np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)==10]
            members=set(held.tolist())
            if previous is not None:
                turns.append(1-len(previous&members)/len(members))
            previous=members
            returns.append(float(self.y[i,held].mean()-self.y[i,ids].mean()))
        turn=float(np.mean(turns)); gross=float(np.mean(returns)*25.2)
        m.update(gross_excess=gross,turnover=turn,net_excess=gross-turn*.006*25.2,
                 corr_size=float(np.mean(shared.rowcorr(sr,cr))),min_coverage=float(coverage.min()))
        return m


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen_candidates.json').exists():
        raise RuntimeError('No retuning after final evaluation')
    threading.Thread(target=shared.watchdog,daemon=True).start()
    shared.validate_alignment_config(shared.alignment_config_snapshot())
    with threadpool_limits(limits=1):
        _,y,cap,dates,axes=shared.prior.load('target')
        del _
        _,fy,fc,fd,fa=shared.prior.load('formal')
        del _
        gc.collect()
        exits=pd.DatetimeIndex(axes['exits'])
        early=(dates<shared.FINAL_START)&(exits<shared.FINAL_START)
        dev=early&(dates>=shared.DEVELOP_START)
        final=dates>=shared.FINAL_START
        specs=[dict(signal=a,mode='plain',sign=sign) for a in SIGNALS for sign in (1,-1)]
        specs += [dict(signal=a,group=b,buckets=n,mode=mode,sign=sign)
                  for a in SIGNALS for b in GROUPS for n in (3,5)
                  for mode in ('rank','z') for sign in (1,-1)]
        shared.write('protocol.json',dict(signals=SIGNALS,groups=GROUPS,candidates=len(specs),
             candidates_predeclared=specs,selection_dates=dates[early].astype(str).tolist(),
             development_dates=dates[dev].astype(str).tolist(),
             final_dates=dates[final].astype(str).tolist(),final_used_for_selection=False,
             final_is_previously_exposed_history=True,formal_dates='saved 120-date platform template',
             target_dates='inferred from opponent first/last/count',platform_cost=0,
             target_match_semantics='RankIC population IR proxy; public ic_mean provenance unavailable',
             missing_opponent_evidence='private formula, signals, per-period scores, single-seat C; October qfq unavailable'))
        shared.log(f'predeclared {len(specs)} literal interpretations; loading causal prices')
        cal,c,v,daily_cap=load_prices(fa['symbols'])
        # Separately evaluate public dates interpreted as completed label dates.
        # These diagnostics never choose a formula or alter the formal grid.
        schedule_hypotheses={shift:cal[cal.get_indexer(dates)+shift] for shift in (-10,-11)}
        union=pd.DatetimeIndex(sorted(set(dates)|set(fd)|set(schedule_hypotheses[-10])|set(schedule_hypotheses[-11])))
        atoms=build(c,v,cal.get_indexer(union))
        eligible=np.isfinite(daily_cap[cal.get_indexer(union)])
        for a in atoms.values():
            a[~eligible]=np.nan
        np.savez_compressed(OUT/'literal_atoms.npz',**atoms)
        shared.write('literal_axes.json',dict(dates=union.astype(str).tolist(),symbols=fa['symbols'],
             schedule_sensitivity_offsets=[-10,-11],eligibility='positive daily_basic.total_mv and nonmissing turnover before cross-sectional transformations'))
        del v
        gc.collect()
        ti=union.get_indexer(dates); fi=union.get_indexer(fd)
        # Physically restrict every search input to the purged early block.
        small={k:a[ti[early]] for k,a in atoms.items()}
        ey,ec,ed=y[early],cap[early],dates[early]
        development=ed>=shared.DEVELOP_START
        ev=SelectionEvaluator(ey,ec)
        dev_ev=SelectionEvaluator(ey[development],ec[development])
        trials=[]
        for j,spec in enumerate(specs):
            s=expression(spec,small)
            try:
                m=ev.evaluate(s)
                dm=dev_ev.evaluate(s[development])
                if j==0:
                    check,_,_=shared.metrics(s,ey,ec,ed)
                    for field in ('rank_ic','rank_ir','win_rate','net_excess','turnover','corr_size'):
                        assert np.isclose(m[field],check[field],rtol=1e-9,atol=1e-12),field
                    shared.write('selection_evaluator_check.json',dict(passed=True,comparison='full detailed evaluator',fields=list(m)))
                loss=.5*shared.objective(m)+shared.objective(dm)
                trials.append(dict(spec=spec,selection_loss=loss,early=m,development=dm))
            except ValueError as e:
                trials.append(dict(spec=spec,selection_loss=1e9,error=str(e)))
            if (j+1)%50==0:
                shared.write('search_internal.json',trials)
                best=min(trials,key=lambda a:a['selection_loss'])
                shared.log(f'literal {j+1}/{len(specs)} best={best["spec"]}')
            shared.guard()
        shared.write('search_internal.json',trials)
        # Keep one of each mechanism, chosen without consulting final labels.
        families={'raw_difference':SIGNALS[:6],'temporal_rank':SIGNALS[6:9],
                  'delayed_or_residual':SIGNALS[9:]}
        frozen=[]
        for family,names in families.items():
            best=min((a for a in trials if a['spec']['signal'] in names),key=lambda a:a['selection_loss'])
            frozen.append(dict(name='FM_LITERAL_'+family.upper(),family=family,**best))
        shared.write('frozen_candidates.json',dict(frozen_before_final_evaluation=True,candidates=frozen))
        shared.write('freeze_hashes.json',dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             frozen=hashlib.sha256((OUT/'frozen_candidates.json').read_bytes()).hexdigest()))
        del small,trials
        gc.collect()
        rows=[]; monthly_rows=[]; date_diagnostics=[]
        for m in frozen:
            all_s=expression(m['spec'],atoms)
            for shift,alternative_dates in schedule_hypotheses.items():
                ii=union.get_indexer(alternative_dates); pos=cal.get_indexer(alternative_dates)
                cp=daily_cap[pos]; yy=c[pos+11].astype(float)/c[pos+1].astype(float)-1
                s=all_s[ii].copy(); s[~np.isfinite(cp)]=np.nan
                stats,periods,_=shared.metrics(s,yy,cp,alternative_dates)
                date_diagnostics.append(dict(candidate=m['name'],signal_offset=shift,
                    interpretation='public date interpreted as label end' if shift==-11 else 'public date interpreted as cycle end',
                    start=str(alternative_dates.min().date()),end=str(alternative_dates.max().date()),**stats))
                periods.to_csv(OUT/f'{m["name"]}_schedule_offset{shift}_diagnostic.csv',index=False)
            for scope,ii,yy,cp,dt,windows in [
                ('target',ti,y,cap,dates,[('purged_early',early),('historical_final24',final),('target119',np.ones(len(dates),bool))]),
                ('formal',fi,fy,fc,fd,[('formal_5y',np.ones(len(fd),bool)),('recent_2026',fd>='2026-01-01'),('formal_final',fd>=shared.FINAL_START)])]:
                s=all_s[ii].copy(); s[~np.isfinite(cp)]=np.nan
                np.save(OUT/(m['name']+'_'+scope+'_signals.npy'),s)
                for window,mask in windows:
                    stats,periods,groups=shared.metrics(s[mask],yy[mask],cp[mask],dt[mask])
                    rows.append(dict(candidate=m['name'],window=window,**stats))
                    periods.to_csv(OUT/f'{m["name"]}_{window}_periods.csv',index=False)
                    groups.to_csv(OUT/f'{m["name"]}_{window}_groups.csv',index=False)
                    shared.log(f'{m["name"]} {window}: IC={stats["rank_ic"]:.6f}, IR={stats["rank_ir"]:.3f}, wins={stats["wins"]}/{stats["periods"]}')
                if scope=='formal':
                    daily,monthly,turns=shared.daily_monthly_c(s,yy,cp,dt,cal,c)
                    daily.to_csv(OUT/(m['name']+'_daily_proxy.csv'),index=False)
                    monthly.to_csv(OUT/(m['name']+'_monthly_c_proxy.csv'),index=False)
                    turns.to_csv(OUT/(m['name']+'_weight_turnover.csv'),index=False)
                    full=monthly[~monthly.partial_month]; last=full[full.month>='2025-09']
                    monthly_rows.append(dict(candidate=m['name'],full_months=len(full),nc_mean=float(full.nc.mean()),
                       nc_full_months=int((full.nc==1).sum()),nc_zero_months=int((full.nc==0).sum()),
                       final_nc_mean=float(last.nc.mean()),final_months=len(last)))
            del s,all_s
        pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)
        pd.DataFrame(date_diagnostics).to_csv(OUT/'schedule_sensitivity_diagnostic.csv',index=False)
        pd.DataFrame(monthly_rows).to_csv(OUT/'monthly_c_summary.csv',index=False)
    shared.STOP.set()
    shared.write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,
        memory_sampled=shared.PEAK,seconds=time.monotonic()-shared.START,
        rule=shared.ALIGNMENT_RULE_VERSION,c_fidelity='local single-seat monthly factor_valid proxy; not opponent six-seat October C'))
    shared.log('literal reconstruction complete; no exact recovery claim')


if __name__=='__main__':
    main()
