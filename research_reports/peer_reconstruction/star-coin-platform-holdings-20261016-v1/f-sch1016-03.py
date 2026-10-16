"""Frozen star_coin v2 AST, equal ten seats (including duplicate cap seats). Causal [date,symbol] Python port.
ST-name mask unavailable in platform fields: numeric tradability only (proxy).
No future labels, fitted predictors, or full-sample time normalization.
"""
import numpy as np

TREES = [{'op': 'neg', 'args': [{'op': 'add', 'args': [{'op': 'rank', 'args': [{'op': 'neg', 'args': [{'op': 'field', 'value': 'cap'}]}]}, {'op': 'mean2', 'args': [{'op': 'rank', 'args': [{'op': 'neg', 'args': [{'op': 'field', 'value': 'close'}]}]}, {'op': 'field', 'value': 'cfp'}]}]}]}, {'op': 'rank', 'args': [{'op': 'ts_std', 'args': [{'op': 'sub', 'args': [{'op': 'div', 'args': [{'op': 'field', 'value': 'close'}, {'op': 'delay', 'args': [{'op': 'field', 'value': 'close'}], 'value': 1}]}, {'op': 'const', 'value': 1.0}]}], 'value': 20}]}, {'op': 'ema', 'args': [{'op': 'zscore', 'args': [{'op': 'neg', 'args': [{'op': 'add', 'args': [{'op': 'rank', 'args': [{'op': 'neg', 'args': [{'op': 'sma', 'args': [{'op': 'field', 'value': 'volume'}], 'value': 1}]}]}, {'op': 'rank', 'args': [{'op': 'neg', 'args': [{'op': 'field', 'value': 'low'}]}]}]}]}]}], 'value': 3}, {'op': 'ts_mean', 'args': [{'op': 'field', 'value': 'turnover'}], 'value': 20}, {'op': 'add', 'args': [{'op': 'mul', 'args': [{'op': 'const', 'value': 0.975}, {'op': 'zscore', 'args': [{'op': 'field', 'value': 'bm'}]}]}, {'op': 'mul', 'args': [{'op': 'const', 'value': 0.025}, {'op': 'zscore', 'args': [{'op': 'rank', 'args': [{'op': 'field', 'value': 'bm'}]}]}]}]}, {'op': 'field', 'value': 'cap'}, {'op': 'field', 'value': 'cap'}, {'op': 'div', 'args': [{'op': 'field', 'value': 'close'}, {'op': 'ts_mean', 'args': [{'op': 'field', 'value': 'open'}], 'value': 10}]}, {'op': 'ts_mean', 'args': [{'op': 'sub', 'args': [{'op': 'field', 'value': 'cap'}, {'op': 'rank', 'args': [{'op': 'sub', 'args': [{'op': 'rank', 'args': [{'op': 'neg', 'args': [{'op': 'neg', 'args': [{'op': 'ts_mean', 'args': [{'op': 'ts_mean', 'args': [{'op': 'field', 'value': 'ep'}], 'value': 1}], 'value': 20}]}]}]}, {'op': 'neg', 'args': [{'op': 'ts_mean', 'args': [{'op': 'ts_mean', 'args': [{'op': 'div', 'args': [{'op': 'const', 'value': 2.0}, {'op': 'ts_kurt', 'args': [{'op': 'field', 'value': 'sp'}], 'value': 18}]}], 'value': 1}], 'value': 18}]}]}]}]}], 'value': 20}, {'op': 'field', 'value': 'ep'}]
DIRECTIONS = [-1.0, -1.0, -1.0, -1.0, 1.0, -1.0, -1.0, -1.0, -1.0, 1.0]
WEIGHTS = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0]



def _cast(value):
    value = np.asarray(value, dtype=np.float32)
    return np.where(np.isfinite(value), value, np.nan).astype(np.float32)


