"""Local-only BM proxy sensitivity for star_coin reconstruction.

This does not create a platform candidate.  It swaps the local BM array with
already-built PIT diagnostics and compares the same frozen ten-leg pool.
"""
from pathlib import Path
import json, sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEARCH = ROOT / 'research_reports/peer_reconstruction/top50-20261013/search_v1'
V2 = ROOT / 'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'
sys.path[:0] = [str(SEARCH), str(V2)]

from grammar import Expr
from engine import Market, Interpreter
from evidence import read, extract, PUBLIC
import objective


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    return x


def main():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    pool = tuple(Expr.from_json(x) for x in manifest['trees'])
    target = next(t for t in read(PUBLIC / 'targets.json') if t['rank'] == 8)
    diag = SEARCH / 'financial_proxy_diagnostic_v1'
    variants = {
        'baseline_pit_exc_latest': None,
        'bm_equity_inc': diag / 'bm_equity_inc.npy',
        'bm_equity_exc_annual': diag / 'bm_equity_exc_annual.npy',
        'bm_equity_inc_annual': diag / 'bm_equity_inc_annual.npy',
        'bm_bps_raw': diag / 'bm_bps_raw.npy',
    }
    rows = []
    for name, path in variants.items():
        market = Market()
        if path is not None:
            market.fields['bm'] = np.load(path)
            market.engine = Interpreter(market.fields)
        market.cache_dir = HERE / 'bm_sensitivity_panels' / name
        market.cache_dir.mkdir(parents=True, exist_ok=True)
        market.panel_cache.clear()
        evidence = extract(target, market)
        out = HERE / 'bm_sensitivity_eval' / name
        e = objective.Objective(market, evidence, out, pool)
        row = e.evaluate(pool, True)
        checks = row.get('checks', [])
        rows.append({
            'name': name,
            'score': row.get('score'),
            'ic_mae': row.get('ic_mae'),
            'rankic_mae': row.get('rankic_mae'),
            'mean_holdings_overlap': float(np.mean([x['overlap'] for x in checks])) if checks else None,
            'min_holdings_overlap': float(np.min([x['overlap'] for x in checks])) if checks else None,
            'top1_fraction': float(np.mean([x['top1_exact'] for x in checks])) if checks else None,
            'checks': checks,
            'proxy_path': str(path) if path is not None else 'financial.py leaves: latest consolidated equity / total_mv',
            'acceptance_eligible': False,
        })
    result = {
        'target': target,
        'pool_source': manifest.get('source_name'),
        'purpose': 'diagnose local BM proxy against platform holdings feedback; no platform submission',
        'rows': rows,
    }
    (HERE / 'star_coin_bm_sensitivity.json').write_text(
        json.dumps(clean(result), ensure_ascii=False, indent=2) + '\n'
    )
    for x in rows:
        print(json.dumps({k: x[k] for k in ('name', 'score', 'ic_mae', 'rankic_mae',
                                             'mean_holdings_overlap', 'min_holdings_overlap',
                                             'top1_fraction')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
