from __future__ import annotations
import hashlib, json, threading
import numpy as np, pandas as pd
import fengmao_information_models_20261011 as task
from verify_fengmao_paper_hypotheses_20261011 import independent_periods


def main():
    out=task.OUT; task.shared.OUT=out
    threading.Thread(target=task.shared.watchdog,daemon=True).start()
    protocol=json.loads((out/'protocol.json').read_text(encoding='utf8'))
    frozen=json.loads((out/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
    results=pd.read_csv(out/'results.csv')
    assert not protocol['final_used_for_selection']
    hashes=json.loads((out/'freeze_hashes.json').read_text(encoding='utf8'))
    assert hashes['script']==hashlib.sha256((task.ROOT/'scripts/fengmao_information_models_20261011.py').read_bytes()).hexdigest()
    assert hashes['frozen']==hashlib.sha256((out/'frozen_candidates.json').read_bytes()).hexdigest()
    assert hashes['tree']==hashlib.sha256((out/'FM_INFO_TREE.txt').read_bytes()).hexdigest()
    exits=pd.DatetimeIndex(protocol['refit_exit_dates'])
    assert (exits<task.shared.FINAL_START).all()
    assert (pd.DatetimeIndex(protocol['refit_dates'])<task.shared.FINAL_START).all()
    checks=[dict(check='freeze_hashes_and_holdout_protocol',passed=True),
            dict(check='purged_refit_label_exits',passed=True,count=len(exits),latest_exit=str(exits.max()))]
    errors=[]
    for scope in ('target','formal'):
        x,names,y,cap,dates,axes=task.matrix(scope)
        for model in frozen:
            saved=np.load(out/f'{model["name"]}_{scope}_signals.npy',mmap_mode='r')
            rebuilt=task.predict(model,x,cap)
            assert np.array_equal(rebuilt,saved,equal_nan=True)
            for cutoff in ('2024-06-28','2025-06-30'):
                prefix=dates<=cutoff
                assert np.array_equal(task.predict(model,x[prefix],cap[prefix]),saved[prefix],equal_nan=True)
                checks.append(dict(check='frozen_inference_prefix',candidate=model['name'],scope=scope,cutoff=cutoff,passed=True))
            for _,row in results[results.candidate.eq(model['name'])].iterrows():
                if scope=='target' and row.window not in ('target119','historical_final24'): continue
                if scope=='formal' and row.window not in ('formal_5y','formal_final','recent_2026'): continue
                pth=out/f'{model["name"]}_{row.window}_periods.csv'; savedp=pd.read_csv(pth)
                mask=dates.isin(pd.DatetimeIndex(savedp.date))
                p=independent_periods(saved[mask],y[mask],cap[mask],dates[mask])
                diff={k:float(np.nanmax(np.abs(p[k]-savedp[k]))) for k in ('rank_ic','ic','gross_excess','turnover')}
                assert max(diff.values())<1e-7,(model['name'],row.window,diff)
                mean=float(p.rank_ic.mean()); ir=mean/float(p.rank_ic.std(ddof=0)); wins=int((p.rank_ic>.02).sum())
                net=float(p.gross_excess.mean()*25.2-p.turnover.mean()*.006*25.2)
                assert abs(mean-row.rank_ic)<1e-8 and abs(ir-row.rank_ir)<1e-8 and wins==row.wins and abs(net-row.net_excess)<1e-7
                errors.append(dict(candidate=model['name'],window=row.window,**diff))
            task.shared.guard()
    pd.DataFrame(errors).to_csv(out/'independent_metrics.csv',index=False)
    task.shared.write('verification.json',dict(status='passed',checks=checks,metric_windows=len(errors),
        final_used_for_selection=False,opponent_exact_recovery_verified=False,pristine_out_of_sample=False,memory=task.shared.PEAK))
    task.shared.STOP.set()
    print(f'{len(errors)} windows independently verified')


if __name__=='__main__': main()
