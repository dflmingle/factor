# Tested Good Factors Index

Generated from the saved PandaAI report files and the E/F/G/H result blocks supplied from the PandaAI backtest interface.

## Selection rule

- Main list: completed five-year result with net excess return greater than 0 after 0.30% one-way cost.
- Standard local runs use 10 groups; the listed cycle is the rebalance cycle.
- YTD-only results are separated and are not ranked against five-year results.
- Repeated runs with different cycles are retained. Exact or near-exact economic duplicates are marked in notes instead of being counted as independent alpha.
- The H formulas are in [h260910-batch.txt](h260910-batch.txt), and the E/F/G formulas are in [field-scan-260910-user-batch.txt](field-scan-260910-user-batch.txt).

## H260910 batch

These are the positive rows from the 15-candidate H batch. The supplied C-ranking subset was H12, H13, H05.

| Supplied C order | Candidate | Rank_IC | ICIR | Net excess %/yr | Decision |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | H260910-12 | 0.0715 | 0.2772 | 16.2645 | escalate |
| 2 | H260910-13 | 0.0632 | 0.2766 | 10.4100 | escalate |
| 3 | H260910-05 | 0.0587 | 0.3136 | 17.5436 | escalate |
| -- | H260910-01 | 0.0469 | 0.2757 | 13.9604 | escalate |
| -- | H260910-02 | 0.0513 | 0.2971 | 17.2735 | escalate |
| -- | H260910-03 | 0.0530 | 0.3073 | 17.9224 | escalate |
| -- | H260910-04 | 0.0476 | 0.2824 | 14.6529 | escalate |
| -- | H260910-10 | 0.0227 | 0.2166 | 1.5132 | escalate |
| -- | H260910-11 | 0.0524 | 0.2995 | 17.5675 | escalate |
| -- | H260910-14 | 0.0520 | 0.3017 | 16.9794 | escalate |
| -- | H260910-15 | 0.0489 | 0.2877 | 15.7782 | escalate |

Full H-batch results and formulas: [h260910-batch-results.md](h260910-batch-results.md).

## User-reported E/F/G batch

All rows below were reported as five-year, 5-day, 10-group, 0.30% one-way-cost PandaAI results. Only the source block supplied Rank_IC and ICIR for the rows shown; missing statistics are kept as `--`.

| Batch | Candidate | Direction | Rank_IC | ICIR | Net excess %/yr |
| --- | --- | ---: | ---: | ---: | ---: |
| E | E260910-04 | 1 | 0.0670 | 0.2637 | 17.7951 |
| E | E260910-14 | 1 | -- | -- | 17.0381 |
| E | E260910-15 | 1 | -- | -- | 14.8251 |
| E | E260910-10 | 1 | -- | -- | 14.1620 |
| E | E260910-11 | 1 | -- | -- | 6.7107 |
| E | E260910-13 | 1 | -- | -- | 1.7271 |
| E | E260910-03 | 1 | -- | -- | 1.5353 |
| E | E260910-05 | 0 | -- | -- | 0.7030 |
| F | F260910-12 | 1 | 0.0662 | 0.2597 | 15.4589 |
| F | F260910-14 | 1 | -- | -- | 14.9289 |
| F | F260910-01 | 1 | -- | -- | 14.6590 |
| F | F260910-15 | 1 | -- | -- | 13.6458 |
| F | F260910-11 | 0 | -- | -- | 3.7672 |
| F | F260910-10 | 1 | -- | -- | 3.0792 |
| F | F260910-09 | 1 | -- | -- | 1.7913 |
| F | F260910-13 | 1 | -- | -- | 1.0699 |
| F | F260910-06 | 1 | -- | -- | 0.2156 |
| G | G260910-13 | 1 | 0.0442 | 0.2612 | 14.1905 |
| G | G260910-01 | 1 | 0.0569 | 0.2521 | 13.1180 |
| G | G260910-12 | 1 | -- | -- | 12.9620 |
| G | G260910-11 | 1 | -- | -- | 12.8259 |
| G | G260910-14 | 1 | -- | -- | 12.7380 |
| G | G260910-10 | 1 | -- | -- | 11.7852 |
| G | G260910-15 | 1 | -- | -- | 11.5150 |
| G | G260910-06 | 1 | -- | -- | 7.1361 |

