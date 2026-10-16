"""Offline EP/CFP/SP proxy sensitivity for the frozen star_coin pool.

The platform result is not rerun here.  This script only swaps causal local
financial leaves built from the existing Tushare PIT cache and measures the
same ten-leg equal-weight pool against the five saved public holding dates.
"""
from pathlib import Path
import hashlib
import json
import sys
import warnings

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEARCH = ROOT / 'research_reports/peer_reconstruction/top50-20261013/search_v1'
V2 = ROOT / 'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'
sys.path[:0] = [str(SEARCH), str(V2), str(ROOT / 'scripts')]

from grammar import Expr
from engine import Market
from evidence import read, extract, PUBLIC
import objective
import financial_factor_local as financial_local

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def daily_pit(frame, column, cal, stocks):
    """Causal daily point-in-time array, matching the local financial loader."""
    out = np.full((len(cal), len(stocks)), np.nan, dtype=np.float32)
    if column not in frame.columns:
        return out
    work = frame[['instrument', 'ann_date', 'end_date', column]].copy()
    work['ann_date'] = pd.to_datetime(work['ann_date'], errors='coerce')
    work['end_date'] = pd.to_datetime(work['end_date'], errors='coerce')
    work[column] = pd.to_numeric(work[column], errors='coerce')
    work = work.dropna(subset=['instrument', 'ann_date']).sort_values(
        ['instrument', 'ann_date', 'end_date']
    )
    cal_values = cal.to_numpy(dtype='datetime64[ns]')
    for instrument, group in work.groupby('instrument', sort=False):
        j = stocks.get_indexer([instrument])[0]
        if j < 0:
            continue
        # The latest row at a repeated announcement date wins, as in the
        # existing PIT financial reconstruction.
        group = group.drop_duplicates(['ann_date'], keep='last')
        anns = group['ann_date'].to_numpy(dtype='datetime64[ns]')
        vals = group[column].to_numpy(dtype=np.float32)
        pos = np.searchsorted(anns, cal_values, side='right') - 1
        ok = pos >= 0
        out[ok, j] = vals[pos[ok]]
    return out


def ratio(numerator, denominator):
    return np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan, dtype=np.float32),
        where=np.isfinite(denominator) & (denominator != 0) & np.isfinite(numerator),
    ).astype(np.float32)


def build_variants(market):
    cache_root = ROOT / 'quantlab/.quantlab/cache/research/cn_equity/financial_full_a'
    cache = financial_local.load_financial_cache(cache_root)
    cal, stocks = market.cal, market.stocks
    cap_yuan = market.fields['cap'].astype(np.float32) * np.float32(10000.0)
    close = market.fields['close'].astype(np.float32)

    income = cache['income_ttm']
    cashflow = cache['cashflow_ttm']
    fina = cache['fina_indicator']
    annual = fina[fina['end_type'].astype(str).eq('4')].copy()

    daily = {}
    for name, frame, column in [
        ('ep_parent_ttm', income, 'ttm_n_income_attr_p'),
        ('ep_net_ttm', income, 'ttm_n_income'),
        ('ep_total_profit_ttm', income, 'ttm_total_profit'),
        ('sp_total_revenue_ttm', income, 'ttm_total_revenue'),
        ('sp_revenue_ttm', income, 'ttm_revenue'),
        ('cfp_ocf_ttm_mv', cashflow, 'ttm_n_cashflow_act'),
        ('cfp_fcf_ttm_mv', cashflow, 'ttm_free_cashflow'),
    ]:
        daily[name] = ratio(daily_pit(frame, column, cal, stocks), cap_yuan)

    for name, frame, column in [
        ('cfp_cfps_cur_price', fina, 'cfps'),
        ('cfp_ocfps_cur_price', fina, 'ocfps'),
        ('cfp_cfps_lyr_price', annual, 'cfps'),
        ('cfp_ocfps_lyr_price', annual, 'ocfps'),
    ]:
        daily[name] = ratio(daily_pit(frame, column, cal, stocks), close)
    return daily


