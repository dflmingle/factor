"""池级换席确认 C（Python 因子模式，2026-10-04，本地零算力预检）。

现役 5 席 − VERIFY10-F（seat_bmimpact） + 技术目录复合 ct_comp_amtdisp 等权池（5 席）。
与 pool5-swapf-lamd10k5v2-20260930 / pool5-swapf-bhv3-20261003 同一换出席位（VERIFY10-F），
第 5 席换入 ct_comp_amtdisp（2026-10-03 平台实测：RankIC .1049 / IR .642 / mono .99 /
换手 27.41%/次 / 净 +13.28% / s_i .0505，本地转移比 1.05）。
席位等权、每席先按日截面 1%/99% 截尾再 z-score（对齐赛事“池内有效因子等权合成”）。

席位（4 现役 + 1 新）：
  1. -RANK(market_cap)                          (SIZE-ONLY-20260911)
  2. impact60                                   (H03-T10-SINGLE)
  3. (t10_base + RANK(bm_lf)) / 6               (T10-ADD-BM-20260911)
  4. RANK(bm_lf) - RANK(market_cap)             (VERIFY10-E260910-04)
  5. ct_comp_amtdisp（2026-10-04 新增）:
     0.5 * RANK(-std20(amount)) + 0.5 * RANK(-ma20(amount))，宽表实现
     （.unstack(level=1) → rolling(20) → .rank(axis=1, pct=True) → .stack()，
     同 probe_ml5_eq_20261001.py / pool5-swapf-bhv3-20261003.py 已平台跑通管线）；
     语义对齐腿库 ct_comp_amtdisp（ct_amt_std20 / ct_amt_ma20 截面 pct-rank 等权）。
换出 VERIFY10-F260910-12（RANK(bm) + 60 日 impact 腿）。

本轮目的：平台实测池级 ΔT/ΔC/ΔNC，裁决 AMTDISP 是否进候选席库（非替换 K10 主候选）。
本地换席账（../caltech-swap-20261003/cand_summary_direct.csv）：s_i .0481 / ΔE −0.086 /
ΔT +.073/月 / ΔNC −.0031 / ΔC −61（全账最轻）/ ΔComb_up +715；
对照 K10 换席 +1,264 / K20 换席 +1,234（≈1.8×，故不改主候选）。
风险对照：bhv3 平台单因子 s_i .0584 过线，池级 A/B 两形态均否（−5.76pp / −5.10pp）。
"""
import numpy as np


def _date_level(s):
    """找出“日期层”的 level（2026-09-29 修正，同 pool5-live：禁止 isdigit 兜底，
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


class Pool5SwapFAmtdispFactor(Factor):
    """现役 5 席 − VERIFY10-F + ct_comp_amtdisp 等权池（5 席）"""

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

        amount_w = amount.unstack(level=1)
        seat_amtdisp = (
            0.5 * (-amount_w.rolling(20).std()).rank(axis=1, pct=True)
            + 0.5 * (-amount_w.rolling(20).mean()).rank(axis=1, pct=True)
        ).stack().reindex(close.index)

        signals = [seat_size, seat_impact, seat_t10bm, seat_bmsize, seat_amtdisp]

        level = _date_level(signals[0])
        normed = [_normalize(s, level) for s in signals]
        return sum(normed) / len(normed)
