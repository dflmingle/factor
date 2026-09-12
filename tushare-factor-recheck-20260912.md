# Tushare Recheck: Workflow 6aa40282

This is a local recheck of the saved workflow structure. It does not call the
PandaAI factor-test API.

- Window: 2021-09-07 to 2026-09-07
- Warm-up: 2021-01-01
- Rebalance: 10 trading observations
- Groups: 10
- Universe proxy: all Tushare daily stock rows; the script also supports an
  explicit `.SH/.SZ` sensitivity with `--market hs`
- Composite: `4 * close20_rank + 3 * open20_rank + 2 * python_obv`
- Platform comparison: direction 0, low-value group

## Comparison

| factor | platform Rank IC | raw Rank IC | qfq Rank IC | platform low excess | raw low excess | qfq low excess | platform turnover | raw turnover | qfq turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| close20 | -0.0880 | -0.0727 | -0.0720 | 10.61% | 2.17% | 2.76% | 70.85% | 69.01% | 70.07% |
| open20 | -0.0843 | -0.0688 | -0.0678 | 10.64% | 1.59% | 1.60% | 71.93% | 69.81% | 70.95% |
| python_obv | -0.0143 | -0.0327 | -0.0331 | 0.39% | -0.76% | -2.11% | 89.25% | 9.08% | 9.35% |
| composite_432 | -0.0849 | -0.0707 | -0.0699 | 10.79% | 1.85% | 2.23% | 71.20% | 69.32% | 70.44% |

## Conclusion

The sign and broad ranking behavior reproduce: both momentum components and the
weighted composite have negative Rank IC, so direction 0 is the stronger side.
The return magnitude does not reproduce. qfq prices make the broad-market
benchmark closer to the platform, but the low-group excess remains around 2%
instead of 10%.

The main remaining sources of non-equivalence are platform universe membership,
the platform's future-return and missing-row semantics, and tie handling in the
binary Python factor. The Python node is effectively binary for positive volume
because `TS_MAX(volume,20) / volume >= 1`; local stable tie ordering therefore
produces much lower turnover than the platform's 89.25%.

Artifacts:

- `scripts/tushare_factor_recheck.py`
- `quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/reports/local_recheck_report.md`
- `quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/reports/local_recheck_report.md`
