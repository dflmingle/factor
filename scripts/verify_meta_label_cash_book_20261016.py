"""Independent dollar/share replay of the nine audited walk-forward paths.

Does not import the ledger implementation. Solves actual post-fee capital via
the active buy/sell sets, then values stock quantities day by day. Reads only
saved holdings and market prices, comparing with persisted daily returns.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/literature/advances-fml-meta-label-20261016-ledger-v2'
MARKET = ROOT/'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl'


def verify():
    calendar, stocks, fields = pd.read_pickle(MARKET)
    close = fields['close']; del fields
    records = []
    for file in sorted(OUT.glob('*.holdings.csv.gz')):
        prefix = file.name.removesuffix('.holdings.csv.gz')
        holds = pd.read_csv(file)
        periods = pd.read_csv(OUT/f'{prefix}.periods.csv', parse_dates=['entry_date','exit_date'])
        saved = pd.read_csv(OUT/f'{prefix}.daily.csv',index_col='date',parse_dates=True)
        entries = {}
        for row in periods.itertuples():
            group = holds[holds['index']==row.index]
            entries[row.entry_date] = stocks.get_indexer(group.stock)
        used = np.unique(np.concatenate(list(entries.values())))
        prices = close[:,used].astype(float)
        if any(np.any(ids < 0) for ids in entries.values()):
            raise AssertionError('unmapped symbol')
        entries = {date:np.searchsorted(used,ids) for date,ids in entries.items()}
        quantity = np.zeros(len(used)); cash = 1.; navs = []; fees = []
        for date in saved.index:
            price = prices[calendar.get_loc(date)]
            active = quantity != 0
            old_value = np.zeros(len(used)); old_value[active] = quantity[active]*price[active]
            wealth = cash+old_value.sum()
            if date in entries:
                ids = entries[date]
                weight = np.zeros(len(used)); weight[ids]=1/len(ids)
                # Piecewise linear solution in dollars, independent of the
                # bisection/weight solver in meta_label_ledger.trade().
                invested = wealth
                for _ in range(30):
                    sign = np.sign(invested*weight-old_value)
                    solved = (wealth+.003*np.dot(sign,old_value))/(1+.003*np.dot(sign,weight))
                    if abs(solved-invested) < 1e-13:
                        invested = solved
                        break
                    invested = solved
                bought = np.maximum(invested*weight-old_value,0).sum()
                sold = np.maximum(old_value-invested*weight,0).sum()
                fee = .003*(bought+sold)
                assert abs(wealth-invested-fee) < 1e-10
                quantity[:] = 0
                quantity[ids] = invested/len(ids)/price[ids]
                cash = cash+sold-bought-fee
                assert abs(cash) < 1e-10
                wealth = invested+cash
                fees.append(fee/(wealth+fee))
            navs.append(wealth)
        expected = np.cumprod(1+saved.portfolio.to_numpy())
        np.testing.assert_allclose(navs, expected,atol=1e-10,rtol=1e-10)
        np.testing.assert_allclose(fees,periods.fee,atol=1e-12,rtol=1e-10)
        records.append(dict(path=prefix,days=len(saved),
                            max_absolute_nav_difference=float(np.max(np.abs(navs-expected))),
                            nav='PASS',fees='PASS',cash_conservation='PASS'))
    if len(records) != 9:
        raise AssertionError(f'expected 9 paths, got {len(records)}')
    (OUT/'independent_cash_share_verification.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records,indent=2))


if __name__ == '__main__':
    verify()
