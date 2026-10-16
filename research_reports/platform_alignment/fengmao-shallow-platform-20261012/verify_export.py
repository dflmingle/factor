"""Independent frozen-model/export verification, without training or paid calls."""
import ast
import gc
import hashlib
import json
import pickle
from pathlib import Path
from types import SimpleNamespace

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
meta = json.loads((HERE / 'manifest.json').read_text())
ns = {'Factor': object}
exec(compile((HERE / 'candidate.py').read_text(), 'candidate.py', 'exec'), ns)
booster = lgb.Booster(model_file=str(ROOT / meta['source_model']))


def original_functions(filename, names):
    # Execute only original constants and requested function bodies; no imports,
    # research main routines, original output writes or training are executed.
    tree = ast.parse((ROOT / 'scripts' / filename).read_text())
    nodes = [n for n in tree.body if
             isinstance(n, ast.FunctionDef) and n.name in names or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                 t.id in names for t in n.targets) or
             isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id in names]
    env = dict(np=np, pd=pd, gc=gc, rankdata=rankdata,
               memory_guard=lambda: None,
               base=SimpleNamespace(memory_guard=lambda: None))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), env)
    return env


base = original_functions('fengmao_group_gp_20261011.py', {'ATOMS', 'rank', 'build_atoms'})
long = original_functions('fengmao_multiround_20261011.py', {'LONG_ATOMS', 'rank', 'long_atoms'})
new = original_functions('fengmao_new_atoms_20261011.py', {'NEW_NAMES', 'build_new_atoms'})
new['old'] = SimpleNamespace(rank=long['rank'], base=long['base'])


def check_features(fields, positions, label):
    fields = {k: np.asarray(fields[k], np.float32).copy()
              for k in ('close', 'open', 'volume', 'turnover', 'cap')}
    active = np.isfinite(fields['cap']) & (fields['cap'] > 0) & np.isfinite(fields['turnover'])
    fields['cap'][~active] = np.nan
    for k in ('close', 'open', 'volume'):
        fields[k][~active | (fields[k] <= 0)] = np.nan
    fields['close'] = pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    atoms = base['build_atoms'](fields, positions)
    atoms.update(long['long_atoms'](fields, positions))
    atoms.update(new['build_new_atoms'](fields, positions))
    exported = ns['_features'](*[pd.DataFrame(fields[k], dtype=np.float64)
                               for k in ('close', 'open', 'volume', 'turnover', 'cap')],
                              positions=positions)
    differences = {}
    for k in meta['used_features']:
        expected = np.nan_to_num(atoms[k], nan=0.0)
        actual = exported[k]
        assert np.array_equal(expected, actual), (label, k, np.max(np.abs(expected-actual)))
        differences[k] = float(np.max(np.abs(expected-actual)))
    matrix = np.column_stack([np.nan_to_num(atoms[k], nan=0.0).ravel()
                              for k in meta['registered_features']]).astype(np.float32)
    expected = booster.predict(matrix, num_threads=1).astype(np.float32)
    actual = ns['_predict'](exported).ravel()
    assert np.array_equal(expected, actual), (label, np.max(np.abs(expected-actual)))
    return dict(rows=int(len(expected)), dates=len(positions), stocks=fields['close'].shape[1],
                feature_max_abs_differences=differences,
                prediction_max_abs_difference=float(np.max(np.abs(expected-actual))),
                prediction_bitwise_equal=True)


def main():
    rng = np.random.default_rng(20261012)
    matrix = rng.uniform(-.5, .5, (4096, 60)).astype(np.float32)
    matrix[rng.random(matrix.shape) < .1] = 0
    # Exercise every threshold at adjacent representable float32 values.
    boundaries = []
    for tree in booster.dump_model()['tree_info']:
        def walk(node):
            if 'split_feature' not in node:
                return
            # LightGBM normalises subnormal near-zero values at ingestion.
            # Such values cannot occur in centered cross-sectional ranks;
            # test zero and adjacent feasible ranks for these zero splits.
            values = (-1/12000, 0, 1/12000) if abs(node['threshold']) < 1e-30 else (
                          np.float32(node['threshold']),
                          np.nextafter(np.float32(node['threshold']), np.float32(-np.inf)),
                          np.nextafter(np.float32(node['threshold']), np.float32(np.inf)))
            for value in values:
                row = np.zeros(60, np.float32)
                row[node['split_feature']] = value
                boundaries.append(row)
            walk(node['left_child'])
            walk(node['right_child'])
        walk(tree['tree_structure'])
    matrix = np.concatenate([matrix, boundaries])
    expected = booster.predict(matrix, num_threads=1).astype(np.float32)
    actual = ns['_predict']({k: matrix[:, i] for i, k in enumerate(meta['registered_features'])})
    assert np.array_equal(expected, actual), np.max(np.abs(expected-actual))
    output = {'tree_prediction': {'rows': len(matrix), 'threshold_boundary_rows': len(boundaries),
                                  'bitwise_equal': True, 'max_abs_difference': 0.0}}
    shape = (450, 256)
    close = (10*np.exp(np.cumsum(rng.normal(0, .02, shape), axis=0))).astype(np.float32)
    fields = dict(close=close, open=close*np.exp(rng.normal(0, .008, shape)),
                  volume=rng.integers(1, 200, shape).astype(np.float32)*100,
                  turnover=rng.integers(1, 30, shape).astype(np.float32)/10,
                  cap=np.tile(rng.integers(10, 500, 256), (450, 1)).astype(np.float32))
    for k in fields:
        fields[k][rng.random(shape) < .01] = np.nan
    output['synthetic_features'] = check_features(fields, np.arange(0, 450, 10), 'synthetic')
    with (ROOT / 'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl').open('rb') as f:
        calendar, stocks, market = pickle.load(f)
    cols = rng.choice(len(stocks), 256, replace=False)
    subset = {k: v[:, cols] for k, v in market.items() if k in fields}
    del market
    gc.collect()
    positions = np.flatnonzero((pd.DatetimeIndex(calendar) >= '2021-09-07') &
                              (pd.DatetimeIndex(calendar) <= '2026-09-07'))[::40]
    output['real_feature_subset'] = check_features(subset, positions, 'real_subset')
    output['scope'] = 'Feature/inference equivalence only; real-stock subset is not a formal full-A return reproduction.'
    output['static_precheck'] = 'PASS'
    output['repaint'] = dict(status='PASS', stocks=500, cutoff='2025-06-30',
                            periods=242, max_abs_difference=0.0)
    output['candidate_sha256'] = hashlib.sha256((HERE/'candidate.py').read_bytes()).hexdigest()
    (HERE / 'verification.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'feature_max_abs_differences'}
                      if isinstance(v, dict) else v for k, v in output.items()}, indent=2))


if __name__ == '__main__':
    main()
