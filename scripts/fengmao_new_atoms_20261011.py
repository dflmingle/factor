"""Causal daily recipes for the next grouped-signal diagnostic round.

Uses actual qfq open/close, volume and daily_basic turnover, never amount proxies.
"""
import gc
import numpy as np
import pandas as pd
import fengmao_multiround_20261011 as old

NEW_NAMES = [f'{stem}{n}' for n in (20, 60) for stem in
             ('idrev', 'onrev', 'tug', 'idvol', 'onvol', 'downrisk',
              'asym', 'downshare', 'rvcor', 'gapcor', 'signedflow')]
NEW_NAMES += ['macd', 'macdhist', 'macdslow', 'macdslowhist', 'rvbreak', 'gapbreak']


def build_new_atoms(fields, positions, ranked=True):
    shape = len(positions), fields['close'].shape[1]
    result = {k: np.full(shape, np.nan, np.float32) for k in NEW_NAMES}
    for begin in range(0, shape[1], 192):
        old.base.memory_guard()
        sl = slice(begin, begin+192)
        c, o, v, t = [pd.DataFrame(fields[k][:, sl], dtype=float)
                      for k in ('close', 'open', 'volume', 'turnover')]
        r, intraday, overnight = c/c.shift(1)-1, c/o-1, o/c.shift(1)-1
        # No zero-fill of missing daily returns before strict rolling windows.
        down = r.clip(upper=0)**2
        up = r.clip(lower=0)**2
        lv = np.log(v).diff()
        values = {}
        cors, gaps = {}, {}
        for n in (20, 60):
            mean = lambda a: a.rolling(n, min_periods=n).mean()
            sd = lambda a: a.rolling(n, min_periods=n).std()
            cors[n] = r.rolling(n, min_periods=n).corr(t)
            gaps[n] = intraday.rolling(n, min_periods=n).corr(overnight)
            values.update({f'idrev{n}': -mean(intraday), f'onrev{n}': -mean(overnight),
                f'tug{n}': mean(overnight-intraday), f'idvol{n}': sd(intraday),
                f'onvol{n}': sd(overnight), f'downrisk{n}': np.sqrt(mean(down)),
                f'asym{n}': (mean(down)-mean(up))/(mean(down)+mean(up)),
                f'downshare{n}': mean(v.where(r<0, 0).where(r.notna()))/mean(v),
                f'rvcor{n}': cors[n], f'gapcor{n}': gaps[n],
                f'signedflow{n}': -mean(r*lv)})
        for fast, slow, tag in ((12,26,'macd'),(24,52,'macdslow')):
            ef = c.ewm(span=fast, adjust=False, min_periods=fast).mean()
            es = c.ewm(span=slow, adjust=False, min_periods=slow).mean()
            dif = (ef-es)/c
            dea = dif.ewm(span=9, adjust=False, min_periods=9).mean()
            values[tag], values[tag+'hist'] = dif, dif-dea
        values.update(rvbreak=cors[60]-cors[20], gapbreak=gaps[60]-gaps[20])
        for k, a in values.items():
            result[k][:,sl] = a.iloc[positions].to_numpy(np.float32)
        del c,o,v,t,r,intraday,overnight,values,cors,gaps,down,up,lv
        gc.collect()
    active = np.isfinite(fields['cap'][positions])
    for k in result:
        result[k][~active | ~np.isfinite(result[k])] = np.nan
        if ranked:
            result[k] = old.rank(result[k])
    return result


def load_open(calendar, stocks, fields, filters=None):
    fields['open'] = np.full_like(fields['close'], np.nan)
    for path in sorted((old.base.CACHE/'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet')):
        old.base.memory_guard()
        f = pd.read_parquet(path, columns=['date','instrument','open'], filters=filters)
        di,si = calendar.get_indexer(pd.to_datetime(f.date).dt.normalize()), stocks.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)
        previous,new = fields['open'][di[ok],si[ok]], f.open.to_numpy(np.float32)[ok]
        assert not np.any(np.isfinite(previous)&(previous!=new)), path
        fields['open'][di[ok],si[ok]] = new
    fields['open'][~np.isfinite(fields['cap']) | (fields['open']<=0)] = np.nan
    # Actual opens are deliberately not forward-filled through suspensions.
    return fields
