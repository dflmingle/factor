"""Bounded offline AlphaPROBE GP search for the public grpvol clue.

The opponent formula is private: this is mechanism exploration, not an exact
replication. Only training labels affect evolution and finalist selection.
"""
from __future__ import annotations

import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

import argparse
import ast
import gc
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np
import pandas as pd
import psutil
from scipy.stats import rankdata, ttest_1samp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'quantlab/third_party/AlphaPROBE/src'))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from platform_aligned_factor_compare import read_platform_run
from search_field_policy import load_field_exclusion_policy
from utils.gplearn.genetic import SymbolicRegressor
from utils.gplearn.functions import _Function
from utils.gplearn.fitness import _Fitness

CACHE = ROOT / 'quantlab/.quantlab/cache/research/cn_equity'
OUT = ROOT / 'research_reports/platform_alignment/fengmao-group-gp-20261011'
REFERENCE = ROOT / 'h03-t10-single-20260911-candidates.results/6aa36bd3ecb163ea7228cffe.json'
GB = 1024 ** 3
PEAK = {'rss_gb': 0., 'private_gb': 0., 'min_available_gb': 100.}
DONE = threading.Event()
ATOMS = ['rev3', 'rev6', 'rev20', 'rev60', 'vol6', 'vol20', 'vol60',
         'vrel3', 'vrel6', 'vrel20', 'lowvolume1', 'lowvolume3', 'lowvolume20',
         'lowturn', 'trel6', 'vstab20', 'size']


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n', encoding='utf-8')


def memory_guard():
    info = psutil.Process().memory_info()
    rss = info.rss / GB
    private = getattr(info, 'private', info.rss) / GB
    available = psutil.virtual_memory().available / GB
    PEAK['rss_gb'] = max(PEAK['rss_gb'], rss)
    PEAK['private_gb'] = max(PEAK['private_gb'], private)
    PEAK['min_available_gb'] = min(PEAK['min_available_gb'], available)
    if max(rss, private) > 2.25 or available < 1.25:
        raise MemoryError(f'Memory boundary reached: rss={rss:.2f}, private={private:.2f}, free={available:.2f} GB')


def watchdog():
    while not DONE.wait(.5):
        try:
            memory_guard()
        except MemoryError as exc:
            dump(OUT / 'memory_stop.json', {'reason': str(exc), 'memory': PEAK, 'resume': 'saved atoms and search progress retained'})
            print(str(exc), flush=True)
            os._exit(78)


def rank(x):
    return (pd.DataFrame(x).rank(axis=1, pct=True).to_numpy(dtype=np.float32) - .5)


def group_rank(x, by, groups):
    result = np.full_like(x, np.nan, dtype=np.float32)
    for i in range(len(x)):
        ok = np.isfinite(x[i]) & np.isfinite(by[i])
        ids = np.flatnonzero(ok)
        if not len(ids):
            continue
        bins = np.minimum((rankdata(by[i, ids]) / len(ids) * groups).astype(int), groups - 1)
        for bucket in range(groups):
            chosen = ids[bins == bucket]
            if len(chosen):
                result[i, chosen] = rankdata(x[i, chosen]) / len(chosen) - .5
    return result


def evaluate_formula(formula, atoms):
    tree = ast.parse(formula, mode='eval')
    if sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.Name, ast.Call))) > 35:
        raise ValueError('expression exceeds 17 program nodes')
    def visit(node):
        if isinstance(node, ast.Name):
            return atoms[node.id]
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError('Only whitelisted expression calls are allowed')
        args = [visit(a) for a in node.args]
        name = node.func.id
        if name == 'Neg' and len(args) == 1:
            return -args[0]
        if name == 'Rank' and len(args) == 1:
            return rank(args[0])
        if name in {'Add', 'Sub', 'Mul'} and len(args) == 2:
            return {'Add': np.add, 'Sub': np.subtract, 'Mul': np.multiply}[name](*args)
        if name in {'Grp3', 'Grp5', 'Grp10'} and len(args) == 2:
            return group_rank(*args, int(name[3:]))
        raise ValueError('Unknown operator/arity: ' + name)
    return visit(tree.body)