## Other saved full-window results

These are completed positive rows from the local PandaAI report files, excluding the duplicate `VERIFY` runs for E/F/G and excluding YTD-only observations.

| Candidate | Cycle | Rank_IC | ICIR | Net excess %/yr | Source |
| --- | ---: | ---: | ---: | ---: | --- |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | 10d | 0.1104 | 0.4527 | 16.3840 | [report](combo-direct-4factor-size-20260909-candidates.report.md) |
| COMBO-DIRECT-OSR2-CHIP-TURN-PAPER-EQ | 10d | 0.1150 | 0.4386 | 12.7744 | [report](combo-direct-4factor-paper-20260909-candidates.report.md) |
| COMBO-DIRECT-OSR2-CHIP-TURN-EQ | 10d | 0.1010 | 0.4039 | 8.6624 | [report](combo-direct-3factor-20260909-candidates.report.md) |
| COMBO-DIRECT-OSR2-CHIP-EQ | 10d | 0.0955 | 0.3591 | 7.8761 | [report](combo-direct-20260909-candidates.report.md) |
| NEW-VALUE-EVEBITDA | 10d | 0.0202 | 0.1731 | 3.3196 | [report](high-potential-5-20260910-candidates.report.md) |
| paper-derived-composite | 5d | 0.0597 | 0.2221 | 11.4088 | [report](paper-derived-full.report.md) |
| paper-derived-composite | 10d | 0.0717 | 0.2696 | 11.2023 | [report](paper-derived-composite-cycle10-candidates.report.md) |
| paper-derived-asset-growth | 5d | -0.0115 | -0.1111 | 0.7650 | [report](paper-derived-full.report.md) |
| OSR2-RET40-TURN-BIAS-PAPER-EQ | 10d | 0.1148 | 0.4456 | 11.6436 | [report](osr2-ret40-turn-bias-paper-composite-cycle10-candidates.report.md) |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ | 10d | 0.1015 | 0.3612 | 5.2247 | [report](osr2-ret40-turn-bias-paper-nomcap-cycle10-candidates.report.md) |
| OSR2-RET40-TURN-BIAS-EQ | 10d | 0.0987 | 0.4228 | 7.3960 | [report](osr2-ret40-turn-bias-composite-cycle10-candidates.report.md) |
| OSR2-RET40 | 10d | 0.0908 | 0.3602 | 5.0310 | [report](positive-cycle10-candidates.report.md) |
| OSR2-DD120 | 10d | 0.0405 | 0.2085 | 4.2462 | [report](positive-cycle10-candidates.report.md) |
| HT13-TURN-BIAS-1M | 10d | -0.0737 | -0.3612 | 4.9621 | [report](positive-cycle10-candidates.report.md) |
| HT-WREV-LOWTURN-21D | 10d | 0.0998 | 0.4790 | 2.7123 | [report](turnover-cost-cycle10-candidates.report.md) |
| HT13-TURN-BIAS-1M | 5d | -0.0652 | -0.3172 | 6.4284 | [report](huatai-series13-candidates.report.md) |
| HT13-TURN-BIAS-1M-POS | 5d | 0.0653 | 0.3173 | 6.3953 | [report](huatai-turn-bias-positive.report.md) |
| HT13-VALUE-BP | 5d | 0.0524 | 0.1068 | 2.0990 | [report](huatai-series13-candidates.report.md) |
| HT13-VALUE-SP | 5d | 0.0333 | 0.0446 | 0.1109 | [report](huatai-series13-candidates.report.md) |
| NONHT-CHIP-COST-250 | 10d | 0.0677 | 0.2694 | 4.2793 | [report](nonht-report-directions-20260909-formula.report.md) |
| NONHT-FSCORELIKE-REV40 | 10d | 0.0697 | 0.3681 | 1.8244 | [report](nonhuatai-factor-6-20260909.report.md) |
| NONHT-FSCORELIKE-REV40-INTERACT | 10d | 0.0743 | 0.3348 | 1.8428 | [report](literature-rankic-optimization-20260909-formula.report.md) |
| NONHT-RESVOL-LOW | 10d | 0.0884 | 0.2831 | 0.3709 | [report](nonhuatai-factor-6-20260909.report.md) |
| OSR2-RET40 | 5d | 0.0731 | 0.2718 | 1.0300 | [report](oversold-rebound-recovery-candidates.report.md) |
| OSR2-DD60 | 5d | 0.0303 | 0.1736 | 1.9485 | [report](oversold-rebound-recovery-candidates.report.md) |
| OSR2-DD120 | 5d | 0.0329 | 0.1841 | 4.7915 | [report](oversold-rebound-recovery-candidates.report.md) |
| OSR3-RET40-BP-EQ | 5d | 0.0844 | 0.2820 | 3.1604 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-REV2 | 5d | 0.0843 | 0.2973 | 2.4776 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-VAL2 | 5d | 0.0760 | 0.2408 | 3.1676 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-CFP | 5d | 0.0670 | 0.2646 | 3.5609 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-EP-CFP | 5d | 0.0605 | 0.1833 | 0.1380 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-MA63 | 5d | 0.0793 | 0.2707 | 2.4111 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-TSRANK756 | 5d | 0.0715 | 0.2558 | 1.6427 | [report](osr3-ret40-value-candidates.report.md) |
| OSR3-RET40-BP-INTERACT | 5d | 0.0848 | 0.2928 | 2.7260 | [report](osr3-ret40-value-candidates.report.md) |
| OSR4-RET40-BP-CFP-REV2 | 5d | 0.0758 | 0.2881 | 2.3675 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-REV3 | 5d | 0.0773 | 0.2896 | 1.6347 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-VAL2 | 5d | 0.0550 | 0.2198 | 3.5587 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-VAL3 | 5d | 0.0493 | 0.1950 | 3.3073 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-MA63 | 5d | 0.0640 | 0.2538 | 2.5895 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-TSRANK756 | 5d | 0.0652 | 0.2587 | 2.4613 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-SP | 5d | 0.0640 | 0.2193 | 2.8768 | [report](osr4-ret40-value-refine-candidates.report.md) |
| OSR4-RET40-BP-CFP-PCF | 5d | 0.0600 | 0.2335 | 2.6686 | [report](osr4-ret40-value-refine-candidates.report.md) |

