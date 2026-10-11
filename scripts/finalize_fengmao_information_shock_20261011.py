from __future__ import annotations
import gc, json, time, threading
from pathlib import Path
import numpy as np, pandas as pd
import fengmao_information_shock_20261011 as task


def main():
    out=task.OUT; task.shared.OUT=out
    start=time.monotonic()
    threading.Thread(target=task.shared.watchdog,daemon=True).start()
    frozen=json.loads((out/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
    _,y,cap,dates,axes=task.shared.prior.load('target'); del _
    _,fy,fc,fd,fa=task.shared.prior.load('formal'); del _
    union=pd.DatetimeIndex(json.loads((out/'axes.json').read_text(encoding='utf8'))['dates'])
    with np.load(out/'atoms_raw.npz') as z: atoms={k:z[k] for k in z.files}
    ix=union.get_indexer(dates); fi=union.get_indexer(fd)
    final=dates>=task.shared.FINAL_START
    rows=[]; years=[]; correlations=[]; sensitivities=[]
    for item in frozen:
        sigall=task.expression(item['spec'],atoms)
        for scope,sig,yy,cc,dd in [('target',sigall[ix],y,cap,dates),('formal',sigall[fi],fy,fc,fd)]:
            sig[~np.isfinite(cc)]=np.nan
            np.save(out/f'{item["name"]}_{scope}_signals.npy',sig)
            windows=[('target119',np.ones(len(dd),bool)),('historical_final24',final)] if scope=='target' else [
                ('formal_5y',np.ones(len(dd),bool)),('recent_2026',dd>=pd.Timestamp('2026-01-01')),('formal_final',dd>=task.shared.FINAL_START)]
            for window,mask in windows:
                m,p,g=task.shared.metrics(sig[mask],yy[mask],cc[mask],dd[mask])
                p.to_csv(out/f'{item["name"]}_{window}_periods.csv',index=False); g.to_csv(out/f'{item["name"]}_{window}_groups.csv',index=False)
                rows.append(dict(candidate=item['name'],window=window,**m))
            if scope=='formal':
                for year in sorted(set(dd.year)):
                    ym=dd.year==year
                    if ym.sum()>=2:
                        mm,_,_=task.shared.metrics(sig[ym],yy[ym],cc[ym],dd[ym]); years.append(dict(candidate=item['name'],year=int(year),**mm))
                with np.load(task.shared.prior.SOURCE/'atoms_formal.npz') as z:
                    for ref in ('rev3','rev20','lowturn','vol20','size'):
                        reference=z[ref]
                        ok=np.isfinite(sig)&np.isfinite(reference)&np.isfinite(cc)
                        rho=task.shared.rowcorr(task.shared.rank(np.where(ok,sig,np.nan)),task.shared.rank(np.where(ok,reference,np.nan)))
                        correlations.append(dict(candidate=item['name'],reference=ref,
                            mean_signal_date_spearman=float(np.nanmean(rho)),fidelity='signal-date diagnostic; not all-daily correlation'))
                mask=np.isfinite(cc)&((task.shared.rank(cc)+.5)>.20)
                # Deliberate universe change in a separately named diagnostic.
                m,_,_=task.shared.metrics(np.where(mask,sig,np.nan),yy,np.where(mask,cc,np.nan),dd)
                sensitivities.append(dict(candidate=item['name'],test='exclude_smallest20_sensitivity_only',**m))
            task.shared.guard()
    pd.DataFrame(rows).to_csv(out/'results.csv',index=False); pd.DataFrame(years).to_csv(out/'years.csv',index=False)
    pd.DataFrame(correlations).to_csv(out/'reference_correlations.csv',index=False)
    pd.DataFrame(sensitivities).to_csv(out/'size_sensitivity.csv',index=False)
    search=json.loads((out/'search_results.json').read_text(encoding='utf8'))
    meta=dict(status='complete',goal_achieved=False,platform_cost=0,rule=task.shared.ALIGNMENT_RULE_VERSION,
              declared_candidates=len(search),evaluated=sum(r['status']=='evaluated' for r in search),
              excluded=sum(r['status']=='failed' for r in search),frozen_candidates=len(frozen),selection_completed_before_finalize=True,
              formal_config=task.alignment_config_snapshot(),final_used_for_selection=False,
              final_is_previously_exposed_history=True,finalize_memory=task.shared.PEAK,
              finalize_seconds=time.monotonic()-start,search_runtime_not_recovered=True)
    task.shared.write('metadata.json',meta)
    task.shared.STOP.set()
    print('finalized',len(rows),'window rows')


if __name__=='__main__': main()
