# AlphaPROBE GFlowNet + Tushare

This is the compact, tracked result from the 10,000-episode full-A run on 2026-09-15.

- Method: AlphaPROBE GFlowNet trajectory balance with AlphaPool
- Data: local Tushare qfq prices, `daily_basic.total_mv`, and cached `amount / volume` VWAP
- Universe: `.SH` and `.SZ` full A proxy
- Label: `close(t+1) -> close(t+6)`
- Cycle: 5 trading days
- Splits: train `2021-09-07..2024-09-06`, valid `2024-09-09..2025-09-05`, test `2025-09-08..2026-09-07`
- Pool: 50 expressions

The final ensemble Rank IC was `-0.0877` on train, `-0.0900` on valid, and `-0.0572` on test. The ensemble is not a validated factor. The strongest candidate that stayed positive across all three splits was pool rank 11, with Rank IC `0.0469 / 0.0493 / 0.0280`:

```text
TsDiv(Pow(Sub(0.5,Inv($volume)),$low),20)
```

Pool rank 14 had the best test Rank IC (`0.0500`), but it was selected by looking at the test results and must not be treated as an out-of-sample winner.

Files:

- `final_pool.json`: 50 expressions and pool weights
- `factor_metrics.csv`: train/valid/test Pearson IC and Rank IC for every expression
- `training_history.json`: loss and ensemble checkpoints

To evaluate this tracked pool after restoring the local Tushare cache:

```bash
python scripts/evaluate_alphaprobe_gfn_tushare.py \
  --device cuda:0 \
  --run-dir research_reports/alphaprobe_gfn_tushare_cycle5_run2 \
  --report-output research_reports/alphaprobe_gfn_tushare_cycle5_run2
```
