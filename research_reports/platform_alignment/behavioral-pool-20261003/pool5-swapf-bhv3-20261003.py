"""池级换席确认 B（Python 因子模式，2026-10-03，本地零算力预检）。

现役 5 席 − VERIFY10-F（seat_bmimpact） + 行为复合 bhv3 等权池（5 席）。
即与 pool5-swapf-lamd10k5v2-20260930 同一换出席位，但换入 bhv3 而非 LAMD10-K5V2。
本地账（behavioral-20261003/）：bhv3 未测过换席形态（append 口径 +1,342/月，仅作参考）。
席位等权、每席先按日截面 1%/99% 截尾再 z-score（对齐赛事"池内有效因子等权合成"）。

席位：
  1. -RANK(market_cap)                          (SIZE-ONLY-20260911)
  2. impact60                                   (H03-T10-SINGLE)
  3. (t10_base + RANK(bm_lf)) / 6               (T10-ADD-BM-20260911)
  4. RANK(bm_lf) - RANK(market_cap)             (VERIFY10-E260910-04)
  5. 行为复合 bhv3（limitup20 + cgo500 + on_minus_id，2026-10-03）
行为复合席（bhv3）：平台公式版 2026-10-03 实测 RankIC .0944 / mono .95 / 净 +5.27% / s_i .0584。
  腿1 limitup20  : -COUNT(RETURNS(C,1)>=0.095, 20)
  腿2 cgo500     : -(C/(SUM(TURNOVER*AMOUNT/VOLUME,500)/SUM(TURNOVER,500))-1)
  腿3 on_minus_id: MA((OPEN-DELAY(C,1))/DELAY(C,1),20) - MA((CLOSE-OPEN)/OPEN,20)
  Python 侧以宽表 pandas 实现（.unstack(level=1) → rolling → .rank(axis=1,pct=True) → .stack()，
  同 probe_ml5_eq_20261001.py 已平台验证的管线）；条件计数用 (ret1>=0.095).astype(float).rolling(20).sum()。
本地校验：公式仿真 vs 腿库逐期秩相关 1.000000（1608 期）；本文件过 repaint_check 与 bhv3 语义对照。
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


class Pool5SwapFBhv3Factor(Factor):
    """现役 5 席 − VERIFY10-F + 行为复合 bhv3 等权池（5 席）"""

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

        idx = close.index
        close_w = close.unstack(level=1)
        open_w = open_.unstack(level=1)
        volume_w = volume.unstack(level=1)
        amount_w = amount.unstack(level=1)
        turnover_w = turnover.unstack(level=1)

        ret1_w = close_w / close_w.shift(1) - 1.0
        cnt20_w = (ret1_w >= 0.095).astype("float64").rolling(20).sum()
        ref500_w = (turnover_w * amount_w / volume_w).rolling(500).sum() / turnover_w.rolling(500).sum()
        cgo_w = close_w / ref500_w - 1.0
        on_w = (open_w - close_w.shift(1)) / close_w.shift(1)
        id_w = (close_w - open_w) / open_w
        onid_w = on_w.rolling(20).mean() - id_w.rolling(20).mean()

        bhv_parts = {
            "limitup20": (-cnt20_w).rank(axis=1, pct=True),
            "cgo500": (-cgo_w).rank(axis=1, pct=True),
            "on_minus_id": onid_w.rank(axis=1, pct=True),
        }
        seat_bhv3 = (sum(bhv_parts.values()) / float(len(bhv_parts))).stack().reindex(idx)

        signals = [seat_size, seat_impact, seat_t10bm, seat_bmsize, seat_bhv3]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)
