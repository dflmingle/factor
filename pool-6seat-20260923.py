import numpy as np


class Pool6SeatFactor(Factor):
    """G03 的 5 席 + BM_SIZE（VERIFY10-E）：补上价值轴、压低换手.

    Seats (equal weight after per-seat cross-sectional z-score):
      1. -RANK(market_cap)                                 (SIZE)
      2. impact60                                          (H03)
      3. (t10_base + agg) / 6                              (T10-ADD-AGG-IMPACT)
      4. (t10_base + downside) / 6                         (T10-ADD-DOWNSIDE-IMPACT)
      5. (-RANK(market_cap) + impact60) / 2                (F-I10-01)
      6. RANK(BM_lf) - RANK(market_cap)                    (BM_SIZE / VERIFY10-E)
    """

    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        turnover = factors['turnover']
        ret1 = close / DELAY(close, 1) - 1
        impact = RANK(SUM((factors['high'] - factors['low']) / (DELAY(close, 1) + 0.000001), 60) / (SUM(factors['amount'], 60) + 1))
        t10_base = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (factors['open'] + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(factors['market_cap'])))
            + impact
        )
        agg = RANK(SUM(ABS(ret1), 60) / (SUM(factors['amount'], 60) + 1))
        downside = RANK(SUM((ABS(ret1) - ret1) / 2, 60) / (SUM(factors['amount'], 60) + 1))
        t10_agg = (t10_base + agg) / 6
        t10_down = (t10_base + downside) / 6
        f_i10 = (-RANK(factors['market_cap']) + impact) / 2
        bm_size = RANK(factors['book_to_market_ratio_lf']) - RANK(factors['market_cap'])
        signals = [
            -RANK(factors['market_cap']),
            impact,
            t10_agg,
            t10_down,
            f_i10,
            bm_size,
        ]

        def normalize(series):
            series = series.replace([np.inf, -np.inf], np.nan)
            clipped = series.clip(lower=series.quantile(0.01), upper=series.quantile(0.99))
            std = clipped.std(ddof=0)
            if not np.isfinite(std) or std <= 1e-12:
                return clipped * 0.0
            return (clipped - clipped.mean()) / std

        normalized = [s.groupby(level=0).transform(normalize) for s in signals]
        return sum(normalized) / len(normalized)
