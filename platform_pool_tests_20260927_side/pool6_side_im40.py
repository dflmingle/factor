import numpy as np


class Pool6SideIm40Factor(Factor):
    """Incumbent 5 seats + SIDE-IM40 (6th-seat test, 2026-09-27 side run).

    Pool = equal-weight average of per-seat cross-sectional z-scores
    (1%/99% winsorized), same convention as pool6_bm4fscore_e_v2.

    Seats:
      1. -RANK(market_cap)                        (SIZE-ONLY-20260911)
      2. impact60                                 (H03-T10-SINGLE)
      3. RANK(bm_lf) - RANK(market_cap)           (VERIFY10-E260910-04)
      4. RANK(bm_lf) + RANK(SUM(ABS(ret1)/(amount+1),60)/60)
                                                  (VERIFY10-F260910-12)
      5. (t10_base + RANK(bm_lf)) / 6             (T10-ADD-BM-20260911)
      6. -MA((close - open) / open, 40)
                                                  (SIDE-IM40-20260927)
    """

    def calculate(self, factors):
        close = factors['close']
        open_ = factors['open']
        high = factors['high']
        low = factors['low']
        volume = factors['volume']
        amount = factors['amount']
        turnover = factors['turnover']
        market_cap = factors['market_cap']
        ret1 = close / DELAY(close, 1) - 1
        rank_cap = RANK(market_cap)
        impact60 = RANK(
            SUM((high - low) / (DELAY(close, 1) + 0.000001), 60)
            / (SUM(amount, 60) + 1)
        )
        bm = RANK(factors['book_to_market_ratio_lf'])
        t10 = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(rank_cap))
            + impact60
        )
        seats = [
            -rank_cap,
            impact60,
            bm - rank_cap,
            bm + RANK(SUM(ABS(ret1) / (amount + 1), 60) / 60),
            (t10 + bm) / 6,
            -MA((close - open_) / open_, 40),
        ]

        def normalize(series):
            series = series.replace([np.inf, -np.inf], np.nan)
            clipped = series.clip(lower=series.quantile(0.01), upper=series.quantile(0.99))
            std = clipped.std(ddof=0)
            if not np.isfinite(std) or std <= 1e-12:
                return clipped * 0.0
            return (clipped - clipped.mean()) / std

        normalized = [signal.groupby(level=0).transform(normalize) for signal in seats]
        return sum(normalized) / len(normalized)