def load_data():
    prices = sorted((CACHE / 'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet'))
    capfiles = sorted((CACHE / 'tushare_factor_recheck/daily_basic_full_a').glob('daily_basic_*.parquet'))
    symbols = set()
    latest = pd.Timestamp('2018-01-01')
    for path in prices:
        memory_guard()
        f = pd.read_parquet(path, columns=['date', 'instrument'])
        symbols.update(s for s in f.instrument.unique() if str(s).endswith(('.SH', '.SZ')))
        latest = max(latest, pd.to_datetime(f.date).max())
    del f
    stocks = pd.Index(sorted(symbols))
    frames = [pd.read_parquet(p, columns=['trade_date', 'is_open']) for p in (CACHE / 'trade_calendar').glob('*.parquet')]
    c = pd.concat(frames, ignore_index=True)
    dates = pd.to_datetime(c.trade_date.astype(str), format='mixed').dt.normalize()
    calendar = pd.DatetimeIndex(sorted(dates[c.is_open.eq(1) & dates.between('2018-01-01', latest)].unique()))
    del c, frames
    shape = len(calendar), len(stocks)
    fields = {k: np.full(shape, np.nan, np.float32) for k in ['close', 'volume', 'turnover', 'cap']}
    print('loading full-A projected arrays', shape, 'latest', latest.date(), flush=True)
    for path in prices:
        memory_guard()
        f = pd.read_parquet(path, columns=['date', 'instrument', 'close', 'volume'])
        di = calendar.get_indexer(pd.to_datetime(f.date).dt.normalize())
        si = stocks.get_indexer(f.instrument)
        ok = (di >= 0) & (si >= 0)
        for k in ['close', 'volume']:
            old = fields[k][di[ok], si[ok]]
            new = f[k].to_numpy(dtype=np.float32)[ok]
            if np.any(np.isfinite(old) & (old != new)):
                raise ValueError('Conflicting price snapshot ' + path.name)
            fields[k][di[ok], si[ok]] = new
    for i, path in enumerate(capfiles):
        memory_guard()
        f = pd.read_parquet(path, columns=['date', 'instrument', 'total_mv', 'turnover'])
        di = calendar.get_indexer(pd.to_datetime(f.date).dt.normalize())
        si = stocks.get_indexer(f.instrument)
        ok = (di >= 0) & (si >= 0) & f.total_mv.gt(0).to_numpy() & f.turnover.notna().to_numpy()
        for k, column in [('cap', 'total_mv'), ('turnover', 'turnover')]:
            fields[k][di[ok], si[ok]] = f[column].to_numpy(dtype=np.float32)[ok]
        if (i + 1) % 600 == 0:
            print('daily_basic', i + 1, '/', len(capfiles), flush=True)
    del f
    active = np.isfinite(fields['cap'])
    for k in ['close', 'volume']:
        fields[k][~active | (fields[k] <= 0)] = np.nan
    fields['close'] = pd.DataFrame(fields['close']).ffill().to_numpy(dtype=np.float32)
    gc.collect()
    return calendar, stocks, fields


def build_atoms(fields, positions):
    atoms = {k: np.full((len(positions), fields['close'].shape[1]), np.nan, np.float32) for k in ATOMS}
    for begin in range(0, fields['close'].shape[1], 192):
        memory_guard()
        sl = slice(begin, begin + 192)
        c, v, t = [pd.DataFrame(fields[k][:, sl], dtype=np.float64) for k in ['close', 'volume', 'turnover']]
        r = c / c.shift(1) - 1
        values = {}
        for n in [3, 6, 20, 60]:
            values[f'rev{n}'] = -(c / c.shift(n) - 1)
        for n in [6, 20, 60]:
            values[f'vol{n}'] = r.rolling(n, min_periods=n).std()
        v60, t60 = [x.rolling(60, min_periods=60).mean() for x in [v, t]]
        for n in [3, 6, 20]:
            values[f'vrel{n}'] = v.rolling(n, min_periods=n).mean() / v60
        for n in [1, 3, 20]:
            values[f'lowvolume{n}'] = -v.rolling(n, min_periods=n).mean()
        values['lowturn'] = -t.rolling(20, min_periods=20).mean()
        values['trel6'] = t.rolling(6, min_periods=6).mean() / t60
        values['vstab20'] = -v.rolling(20, min_periods=20).std() / v.rolling(20, min_periods=20).mean()
        for key, val in values.items():
            atoms[key][:, sl] = val.iloc[positions].to_numpy(dtype=np.float32)
        atoms['size'][:, sl] = -fields['cap'][positions, sl]
        del values, c, v, t, r, v60, t60
        gc.collect()
    active = np.isfinite(fields['cap'][positions])
    for key in atoms:
        atoms[key][~active | ~np.isfinite(atoms[key])] = np.nan
        atoms[key] = rank(atoms[key])
    return atoms


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    x, y = x - x.mean(), y - y.mean()
    den = np.sqrt(np.dot(x, x) * np.dot(y, y))
    return float(np.dot(x, y) / den) if den > 0 else 0.


