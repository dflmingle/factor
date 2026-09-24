import numpy as np


class CandBPoolFactor(Factor):
    """Pool proxy B: SIZE + H03 + ASSET_GROWTH + BM_ILLIQ + ILLIQ."""

    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        illiq = RANK(SUM(ABS(close / DELAY(close, 1) - 1) / (factors['amount'] + 1), 60) / 60)
        signals = [
            -RANK(factors['market_cap']),
            RANK(SUM((factors['high'] - factors['low']) / (DELAY(close, 1) + 0.000001), 60) / (SUM(factors['amount'], 60) + 1)),
            -RANK(factors['gr_total_asset_lyr']),
            RANK(factors['book_to_market_ratio_lf']) + illiq,
            illiq,
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
