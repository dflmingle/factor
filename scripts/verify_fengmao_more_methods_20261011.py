"""Independent pandas decile checks and real daily-input prefix recomputation.

No torch or platform CLI import. Raw causality checks use 100 fixed stocks;
this is a local audit, not platform Python submission certification.
"""
from pathlib import Path
import argparse
import gc
import json
import os
import sys
import time
import warnings

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/platform_alignment/fengmao-more-methods-20261011'
SOURCE = ROOT/'research_reports/platform_alignment/fengmao-multiround2-20261011'
sys.path.insert(0,str(ROOT/'scripts'))


def write(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')


def check_periods():
    a = np.load(SOURCE/'atoms.npz')
    y,cap = a['target'],a['market_cap']
    a.close()
    axes = json.loads((OUT/'axes.json').read_text(encoding='utf-8'))
    dates = pd.DatetimeIndex(axes['dates'])
    saved_stats = pd.read_csv(OUT/'results.csv')
    models = json.loads((OUT/'models_frozen.json').read_text(encoding='utf-8'))
    assert len(models)==3
    groups, yearrows, diagnostics = [], [], []
    count, maxdelta = 0,0.
    for ci in range(1,4):
        name = f'FM_MORE_{ci:02d}'
        x = np.load(OUT/(name+'_signals.npy'))
        assert x.shape==y.shape
        for window in saved_stats.window.unique():
            p = pd.read_csv(OUT/f'{name}_{window}_periods.csv')
            prev, detail = {},[]
            for row in p.itertuples():
                at = dates.get_loc(pd.Timestamp(row.date))
                ok = np.isfinite(x[at]) & np.isfinite(y[at]) & np.isfinite(cap[at])
                ids = np.flatnonzero(ok)
                xx,yy = pd.Series(x[at,ids],index=ids),pd.Series(y[at,ids],index=ids)
                assert len(ids)==row.stocks
                ic,ric = xx.corr(yy),xx.corr(yy,method='spearman')
                maxdelta = max(maxdelta,abs(ic-row.ic),abs(ric-row.rank_ic))
                assert abs(ic-row.ic)<2e-8 and abs(ric-row.rank_ic)<2e-8
                tied = float(xx.duplicated(keep=False).mean())
                assert abs(tied-row.tied_fraction)<1e-12
                buckets = np.ceil(xx.rank(method='first')*10/len(xx)).clip(1,10).astype(int)
                assert set(buckets)==set(range(1,11))
                for group in range(1,11):
                    held = set(buckets.index[buckets.eq(group)])
                    turn = np.nan if group not in prev else 1-len(held & prev[group])/len(held)
                    prev[group] = held
                    gross = float(yy.loc[list(held)].mean()-yy.mean())
                    detail.append(dict(candidate=name,window=window,date=row.date,group=group,
                                       gross_excess=gross,turnover=turn,stocks=len(held)))
                    if group==10:
                        assert abs(gross-row.gross_excess)<1e-10
                        assert (np.isnan(turn) and np.isnan(row.turnover)) or abs(turn-row.turnover)<1e-10
                count += 1
            table = pd.DataFrame(detail)
            table.to_csv(OUT/f'{name}_{window}_group_periods.csv',index=False)
            summary = saved_stats[(saved_stats.candidate==name)&(saved_stats.window==window)].iloc[0]
            for group,b in table.groupby('group'):
                gross,turn = float(b.gross_excess.mean()*25.2),float(b.turnover.mean())
                net = gross-turn*.006*25.2
                groups.append(dict(candidate=name,window=window,group=int(group),gross_excess=gross,
                                   turnover=turn,net_excess=net))
                if group==10:
                    assert abs(net-summary.net_excess)<1e-10
                    assert abs(turn-summary.turnover)<1e-10
            icir = float(p.ic.mean()/p.ic.std(ddof=1))
            win = float(p.ic.gt(.02).mean())
            s_i = abs(float(p.rank_ic.mean()))*max(icir,0)*win
            assert abs(icir-summary.icir)<1e-10
            assert abs(s_i-summary.s_i_proxy)<1e-10
            if window=='training':
                # Re-read trade calendar independently for split-boundary purge.
                paths = list((ROOT/'quantlab/.quantlab/cache/research/cn_equity/trade_calendar').glob('*.parquet'))
                f = pd.concat([pd.read_parquet(path,columns=['trade_date','is_open']) for path in paths],ignore_index=True)
                d = pd.to_datetime(f.trade_date.astype(str),format='mixed').dt.normalize()
                cal = pd.DatetimeIndex(sorted(d[f.is_open.eq(1)].unique()))
                exits = cal[cal.get_indexer(pd.DatetimeIndex(p.date))+11]
                assert np.all(exits<=pd.Timestamp('2023-12-29'))
            if window=='formal_5y':
                for year,b in p.groupby(p.date.str[:4]):
                    yearrows.append(dict(candidate=name,year=year,periods=len(b),ic_mean=float(b.ic.mean()),
                        rank_ic=float(b.rank_ic.mean()),net_excess=float(b.gross_excess.mean()*25.2-b.turnover.mean()*.006*25.2),
                        turnover=float(b.turnover.mean())))
        top = pd.read_csv(OUT/(name+'_top20.csv'))
        for day,b in top.groupby('date'):
            at = dates.get_loc(pd.Timestamp(day))
            ids = np.flatnonzero(np.isfinite(x[at]))
            selected = pd.Series(x[at,ids],index=ids).sort_values(ascending=False,kind='stable').index[:20]
            assert b.instrument.tolist()==[axes['symbols'][ident] for ident in selected]
        diagnostics.append(dict(candidate=name,top20_verified=True))
    pd.DataFrame(groups).to_csv(OUT/'deciles.csv',index=False)
    pd.DataFrame(yearrows).to_csv(OUT/'years.csv',index=False)
    signals = [np.load(OUT/f'FM_MORE_{i:02d}_signals.npy') for i in range(1,4)]
    pairs = []
    for i in range(3):
        for j in range(i+1,3):
            rho = [pd.Series(l).corr(pd.Series(r),method='spearman') for l,r in zip(signals[i],signals[j])]
            pairs.append(dict(left=f'FM_MORE_{i+1:02d}',right=f'FM_MORE_{j+1:02d}',
                              mean_signal_date_spearman=float(np.nanmean(rho)),scope='signal dates; not daily factor correlation'))
    pd.DataFrame(pairs).to_csv(OUT/'candidate_correlations.csv',index=False)
    return dict(period_records=count,summary_rows=len(saved_stats),ic_max_delta=maxdelta,
                deciles_membership_cost_verified=True,training_label_purge_verified=True,
                top20=diagnostics)


def raw_causality():
    import fengmao_multiround_20261011 as task
    warnings.filterwarnings('ignore',category=RuntimeWarning)
    cache = task.base.CACHE
    axes = json.loads((OUT/'axes.json').read_text(encoding='utf-8'))
    allsymbols = axes['symbols']
    symbols = pd.Index([allsymbols[i] for i in np.linspace(0,len(allsymbols)-1,100,dtype=int)])
    dates = pd.DatetimeIndex(axes['dates'])
    f = pd.concat([pd.read_parquet(p,columns=['trade_date','is_open']) for p in (cache/'trade_calendar').glob('*.parquet')],ignore_index=True)
    d = pd.to_datetime(f.trade_date.astype(str),format='mixed').dt.normalize()
    cal = pd.DatetimeIndex(sorted(d[f.is_open.eq(1)&d.between('2018-01-01','2026-09-07')].unique()))
    fields = {k:np.full((len(cal),len(symbols)),np.nan,np.float32) for k in ('close','volume','turnover','cap')}
    filters = [('instrument','in',symbols.tolist())]
    for p in sorted((cache/'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet')):
        task.base.memory_guard()
        f = pd.read_parquet(p,columns=['date','instrument','close','volume'],filters=filters)
        di,si = cal.get_indexer(pd.to_datetime(f.date).dt.normalize()),symbols.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)
        for key in ('close','volume'):
            fields[key][di[ok],si[ok]] = f[key].to_numpy(np.float32)[ok]
    paths = sorted((cache/'tushare_factor_recheck/daily_basic_full_a').glob('daily_basic_*.parquet'))
    for i,p in enumerate(paths):
        task.base.memory_guard()
        f = pd.read_parquet(p,columns=['date','instrument','total_mv','turnover'],filters=filters)
        di,si = cal.get_indexer(pd.to_datetime(f.date).dt.normalize()),symbols.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)&f.total_mv.gt(0).to_numpy()&f.turnover.notna().to_numpy()
        for key,col in [('cap','total_mv'),('turnover','turnover')]:
            fields[key][di[ok],si[ok]] = f[col].to_numpy(np.float32)[ok]
        if (i+1)%600==0:
            print('raw audit daily_basic',i+1,'/',len(paths),flush=True)
    del f
    active = np.isfinite(fields['cap'])
    for key in ('close','volume'):
        fields[key][~active|(fields[key]<=0)] = np.nan
    fields['close'] = pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    pos = cal.get_indexer(dates)
    assert np.all(pos>=0)
    cached = np.load(SOURCE/'atoms.npz')
    original_idx = pd.Index(allsymbols).get_indexer(symbols)
    rebuilt_y = fields['close'][pos+11].astype(float)/fields['close'][pos+1].astype(float)-1
    cached_y = cached['target'][:,original_idx]
    cached_cap = cached['market_cap'][:,original_idx]
    assert np.array_equal(np.isfinite(rebuilt_y),np.isfinite(cached_y))
    assert np.allclose(rebuilt_y,cached_y,equal_nan=True,atol=1e-12,rtol=0)
    assert np.array_equal(fields['cap'][pos],cached_cap,equal_nan=True)
    cached.close()
    print('100-stock cached qfq label-1 and total_mv parity PASS',flush=True)
    full = task.base.build_atoms(fields,pos)
    full.update(task.long_atoms(fields,pos))
    models = json.loads((OUT/'models_frozen.json').read_text(encoding='utf-8'))
    checks = []
    for cutoff in ('2024-06-28','2025-06-30'):
        end = int(cal.searchsorted(pd.Timestamp(cutoff),side='right'))
        mask = dates<=cal[end-1]
        truncated = {k:v[:end] for k,v in fields.items()}
        cut = task.base.build_atoms(truncated,pos[mask])
        cut.update(task.long_atoms(truncated,pos[mask]))
        atom_checks = []
        for key in full:
            left,right = full[key][mask],cut[key]
            assert np.array_equal(np.isfinite(left),np.isfinite(right)),key
            valid = np.isfinite(right)
            diff = float(np.max(np.abs(left[valid]-right[valid]))) if valid.any() else 0.
            assert diff==0.,(key,diff)
            atom_checks.append(dict(atom=key,cells=int(valid.sum()),max_difference=diff))
        model_checks = []
        for i,m in enumerate(models,1):
            left,right = task.model_value(m,full)[mask],task.model_value(m,cut)
            assert np.array_equal(np.isfinite(left),np.isfinite(right))
            valid = np.isfinite(right)
            diff = float(np.max(np.abs(left[valid]-right[valid]))) if valid.any() else 0.
            assert diff==0.
            model_checks.append(dict(candidate=f'FM_MORE_{i:02d}',cells=int(valid.sum()),max_difference=diff))
        checks.append(dict(cutoff=cutoff,stocks=len(symbols),signals=int(mask.sum()),atoms=atom_checks,models=model_checks,status='passed'))
        print('raw daily-input prefix PASS',cutoff,len(symbols),'stocks',flush=True)
    write('raw_causality_checks.json',dict(status='passed',sampling='fixed evenly spaced 100 symbols; 20180101 warmup',
        scope='actual daily-input atom-building code + frozen expressions/weights',checks=checks,
        cached_qfq_label1_and_total_mv_verified=True,
        limitation='local sample audit, not platform_precheck or repaint_check certification'))
    return dict(status='passed',stocks=100,cutoffs=2,memory=task.base.PEAK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-raw',action='store_true')
    args = ap.parse_args()
    periods = check_periods()
    raw = dict(status='not_run') if args.skip_raw else raw_causality()
    prefix = json.loads((OUT/'expression_prefix_checks.json').read_text(encoding='utf-8'))
    assert all(p['masks_equal'] and p['max_difference']==0 for p in prefix)
    meta = json.loads((OUT/'metadata.json').read_text(encoding='utf-8'))
    # Conservative calls include the prior GP allowance and this round's token
    # upper bound; not a claim that adaptive tests are statistically independent.
    denominator = 240+5760+2*6144+1536+32+3
    write('verification.json',dict(status='passed' if raw['status']=='passed' else 'periods_only',**periods,
        expression_prefix_cells=sum(p['cells'] for p in prefix),raw_daily_input_causality=raw,
        training_unique_formulas=meta['training_unique_formulas'],conservative_test_denominator=denominator,
        correction_threshold=.05/denominator,statistical_limit='historical validation has already been researched'))
    print('INDEPENDENT VERIFICATION COMPLETE',periods,'raw',raw['status'],flush=True)


if __name__=='__main__':
    main()
