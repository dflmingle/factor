"""Cost, redundancy, size falsification and monthly ledger for frozen sideproducts."""
from __future__ import annotations
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import argparse, gc, hashlib, json, threading, time
from pathlib import Path
import numpy as np, pandas as pd
import fengmao_grammar_mcts_20261011 as mcts
from verify_fengmao_paper_hypotheses_20261011 import independent_periods
from threadpoolctl import threadpool_limits

shared=mcts.shared
ROOT=mcts.ROOT


def audit(out):
    shared.OUT=out
    threading.Thread(target=shared.watchdog,daemon=True).start()
    start=time.monotonic()
    frozen=json.loads((out/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
    results=pd.read_csv(out/'results.csv')
    checks=[]; errors=[]; corr=[]; sensitivity=[]; tops=[]
    hashes=json.loads((out/'freeze_hashes.json').read_text(encoding='utf8'))
    assert hashes['frozen']==hashlib.sha256((out/'frozen_candidates.json').read_bytes()).hexdigest()
    assert hashes['script']==hashlib.sha256((ROOT/'scripts/fengmao_grammar_mcts_20261011.py').read_bytes()).hexdigest()
    checks.append(dict(check='frozen_script_and_config_hashes',passed=True))
    rawaxes=json.loads((mcts.shock.OUT/'axes.json').read_text(encoding='utf8'))
    union=pd.DatetimeIndex(rawaxes['dates'])
    with np.load(mcts.shock.OUT/'atoms_raw.npz') as z:
        atoms={'raw_'+k:shared.rank(z[k]) for k in z.files}
    contexts={}
    for scope in ('target','formal'):
        context,y,cap,dates,axes=shared.prior.load(scope)
        contexts[scope]=(context,dates)
        for model in frozen:
            saved_sig=np.load(out/f'{model["name"]}_{scope}_signals.npy',mmap_mode='r')
            op,x,ctx,by=model['spec']
            local={k:a[union.get_indexer(dates)] for k,a in atoms.items()}
            local['ctx_'+ctx]=context[ctx]
            rebuilt=mcts.expression(model['spec'],local); rebuilt[~np.isfinite(cap)]=np.nan
            assert np.array_equal(rebuilt,saved_sig,equal_nan=True)
            for cutoff in ('2024-06-28','2025-06-30'):
                prefix=dates<=cutoff
                r=mcts.expression(model['spec'],{k:a[prefix] for k,a in local.items()})
                r[~np.isfinite(cap[prefix])]=np.nan
                assert np.array_equal(r,saved_sig[prefix],equal_nan=True)
                checks.append(dict(check='time_prefix_reconstruction',candidate=model['name'],scope=scope,
                                   cutoff=cutoff,max_difference=0.,passed=True))
            for _,row in results[results.candidate.eq(model['name'])].iterrows():
                if scope=='target' and row.window not in ('target119','historical_final24'): continue
                if scope=='formal' and row.window not in ('formal_5y','formal_final','recent_2026'): continue
                saved=pd.read_csv(out/f'{model["name"]}_{row.window}_periods.csv')
                mask=dates.isin(pd.DatetimeIndex(saved.date))
                p=independent_periods(saved_sig[mask],y[mask],cap[mask],dates[mask])
                diff={k:float(np.nanmax(np.abs(p[k]-saved[k]))) for k in ('rank_ic','ic','gross_excess','turnover')}
                assert max(diff.values())<1e-7,(model['name'],row.window,diff)
                mean=float(p.rank_ic.mean()); ir=mean/float(p.rank_ic.std(ddof=0)); wins=int((p.rank_ic>.02).sum())
                net=float(p.gross_excess.mean()*25.2-p.turnover.mean()*.006*25.2)
                assert abs(mean-row.rank_ic)<1e-8 and abs(ir-row.rank_ir)<1e-8 and wins==row.wins
                assert abs(net-row.net_excess)<1e-7
                errors.append(dict(candidate=model['name'],window=row.window,**diff))
            if scope=='formal':
                for ref in ('rev3','rev20','lowturn','vol20','vstab20','size'):
                    a=context[ref]; ok=np.isfinite(saved_sig)&np.isfinite(a)&np.isfinite(cap)
                    rho=shared.rowcorr(shared.rank(np.where(ok,saved_sig,np.nan)),shared.rank(np.where(ok,a,np.nan)))
                    corr.append(dict(candidate=model['name'],reference=ref,mean_signal_date_spearman=float(np.mean(rho)),
                                     fidelity='signal-date diagnostic, not full-daily correlation'))
                mask=np.isfinite(cap)&((shared.rank(cap)+.5)>.20)
                # Explicitly shrink cap eligibility only in this separately
                # labelled falsification; formal results above remain intact.
                m,_,_=shared.metrics(np.where(mask,saved_sig,np.nan),y,np.where(mask,cap,np.nan),dates)
                sensitivity.append(dict(candidate=model['name'],test='exclude_smallest20_sensitivity_only',**m))
                i=len(dates)-1
                ids=np.flatnonzero(np.isfinite(saved_sig[i]))
                chosen=ids[np.argsort(-saved_sig[i,ids],kind='stable')][:20]
                for j,k in enumerate(chosen):
                    tops.append(dict(candidate=model['name'],date=str(dates[i].date()),rank=j+1,
                                     symbol=axes['symbols'][k],value=float(saved_sig[i,k])))
            shared.guard()
        del local,rebuilt
        gc.collect()
    pd.DataFrame(errors).to_csv(out/'independent_metrics.csv',index=False)
    pd.DataFrame(corr).to_csv(out/'reference_correlations.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(out/'size_sensitivity.csv',index=False)
    pd.DataFrame(tops).to_csv(out/'top20_raw.csv',index=False)
    shared.write('verification.json',dict(status='passed',checks=checks,metric_windows=len(errors),
                                        opponent_exact_recovery_verified=False,pristine_out_of_sample=False))
    del atoms,context,contexts,y,cap
    gc.collect()
    _,fy,fc,fd,fa=shared.prior.load('formal'); del _
    cal,close=shared.load_close(fa['symbols'])
    ledgerrows=[]
    for model in frozen:
        s=np.load(out/f'{model["name"]}_formal_signals.npy',mmap_mode='r')
        daily,monthly,turns=shared.daily_monthly_c(s,fy,fc,fd,cal,close)
        daily.to_csv(out/f'{model["name"]}_daily_proxy.csv',index=False)
        monthly.to_csv(out/f'{model["name"]}_monthly_c_proxy.csv',index=False)
        turns.to_csv(out/f'{model["name"]}_weight_turnover.csv',index=False)
        full=monthly[~monthly.partial_month]; last=full[full.month>='2025-09']
        ledgerrows.append(dict(candidate=model['name'],full_months=len(full),nc_mean=float(full.nc.mean()),
                              full_score_months=int((full.nc==1).sum()),zero_months=int((full.nc==0).sum()),
                              final_months=len(last),final_nc_mean=float(last.nc.mean())))
        # Independent monthly recomposition, never compare this single-factor
        # proxy to the opponent's October six-seat pool score.
        for _,r in monthly.iterrows():
            d=daily[pd.to_datetime(daily.date).dt.strftime('%Y-%m').eq(r.month)]
            pr=d.portfolio.to_numpy(); br=d.benchmark.to_numpy(); n=len(d)
            rex=np.prod(1+pr)**(252/n)-np.prod(1+br)**(252/n)
            sr=pr.mean()/pr.std(ddof=1)*np.sqrt(252) if n>1 and pr.std(ddof=1)>0 else 0.
            nav=np.r_[1.,np.cumprod(1+pr)]; dd=-(nav/np.maximum.accumulate(nav)-1).min()
            raw=max(rex,0)/max(d.turnover.sum(),.3)*sr*(1-1.2*dd) if n>=2 else 0.
            assert np.isclose(raw,r.raw_c,rtol=1e-8,atol=1e-9)
        checks.append(dict(check='monthly_daily_cost_ledger_algebra',candidate=model['name'],passed=True,months=len(monthly)))
        shared.guard()
    pd.DataFrame(ledgerrows).to_csv(out/'monthly_c_summary.csv',index=False)
    shared.write('verification.json',dict(status='passed',checks=checks,metric_windows=len(errors),
                                        monthly_ledgers=len(frozen),opponent_exact_recovery_verified=False,
                                        pristine_out_of_sample=False))
    shared.write('sideproduct_audit_metadata.json',dict(status='complete',memory=shared.PEAK,seconds=time.monotonic()-start,
                 platform_cost=0,c_fidelity='single-factor monthly daily path proxy; opponent October signals/data unavailable'))
    shared.STOP.set()
    print(f'{len(errors)} metric windows and {len(frozen)} daily/monthly ledgers passed')


if __name__=='__main__':
    audit(mcts.OUT)