## YTD-only observations

These are retained for history but are not part of the five-year ranking.

| Candidate | Window | Rank_IC | ICIR | Net excess %/yr | Source |
| --- | --- | ---: | ---: | ---: | --- |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ-2026YTD | 2026 YTD | 0.0819 | 0.1810 | 10.7269 | [report](combo-direct-4factor-size-2026-ytd-candidates.report.md) |
| OSR2-RET40-TURN-BIAS-PAPER-EQ-2026-YTD | 2026 YTD | 0.0888 | 0.1279 | 7.6993 | [report](osr2-ret40-turn-bias-paper-2026-ytd-candidates.report.md) |
| OSR2-RET40-TURN-BIAS-PAPER-NOMCAP-EQ-2026-YTD | 2026 YTD | 0.0682 | 0.0622 | 4.6727 | [report](osr2-ret40-turn-bias-paper-nomcap-2026-ytd-candidates.report.md) |

## Interpretation notes

- The local report files contain the exact formulas for the local workflows; the two newly saved user-reported batches contain their formulas in the linked `.txt` files.
- `H260910-01` through `H260910-05`, `H260910-10`, `H260910-11`, `H260910-14`, and `H260910-15` are mostly variants of the same price-impact/liquidity hypothesis. H12 combines that family with value; H13 is its low-traded-value baseline.
- `F260910-12`, `G260910-01`, `G260910-11`, `G260910-12`, `G260910-14`, and `G260910-15` reuse the G13 price-impact component. They should not be counted as independent discoveries.
- The positive rows are screening results, not official pool-level C scores and not independent out-of-sample validation.
