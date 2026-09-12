# Positive-net-excess factor local reproduction

This report records the local reproduction of every saved completed platform run with `net_excess_pct > 0`. It uses the local Tushare snapshot and does not create or run a new PandaAI backtest.

## Final state

- 45 positive platform records were found.
- 45/45 were rebuilt locally; 0 remain data-unavailable.
- The local pool is the 4,879-symbol ST-filtered pool, with qfq daily prices.
- The comparison window is 2021-09-07 through 2026-09-07, with 2019-07-01 warmup, 10 groups, and 0.30% one-way cost.
- 39/45 records have an absolute RankIC difference no larger than 0.005.
- 35/45 records have an absolute net-excess difference no larger than 2 percentage points; 21/45 are within 1 point.
- Mean absolute differences are 0.00322 RankIC and 1.44 percentage points of net excess.

The full row-level comparison is generated at:

`quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare/positive_factor_local_compare.md`

The JSON file beside it contains formulas, periods, top-20 overlap, and all platform/local metrics.

## What was added

The 29 records that previously depended on unavailable financial or Barra fields are now rebuilt from Tushare data:

- `fina_indicator`, `income`, `balancesheet`, and `cashflow` are cached locally.
- Financial data is joined point-in-time using `ann_date`; no future report is used.
- Tushare consolidated statements (`comp_type=1`) are preferred.
- Cumulative quarterly income and cash-flow values are converted to discrete quarters and TTM values.
- BM, SP, EP, CFP, PCF, asset growth, paper composite, F-score-like, and weighted value/reversal combinations are implemented.
- The original weights are preserved, including CFP REV2/REV3, CFP VAL2/VAL3, SP, PCF, MA63, and TSRANK756 variants.

## Main findings

The direct market-data factors remain the best alignment reference. The full-window four-factor size composite is close: platform net excess is 16.38% versus local 15.88%. The paper-derived composites are also close, at 11.20% versus 11.13% for the 10-day run and 11.41% versus 11.13% for the 5-day run.

Simple financial value factors are close after the point-in-time and consolidated-report fixes: BM is 2.10% versus 2.32%, and SP is 0.11% versus 0.08%. The OSR3 BM/REV2 formula is also close in net excess, 2.48% versus 2.00%.

Several CFP combinations have near-platform RankIC but materially lower local net excess. This points to differences in cash-flow field definition, report revision/TTM treatment, missing-value portfolio membership, or platform-specific field preprocessing. It is not evidence that the factor direction is reversed. The 5-day CFP time-series-rank combination is comparatively close, while the CFP/SP, CFP/PCF, and CFP value-weighted variants remain less aligned.

The 5-day drawdown factors have nearly identical RankIC but higher local gross excess, so their larger net differences are more consistent with portfolio path, return alignment, or annualization differences than with a direction error. Short 2026 YTD records have only 16 periods and should not be used as equivalence tests.

## Known approximation boundaries

- `residual_volatility` is a market-model residual-volatility proxy, not the platform's internal Barra residual-volatility field.
- `MA(...,63)` and `TS_RANK(...,756)` use daily point-in-time Tushare ratios. The local daily cache starts at 2019-07-01, so 756-day formulas have a local warmup gap and only 197 valid periods versus the platform's 241 chart periods.
- Platform financial fields are internal fields; the local implementation maps them to documented Tushare fields. Matching RankIC does not establish byte-for-byte field equivalence.
- The local result uses the same saved platform signal dates where available. The momentum record has no saved chart payload and uses the reference 10-day schedule.

## Reproduce

After the repository and local data snapshot are available:

```powershell
python scripts/local_recheck_data.py import --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py verify
python scripts/positive_factor_local_compare.py
```

The current LFS snapshot contains 1,070 files, including the 245 financial Parquet batches used by this report. A Tushare token is only needed when rebuilding the snapshot with `tushare_financial_cache.py`.

The financial cache builder is:

```powershell
python scripts/tushare_financial_cache.py --start-date 20180101 --end-date 20260907 --batch-size 80 --workers 2
```

The Tushare token is supplied through the current process environment and is not stored in the repository.
