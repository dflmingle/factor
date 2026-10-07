"""A 阶梯 T3：删 VERIFY10-E（BM 族，与 F 同族）、换入 K10（ΔA +1,018）

B 钟表账（第 57/58 条）：本池 1 换 1、只删 1 个现役席位 => den_b 5->4，仍 >= 4，样本外时钟不重开。
A 段靠"换入高 s_i 席"补（ΔA 阶梯，第 59 条 §6.4）。席位代码逐字节沿用已通过平台验证的两个来源：
  现役 5 席  <- pool5-live-20260928.py（修正版 CTRL，复现平台池记录 .0919/13.39%/20.30%）
  K10/K20/STD20/AMTDISP <- pool5-rebuild-l6-20261004.py（第 53 条平台确认）
  TOPMIX <- pool5-rebuild-l5-20261004.py（cal-date 8 腿复合，平台 s_i .0610）
席位等权、每席先按日截面 1%/99% 截尾后 z-score（对齐赛制"池内有效因子等权合成"）。
"""
import numpy as np


def _date_level(s):
    """找出"日期层"的 level（平台 Python 运行时索引为 [date, symbol]）。"""
    idx = s.index
    for lv in range(getattr(idx, "nlevels", 0)):
        try:
            v = idx.get_level_values(lv)[0]
        except Exception:
            continue
        if hasattr(v, "year") or "datetime" in type(v).__name__.lower():
            return lv
    return 0


def _normalize(s, level):
    def _one(x):
        x = x.replace([np.inf, -np.inf], np.nan)
        lo, hi = x.quantile(0.01), x.quantile(0.99)
        x = x.clip(lower=lo, upper=hi)
        sd = x.std(ddof=0)
        if not np.isfinite(sd) or sd <= 1e-12:
            return x * 0.0
        return (x - x.mean()) / sd
    return s.groupby(level=level).transform(_one)


def _rollstd(s, n):
    return s.groupby(level=0).transform(lambda x: x.rolling(n).std(ddof=0))


class Pool5SwapEK10Factor(Factor):
    """A 阶梯 T3：删 VERIFY10-E（BM 族，与 F 同族）、换入 K10（ΔA +1,018）"""

    def calculate(self, factors):
        close = factors['close']
        open_ = factors['open']
        high = factors['high']
        low = factors['low']
        volume = factors['volume']
        amount = factors['amount']
        turnover = factors['turnover']
        mcap = factors['market_cap']
        bm = factors['book_to_market_ratio_lf']

        ret1 = close / DELAY(close, 1) - 1
        impact = RANK(SUM((high - low) / (DELAY(close, 1) + 0.000001), 60) / (SUM(amount, 60) + 1))

        def _std(x, n):
            try:
                return STDDEV(x, n)
            except NameError:
                pass
            try:
                return STD(x, n)
            except NameError:
                pass
            return _rollstd(x, n)

        seat_t10 = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(mcap)))
            + impact
            + RANK(bm)
        ) / 6

        seat_bm_minus_size = RANK(bm) - RANK(mcap)
        seat_bm_plus_impact = RANK(bm) + RANK(SUM(ABS(close / DELAY(close, 1) - 1) / (amount + 1), 60) / 60)
        seat_size = -RANK(mcap)
        seat_impact = impact

        seat_k10 = (
            RANK(-MA(amount, 60))
            + RANK(-MA((close - open_) / open_, 20))
            + RANK(-_std(turnover, 20))
            + RANK(MA(ABS(ret1) / amount, 20))
            + RANK(-(_std(volume, 6) / _std(volume, 756)))
        ) / 5

        seat_k20 = (
            RANK(-MA(amount, 60))
            + RANK(-MA(turnover, 1))
            + RANK(MA(ABS(ret1) / amount, 20))
            + RANK(-MA((close - open_) / open_, 20))
            + RANK(-MA(close * volume / amount, 20))
        ) / 5

        amount_w = amount.unstack(level=1)
        volume_w = volume.unstack(level=1)
        turnover_w = turnover.unstack(level=1)
        high_w = high.unstack(level=1)
        low_w = low.unstack(level=1)
        close_w = close.unstack(level=1)

        seat_std20 = (-amount_w.rolling(20).std()).stack().reindex(close.index)
        seat_amtdisp = (
            0.5 * (-amount_w.rolling(20).std()).rank(axis=1, pct=True)
            + 0.5 * (-amount_w.rolling(20).mean()).rank(axis=1, pct=True)
        ).stack().reindex(close.index)

        legs_topmix = [
            -amount_w.rolling(20).std(),
            -amount_w.rolling(20).mean(),
            -volume_w.rolling(10).std(),
            -volume_w.rolling(20).std(),
            -(turnover_w.rolling(10).mean() / turnover_w.rolling(120).mean()),
            -turnover_w.rolling(5).mean(),
            -(turnover_w.rolling(5).mean() / turnover_w.rolling(120).mean()),
            -((high_w.rolling(10).max() - low_w.rolling(10).min()) / close_w.shift(10)),
        ]
        seat_topmix = (
            sum(leg.rank(axis=1, pct=True) for leg in legs_topmix) / 8.0
        ).stack().reindex(close.index)

        signals = [seat_t10, seat_bm_plus_impact, seat_impact, seat_size, seat_k10]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)