def evaluate_variant(name, fields, pool, target, source_name):
    market = Market(financial=False)
    market.fields = dict(fields)
    # The star pool only uses fields already present in the expression grammar.
    from engine import Interpreter
    market.engine = Interpreter(market.fields)
    market.cache_dir = HERE / 'financial_sensitivity_panels' / name
    market.cache_dir.mkdir(parents=True, exist_ok=True)
    evidence = extract(target, market)
    out = HERE / 'financial_sensitivity_eval' / name
    e = objective.Objective(market, evidence, out, pool)
    result = e.evaluate(pool, True)
    legs = [e.leg(expr, j)['z'] for j, expr in enumerate(pool)]
    z = np.asarray(legs)
    top20_path = []
    only = None
    for record in e.records:
        signal = pd.Timestamp(record['signal'])
        i = e.index[signal]
        active = e.active[:, i]
        composite = np.sum(z[active, i], axis=0) / max(int(active.sum()), 1)
        ids = np.flatnonzero(e.mask[i] & np.isfinite(composite))
        order = ids[np.argsort(composite[ids], kind='stable')]
        got = {str(e.stocks[j]) for j in order[-20:]}
        peer = {x['symbol'] for x in record['rows'][:20]}
        top20_path.append(len(got & peer))
        if signal == pd.Timestamp('20261008'):
            only = {
                'peer_only': sorted(peer - got),
                'local_only': sorted(got - peer),
            }
    checks = result.get('checks', [])
    overlaps = [x['overlap'] for x in checks]
    return {
        'name': name,
        'source_name': source_name,
        'score': result.get('score'),
        'ic_mae': result.get('ic_mae'),
        'rankic_mae': result.get('rankic_mae'),
        'top20_path': top20_path,
        'mean_top20': float(np.mean(top20_path)) if top20_path else None,
        'latest_top20': int(top20_path[-1]) if top20_path else None,
        'mean_holdings_overlap': float(np.mean(overlaps)) if overlaps else None,
        'min_holdings_overlap': float(np.min(overlaps)) if overlaps else None,
        'latest_holdings_overlap': float(overlaps[-1]) if overlaps else None,
        'top20_20261008': only,
        'checks': checks,
    }


def main():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    pool = tuple(Expr.from_json(x) for x in manifest['trees'])
    target = next(t for t in read(PUBLIC / 'targets.json') if t['rank'] == 8)
    base_market = Market()
    base_fields = dict(base_market.fields)
    financial = build_variants(base_market)

    variants = {
        'baseline': {},
        'ep_net_ttm': {'ep': 'ep_net_ttm'},
        'ep_total_profit_ttm': {'ep': 'ep_total_profit_ttm'},
        'cfp_cfps_cur_price': {'cfp': 'cfp_cfps_cur_price'},
        'cfp_ocfps_cur_price': {'cfp': 'cfp_ocfps_cur_price'},
        'cfp_cfps_lyr_price': {'cfp': 'cfp_cfps_lyr_price'},
        'cfp_ocfps_lyr_price': {'cfp': 'cfp_ocfps_lyr_price'},
        'cfp_fcf_ttm_mv': {'cfp': 'cfp_fcf_ttm_mv'},
        'sp_revenue_ttm': {'sp': 'sp_revenue_ttm'},
        'ep_net_cfp_cfps': {'ep': 'ep_net_ttm', 'cfp': 'cfp_cfps_cur_price'},
        'ep_net_cfp_ocfps': {'ep': 'ep_net_ttm', 'cfp': 'cfp_ocfps_cur_price'},
    }
    rows = []
    for name, swaps in variants.items():
        fields = dict(base_fields)
        for field, variant in swaps.items():
            fields[field] = financial[variant]
        rows.append(evaluate_variant(name, fields, pool, target, manifest.get('source_name')))
        print(json.dumps({k: rows[-1][k] for k in (
            'name', 'score', 'mean_top20', 'latest_top20',
            'mean_holdings_overlap', 'min_holdings_overlap',
            'latest_holdings_overlap')}, ensure_ascii=False), flush=True)

    rows.sort(key=lambda x: (x['mean_top20'], x['mean_holdings_overlap'], x['score']), reverse=True)
    report = {
        'purpose': 'offline EP/CFP/SP PIT proxy sensitivity; no platform submission',
        'pool_source': manifest.get('source_name'),
        'target': target,
        'variants': rows,
        'selection_rule': 'Prefer stable improvement across top20 and full-holdings paths; no weight changes.',
    }
    (HERE / 'star_coin_financial_sensitivity.json').write_text(
        json.dumps(clean(report), ensure_ascii=False, indent=2) + '\n'
    )


if __name__ == '__main__':
    main()
