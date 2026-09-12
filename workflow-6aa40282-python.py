class CombinedFactor(Factor):
    def calculate(self, factors):
        volume = factors['volume']
        large_order_volume = TS_MAX(volume,20)
        large_order_ratio = large_order_volume / volume
        buy_signal = (large_order_ratio > 0.01).astype(int)
        sell_signal = (large_order_ratio < 0).astype(int) * -1

        close = factors['close']
        obv = (volume * ((close - close.shift(1)) / close.shift(1))).cumsum()
        obv_90_high = obv.rolling(window=90).max()
        obv_30_ma = obv.rolling(window=30).mean()
        obv_signal = ((obv == obv_90_high) & (obv > obv_30_ma)).astype(int)

        return buy_signal + sell_signal + obv_signal
