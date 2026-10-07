"""L2c pool rebuild for platform confirmation (2026-10-05, user-approved spend).

Seats (equal weight, each z-scored cross-sectionally after 1%/99% winsorize):
  1. (t10_base + RANK(bm_lf)) / 6          (T10-ADD-BM-20260911, incumbent t10)
  2. impact60                              (H03-T10-SINGLE, incumbent impact60)
  3. LAMD10-K5V2                           (platform factor 6abb67a29e9d797cfb2d0776)
  4. ct_comp_topmix                        (8-leg cal-date composite, platform s_i .0610)
  5. ct_amt_std20                          (0-CAL_20D_AMT_STD, platform s_i .0557)

Local ledger (pool-variants-20261005): raw_a .05225 -> na .6531, dA +2,899,
dC -1,243, dComb_AC +1,656/month, turn/reb .3201, corr_size .6064.
Purpose: first platform confirmation of the designated backup pool."""
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


class Pool5RebuildL2cFactor(Factor):
    """整池备选 L2c：现役 t10 + impact60 两席 + K10/TOPMIX/STD20（5 席）"""

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
        seat_impact = impact

        signals = [seat_t10bm, seat_impact, seat_lamd10k5, seat_topmix, seat_std20]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)