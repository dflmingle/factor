"""换席候选（Python 因子模式，2026-09-30，本地生成，零平台算力预检通过后提交）。

现役 5 席 − VERIFY10-F（seat_bmimpact） + LAMD10-K5V2 等权池（5 席）。
席位等权、每席先按日截面 1%/99% 截尾再 z-score（对齐赛事"池内有效因子等权合成"）。

席位（4 现役 + 1 新）：
  1. -RANK(market_cap)                          (SIZE-ONLY-20260911)
  2. impact60                                   (H03-T10-SINGLE)
  3. (t10_base + RANK(bm_lf)) / 6               (T10-ADD-BM-20260911)
  4. RANK(bm_lf) - RANK(market_cap)             (VERIFY10-E260910-04)
  5. LAMD10-K5V2-20260929（平台因子 6abb67a29e9d797cfb2d0776）:
     (RANK(-MA(AMOUNT,60)) + RANK(-MA((CLOSE-OPEN)/OPEN,20)) + RANK(-STD(TURNOVER,20))
      + RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)) + RANK(-STDDEV(VOLUME,6)/STDDEV(VOLUME,756))) / 5
换出 VERIFY10-F260910-12（RANK(bm) + 60 日 impact 腿）。

本地换席账（c-cap-rescreen-20260930/swap/）对 5 个换席目标做了全账：
换 F 的三段账 +3288 分/月（本地口径）为全部情景最优，本文件即其平台确认版。
"""
import numpy as np


def _date_level(s):
    """找出"日期层"的 level（2026-09-29 修正，同 pool5-live：禁止 isdigit 兜底，
    平台 Python 运行时索引为 [date, symbol]，旧实现会误用 symbol 层做时序 z-score）。"""
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


def _rollmax(s, n):
    return s.groupby(level=0).transform(lambda x: x.rolling(n).max())


def _rollstd(s, n):
    return s.groupby(level=0).transform(lambda x: x.rolling(n).std(ddof=0))


def _rollcorr(a, b, n):
    tmp = a.to_frame("a").copy()
    tmp["b"] = b
    out = tmp.groupby(level=0).apply(lambda d: d["a"].rolling(n).corr(d["b"]))
    out.index = out.index.droplevel(0)
    return out.reindex(a.index)


class Pool5SwapFLamd10K5V2Factor(Factor):
    """现役 5 席 − VERIFY10-F + LAMD10-K5V2 等权池（5 席）"""

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

        seat_size = -RANK(mcap)
        seat_impact = impact
        seat_t10bm = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(mcap)))
            + impact
            + RANK(bm)
        ) / 6
        seat_bmsize = RANK(bm) - RANK(mcap)

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

        signals = [seat_size, seat_impact, seat_t10bm, seat_bmsize, seat_lamd10k5]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)
