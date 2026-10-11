"""Independent decile audit plus real-input recomputation for new signal round."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
import hashlib
import json
from pathlib import Path
import threading
import time
import numpy as np
import pandas as pd
import fengmao_multiround_20261011 as old
import fengmao_new_atoms_20261011 as features
import verify_fengmao_more_methods_20261011 as previous

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/platform_alignment/fengmao-new-signals-20261011'
CONTEXT = ['rev3','rev20','rev60','vol20','vol60','vrel20','lowturn','vstab20']


def raw_causality():
    cache = old.base.CACHE
    axes = json.loads((OUT/'axes.json').read_text(encoding='utf-8'))
    allsymbols = axes['symbols']
    symbols = pd.Index([allsymbols[i] for i in np.linspace(0,len(allsymbols)-1,100,dtype=int)])
    dates = pd.DatetimeIndex(axes['dates'])
    f = pd.concat([pd.read_parquet(p,columns=['trade_date','is_open']) for p in
                   (cache/'trade_calendar').glob('*.parquet')],ignore_index=True)
    d = pd.to_datetime(f.trade_date.astype(str),format='mixed').dt.normalize()
    cal = pd.DatetimeIndex(sorted(d[f.is_open.eq(1)&d.between('2018-01-01','2026-09-07')].unique()))
    fields = {k:np.full((len(cal),len(symbols)),np.nan,np.float32)
              for k in ('close','volume','turnover','cap')}
    filters = [('instrument','in',symbols.tolist())]
    for p in sorted((cache/'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet')):
        old.base.memory_guard()
        f = pd.read_parquet(p,columns=['date','instrument','close','volume'],filters=filters)
        di,si = cal.get_indexer(pd.to_datetime(f.date).dt.normalize()),symbols.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)
        for key in ('close','volume'):
            fields[key][di[ok],si[ok]] = f[key].to_numpy(np.float32)[ok]
    for i,p in enumerate(sorted((cache/'tushare_factor_recheck/daily_basic_full_a').glob('daily_basic_*.parquet'))):
        old.base.memory_guard()
        f = pd.read_parquet(p,columns=['date','instrument','total_mv','turnover'],filters=filters)
        di,si = cal.get_indexer(pd.to_datetime(f.date).dt.normalize()),symbols.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)&f.total_mv.gt(0).to_numpy()&f.turnover.notna().to_numpy()
        for key,col in (('cap','total_mv'),('turnover','turnover')):
            fields[key][di[ok],si[ok]] = f[col].to_numpy(np.float32)[ok]
        if (i+1)%600==0:
            print('raw audit daily_basic',i+1,flush=True)
    del f
    active = np.isfinite(fields['cap'])
    for key in ('close','volume'):
        fields[key][~active|(fields[key]<=0)] = np.nan
    fields['close'] = pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    features.load_open(cal,symbols,fields,filters)
    pos = cal.get_indexer(dates)
    ids = pd.Index(allsymbols).get_indexer(symbols)
    with np.load(OUT/'atoms.npz') as cached:
        y = fields['close'][pos+11].astype(float)/fields['close'][pos+1].astype(float)-1
        assert np.allclose(y,cached['target'][:,ids],equal_nan=True,atol=1e-12,rtol=0)
        assert np.array_equal(fields['cap'][pos],cached['market_cap'][:,ids],equal_nan=True)
    def build(data,positions):
        context = old.base.build_atoms(data,positions)
        atoms = {k:context[k] for k in CONTEXT}
        atoms.update(features.build_new_atoms(data,positions))
        return atoms
    full = build(fields,pos)
    models = json.loads((OUT/'models_frozen.json').read_text(encoding='utf-8'))
    checks = []
    for cutoff in ('2024-06-28','2025-06-30'):
        end = int(cal.searchsorted(pd.Timestamp(cutoff),side='right'))
        mask = dates<=cal[end-1]
        cut = build({k:v[:end] for k,v in fields.items()},pos[mask])
        atoms_checked,models_checked = [],[]
        for key in full:
            l,r = full[key][mask],cut[key]
            assert np.array_equal(np.isfinite(l),np.isfinite(r)),key
            valid = np.isfinite(r)
            delta = float(np.max(np.abs(l[valid]-r[valid]))) if valid.any() else 0.
            assert delta==0.,(key,delta)
            atoms_checked.append(dict(atom=key,cells=int(valid.sum()),max_difference=delta))
        for i,m in enumerate(models,1):
            l,r = old.model_value(m,full)[mask],old.model_value(m,cut)
            assert np.array_equal(np.isfinite(l),np.isfinite(r))
            valid = np.isfinite(r)
            delta = float(np.max(np.abs(l[valid]-r[valid]))) if valid.any() else 0.
            assert delta==0.
            models_checked.append(dict(candidate=f'FM_MORE_{i:02d}',cells=int(valid.sum()),max_difference=delta))
        checks.append(dict(cutoff=cutoff,stocks=100,signals=int(mask.sum()),
                           atoms=atoms_checked,models=models_checked,status='passed'))
        print('real daily-input prefix PASS',cutoff,flush=True)
        del cut
        gc.collect()
    previous.write('raw_causality_checks.json',dict(status='passed',checks=checks,
        actual_qfq_open=True,cached_label1_total_mv_parity=True,
        scope='actual daily-input atom builder and frozen model on fixed 100-stock sample',
        limitation='local sample audit; not platform_precheck/repaint_check certification'))
    return dict(status='passed',stocks=100,cutoffs=2,memory=old.base.PEAK)


def main():
    started = time.monotonic()
    previous.OUT = previous.SOURCE = OUT
    old.base.OUT = OUT
    threading.Thread(target=old.base.watchdog,daemon=True).start()
    periods = previous.check_periods()
    raw = raw_causality()
    correlations = []
    with np.load(OUT/'atoms.npz') as saved:
        references = {k:saved[k] for k in saved.files if k not in ('target','market_cap')}
    prior = ROOT/'research_reports/platform_alignment/fengmao-more-methods-20261011'
    references.update({f'previous_method_{i:02d}': np.load(prior/f'FM_MORE_{i:02d}_signals.npy') for i in range(1,4)})
    for i in range(1,4):
        x = np.load(OUT/f'FM_MORE_{i:02d}_signals.npy')
        for name,y in references.items():
            valid = np.isfinite(x)&np.isfinite(y)
            rho = old.rowcorr(old.rank(np.where(valid,x,np.nan)),old.rank(np.where(valid,y,np.nan)))
            correlations.append(dict(candidate=f'FM_MORE_{i:02d}',reference=name,
                mean_spearman=float(np.nanmean(rho)),mean_abs_spearman=float(np.nanmean(np.abs(rho))),
                scope='saved signal-date cross sections, not daily factor correlation'))
    pd.DataFrame(correlations).to_csv(OUT/'reference_correlations.csv',index=False)
    prefix = json.loads((OUT/'expression_prefix_checks.json').read_text(encoding='utf-8'))
    assert all(p['masks_equal'] and p['max_difference']==0 for p in prefix)
    meta = json.loads((OUT/'metadata.json').read_text(encoding='utf-8'))
    denominator = 19859+6144+384+56+3
    previous.write('verification.json',dict(status='passed',**periods,
        expression_prefix_cells=sum(p['cells'] for p in prefix),raw_daily_input_causality=raw,
        training_unique_formulas=meta['training_unique_formulas'],
        conservative_test_denominator=denominator,correction_threshold=.05/denominator,
        verification_seconds=time.monotonic()-started,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        statistical_limit='validation already researched; allowance accumulates prior GP/PPO/GFN research'))
    old.base.DONE.set()
    print('INDEPENDENT VERIFICATION COMPLETE',periods,flush=True)


if __name__=='__main__':
    main()
