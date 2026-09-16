# AlphaPROBE GFlowNet + Tushare: signed positive IC

This is the compact tracked result from the 10,000-episode full-A run on 2026-09-16.

- Method: AlphaPROBE GFlowNet trajectory balance with AlphaPool
- Data: local Tushare qfq prices, `daily_basic.total_mv`, and cached `amount / volume` VWAP
- Universe: `.SH` and `.SZ` full A proxy
- Label: `close(t+1) -> close(t+6)`
- Cycle: 5 trading days
- Pool: 50 expressions
- Objective: `signed_positive` (single-factor IC keeps its sign; non-positive candidates are rejected; mutual IC remains absolute)
- Device: NVIDIA GeForce RTX 3090, `cuda:0`

Final ensemble metrics:

| Split | Pearson IC | Rank IC |
| --- | ---: | ---: |
| Train | 0.0337 | 0.0913 |
| Valid | 0.0181 | 0.0794 |
| Test | 0.0066 | 0.0556 |

The previous absolute-IC run had Rank IC `-0.0877 / -0.0900 / -0.0572` on the same splits. The new positive direction is an improvement in orientation, not proof that every expression generalizes: 27 of 50 expressions have positive Pearson IC in all three splits, 22 have positive Rank IC in all three splits, and 26 have positive test Rank IC.

The compact tracked report is this directory. The full local output and checkpoints are under
`quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_run1/`;
the raw training log is beside it as
`quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_run1.training.log`.

To reevaluate the tracked pool after restoring the local Tushare cache:

```bash
python scripts/evaluate_alphaprobe_gfn_tushare.py \
  --device cuda:0 \
  --run-dir quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_run1 \
  --report-output quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_run1
```
