# AlphaPROBE GFlowNet + Tushare: signed positive IC with fundamentals

This is the compact tracked result from the 10,000-episode full-A run on 2026-09-16.

- Method: AlphaPROBE GFlowNet trajectory balance with AlphaPool
- Data: local Tushare qfq prices, `daily_basic.total_mv`, cached `amount / volume` VWAP, and PIT/TTM financial data
- Universe: `.SH` and `.SZ` full A proxy
- Label: `close(t+1) -> close(t+6)`
- Cycle: 5 trading days
- Pool: 50 expressions
- Objective: `signed_positive` (non-positive single-factor IC is rejected; mutual IC remains absolute)
- Device: `cuda:0`
- Expression warmup: 512 trading days, covering nested 50-day operators in the 20-token action space

## Ensemble comparison

The baseline is the previous 10,000-episode signed-positive run with price/volume fields only. Both runs use the same split dates and alignment contract.

| Split | Baseline Pearson IC | Fundamental Pearson IC | Delta | Baseline Rank IC | Fundamental Rank IC | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 0.03366 | 0.03679 | +0.00313 | 0.09135 | 0.12126 | +0.02992 |
| Valid | 0.01809 | 0.04046 | +0.02237 | 0.07940 | 0.09384 | +0.01443 |
| Test | 0.00662 | 0.01413 | +0.00750 | 0.05560 | 0.06950 | +0.01390 |

The fundamental run has positive test Rank IC for 25/50 expressions. 20/50 have positive Pearson IC in all three splits, and 16/50 have positive Rank IC in all three splits. These are research diagnostics, not a cost-adjusted portfolio result or a guarantee of future performance.

## Top test Rank IC expressions

Values below are Rank IC for train / valid / test. The complete 50-row result is in `factor_metrics.csv`.

| Pool rank | Train | Valid | Test | Expression |
| ---: | ---: | ---: | ---: | --- |
| 39 | 0.05417 | 0.06893 | 0.05452 | `Sub(2.0,$volume)` |
| 6 | 0.05683 | 0.08635 | 0.04875 | `TsDiv($book_to_market_ratio_lf,40)` |
| 48 | 0.04801 | 0.07231 | 0.03532 | `Sub($close,TsDelta($market_cap_3,30))` |
| 5 | 0.04357 | 0.05112 | 0.03178 | `Sub(TsMin($high,10),$low)` |
| 45 | 0.03910 | 0.01897 | 0.02906 | `Inv($ps_ratio_ttm)` |
| 18 | 0.02134 | 0.03144 | 0.02550 | `TsMaxDiff($ps_ratio_ttm,40)` |
| 35 | 0.02056 | 0.02142 | 0.02187 | `TsMaxDiff($vwap,10)` |
| 19 | 0.05244 | 0.01331 | 0.02087 | `Div($book_to_market_ratio_ttm,Mul(Pow($low,2.0),SLog1p(TsRank($ev_ttm,20))))` |
| 3 | 0.04974 | 0.04704 | 0.01776 | `TsIr($book_to_market_ratio_ttm,50)` |
| 25 | 0.03050 | 0.01621 | 0.01551 | `TsCorr($volume,Rank(Less(Less(-2.0,Pow(Abs($net_profit_deduct_non_recurring_pnl_ttm),Less(Sub(0.5,$volume),-5.0))),2.0)),50)` |

## Named fields

The run explicitly searched these 17 local fields:

`market_cap_3`, `pb_ratio_ttm`, `pb_ratio_lf`, `book_to_market_ratio_ttm`, `book_to_market_ratio_lf`, `ps_ratio_ttm`, `ev_ttm`, `revenue_ttm`, `operating_revenue_ttm`, `net_profit_ttm`, `net_profit_deduct_non_recurring_pnl_ttm`, `total_assets_ttm`, `total_liabilities_ttm`, `equity_parent_company_ttm`, `cash_flow_from_operating_activities_ttm`, `gross_profit_ttm`, `profit_from_operation_ttm`.

`net_profit_deduct_non_recurring_pnl_ttm` and `gross_profit_ttm` are explicitly labelled local proxies in the metadata; the remaining fields are direct or PIT-derived mappings documented by the local coverage report.

## Reproduction

After restoring the local Tushare cache, run:

```bash
python scripts/alphaprobe_gfn_tushare.py \
  --device cuda:0 \
  --feature-set fundamental_core \
  --backtrack-days 512 \
  --output quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_fundamental_run2 \
  --pool-capacity 50 \
  --n-episodes 10000 \
  --trajectories-per-episode 1 \
  --log-freq 1000 \
  --update-freq 128

python scripts/evaluate_alphaprobe_gfn_tushare.py \
  --device cuda:0 \
  --run-dir quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_fundamental_run2 \
  --report-output quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_fundamental_run2
```

The failed 64-day-warmup attempt is preserved separately as `...fundamental_run1`; it is not included in these results.
