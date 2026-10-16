class QuantStyleCandidate(Factor):
    def calculate(self, factors):
        # Fixed platform index [date, symbol]. No whole-sample normalization.
        source = factors['close']
        close = source.unstack(level=1).sort_index()
        cap = factors['market_cap'].unstack(level=1).reindex_like(close)
        bm = factors['book_to_market_ratio_lf'].unstack(level=1).reindex_like(close)
        # These two fields preserve the earlier FF3/FF5 common-support gate.
        # Platform ROE semantics differ from Tushare reported ROE: field proxy.
        roe = factors['oper_roe_ttm'].unstack(level=1).reindex_like(close)
        assets = factors['total_assets'].unstack(level=1).reindex_like(close)
        prices = close.to_numpy(dtype=float)
        caps = cap.to_numpy(dtype=float)
        books = bm.to_numpy(dtype=float)
        profits = roe.to_numpy(dtype=float)
        totals = assets.to_numpy(dtype=float)
        ret = np.full_like(prices, np.nan)
        np.divide(prices[1:], prices[:-1], out=ret[1:], where=prices[:-1] > 0)
        ret[1:] -= 1.0
        values = np.full_like(prices, np.nan)
        window = 120
        for t in range(window, len(prices)):
            start = t - window
            previous = max(0, start - 252)
            y = ret[start + 1:t + 1]
            good = (caps[start] > 0) & np.isfinite(caps[start])
            good &= np.isfinite(y).all(axis=0)
            good &= np.isfinite(books[start]) & np.isfinite(profits[start])
            good &= (totals[start] > 0) & (totals[previous] > 0)
            good &= np.isfinite(totals[start]) & np.isfinite(totals[previous])
            ids = np.flatnonzero(good)
            if len(ids) < 100:
                continue
            weights = caps[start, ids]
            returns = y[:, ids]
            third = len(ids) // 3
            def spread(scores):
                order = np.argsort(scores, kind='stable')
                low, high = order[:third], order[-third:]
                lo = np.sum(returns[:, low] * (weights[low] / weights[low].sum()), axis=1)
                hi = np.sum(returns[:, high] * (weights[high] / weights[high].sum()), axis=1)
                return hi - lo
            market = np.sum(returns * (weights / weights.sum()), axis=1)
            smb = -spread(weights)
            hml = spread(books[start, ids])
            x = np.column_stack((market, smb, hml))
            x -= x.mean(axis=0)
            centered = returns - returns.mean(axis=0)
            cross = np.einsum('ti,tj->ij', x, centered)
            gram = np.einsum('ti,tj->ij', x, x)
            total_var = np.mean(centered * centered, axis=0)
            capm_var = total_var - cross[0] ** 2 / (window * gram[0, 0]) if gram[0, 0] > 0 else total_var
            coef = np.linalg.pinv(gram, rcond=1e-15) @ cross
            ff3_var = total_var - np.sum(cross * coef, axis=0) / window
            capm_var = np.maximum(capm_var, 0.0)
            ff3_var = np.maximum(ff3_var, 0.0)
            explained = np.full(len(ids), np.nan)
            np.divide(ff3_var, capm_var, out=explained, where=capm_var > 1e-12 / 252)
            explained = 1.0 - explained
            low = -np.sqrt(ff3_var) * np.sqrt(252.0)
            values[t, ids] = explained
        result = close.copy()
        result.iloc[:, :] = values
        result = result.where(cap > 0)
        return result.stack(dropna=False).reindex(source.index).rename('value')
