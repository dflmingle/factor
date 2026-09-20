import numpy as np


class QTLD60PythonFactor(Factor):
    """Trailing 20th-percentile close divided by the current close."""

    def calculate(self, factors):
        close = factors["close"]
        quantile = close.groupby(level=0, group_keys=False).apply(
            lambda series: series.rolling(60, min_periods=60).quantile(0.2)
        )
        value = quantile / close
        value = value.replace([np.inf, -np.inf], np.nan)
        return value.rename("value")
