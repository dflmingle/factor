# Paper-Inspired Factor Retrospective

## Locked definition

```text
ZSCORE(RANK(book_to_market_ratio_lyr))
+ ZSCORE(RANK(oper_roe_lyr))
- ZSCORE(RANK(gr_total_asset_lyr))
- ZSCORE(RANK(MARKET_CAP))
```

- Direction: 1 (higher is better)
- Rebalance: 5 trading days
- Groups: 10
- One-way cost: 0.30%
- Hypothesis count used for screening: 8; reference p threshold: 0.0063

## Screen

Requested window: 20210907-20260907. The returned chart covers 241 rebalance observations through 2026-08-24.

| metric | value |
|---|---:|
| IC_mean | 0.0318 |
| Rank_IC | 0.0597 |
| IC p-value | 0.0007 |
| monotonicity | 0.99 |
| long-side excess | 13.32% |
| turnover | 6.32% |
| annual cost | 1.91% |
| net excess | 11.41% |
| long Sharpe | 0.8395 |
| max drawdown | 35.74% |

## Non-overlapping validation

Requested window: 20160907-20210906. The returned chart covers 227 rebalance observations from 2017-01-03 through 2021-08-24.

| metric | value |
|---|---:|
| IC_mean | 0.0111 |
| Rank_IC | 0.0209 |
| IC p-value | 0.1339 |
| monotonicity | 0.74 |
| long-side excess | 4.98% |
| turnover | 6.77% |
| annual cost | 2.05% |
| net excess | 2.93% |
| long Sharpe | 0.3625 |
| max drawdown | 45.67% |

## Decision

- Hypothesized mechanism: a joint value, profitability, conservative-investment, and small-cap tilt.
- Falsification result: the positive cost-adjusted excess survives in the earlier window, but IC significance and monotonicity weaken materially.
- Redundancy check: not completed; the CLI returned summary data and top-ranked names but no full cross-sectional CSV.
- Decision: retain as a research candidate; do not submit as a proven factor and do not claim an exact AP Tree replication.

## Data boundary

The PandaAI result endpoint exposed IC/group summaries, charts, and the latest top-factor rows. The documented CSV download exited successfully but produced no file because the returned nodes had no download URL. Exact recursive node splits, covariance shrinkage, LASSO pruning, and local Spearman redundancy analysis therefore remain pending.
