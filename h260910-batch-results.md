# H260910 PandaAI Batch

This file records the result block supplied from the PandaAI backtest interface. It is a platform-result record, not a new local rerun.

- Formal window: 2021-09-07 to 2026-09-07
- Effective chart intersection reported by the platform: 2021-09-09 to 2026-08-26
- Rebalance: 5 trading days
- Groups: 10
- One-way cost: 0.30%
- Direction: 1 for the batch; H260910-13 embeds the low-traded-value preference with a negative rank
- Selection rule for the good-factor index: net excess > 0 after the stated cost

| IC rank | Candidate | Hypothesis | Rank_IC | ICIR | Net excess %/yr | Turnover % | Annual cost % | Decision |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 10 | H260910-01 | 60d median price impact | 0.0469 | 0.2757 | 13.9604 | 7.34 | 2.2196 | escalate |
| 7 | H260910-02 | 60d aggregate return impact | 0.0513 | 0.2971 | 17.2735 | 6.04 | 1.8265 | escalate |
| 4 | H260910-03 | 60d intraday range impact | 0.0530 | 0.3073 | 17.9224 | 5.25 | 1.5876 | escalate |
| 9 | H260910-04 | 60d overnight gap impact | 0.0476 | 0.2824 | 14.6529 | 7.53 | 2.2771 | escalate |
| 3 | H260910-05 | 60d downside impact | 0.0587 | 0.3136 | 17.5436 | 8.09 | 2.4464 | escalate |
| 14 | H260910-06 | net cash / market cap | -0.0070 | 0.0121 | -2.0250 | 4.15 | 1.2550 | abandon |
| 15 | H260910-07 | interest expense / revenue | -0.0029 | -0.0230 | -1.3625 | 2.72 | 0.8225 | abandon |
| 12 | H260910-08 | bounded internal funding ratio | 0.0092 | -0.0031 | -1.1038 | 3.65 | 1.1038 | abandon |
| 13 | H260910-09 | financing cash flow / assets | -0.0082 | -0.0907 | -2.1358 | 6.17 | 1.8658 | abandon |
| 11 | H260910-10 | absolute price-change scale control | 0.0227 | 0.2166 | 1.5132 | 4.52 | 1.3669 | escalate |
| 5 | H260910-11 | 10% capped return impact | 0.0524 | 0.2995 | 17.5675 | 6.06 | 1.8325 | escalate |
| 1 | H260910-12 | book-to-market + intraday impact | 0.0715 | 0.2772 | 16.2645 | 5.64 | 1.7055 | escalate |
| 2 | H260910-13 | low traded-value baseline | 0.0632 | 0.2766 | 10.4100 | 6.68 | 2.0200 | escalate |
| 6 | H260910-14 | intraday impact delayed 1d | 0.0520 | 0.3017 | 16.9794 | 5.26 | 1.5906 | escalate |
| 8 | H260910-15 | intraday impact delayed 5d | 0.0489 | 0.2877 | 15.7782 | 5.33 | 1.6118 | escalate |

The supplied C-ranking subset was H260910-12, H260910-13, and H260910-05 in that order. Numeric C ranks were not included in the source block; the numeric column above is the platform-reported IC rank.

The exact definitions are in [h260910-batch.txt](h260910-batch.txt). H01-H05 and H10-H15 are variants of the price-impact/liquidity family; H06-H09 are a separate financial-cash-flow branch.
