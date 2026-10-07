"""PROBE 2026-10-01: literal field delivery + the ML factor pane skeleton.

Approved 2026-10-01 (~2-4 credits).  Purpose: before re-running the 1.2 MB
ML-GBDT-WF factor after the literal-field-access fix, verify on the platform
that
  (a) literal ``factors["..."]`` subscripts deliver volume / amount /
      turnover / market_cap / high / low as real (non-NaN) series, and
  (b) the ``unstack(level=1) -> rolling/rank -> stack().reindex(close.index)``
      skeleton returns a Series the analysis node can group.

Value = equal-weight rank blend of five features that together touch every
field the ML factor needs (close, volume, amount, turnover, market_cap, high,
low).  If (a) or (b) is broken the factor comes back all-NaN and the analysis
node fails with ?????????? 0 ?????.
"""
import numpy as np


class Ml5EqProbe(Factor):
    def calculate(self, factors):
        close = factors["close"]
        volume = factors["volume"]
        amount = factors["amount"]
        turnover = factors["turnover"]
        market_cap = factors["market_cap"]
        high = factors["high"]
        low = factors["low"]
        idx = close.index

        def wide(series):
            # platform python pane is fixed [date, symbol]: level 1 = symbol
            return series.unstack(level=1)

        close_w = wide(close)
        volume_w = wide(volume)
        amount_w = wide(amount)
        turnover_w = wide(turnover)
        cap_w = wide(market_cap)
        high_w = wide(high)
        low_w = wide(low)

        ret1 = close_w / close_w.shift(1) - 1.0
        raw = {
            "vv6_500": -(volume_w.rolling(6).std() / volume_w.rolling(500, min_periods=250).std()),
            "turn_stab": -(turnover_w.rolling(10).std() / turnover_w.rolling(750, min_periods=240).std()),
            "size": np.log(cap_w),
            "hl20": ((high_w - low_w) / close_w).rolling(20).mean(),
            "amihud20": (ret1.abs() / amount_w * 1e8).rolling(20).mean(),
        }
        feats = {k: v.rank(axis=1, pct=True) for k, v in raw.items()}
        blend = sum(feats.values()) / float(len(feats))

        out_w = close_w.astype("float64") * np.nan
        out_w.iloc[:, :] = blend.to_numpy(dtype="float64").reshape(close_w.shape)
        return out_w.stack().reindex(idx).rename("value")
