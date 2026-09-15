# PandaAI Factor Research Report

- Candidates: 1; completed: 1; failed: 0
- Settings: 5-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0500
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-NET01-PLAT-20260914 | 1 | 0.0577 | 0.3041 | 16.06% | 8.04% | 2.43% | 13.63% | 0.9352 | 33.95% | 63.33% |

## Correlation references

The factor was compared with `64` saved factors whose platform net excess is positive. The fixed method is `daily_cross_sectional_spearman_mean` over `2021-09-07..2026-09-07`. High correlation is recorded at `abs(rho) >= 0.60`.

| Rank | Factor | Handler | Correlation | Platform net excess | Formula |
|---:|---|---|---:|---:|---|
| 1 | VERIFY-F260910-12 | `book_to_market_lf_plus_impact` | +0.751164 | 15.59% | `RANK(book_to_market_ratio_lf) + RANK(SUM(ABS(CLOSE / DELAY(CLOSE,1) - 1) / (AMOUNT + 1),60) / 60)` |
| 2 | VERIFY10-F260910-12 | `book_to_market_lf_plus_impact` | +0.751164 | 15.05% | `RANK(book_to_market_ratio_lf) + RANK(SUM(ABS(CLOSE / DELAY(CLOSE,1) - 1) / (AMOUNT + 1),60) / 60)` |
| 3 | H03-T10-SINGLE | `impact60` | +0.723887 | 16.44% | `RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))` |
| 4 | VERIFY-G260910-13 | `impact_abs_return60` | +0.711041 | 14.70% | `RANK(SUM(ABS(CLOSE / DELAY(CLOSE,1) - 1) / (AMOUNT + 1),60) / 60)` |
| 5 | VERIFY10-G260910-13 | `impact_abs_return60` | +0.711041 | 13.94% | `RANK(SUM(ABS(CLOSE / DELAY(CLOSE,1) - 1) / (AMOUNT + 1),60) / 60)` |
| 6 | VERIFY-E260910-04 | `book_to_market_lf_minus_size` | +0.691718 | 17.76% | `RANK(book_to_market_ratio_lf) - RANK(MARKET_CAP)` |
| 7 | VERIFY10-E260910-04 | `book_to_market_lf_minus_size` | +0.691718 | 16.74% | `RANK(book_to_market_ratio_lf) - RANK(MARKET_CAP)` |
| 8 | T10-ADD-G13-20260911 | `t10_size_plus_impact_g13` | +0.683916 | 19.62% | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP))) + RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1)) + RANK(SUM(ABS(CLOSE / DELAY(CLOSE,1) - 1) / (AMOUNT + 1),60) / 60)) / 6` |
| 9 | T10-ADD-AGG-IMPACT-20260911 | `t10_size_plus_impact_aggregate` | +0.681918 | 19.76% | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP))) + RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1)) + RANK(SUM(ABS(CLOSE / DELAY(CLOSE,1) - 1),60) / (SUM(AMOUNT,60) + 1))) / 6` |
| 10 | T10-ADD-DOWNSIDE-IMPACT-20260911 | `t10_size_plus_impact_downside` | +0.675163 | 19.39% | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP))) + RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1)) + RANK(SUM((ABS(CLOSE / DELAY(CLOSE,1) - 1) - (CLOSE / DELAY(CLOSE,1) - 1)) / 2,60) / (SUM(AMOUNT,60) + 1))) / 6` |
| 11 | T10-ADD-BM-20260911 | `t10_size_plus_impact_bm` | +0.659967 | 18.09% | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP))) + RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1)) + RANK(book_to_market_ratio_lf)) / 6` |
| 12 | SIZE-ONLY-20260911 | `size_only` | -0.623662 | 21.43% | `RANK(MARKET_CAP)` |
| 13 | paper-derived-composite | `paper_composite` | +0.607046 | 11.20% | `ZSCORE(RANK(book_to_market_ratio_lyr))+ZSCORE(RANK(oper_roe_lyr))-ZSCORE(RANK(gr_total_asset_lyr))-ZSCORE(RANK(MARKET_CAP))` |
| 14 | paper-derived-composite | `paper_composite` | +0.607046 | 11.41% | `ZSCORE(RANK(book_to_market_ratio_lyr))+ZSCORE(RANK(oper_roe_lyr))-ZSCORE(RANK(gr_total_asset_lyr))-ZSCORE(RANK(MARKET_CAP))` |
| 15 | T10-SIZE-PLUS-IMPACT | `t10_size_plus_impact` | +0.600083 | 18.16% | `(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP))) + RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))) / 5` |

Full pairwise results: `research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915.json`. The cumulative per-factor record is `research_reports/platform_alignment/factor-correlation-registry.json`.
