"""Independent pandas rank and portfolio-membership audit of frozen raw recipes."""
from __future__ import annotations
import argparse
import hashlib
import json
import threading
import numpy as np
import pandas as pd
import fengmao_information_shock_20261011 as task
from verify_fengmao_paper_hypotheses_20261011 import independent_periods


def main(out=None):
    out=out or task.OUT
    task.shared.OUT=out
    threading.Thread(target=task.shared.watchdog,daemon=True).start()
    protocol=json.loads((out/'protocol.json').read_text(encoding='utf8'))
    frozen=json.loads((out/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
    union=pd.DatetimeIndex(json.loads((out/'axes.json').read_text(encoding='utf8'))['dates'])
    results=pd.read_csv(out/'results.csv')
    exits=pd.DatetimeIndex(protocol['selection_exit_dates'])
    assert (exits<task.shared.FINAL_START).all()
    assert not protocol['final_used_for_selection']
    hashes=json.loads((out/'freeze_hashes.json').read_text(encoding='utf8'))
    script='fengmao_daily_rankcorr_20261011.py' if out.name=='fengmao-daily-rankcorr-20261011' else 'fengmao_information_shock_20261011.py'
    assert hashes['script']==hashlib.sha256((task.ROOT/'scripts'/script).read_bytes()).hexdigest()
    assert hashes['frozen']==hashlib.sha256((out/'frozen_candidates.json').read_bytes()).hexdigest()
    checks=[dict(check='purged_selection_label_exit',passed=True,count=len(exits),latest_exit=str(exits.max())),
            dict(check='frozen_hashes',passed=True)]
    with np.load(out/'atoms_raw.npz') as z: atoms={k:z[k] for k in z.files}
    errors=[]
    for scope in ('target','formal'):
        _,y,cap,dates,axes=task.shared.prior.load(scope); del _
        for model in frozen:
            saved_signal=np.load(out/f'{model["name"]}_{scope}_signals.npy',mmap_mode='r')
            signal=task.expression(model['spec'],atoms)[union.get_indexer(dates)]
            signal[~np.isfinite(cap)]=np.nan
            assert np.array_equal(np.isfinite(signal),np.isfinite(saved_signal))
            assert np.allclose(signal,saved_signal,rtol=0,atol=0,equal_nan=True)
            for cutoff in ('2024-06-28','2025-06-30'):
                m=union<=cutoff
                prefix=task.expression(model['spec'],{k:v[m] for k,v in atoms.items()})
                full=task.expression(model['spec'],atoms)[m]
                assert np.array_equal(prefix,full,equal_nan=True)
                checks.append(dict(check='formula_time_prefix',candidate=model['name'],scope=scope,
                                   cutoff=cutoff,passed=True,max_difference=0.))
            for _,row in results[results.candidate.eq(model['name'])].iterrows():
                if scope=='target' and row.window not in ('target119','historical_final24'): continue
                if scope=='formal' and row.window not in ('formal_5y','formal_final','recent_2026'): continue
                saved=pd.read_csv(out/f'{model["name"]}_{row.window}_periods.csv')
                mask=dates.isin(pd.DatetimeIndex(saved.date))
                p=independent_periods(saved_signal[mask],y[mask],cap[mask],dates[mask])
                assert p.date.tolist()==saved.date.tolist()
                differences={k:float(np.nanmax(np.abs(p[k]-saved[k]))) for k in ('rank_ic','ic','gross_excess','turnover')}
                assert max(differences.values())<1e-7,(model['name'],row.window,differences)
                mean=float(p.rank_ic.mean()); ir=mean/float(p.rank_ic.std(ddof=0)); wins=int((p.rank_ic>.02).sum())
                net=float(p.gross_excess.mean()*25.2-p.turnover.mean()*.006*25.2)
                assert abs(mean-row.rank_ic)<1e-8 and abs(ir-row.rank_ir)<1e-8
                assert wins==row.wins and abs(net-row.net_excess)<1e-7
                errors.append(dict(candidate=model['name'],window=row.window,**differences))
            task.shared.guard()
    pd.DataFrame(errors).to_csv(out/'independent_metrics.csv',index=False)
    task.shared.write('verification.json',dict(status='passed',checks=checks,metric_windows=len(errors),
        actual_daily_atom_prefix_checks=len(json.loads((out/'daily_recipe_prefix_check.json').read_text())),
        opponent_exact_recovery_verified=False,pristine_out_of_sample=False,memory=task.shared.PEAK))
    task.shared.STOP.set()
    print(f'{len(errors)} windows and frozen prefix checks verified')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--directory')
    args=parser.parse_args()
    main(task.ROOT/'research_reports/platform_alignment'/args.directory if args.directory else None)
