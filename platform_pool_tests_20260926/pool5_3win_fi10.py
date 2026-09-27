import numpy as np


class Pool5ThreeWinFi10Factor(Factor):
    """三窗口综合口径最优 5 席（2026-09-26 本地枚举，3win 16,996 分/月，现役 15,744）：
    SIZE-ONLY + H03-T10-SINGLE + T10-ADD-AGG-IMPACT + T10-ADD-G13 + F-I10-01。

    席位公式与平台 2026-09-11 批次 candidates.txt 逐字对齐：
      size-only-20260911 / h03-t10-single-20260911 / t10-more-additions-20260911 (AGG-IMPACT)
      / t10-additions-20260911 (G13) / size-impact-platform-20260918 (F-I10-01)
    池 = 席位 1%/99% winsorize 后横截面 z-score 等权平均（与 09-24 / 09-26 池测试一致）。
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
        ret1 = close / DELAY(close, 1) - 1
        impact60 = RANK(
            SUM((high - low) / (DELAY(close, 1) + 0.000001), 60)
            / (SUM(amount, 60) + 1)
        )
        t10 = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(market_cap)))
            + impact60
        )
        agg = RANK(SUM(ABS(ret1), 60) / (SUM(amount, 60) + 1))
        g13 = RANK(SUM(ABS(ret1) / (amount + 1), 60) / 60)
        signals = [
            -RANK(market_cap),
            impact60,
            (t10 + agg) / 6,
            (t10 + g13) / 6,
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
