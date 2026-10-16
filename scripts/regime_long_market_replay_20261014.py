#!/usr/bin/env python3
"""Replay mapped market-only source builders, with real prefix checks."""
from __future__ import annotations
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import importlib, json, gc
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
import regime_long_history_data_20261014 as data
import regime_long_base_replay_20261014 as base

OUT=q.ROOT/'research_reports/platform_alignment/regime-long-market-replay-20261014'

def call(module,args,f,cal,pos):
    # Some displayed source kernels assume an already warmed-up grid and
    # index directly into 360/800-day windows. Keep early rows missing rather
    # than permitting Python negative indexing to read the end of history.
    minimum={'quant_corpus_ar2labelprojection_20261013':801,'quant_corpus_ar2spectrum_20261013':801,'quant_corpus_eventmath_helpers_20261013':360}.get(module.__name__,0)
    use=pos>=minimum;working=pos[use]
    mapping={'f':f,'c':f['close'],'cal':cal,'pos':working}
    x=module.values(*[mapping[a] for a in args.split(',')])
    result=[]
    for value in x:
        value=value[working] if len(value)==len(cal) else value
        if minimum:
            out=np.full((len(pos),f['close'].shape[1]),np.nan);out[use]=value;result.append(out)
        else:result.append(value)
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,f=pd.read_pickle(data.training_market_path());q.dates_all=cal
    original=pd.read_pickle(base.BASE/'signal_panels.pkl');formal=original['dates'];first=cal.get_loc(formal[0]);hp=np.arange(first%10,first,10);hp=hp[hp>=252];pos=np.r_[hp,cal.get_indexer(formal)];grid=cal[pos];n=len(hp)
    inventory=pd.read_csv(data.OUT/'all_factor_replay_inventory.csv');meta=pd.read_csv(q.ROOT/'research_reports/platform_alignment/shu-mulvey-sjm-bl-20261014/factor_metadata.csv').set_index('key')
    errors=[];rows=[];coverage=inventory.copy();cap=f['cap'][pos]
    def store(key,value,checks):
        path=OUT/f'{key}.history.pkl'
        if path.exists():rows.append(json.loads((OUT/f'{key}.audit.json').read_text()));return
        x=np.asarray(value,np.float32)
        if x.shape!=(len(grid),len(stocks)):raise ValueError(f'{key}: invalid builder shape {x.shape}')
        obj=pd.read_pickle(q.ROOT/meta.loc[key,'panel_path']);saved=obj['panels'][key]
        oldstock=stocks.get_indexer(obj['stocks']);current=x[n:,oldstock];old=saved.to_numpy(np.float32)
        good=np.isfinite(current)&np.isfinite(old);maximum=float(np.max(abs(current[good]-old[good]))) if good.any() else None
        mismatch=int(np.sum(np.isfinite(current)!=np.isfinite(old)))
        x[n:]=np.nan;x[n:,oldstock]=old;x=np.where(cap>0,x,np.nan)
        result,p,d=q.evaluate(x,grid,stocks,pos,f)
        p.to_csv(OUT/f'{key}.periods.csv',index=False);d.to_csv(OUT/f'{key}.daily_nav.csv',index=False);pd.to_pickle(dict(key=key,dates=grid,stocks=stocks,values=x),path)
        r=dict(key=key,historical_periods=int((p.date<formal[0]).sum()) if len(p) else 0,total_periods=len(p),formal_rebuild_finite_mask_mismatch=mismatch,formal_rebuild_max_absolute_difference=maximum,formal_saved_values_preserved=True,prefix_tests=checks)
        q.dump(OUT/f'{key}.audit.json',r);rows.append(r);pd.DataFrame(rows).drop(columns='prefix_tests',errors='ignore').to_csv(OUT/'replay_audit.csv',index=False)
        print('MARKET_REPLAYED',len(rows),key,'history',r['historical_periods'],flush=True)
    eligible=inventory[(inventory.adapter=='values')&inventory.arguments.isin(['f,pos','f','c,pos','f,cal,pos','c','c,cal,pos','cal,c,pos','f,cal'])]
    for script,g in eligible.groupby('builder_script',sort=True):
        keys=g.key.tolist()
        if all((OUT/f'{key}.history.pkl').exists() for key in keys):
            for key in keys:rows.append(json.loads((OUT/f'{key}.audit.json').read_text()))
            continue
        try:
            module=importlib.import_module(script.split('/')[-1][:-3]);specs=module.SPECS
            if isinstance(specs,dict):raise ValueError('batch dictionary requires explicit separate adapter')
            sk=[s['key'] if isinstance(s,dict) else s[0] for s in specs];args=g.arguments.iloc[0]
            ids=np.flatnonzero(np.isfinite(f['close'][-500:]).all(axis=0))[:16];small={k:v[:,ids] for k,v in f.items()}
            cp=hp[hp<1500];stop=int(cp[-1]+1)
            a=call(module,args,small,cal,cp);b=call(module,args,{k:v[:stop] for k,v in small.items()},cal[:stop],cp)
            if len(a)!=len(sk) or len(b)!=len(sk):raise ValueError('specification / output count mismatch')
            for aa,bb in zip(a,b):np.testing.assert_allclose(aa,bb,equal_nan=True,rtol=1e-5,atol=1e-6)
            values=call(module,args,f,cal,pos)
            if len(values)!=len(sk):raise ValueError('full output count mismatch')
            for key,value in zip(sk,values):
                if key in keys:store(key,value,[dict(test='historical_prefix_rebuild',cutoff=str(cal[stop-1].date()),passed=True)])
            del values,a,b;gc.collect()
        except Exception as e:
            errors.append(dict(script=script,keys=keys,error=str(e)[:700]));q.dump(OUT/'replay_errors.json',errors);print('REPLAY_ADAPTER_FAILED',script,str(e)[:200],flush=True)
    # The corrected TA-Lib source supplies a dedicated finite-segment adapter.
    source5=importlib.import_module('quant_corpus_semantic_source5_20261012')
    source5_checks=source5.verify(f)
    built,iv=source5.build(f)
    for spec,value in zip(source5.SPECS,built):
        key=spec[0]
        if key in set(inventory.key):store(key,value[pos],source5_checks)
    del built,iv;gc.collect()
    candle=importlib.import_module('quant_corpus_candles_20261013')
    from talib import abstract
    candle.talib.abstract=abstract
    for key in inventory.loc[inventory.adapter=='safe_talib_calculate','key']:
        name=key[len('candle_'):].upper()
        ids=np.flatnonzero(np.isfinite(f['close'][-500:]).all(axis=0))[:8];small={k:v[:,ids] for k,v in f.items()};stop=1500
        a=candle.calculate(name,small);b=candle.calculate(name,{k:v[:stop] for k,v in small.items()})
        np.testing.assert_array_equal(a[:stop],b)
        store(key,candle.calculate(name,f)[pos],[dict(test='historical_safe_talib_prefix',passed=True)])
    for r in rows:
        mask=coverage.key==r['key'];coverage.loc[mask,'replay_status']='replayed';coverage.loc[mask,'data_ready']=True;coverage.loc[mask,'reason']='historical prefix check passed; formal saved panels preserved'
    for path in base.OUT.glob('*.history.pkl'):
        key=path.name[:-12];mask=coverage.key==key;coverage.loc[mask,'replay_status']='replayed_base';coverage.loc[mask,'data_ready']=True;coverage.loc[mask,'reason']='base history rebuilt; audit in base replay directory'
    coverage.to_csv(data.OUT/'all_factor_replay_inventory_completed.csv',index=False)
    q.dump(OUT/'verification.json',dict(completed=True,replayed_market_factors=len(rows),adapter_failures=errors,all592_completed=bool(coverage.data_ready.all()),total_ready=int(coverage.data_ready.sum()),failed_adapters_kept=True,no_performance_filter=True,platform_calls=0))
    print('MARKET_REPLAY_FINISHED',len(rows),'ready',int(coverage.data_ready.sum()),flush=True)

if __name__=='__main__':main()
