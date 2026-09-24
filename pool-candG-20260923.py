import numpy as np


class CandGPoolFactor(Factor):
    """Exhaustive-search local winner:

    SIZE + H03 + T10-ADD-AGG-IMPACT + T10-ADD-DOWNSIDE-IMPACT + F-I10-01.
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
        signals = [-RANK(factors['market_cap']), impact, t10_agg, t10_down, f_i10]

        def normalize(series):
            series = series.replace([np.inf, -np.inf], np.nan)
            clipped = series.clip(lower=series.quantile(0.01), upper=series.quantile(0.99))
            std = clipped.std(ddof=0)
            if not np.isfinite(std) or std <= 1e-12:
                return clipped * 0.0
            return (clipped - clipped.mean()) / std

        normalized = [s.groupby(level=0).transform(normalize) for s in signals]
        return sum(normalized) / len(normalized)