def _normalize(value, mask):
    value = np.where(mask & np.isfinite(value), value, np.nan).astype(float)
    lo, hi = np.nanquantile(value, [0.01, 0.99], axis=1)
    value = np.clip(value, lo[:, None], hi[:, None])
    mean = np.nanmean(value, axis=1, keepdims=True)
    std = np.nanstd(value, axis=1, keepdims=True)
    return np.divide(value-mean, std, out=np.full_like(value, np.nan), where=std>0)


def _evaluate(node, fields, template, mask):
    op = node['op']
    if op == 'field':
        return fields[node['value']]
    if op == 'const':
        return np.broadcast_to(float(node['value']), template.shape)
    args = [_evaluate(child, fields, template, mask) for child in node['args']]
    a = args[0]
    if op == 'neg':
        result = -a
    elif op == 'logabs':
        result = np.log(np.maximum(np.abs(a), 1e-12))
    elif op == 'sqrtabs':
        result = np.sqrt(np.abs(a))
    elif op == 'rank':
        frame = template.copy()
        frame.iloc[:, :] = np.where(mask & np.isfinite(a), a, np.nan)
        result = frame.rank(axis=1, method='average', pct=True).to_numpy()
    elif op == 'zscore':
        result = _normalize(a, mask)
    elif op == 'add':
        result = a + args[1]
    elif op == 'sub':
        result = a - args[1]
    elif op == 'mul':
        result = a * args[1]
    elif op == 'mean2':
        result = (a + args[1]) / 2
    elif op == 'max2':
        result = np.maximum(a, args[1])
    elif op == 'div':
        result = np.divide(a, args[1], out=np.full(template.shape, np.nan), where=args[1]!=0)
    elif op == 'delay':
        result = np.full(template.shape, np.nan)
        n = node['value']
        result[n:] = a[:-n]
    elif op in ('sma', 'ema', 'ts_std', 'ts_mean', 'ts_kurt'):
        frame = template.copy()
        frame.iloc[:, :] = a.astype(float)
        n = node['value']
        if op == 'sma':
            result = frame.ewm(alpha=1.0/n, adjust=False, min_periods=n).mean().to_numpy()
        elif op == 'ema':
            result = frame.ewm(alpha=2.0/(n+1), adjust=False, min_periods=n).mean().to_numpy()
        elif op == 'ts_kurt':
            result = frame.rolling(n, min_periods=n).kurt().to_numpy()
        elif op == 'ts_std':
            result = frame.rolling(n, min_periods=n).std(ddof=1).to_numpy()
        else:
            result = frame.rolling(n, min_periods=n).mean().to_numpy()
    else:
        raise ValueError(op)
    return _cast(result)


class StarCoinX01Weight2Factor(Factor):
    def calculate(self, factors):
        close = factors['close']
        template = close.unstack(1).sort_index().astype(float)
        fields = {
            'close': template.to_numpy(dtype=np.float32),
            'low': factors['low'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'volume': factors['volume'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'ep': factors['ratio_ep_ttm'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'cfp': factors['ratio_cfp_ttm'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'sp': factors['ratio_sp_ttm'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'open': factors['open'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'amount': factors['amount'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'turnover': factors['turnover'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'cap': factors['market_cap'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
            'bm': factors['book_to_market_ratio_lf'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32),
        }
        volume = factors['volume'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32)
        high = factors['high'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32)
        low = factors['low'].unstack(1).reindex_like(template).to_numpy(dtype=np.float32)
        mask = np.isfinite(fields['cap']) & (fields['cap']>0)
        eligible = mask & np.isfinite(fields['turnover'])
        eligible &= ~(volume<=0) & ~(fields['amount']<=0)
        eligible &= ~np.isclose(high, low, rtol=1e-8, atol=1e-8)
        composite = np.zeros(template.shape, dtype=np.float32)
        for tree, direction, weight in zip(TREES, DIRECTIONS, WEIGHTS):
            native = _evaluate(tree, fields, template, mask)
            normalized = _normalize(native.astype(float), eligible).astype(np.float32)
            composite += np.float32(direction) * np.float32(weight) * normalized
        template.iloc[:, :] = composite / np.float32(len(TREES))
        return template.stack(dropna=False).reindex(close.index).rename("value")
