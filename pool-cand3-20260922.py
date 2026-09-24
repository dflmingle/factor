import numpy as np


class CandThreePoolFactor(Factor):
    """Pool proxy: SIZE + H03 + CHIP250 + ASSET_GROWTH + BM_SIZE + F-B06.

    The F-B06 member is ``WMA(((1/LOW)/LOW)/VOLUME, 40)``.  The platform does
    not document WMA's weight scheme, so the local linearly weighted
    reconstruction (newest observation heaviest) is used here.
    """

    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        low = factors['low']
        weighted_input = 1.0 / low / low / volume
        # Linear weighted moving average expanded with DELAY only: no pandas and
        # no dependency on whether the Python runtime exposes the WMA operator.
        total = weighted_input * 0.0
        weight_sum = 0.0
        for lag in range(40):
            weight = float(40 - lag)
            shifted = weighted_input if lag == 0 else DELAY(weighted_input, lag)
            total = total + shifted * weight
            weight_sum += weight
        wma_series = total / weight_sum
        signals = [
            -RANK(factors['market_cap']),
            RANK(SUM((factors['high'] - factors['low']) / (DELAY(close, 1) + 0.000001), 60) / (SUM(factors['amount'], 60) + 1)),
            RANK((SUM(volume * (factors['open'] + close) / 2, 250) / SUM(volume, 250)) / close - 1),
            -RANK(factors['gr_total_asset_lyr']),
            RANK(factors['book_to_market_ratio_lf']) - RANK(factors['market_cap']),
            wma_series,
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
