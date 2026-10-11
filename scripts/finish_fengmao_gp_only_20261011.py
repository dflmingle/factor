"""Freeze and evaluate the six-round GP frontier without importing torch."""
from pathlib import Path
import hashlib,json,time
import numpy as np,pandas as pd
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/fengmao-multiround2-20261011'
sys.path.insert(0,str(ROOT/'scripts'))
import fengmao_multiround_20261011 as task

def main():
    started=time.perf_counter()
    a=np.load(OUT/'atoms.npz'); atoms={k:a[k] for k in a.files if k not in ['target','market_cap']}; target=a['target']; cap=a['market_cap']
    axes=json.loads((OUT/'axes.json').read_text(encoding='utf-8')); dates=pd.DatetimeIndex(axes['dates'])
    records={}
    for line in (OUT/'search_progress.jsonl').read_text(encoding='utf-8').splitlines():
        r=json.loads(line); records[r['formula']]=r
    valid=[r for r in records.values() if r.get('status')=='evaluated']
    picks,panels=task.diverse_frontier(task.Search(atoms,target if False else type('E',(),{})(),records)) if False else ([],[])
    # Rebuild the same training-only diversity frontier from stored records.
    train=dates<='2023-12-29'; names=[]; values=[]
    for row in sorted(valid,key=lambda r:r['fitness'],reverse=True):
        x=task.value(row['formula'],{k:v[train] for k,v in atoms.items()})
        rx=task.rank(x)
        if any(abs(float(np.nanmean(task.rowcorr(rx,task.rank(p)))))>.95 for p in values): continue
        names.append(row); values.append(x)
        if len(names)>=3: break
    assert len(names)==3
    models=[dict(engine='GP_six_round_best_diverse',formula=r['formula'],training=r,round_origin=r.get('origin')) for r in names]
    (OUT/'frozen_models.json').write_text(json.dumps(models,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    masks={'formal_5y':np.ones(len(dates),bool),'training':train,
           'validation_2024_2025':(dates>='2024-01-01')&(dates<='2025-12-31'),
           'recent_2026':dates>='2026-01-01'}
    results=[]; years=[]
    for i,m in enumerate(models,1):
        name=f'FM_MULTI_{i:02d}'; x=task.value(m['formula'],atoms); np.save(OUT/(name+'_signals.npy'),x)
        for window,mask in masks.items():
            p=task.FastEvaluator(target[mask],cap[mask],dates[mask]).periods(x[mask]); p['tied_fraction']=0.0
            s=task.base.summarize(p); results.append(dict(candidate=name,engine=m['engine'],formula=m['formula'],window=window,**s))
            p.to_csv(OUT/f'{name}_{window}_periods.csv',index=False)
            if window=='formal_5y':
                for year,b in p.groupby(p.date.str[:4]):
                    years.append(dict(candidate=name,year=year,**task.base.summarize(b)))
            print(name,window,'formula',m['formula'],'net',round(s['net_excess']*100,2),'turn',round(s['turnover']*100,1),'size',round(s['corr_size'],3),flush=True)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False); pd.DataFrame(years).to_csv(OUT/'years.csv',index=False)
    meta=dict(status='complete',method='fengmao-multiround-gp-only-causal-full-a-arithmetic-v2',
        alignment_reference=task.base.ALIGNMENT_RULE_VERSION,GP_rounds=6,GP_population=96,GP_generations=10,
        GP_evaluation_upper_bound=5760,unique_formulas=len(records),valid_formulas=len(valid),finalists=3,
        GFN_status='not_run: torchgfn unavailable and system torch c10.dll WinError1114; isolated CPU torch download failed due temporary disk space',
        AlphaPool_status='not_run: depends on torch',platform_cost=0,memory=task.base.PEAK,seconds=time.perf_counter()-started,
        nominal_window=['20210907','20260907'],warmup='20180101',latest='2026-09-07',last_signal=str(dates[-1].date()),
        last_realized_end='2026-08-25',fields=['qfq close','volume','turnover','total_mv'],label='close(t+1)->close(t+11)',groups=10,one_way_cost=.003,
        training='2021-2023 labels only, six rounds and diversity frozen before validation',validation='historical previously researched 2024-2025, not pristine OOS',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['private opponent formula unavailable','no official S_i','stable ties proxy','amount unavailable','GP search rewards penalize size correlation'])
    (OUT/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    print('GP-ONLY COMPLETE',len(records),'records',flush=True)

if __name__=='__main__': main()
