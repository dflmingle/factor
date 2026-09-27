from pathlib import Path

OUT = Path(r"D:\factor\platform_pool_tests_20260926")

bmt10 = """import numpy as np


class Pool4BmT10Fi10Factor(Factor):
    \"\"\"Incumbent minus VERIFY10-E and VERIFY10-F plus F-I10-01 (4-seat, 2026-09-27).

    Pool = equal-weight average of per-seat cross-sectional z-scores
    (1%/99% winsorized), same convention as pool5_swapf_fi10 / pool5_partial_t10.

    Seats:
      1. -RANK(market_cap)                      (SIZE-ONLY-20260911)
      2. impact60                               (H03-T10-SINGLE)
      3. (t10_base + RANK(bm_lf)) / 6           (T10-ADD-BM-20260911)
      4. (-RANK(market_cap) + impact60) / 2     (F-I10-01)
    \"\"\"

    def calculate(self, factors):
        close = factors['close']
        open_ = factors['open']
        high = factors['high']
        low = factors['low']
        volume = factors['volume']
        amount = factors['amount']
        turnover = factors['turnover']
        market_cap = factors['market_cap']
        impact60 = RANK(
            SUM((high - low) / (DELAY(close, 1) + 0.000001), 60)
            / (SUM(amount, 60) + 1)
        )
        bm = RANK(factors['book_to_market_ratio_lf'])
        t10 = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(market_cap)))
            + impact60
        )
        signals = [
            -RANK(market_cap),
            impact60,
            (t10 + bm) / 6,
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
"""

(OUT / "pool4_bmt10_fi10.py").write_text(bmt10, encoding="utf-8", newline="\n")
(OUT / "pool5-partt10-20260927-candidates.txt").write_text(
    "POOL5-PARTT10-20260927 ~ pool5_partial_t10.py ~ 1\n", encoding="utf-8", newline="\n")
(OUT / "pool4-bmt10-fi10-20260927-candidates.txt").write_text(
    "POOL4-BMT10-FI10-20260927 ~ pool4_bmt10_fi10.py ~ 1\n", encoding="utf-8", newline="\n")

for f in ("pool4_bmt10_fi10.py", "pool5-partt10-20260927-candidates.txt", "pool4-bmt10-fi10-20260927-candidates.txt"):
    p = OUT / f
    b = p.read_bytes()
    print(f, "bytes:", len(b), "BOM:", b[:3] == b"\xef\xbb\xbf", "head:", b[:40])