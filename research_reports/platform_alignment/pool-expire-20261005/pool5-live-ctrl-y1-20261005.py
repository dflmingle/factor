# 2026-10-05 expiring-credit rerun (POOL5-CTRL-Y1): byte-identical logic from repo-root pool5-live-20260928.py
# (the corrected CTRL 5-seat file that reproduced platform pool record .0919/13.39%/20.30%).
# Only window differs: 20250907..20260907.
"""池合成对照/处理（Python 因子模式，2026-09-28，本地生成）。

现役 5 席等权池（SIZE + H03-impact + T10-ADD-BM + BM-SIZE + BM+impact）
席位等权、每席先按日截面 1%/99% 截尾再 z-score（对齐赛事"池内有效因子等权合成"）。
"""
import numpy as np


def _date_level(s):
    """找出"日期层"的 level。

    2026-09-29 修正：旧实现用 `str(v)[:4].isdigit()` 兜底，而平台 Python 运行时的
    索引是 [date, symbol]（见 research_reports/platform_alignment/
    pool-horizontal-selection-20260921/platform-validation.md），symbol 形如
    "000001.SZ" 前四位是数字，会被误判成日期 → 用 level=1（symbol）做了按股票的
    时序 z-score，导致代理池收益/换手虚高（本地 mock 对照：截面口径 5 席换手 13.4%
    ≈ 平台池记录 13.39%；错误口径 22.4% ≈ 平台代理 24.10%）。
    """
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


class Pool5LiveFactor(Factor):
    """现役 5 席等权池（SIZE + H03-impact + T10-ADD-BM + BM-SIZE + BM+impact）"""

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
        seat_bmimpact = RANK(bm) + RANK(SUM(ABS(close / DELAY(close, 1) - 1) / (amount + 1), 60) / 60)

        signals = [seat_size, seat_impact, seat_t10bm, seat_bmsize, seat_bmimpact]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)
