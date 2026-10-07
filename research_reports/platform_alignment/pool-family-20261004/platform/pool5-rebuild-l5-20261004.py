"""池级整池换席确认 L5（Python 因子模式，2026-10-04，本地零算力预检后提交）。

整池账候选 L5（本地 ΔComb_AC +1,481 分/月，见 ../summary.md §六）：
  现役 t10 席 + K10/TOPMIX/STD20/AMTDISP 四强席 等权池（5 席）—— 与 L6 同封顶 .70、
  s_i 余量更大（+4.9%），差分只含 TOPMIX↔K20 的换手定价。
席位等权、每席先按日截面 1%/99% 截尾再 z-score（对齐赛事"池内有效因子等权合成"）。

席位（5）：
  1. (t10_base + RANK(bm_lf)) / 6                  (T10-ADD-BM-20260911，现役)
  2. LAMD10-K5V2-20260929（平台因子 6abb67a29e9d797cfb2d0776，平台 s_i .0673）
  3. ct_comp_topmix（2026-10-03 平台实测 s_i .0610 / 换手 47.3%/次）：
     8 腿截面 pct-rank 等权平均（腿 = 平台字段 × 方向 -1，本地口径同 caltech_legs）：
       -std20(amount), -ma20(amount), -std10(volume), -std20(volume),
       -(MA(turnover,10)/MA(turnover,120)), -MA(turnover,5),
       -(MA(turnover,5)/MA(turnover,120)), -amp10
     amp10 = (max(high,10) - min(low,10)) / shift(close,10)
  4. ct_amt_std20（平台公式 0-CAL_20D_AMT_STD，s_i .0557）: -std20(amount)
  5. ct_comp_amtdisp（平台 s_i .0505 / 换手 27.41%/次 / 净 +13.28%）:
     0.5 * RANK(-std20(amount)) + 0.5 * RANK(-ma20(amount))

平台目的：A 余量对照 + 同封顶差分的换手定价（与 L6 同批提交）。
"""
import numpy as np


def _date_level(s):
    """找出"日期层"的 level（同 pool5-live：禁止 isdigit 兜底，
    平台 Python 运行时索引为 [date, symbol]。"""
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


class Pool5RebuildL5Factor(Factor):
    """现役 t10 席 + K10/TOPMIX/STD20/AMTDISP 整池换席版（5 席）"""

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

        seat_t10bm = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(mcap)))
            + impact
            + RANK(bm)
        ) / 6

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

        seat_lamd10k5 = (
            RANK(-MA(amount, 60))
            + RANK(-MA((close - open_) / open_, 20))
            + RANK(-_std(turnover, 20))
            + RANK(MA(ABS(ret1) / amount, 20))
            + RANK(-(_std(volume, 6) / _std(volume, 756)))
        ) / 5

        amount_w = amount.unstack(level=1)
        volume_w = volume.unstack(level=1)
        turnover_w = turnover.unstack(level=1)
        high_w = high.unstack(level=1)
        low_w = low.unstack(level=1)
        close_w = close.unstack(level=1)

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

        seat_std20 = (-amount_w.rolling(20).std()).stack().reindex(close.index)
        seat_amtdisp = (
            0.5 * (-amount_w.rolling(20).std()).rank(axis=1, pct=True)
            + 0.5 * (-amount_w.rolling(20).mean()).rank(axis=1, pct=True)
        ).stack().reindex(close.index)

        signals = [seat_t10bm, seat_lamd10k5, seat_topmix, seat_std20, seat_amtdisp]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)