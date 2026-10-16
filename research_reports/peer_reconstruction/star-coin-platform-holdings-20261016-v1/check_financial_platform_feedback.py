"""Compare saved platform Top20 with cached local sensitivity panels.

Use numeric eligibility, exactly as the submitted Python candidate did.
No Market constructor, network calls or shared-cache writes are required.
"""
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1'))
from grammar import Expr
from engine import standardize


def main():
    cal, stocks, fields = pickle.load((ROOT/'research_reports/platform_alignment/bc-peer-pools-20261012/market_extended.pkl').open('rb'))
    cal, stocks = pd.DatetimeIndex(cal), pd.Index(stocks)
    signal = pd.Timestamp('20261008')
    pos = cal.get_loc(signal)
    recent_pos = cal[cal >= pd.Timestamp('20260801')].get_loc(signal)
    mask = np.isfinite(fields['cap'][pos]) & (fields['cap'][pos] > 0) & np.isfinite(fields['turnover'][pos])
    mask &= ~((fields['volume'][pos] <= 0) | (fields['amount'][pos] <= 0) |
              np.isclose(fields['high'][pos], fields['low'][pos], rtol=1e-8, atol=1e-8))
    manifest = json.loads((HERE/'manifest.json').read_text())
    platform = json.loads((HERE/'platform_vs_peer.json').read_text())['platform_top20']
    platform_ids = {x['symbol'] for x in platform}
    target = json.loads((ROOT/'research_reports/peer_reconstruction/top50-20261013/public/holdings/18067f13fb2f894e0a45b181/20261009.json').read_text())['rows']
    peer20 = {x['symbol'] for x in target[:20]}
    study = json.loads((HERE/'star_coin_financial_sensitivity.json').read_text())
    rows = []
    for variant in study['variants']:
        name = variant['name']
        legs = []
        for tree, direction in zip(manifest['trees'], [-1,-1,-1,-1,1,-1,-1,-1,-1,1]):
            expr = Expr.from_json(tree)
            key = hashlib.sha256(expr.key().encode()).hexdigest()
            panel = np.load(HERE/'financial_sensitivity_panels'/name/(key+'.npy'), mmap_mode='r')
            legs.append(standardize(panel[recent_pos:recent_pos+1], mask[None,:])[0]*direction)
        comp = np.asarray(legs).sum(axis=0)/10
        ids = np.flatnonzero(mask & np.isfinite(comp))
        order = ids[np.argsort(comp[ids], kind='stable')][::-1]
        got = list(map(str, stocks[order[:20]]))
        ranks = {str(stocks[j]): k+1 for k,j in enumerate(order)}
        observations = [dict(symbol=x['symbol'], platform_rank=x['platform_rank'],
                             local_rank=ranks.get(x['symbol'])) for x in platform]
        rows.append(dict(name=name, platform_top20_overlap=len(set(got)&platform_ids),
                         peer_top20_overlap=len(set(got)&peer20), top20=got,
                         platform_stock_ranks=observations))
    report = dict(signal_date='20261008', mask='numeric eligibility as submitted Python candidate',
                  scope='saved single-date platform Top20 only; no platform leg-level data', rows=rows)
    (HERE/'financial_platform_feedback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ('name','platform_top20_overlap','peer_top20_overlap')} for r in rows],ensure_ascii=False))


if __name__ == '__main__':
    main()
