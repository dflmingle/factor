# Local AP Tree Reproduction

This is a China A-share method reproduction of Bryzgalova, Pelger and Zhu (2025), not a cell-by-cell replication of the U.S. CRSP/Compustat sample.

## Result

| K | train Sharpe | validation Sharpe | test Sharpe | selected nodes | lambda0 | lambda2 / median diagonal |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 3.1653 | 2.8513 | 0.7175 | 11 | 0.5 | 0.1 |
| 40 | 3.3442 | 2.8723 | 0.9210 | 44 | 0.1 | 1 |

## Reproduction Boundary

- `OP` is an explicit proxy because the cache exposes `operate_profit`, not all four components `REVT`, `COGS`, `TIE`, and `XSGA`.
- Returns use unadjusted close-to-close prices; dividends and a risk-free series are not available in this local cache.
- The paper has 53 years and uses 20 years of training, 10 years of validation, and 23 years of testing. This cache provides roughly 11 years, so the run uses 60 months, 24 months, and the remaining months.
- The output reports annualized monthly Sharpe ratios with `sqrt(12)`. They are SDF diagnostics, not the long-only PandaAI competition score.

## Files

- `summary.json`: exact settings, definitions, split dates, grid, and metrics.
- `selected_nodes.csv`: selected node descriptions and signed SDF weights.
- `node_catalog.csv`: all recursive nodes used by the pruning candidate set.
- `monthly_sdf.csv`: monthly SDF diagnostics by K.
