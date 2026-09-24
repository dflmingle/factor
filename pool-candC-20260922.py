import numpy as np


class CandCPoolFactor(Factor):
    """Pool proxy C: SIZE + H03 + T10-ADD-BM + BM_SIZE + BM_ILLIQ."""

    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        turnover = factors['turnover']
        impact = RANK(SUM((factors['high'] - factors['low']) / (DELAY(close, 1) + 0.000001), 60) / (SUM(factors['amount'], 60) + 1))
        t10_bm = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (factors['open'] + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(factors['market_cap'])))
            + impact
            + RANK(factors['book_to_market_ratio_lf'])
        ) / 6
        signals = [
            -RANK(factors['market_cap']),
            impact,
            t10_bm,
            RANK(factors['book_to_market_ratio_lf']) - RANK(factors['market_cap']),
            RANK(factors['book_to_market_ratio_lf'])
            + RANK(SUM(ABS(close / DELAY(close, 1) - 1) / (factors['amount'] + 1), 60) / 60),
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
