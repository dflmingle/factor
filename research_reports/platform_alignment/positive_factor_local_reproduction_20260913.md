# Positive-net-excess factor local reproduction

This report records the local reproduction of every saved completed platform run with `net_excess_pct > 0`. It uses the local Tushare snapshot and does not create or run a new PandaAI backtest.

## Final state

- 45 positive platform records were found.
- 45/45 were rebuilt locally; 0 remain data-unavailable.
- The local pool is a 5,456-instrument `.SH/.SZ` full-A proxy, using qfq daily prices joined with `daily_basic`.
- The comparison window is 2021-09-07 through 2026-09-07, with local data from 2018-01-01, 10 groups, and 0.30% one-way cost.
- 33/45 records have an absolute RankIC difference no larger than 0.005.
- 15/45 records have an absolute net-excess difference no larger than 2 percentage points; 5/45 are within 1 point.
- Mean absolute differences are 0.00421 RankIC and 2.97 percentage points of net excess.

The full row-level comparison is generated at:

`quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a/positive_factor_local_compare.md`

The JSON file beside it contains formulas, periods, top-20 overlap, and all platform/local metrics.

## What was added

The full-A recheck now rebuilds all 45 positive records from the local Tushare snapshot:

- The platform configuration index records 171 workflows; 167 explicitly use the `沪深全A` pool label.
- qfq prices cover 2018-01-02 through 2026-09-07; `daily_basic` covers 2,107 open trading dates.
- `fina_indicator`, `income`, `balancesheet`, and `cashflow` are cached locally.
- Financial data is joined point-in-time using `ann_date`; no future report is used.
- Tushare consolidated statements (`comp_type=1`) are preferred.
- Cumulative quarterly income and cash-flow values are converted to discrete quarters and TTM values.
- BM, SP, EP, CFP, PCF, asset growth, paper composite, F-score-like, and weighted value/reversal combinations are implemented.
- The original weights are preserved, including CFP REV2/REV3, CFP VAL2/VAL3, SP, PCF, MA63, and TSRANK756 variants.

## Main findings

Switching from the fixed ST pool to the recorded full-A configuration removes the main universe-selection ambiguity, but it does not remove all gaps. Thirty of the 45 records still differ by at least 2 percentage points of net excess.

The direct price combinations are typically 3-6 points below the platform in gross excess while turnover is relatively close and period excess-return correlation is about 0.84-0.89. This points to price adjustment, forward-return labeling, suspended-row handling, or portfolio construction rather than a missing factor field.

CFP, paper-derived, and time-series value combinations remain 2-7 points below the platform. The largest discrepancies cluster around 2024-02-20 and 2024-11-08, which points to financial-field definitions, report revision/TTM treatment, or platform-specific preprocessing. It is not evidence that the factor direction is reversed.

The 2026 YTD records have only 16 periods and should not be used as equivalence tests; the largest is the size composite at -11.25 points. `OSR2-DD120` with 5-day rebalancing is a useful near-alignment control, at roughly -0.05 points.

## Known approximation boundaries

- `residual_volatility` is a market-model residual-volatility proxy, not the platform's internal Barra residual-volatility field.
- `MA(...,63)` and `TS_RANK(...,756)` use daily point-in-time Tushare ratios. The 2018 qfq and `daily_basic` extension now covers the 756-observation warmup; the current `TS_RANK756` comparison has all 241 platform chart periods.
- Platform financial fields are internal fields; the local implementation maps them to documented Tushare fields. Matching RankIC does not establish byte-for-byte field equivalence.
- The local result uses the same saved platform signal dates where available. The momentum record has no saved chart payload and uses the reference 10-day schedule.
- Two saved positive records do not have a current workflow configuration in the local registry, so their historical pool cannot be independently confirmed.

## Reproduce

After the repository and local data snapshot are available:

```powershell
python scripts/local_recheck_data.py import --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py verify
python scripts/positive_factor_local_compare.py --universe full_a --data-start 20180101 --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a --output quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a
python scripts/diagnose_positive_factor_deltas.py --universe full_a --data-start 20180101 --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a --compare-json quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a/positive_factor_local_compare.json --output quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_delta_diagnosis_full_a
```

The current LFS snapshot contains 4,836 files and about 688 MB of source data, including the full-A qfq, `daily_basic`, financial, comparison, and diagnosis caches. A Tushare token is only needed when rebuilding the snapshot with the download scripts.

The financial cache builder is:

```powershell
python scripts/tushare_financial_cache.py --start-date 20180101 --end-date 20260907 --batch-size 80 --workers 2
```

The Tushare token is supplied through the current process environment and is not stored in the repository.
