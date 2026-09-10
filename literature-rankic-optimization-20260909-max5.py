# MAX(5): average of the five highest daily returns in the trailing 21 sessions.

import numpy as np


class Max5LowFactor(Factor):
    def calculate(self, factors):
        close = factors["close"]
        returns = close / DELAY(close, 1) - 1

        def top5_mean(window):
            valid = window[~np.isnan(window)]
            if len(valid) < 5:
                return np.nan
            top = np.partition(valid, -5)[-5:]
            return top.mean()

        max5 = returns.groupby(level=0, group_keys=False).apply(
            lambda series: series.rolling(21, min_periods=21).apply(top5_mean, raw=True)
        )
        return RANK(-max5).rename("value")
