import numpy as np


class Pool6Bm4FscoreEFactor(Factor):
    """BM4 core + T10-ADD-FSCORE + VERIFY10-E (6-seat, 2026-09-27).

    Pool = equal-weight average of per-seat cross-sectional z-scores
    (1%/99% winsorized), same convention as pool4_bmt10_fi10 / pool5_partial_t10.

    Seats:
      1. -RANK(market_cap)                        (SIZE-ONLY-20260911)
      2. impact60                                 (H03-T10-SINGLE)
      3. (t10_base + RANK(bm_lf)) / 6             (T10-ADD-BM-20260911)
      4. (-RANK(market_cap) + impact60) / 2       (F-I10-01)
      5. (t10_base + fscore) / 6            (T10-ADD-FSCORE-20260911)
      6. RANK(bm_lf) - RANK(market_cap)           (VERIFY10-E260910-04)
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
        bm = RANK(factors['book_to_market_ratio_lf'])
        t10 = (
            RANK(1 - RETURNS(close, 40))
            + RANK((SUM(volume * (open_ + close) / 2, 250) / SUM(volume, 250)) / close - 1)
            + RANK(1 - MA(turnover, 21) / MA(turnover, 504))
            + RANK(-ZSCORE(RANK(market_cap)))
            + impact60
        )
        oper_roa_net_ttm = factors['oper_roa_net_ttm']
        oper_roa_net_lyr = factors['oper_roa_net_lyr']
        cfd_ocf_to_debt_ttm = factors['cfd_ocf_to_debt_ttm']
        cfd_surplus_cash_multi_ttm = factors['cfd_surplus_cash_multi_ttm']
        fin_debt_to_asset_ttm = factors['fin_debt_to_asset_ttm']
        fin_debt_to_asset_lyr = factors['fin_debt_to_asset_lyr']
        fin_current_ratio_ttm = factors['fin_current_ratio_ttm']
        fin_current_ratio_lyr = factors['fin_current_ratio_lyr']
        oper_gross_margin_ttm = factors['oper_gross_margin_ttm']
        oper_gross_margin_lyr = factors['oper_gross_margin_lyr']
        oper_total_asset_turnover_ttm = factors['oper_total_asset_turnover_ttm']
        oper_total_asset_turnover_lyr = factors['oper_total_asset_turnover_lyr']
        fscore = RANK(
            (
                IF(oper_roa_net_ttm > 0, 1, 0)
                + IF(cfd_ocf_to_debt_ttm > 0, 1, 0)
                + IF(oper_roa_net_ttm > oper_roa_net_lyr, 1, 0)
                + IF(cfd_surplus_cash_multi_ttm > 1, 1, 0)
                + IF(fin_debt_to_asset_ttm < fin_debt_to_asset_lyr, 1, 0)
                + IF(fin_current_ratio_ttm > fin_current_ratio_lyr, 1, 0)
                + IF(oper_gross_margin_ttm > oper_gross_margin_lyr, 1, 0)
                + IF(oper_total_asset_turnover_ttm > oper_total_asset_turnover_lyr, 1, 0)
            ) / 8
        )

        signals = [
            -RANK(market_cap),
            impact60,
            (t10 + bm) / 6,
            (-RANK(market_cap) + impact60) / 2,
            (t10 + fscore) / 6,
            bm - RANK(market_cap),
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
