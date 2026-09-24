import numpy as np


class AlternativePoolTURNFactor(Factor):
    """Five saved signals, oriented, daily winsorized and standardized equally."""
    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        signals = [
            -RANK(factors['market_cap']),
            RANK(SUM((factors['high']-factors['low'])/(DELAY(close,1)+0.000001),60)/(SUM(factors['amount'],60)+1)),
            1-MA(factors['turnover'],21)/MA(factors['turnover'],504),
            RANK((SUM(volume*(factors['open']+close)/2,250)/SUM(volume,250))/close-1),
            -RANK(factors['gr_total_asset_lyr']),
        ]
        # Saved Python-runtime evidence establishes [date, symbol] ordering.
        def normalize(series):
            series = series.replace([np.inf, -np.inf], np.nan)
            clipped = series.clip(lower=series.quantile(0.01), upper=series.quantile(0.99))
            std = clipped.std(ddof=0)
            if not np.isfinite(std) or std <= 1e-12:
                return clipped * 0.0
            return (clipped-clipped.mean())/std
        normalized = [s.groupby(level=0).transform(normalize) for s in signals]
        return ((normalized[0]+normalized[1]+normalized[2]+normalized[3]+normalized[4])/5).rename('value')
