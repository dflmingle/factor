import numpy as np
import pandas as pd


class ValuationResidualFactor(Factor):
    """Cheapness unexplained by profitability, growth, leverage, and size."""

    @staticmethod
    def _residual(group):
        value_cols = ["ep", "bm", "sp"]
        control_cols = ["roe", "revenue_growth", "profit_growth", "low_debt", "log_size"]
        ranked = group[value_cols + control_cols].rank(pct=True, method="average")
        y = ranked[value_cols].mean(axis=1).to_numpy(dtype=float)
        x_values = ranked[control_cols].to_numpy(dtype=float)
        valid = np.isfinite(y) & np.isfinite(x_values).all(axis=1)
        residual = np.full(len(group), np.nan, dtype=float)
        if valid.sum() < len(control_cols) + 5:
            return pd.Series(residual, index=group.index, name="value")

        x = np.column_stack([np.ones(valid.sum()), x_values[valid]])
        beta = np.linalg.lstsq(x, y[valid], rcond=None)[0]
        residual[valid] = y[valid] - x @ beta
        return pd.Series(residual, index=group.index, name="value")

    def calculate(self, factors):
        raw = pd.concat(
            {
                "ep": factors["ratio_ep_ttm"],
                "bm": factors["ratio_bm_ttm"],
                "sp": factors["ratio_sp_ttm"],
                "roe": factors["oper_roe_ttm"],
                "revenue_growth": factors["gr_revenue_ttm"],
                "profit_growth": factors["gr_oper_profit_ttm"],
                "low_debt": -factors["fin_debt_to_asset_ttm"],
                "log_size": np.log(np.maximum(factors["market_cap"], 1e-12)),
            },
            axis=1,
        )
        result = raw.groupby(level=1, group_keys=False).apply(self._residual)
        return result.rename("value")