def periods(value, target, dates, size):
    records = []
    prev = None
    for i, date in enumerate(dates):
        ok = np.isfinite(value[i]) & np.isfinite(target[i]) & np.isfinite(size[i])
        ids = np.flatnonzero(ok)
        if len(ids) < 100:
            continue
        x, y = value[i, ids], target[i, ids]
        if np.std(x) < 1e-10:
            continue
        # Equal values retain stable symbol order; tie sensitivity is diagnostic.
        order = np.argsort(x, kind='stable')
        groups = np.ceil(np.arange(1, len(ids) + 1) * 10 / len(ids)).astype(int)
        chosen = ids[order[groups == 10]]
        members = set(chosen)
        turnover = np.nan if prev is None else 1 - len(members & prev) / len(members)
        prev = members
        records.append(dict(date=str(date.date()), stocks=len(ids), ic=corr(x, y),
                            rank_ic=corr(rankdata(x), rankdata(y)), turnover=turnover,
                            gross_excess=float(target[i, chosen].mean() - y.mean()),
                            corr_size=corr(rankdata(x), rankdata(size[i, ids])),
                            tied_fraction=float(pd.Series(x).duplicated(keep=False).mean())))
    return pd.DataFrame(records)


def summarize(p):
    if len(p) < 2:
        raise ValueError('Insufficient periods')
    ic, ric = p.ic.to_numpy(), p.rank_ic.to_numpy()
    icir = float(ic.mean() / ic.std(ddof=1)) if ic.std(ddof=1) > 1e-10 else 0.
    gross, turn = float(p.gross_excess.mean() * 25.2), float(p.turnover.mean())
    return dict(periods=len(p), ic_mean=float(ic.mean()), rank_ic=float(ric.mean()), icir=icir,
                ic_win=float((ic > .02).mean()), s_i_proxy=abs(float(ric.mean())) * max(icir, 0) * float((ic > .02).mean()),
                gross_excess=gross, turnover=turn, annual_cost=turn * .006 * 25.2,
                net_excess=gross - turn * .006 * 25.2, corr_size=float(p.corr_size.mean()),
                tied_fraction=float(p.tied_fraction.mean()), p_naive=float(ttest_1samp(ic, 0).pvalue),
                first_signal=p.date.min(), last_signal=p.date.max())


