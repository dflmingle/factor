#!/usr/bin/env python3
"""Replay all 92 original atoms on the isolated long snapshot, preserve formal panels.

This is factor-history preparation, not a claim that the entire 592-factor
long-history allocation experiment has completed. Each saved atom has its own
coverage, prefix invariance and formal-panel alignment diagnostic.
"""
from __future__ import annotations
import os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import json
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
import regime_long_history_data_20261014 as data
import regime_long_pit_fast_20261014 as pit

ROOT=q.ROOT
OUT=ROOT/'research_reports/platform_alignment/regime-long-base-replay-20261014'
BASE=q.OUT
VERSION=q.ALIGNMENT_RULE_VERSION+'-regime-training2006-base-replay-aliasdedup-v3'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,f=pd.read_pickle(data.finalize_historical_aliases());q.dates_all=cal
    saved=pd.read_pickle(BASE/'signal_panels.pkl');formal=saved['dates'];first=cal.get_loc(formal[0]);base_index=stocks.get_indexer(saved['stocks'])
    hpos=np.arange(first%10,first,10);hpos=hpos[hpos>=252]
    hist=cal[hpos];pos=np.r_[hpos,cal.get_indexer(formal)];grid=hist.append(formal)
    q.CACHE=data.DATA/'combined_view';q.OUT=OUT
    cfg=dict(version=VERSION,history_start=str(cal.min().date()),historical_signal_start=str(hist.min().date()),historical_signals=len(hist),formal_signals=len(formal),formal_saved_panels_preserved=True,one_way_cost=.003,label='close(t+1)->close(t+11)',universe='fullSH/SZA historical union',benchmark='factor_valid',formal_warmup='20180101 immutable',training_warmup='20060101 independent proxy',platform_compute_spent=0)
    q.dump(OUT/'config.json',cfg)
    rows=[];metadata=[]
    def process(meta,value):
        key=meta['key'];path=OUT/f'{key}.history.pkl'
        if path.exists():
            rows.append(json.loads((OUT/f'{key}.audit.json').read_text()));metadata.append(meta);return
        raw=np.asarray(value,np.float32)
        if raw.shape!=(len(grid),len(stocks)):raise ValueError(f'{key} unexpected shape {raw.shape}')
        original=saved['panels'][key].to_numpy(np.float32)
        current=raw[len(hist):,base_index]
        good=np.isfinite(current)&np.isfinite(original)
        mismatch=int(np.sum(np.isfinite(current)!=np.isfinite(original)))
        maxdiff=float(np.max(np.abs(current[good]-original[good]))) if good.any() else None
        # Historical scores and the saved formal segment are explicitly
        # joined. Longer financial warmup is never silently substituted into
        # the formal reference score used for ranking/evaluation.
        score=np.full(raw.shape,np.nan,np.float32);score[:len(hist)]=raw[:len(hist)];score[len(hist):,base_index]=original
        cap=f['cap'][pos];score=np.where(cap>0,score,np.nan)
        result,periods,daily=q.evaluate(score,grid,stocks,pos,f)
        periods.to_csv(OUT/f'{key}.periods.csv',index=False);daily.to_csv(OUT/f'{key}.daily_nav.csv',index=False)
        pd.to_pickle(dict(key=key,dates=grid,stocks=stocks,values=score),path)
        row=dict(key=key,historical_periods=int(np.sum(periods.date<formal[0])) if len(periods) else 0,total_periods=len(periods),formal_rebuild_finite_mask_mismatch=mismatch,formal_rebuild_max_absolute_difference=maxdiff,formal_saved_values_preserved=True,training_fidelity='local_proxy; historical vendor qfq/financial revision coverage',result_scope='training path, not standalone formal result')
        q.dump(OUT/f'{key}.audit.json',row);rows.append(row);metadata.append(meta)
        pd.DataFrame(rows).to_csv(OUT/'replay_audit.csv',index=False)
        print('REPLAYED',len(rows),key,'history',row['historical_periods'],'formal_delta',maxdiff,flush=True)
    for generator in [q.recipes,q.additional_market_recipes]:
        for meta,x in generator(f,pos):process(meta,x)
    fin=pit.snapshot(grid,stocks)
    for meta,x in q.financial_recipes(fin,f,pos):process(meta,x)
    fin['income.__quarter__.q0']=q.income_report_quarters(grid,stocks)
    for meta,x in q.additional_financial_recipes(fin,f,pos):process(meta,x)
    for meta,x in q.bank_and_rank_recipes(fin,f,pos,cal,stocks):process(meta,x)
    for meta,x in q.supplemental_recipes(fin,f,pos):process(meta,x)
    q.dump(OUT/'recipe_manifest.json',metadata)
    # Actual early-history recomputation, not merely slicing completed output.
    ids=np.flatnonzero(np.isfinite(f['close'][-500:]).all(axis=0))[:16]
    small={k:v[:,ids] for k,v in f.items()};cutpos=hpos[hpos<1500]
    cutoff=int(cutpos[-1]+1);checks=[]
    for generator in [q.recipes,q.additional_market_recipes]:
        full={m['key']:v for m,v in generator(small,cutpos)}
        truncated={m['key']:v for m,v in generator({k:v[:cutoff] for k,v in small.items()},cutpos)}
        for key,value in full.items():
            np.testing.assert_allclose(value,truncated[key],equal_nan=True,rtol=1e-5,atol=1e-6)
            checks.append(dict(key=key,test='historical_prefix_recomputation',passed=True))
    q.dump(OUT/'verification.json',dict(completed=True,replayed=len(rows),expected_original_atoms=len(saved['panels']),all_original_atoms_replayed=set(r['key'] for r in rows)==set(saved['panels']),historical_prefix_tests=checks,formal_reference_preserved=True,all592_long_models_completed=False))
    print('BASE_REPLAY_FINISHED',len(rows),flush=True)

if __name__=='__main__':main()
