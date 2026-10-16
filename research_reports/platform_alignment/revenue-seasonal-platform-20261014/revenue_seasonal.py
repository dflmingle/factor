class SeasonalRevenueSurprise(Factor):
    def calculate(self, factors):
        # Platform PIT native statement-period values; single-quarter/YTD
        # vendor semantics are unverified. Not a claim of local byte parity.
        current = factors['is_revenue'].astype(float)
        prior4 = factors['is_revenue_mrq_4'].reindex(current.index).astype(float)
        prior8 = factors['is_revenue_mrq_8'].reindex(current.index).astype(float)
        prior12 = factors['is_revenue_mrq_12'].reindex(current.index).astype(float)
        # Scaling before squaring avoids overflow and preserves the score.
        scale = (prior4.abs() + prior8.abs() + prior12.abs()) / 3.0
        scale = scale.where(scale > 0)
        a = prior4 / scale
        b = prior8 / scale
        c = prior12 / scale
        normalized_mean = (a + b + c) / 3.0
        variance = ((a - normalized_mean) ** 2 +
                    (b - normalized_mean) ** 2 +
                    (c - normalized_mean) ** 2) / 2.0
        std = np.sqrt(variance).where(variance > 1e-24)
        result = (current / scale - normalized_mean) / std
        return result.where(np.isfinite(result)).rename('value')