def symbol_function(name, arity):
    def emit(*args):
        return np.asarray([name + '(' + ','.join(str(np.asarray(a).flat[0]) for a in args) + ')'], dtype=object)
    return _Function(emit, name, arity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        x = np.asarray([[1., 2., 3., 4.], [4., 3., 2., 1.]], np.float32)
        a = {'x': x, 'y': np.asarray([[1., 1., 2., 2.]] * 2, np.float32)}
        expected = np.asarray([[0., .5, 0., .5], [.5, 0., .5, 0.]], np.float32)
        assert np.array_equal(evaluate_formula('Grp3(x,y)', a), expected)
        assert np.array_equal(evaluate_formula('Neg(Grp3(x,y))', a), -expected)
        print('group axis, tie ranks and safe formula evaluation passed')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'metadata.json').exists() or (OUT / 'search_progress.jsonl').exists():
        raise RuntimeError('Refuse overwrite: choose a new dated batch')
    started = time.perf_counter()
    validate_alignment_config(alignment_config_snapshot())
    policy = load_field_exclusion_policy(allow_version_mismatch=True)
    fields_used = {'close', 'volume', 'market_cap', 'turnover'}
    if fields_used.intersection(policy['blocked_fields']):
        raise ValueError('This search requires blocked fields; do not silently broaden it')
    dump(OUT / 'plan.json', dict(population=48, generations=5, evaluations_max=240, finalists=3,
        train='20210907..20231229', validation='20240101..20251231', recent='20260101..local_latest',
        fields=sorted(fields_used), terminals=ATOMS, operators=['Neg', 'Rank', 'Add', 'Sub', 'Mul', 'Grp3', 'Grp5', 'Grp10'],
        memory_limits={'process_gb': 2.25, 'system_available_min_gb': 1.25, 'stock_chunk': 192},
        opponent_formula='unknown', objective='training score and cost, never opponent headline matching',
        rule=ALIGNMENT_RULE_VERSION, field_policy=policy, platform_cost=0))
    threading.Thread(target=watchdog, daemon=True).start()
    calendar, stocks, fields = load_data()
    saved = read_platform_run(REFERENCE)
    dates = pd.DatetimeIndex(sorted(d for d in set(saved['dates']) if d in calendar and calendar.get_loc(d) + 11 < len(calendar)))
    pos = calendar.get_indexer(dates)
    target = fields['close'][pos + 11].astype(float) / fields['close'][pos + 1].astype(float) - 1
    size = fields['cap'][pos]
    atoms = build_atoms(fields, pos)
    train = (dates <= '2023-12-29')
    train_atoms = {k: v[train] for k, v in atoms.items()}
    np.savez_compressed(OUT / 'atoms.npz', **atoms, target=target, market_cap=size)
    dump(OUT / 'axes.json', {'dates': [str(d.date()) for d in dates], 'symbols': stocks.tolist()})
    cache = {}
    def score(_y, formulas, _w):
        formula = str(np.asarray(formulas).flat[0])
        if formula in cache:
            return cache[formula]['fitness']
        memory_guard()
        row = {'formula': formula, 'fitness': -10., 'status': 'invalid'}
        try:
            if 'Grp' not in formula:
                raise ValueError('Require grouping mechanism; do not relabel an ordinary factor')
            value = evaluate_formula(formula, train_atoms)
            p = periods(value, target[train], dates[train], size[train])
            stats = summarize(p)
            if len(p) < .95 * train.sum():
                raise ValueError('Insufficient training coverage')
            row.update(stats)
            # A-first, with explicit penalties for negative held-side net and
            # excessive turnover. This is a search reward, not official points.
            row['fitness'] = stats['s_i_proxy'] + .2 * min(stats['net_excess'], 0) - .02 * max(stats['turnover'] - .4, 0)
            row['status'] = 'evaluated'
        except (ValueError, KeyError, SyntaxError) as exc:
            row['error'] = str(exc)
        cache[formula] = row
        with (OUT / 'search_progress.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, allow_nan=False) + '\n')
        return row['fitness']
    generations = []
    def callback():
        row = {'generation': len(generations) + 1, 'unique_formulas': len(cache),
               'best': max(cache.values(), key=lambda r: r['fitness']), 'memory': dict(PEAK)}
        generations.append(row)
        dump(OUT / 'generations.json', generations)
        print('generation', row['generation'], 'unique', len(cache), 'best', row['best']['formula'], 'fitness', round(row['best']['fitness'], 5), 'memory', PEAK, flush=True)
    functions = [symbol_function(n, a) for n, a in [('Neg', 1), ('Rank', 1), ('Add', 2), ('Sub', 2), ('Mul', 2), ('Grp3', 2), ('Grp5', 2), ('Grp10', 2)]]
    estimator = SymbolicRegressor(population_size=48, generations=5, tournament_size=8,
        init_depth=(1, 3), const_range=None, function_set=functions,
        metric=_Fitness(score, greater_is_better=True), stopping_criteria=1.,
        parsimony_coefficient=.0005, random_state=20261011, n_jobs=1,
        p_crossover=.45, p_subtree_mutation=.25, p_hoist_mutation=.1,
        p_point_mutation=.1, max_samples=1., low_memory=True, verbose=1)
    estimator.fit(np.asarray([ATOMS], dtype=object), np.asarray([1.]), callback=callback)
    selected, train_values = [], []
    for row in sorted(cache.values(), key=lambda r: r['fitness'], reverse=True):
        if row['status'] != 'evaluated':
            continue
        value = evaluate_formula(row['formula'], train_atoms)
        duplicate = False
        for prior in train_values:
            correlations = []
            for x, y in zip(value, prior):
                ok = np.isfinite(x) & np.isfinite(y)
                if ok.sum() > 100:
                    correlations.append(corr(rankdata(x[ok]), rankdata(y[ok])))
            if correlations and abs(np.mean(correlations)) > .98:
                duplicate = True
                break
        if not duplicate:
            selected.append(row)
            train_values.append(value)
        if len(selected) == 3:
            break
    if len(selected) != 3:
        raise ValueError('Fewer than three distinct finalists; no automatic second round')
    dump(OUT / 'frozen_finalists.json', selected)
    del train_values, train_atoms, estimator
    gc.collect()
    print('finalists frozen before validation labels used', flush=True)
    # Prefix recomputation from the actual daily inputs, retaining all stocks.
    cutoff = calendar.get_loc(pd.Timestamp('2024-06-28'))
    prefix = dates <= calendar[cutoff]
    cut_atoms = build_atoms({k: v[:cutoff + 1] for k, v in fields.items()}, pos[prefix])
    checks, results, year_rows = [], [], []
    masks = {'formal_5y': np.ones(len(dates), bool), 'training': train,
             'validation_2024_2025': (dates >= '2024-01-01') & (dates <= '2025-12-31'),
             'recent_2026': dates >= '2026-01-01'}
    for i, row in enumerate(selected, 1):
        name = f'FMGP{i:02d}'
        value = evaluate_formula(row['formula'], atoms)
        truncated = evaluate_formula(row['formula'], cut_atoms)
        same = np.array_equal(np.isfinite(value[prefix]), np.isfinite(truncated))
        valid = np.isfinite(truncated)
        difference = float(np.max(np.abs(value[prefix][valid] - truncated[valid])))
        assert same and difference == 0, 'Prefix leakage: ' + name
        checks.append(dict(candidate=name, cutoff='2024-06-28', dates=int(prefix.sum()), valid_cells=int(valid.sum()), masks_equal=same, max_abs_difference=difference))
        np.save(OUT / (name + '_signals.npy'), value)
        for window, mask in masks.items():
            p = periods(value[mask], target[mask], dates[mask], size[mask])
            stats = summarize(p)
            results.append(dict(candidate=name, formula=row['formula'], window=window, **stats))
            p.to_csv(OUT / f'{name}_{window}_periods.csv', index=False)
            # Independently reconstruct arithmetic return/cost from persisted periods.
            reread = pd.read_csv(OUT / f'{name}_{window}_periods.csv')
            check_net = reread.gross_excess.sum() * 252 / (len(reread) * 10) - reread.turnover.dropna().sum() / (len(reread) - 1) * .006 * 25.2
            assert abs(check_net - stats['net_excess']) < 1e-10
            assert np.isnan(reread.turnover.iloc[0])
            print(name, window, 'IC', round(stats['ic_mean'], 4), 'ICIR', round(stats['icir'], 3), 'net', round(stats['net_excess'] * 100, 2), flush=True)
            if window == 'formal_5y':
                for year, b in p.groupby(p.date.str[:4]):
                    if len(b) >= 2:
                        year_rows.append(dict(candidate=name, year=year, **summarize(b)))
    pd.DataFrame(results).to_csv(OUT / 'results.csv', index=False)
    pd.DataFrame(year_rows).to_csv(OUT / 'years.csv', index=False)
    pd.DataFrame(cache.values()).to_csv(OUT / 'search_registry.csv', index=False)
    dump(OUT / 'causality_checks.json', checks)
    dump(OUT / 'metadata.json', dict(status='complete', method='fengmao-group-gp-full-a-arithmetic-proxy-v1',
        alignment_reference=ALIGNMENT_RULE_VERSION, actual_evaluations=len(cache), population=48, generations=5,
        finalists=3, seed=20261011, cost=0, source='local full-A qfq cache, current daily_basic total_mv',
        date_source=str(REFERENCE.relative_to(ROOT)), label='close(t+1)->close(t+11)', groups=10, one_way_cost=.003,
        warmup='20180101', nominal_window=['20210907','20260907'], data_latest=str(calendar[-1].date()),
        last_signal=str(dates[-1].date()), last_realized_end=str(calendar[pos[-1]+11].date()),
        direction=1, memory=PEAK, elapsed_seconds=time.perf_counter()-started,
        selection='training 2021-2023 only, rank-correlation dedupe .98; finalists frozen before validation',
        validation_scope='historical research validation, previously researched data, not pristine OOS or official B',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        array_precision='float32 storage, float64 rolling statistics and labels',
        limitations=['private opponent formula unavailable', 'opponent dates not identical', 'no official S_i or pool scoring', 'stable symbol tie ordering proxy'],
        verification='prefix recomputation all stocks and independent saved-period net/cost checks passed'))
    DONE.set()
    print('COMPLETE', OUT, 'seconds', round(time.perf_counter()-started, 1), 'peak', PEAK, flush=True)


if __name__ == '__main__':
    main()
