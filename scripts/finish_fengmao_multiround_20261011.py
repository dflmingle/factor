"""Resume only GFN/AlphaPool/evaluation after the six saved GP rounds.

Use the task-local torch runtime; do not rerun completed GP generations.
"""
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/fengmao-multiround2-20261011'
RUNTIME=OUT/'.runtime'
sys.path.insert(0,str(RUNTIME))
sys.path.insert(0,str(ROOT/'scripts'))
import fengmao_multiround_20261011 as task
import numpy as np
import pandas as pd


def main():
    if (OUT/'metadata.json').exists():
        raise RuntimeError('Already complete; refuse duplicate evaluation')
    rounds=[]
    for name,mechanism,seed in task.ROUNDS:
        rounds.append(json.loads((OUT/(name+'_result.json')).read_text(encoding='utf-8')))
    records={}
    for line in (OUT/'search_progress.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);records[row['formula']]=row
    task.base.OUT=OUT
    threading.Thread(target=task.base.watchdog,daemon=True).start()
    started=time.perf_counter()
    archive=np.load(OUT/'atoms.npz')
    atoms={k:archive[k] for k in archive.files if k not in ['target','market_cap']}
    target,cap=archive['target'],archive['market_cap']
    axes=json.loads((OUT/'axes.json').read_text(encoding='utf-8'))
    dates=pd.DatetimeIndex(axes['dates'])
    calendar,stocks,fields=task.base.load_data()
    assert stocks.tolist()==axes['symbols']
    pos=calendar.get_indexer(dates)
    training=(dates<='2023-12-29') & (calendar[pos+11]<='2023-12-29')
    search=task.Search({k:v[training] for k,v in atoms.items()},task.FastEvaluator(target[training],cap[training],dates[training]),records)
    picks,panels=task.diverse_frontier(search)
    best=picks[0]
    gpmodel=dict(engine='best_of_six_GP_rounds',formula=best['formula'],training=best)
    gfnmodel=task.train_gfn(search,picks)
    alphamodel=task.train_alphapool(search,picks,panels)
    task.finish([gpmodel,gfnmodel,alphamodel],atoms,target,cap,dates,calendar,pos,fields,started,rounds,search.records)
    import torch
    task.base.dump(OUT/'resume_runtime.json',dict(GP_rounds_reused=6,GP_rerun=False,
        torch_version=torch.__version__,torch_path=str(Path(torch.__file__).relative_to(ROOT)),
        resume_seconds=time.perf_counter()-started,
        resume_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    task.base.DONE.set()
    print('RESUMED PHASE COMPLETE',flush=True)


if __name__=='__main__':
    import warnings
    warnings.filterwarnings('ignore',category=RuntimeWarning)
    main()
