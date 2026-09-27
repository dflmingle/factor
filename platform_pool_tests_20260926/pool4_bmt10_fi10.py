import numpy as np


class Pool4BmT10Fi10Factor(Factor):
    """Incumbent minus VERIFY10-E and VERIFY10-F plus F-I10-01 (4-seat, 2026-09-27).

    Pool = equal-weight average of per-seat cross-sectional z-scores
    (1%/99% winsorized), same convention as pool5_swapf_fi10 / pool5_partial_t10.

    Seats:
      1. -RANK(market_cap)                      (SIZE-ONLY-20260911)
      2. impact60                               (H03-T10-SINGLE)
      3. (t10_base + RANK(bm_lf)) / 6           (T10-ADD-BM-20260911)
      4. (-RANK(market_cap) + impact60) / 2     (F-I10-01)
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
        impact60 = RANK(
            SUM((high - low) / (DELAY(close, 1) + 0.000001), 60)
            / (SUM(amount, 60) + 1)
        )
        bm = RANK(factors['book_to_market_ratio_lf'])
        t10 = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(market_cap)))
            + impact60
        )
        signals = [
            -RANK(market_cap),
            impact60,
            (t10 + bm) / 6,
            (-RANK(market_cap) + impact60) / 2,
        ]

        def normalize(series):
            series = series.replace([np.inf, -np.inf], np.nan)
            clipped = series.clip(lower=series.quantile(0.01), upper=series.quantile(0.99))
            std = clipped.std(ddof=0)
            if not np.isfinite(std) or std <= 1e-12:
                return clipped * 0.0
            return (clipped - clipped.mean()) / std

        normalized = [signal.groupby(level=0).transform(normalize) for signal in signals]
        return sum(normalized) / len(normalized)
