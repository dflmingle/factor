# RSQR60 local alignment test

- Formula: `Rsquare(CLOSE,60)`; handler: `rsquare60`; direction: `1`.
- Rule version: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; local universe: `full_a`; price: `qfq`; market cap join: `total_mv`.
- Window: `2021-09-07 00:00:00..2026-09-07 00:00:00`; warm-up: `20180101`; cycle: `5`; groups: `10`.
- Label: `close(t+1) -> close(t+1+cycle)`; benchmark: `factor_valid`; one-way cost: `0.30%`.
- Signal dates: `generated_calendar_due_platform_run_failure` because the PandaAI run failed and supplied no chart dates.

## Platform status

- status: `failed`
- factor_id: `6aacc75e3e7967143f8fbbdb`
- run_id: `6aacc75f3e7967143f8fbbdc`
- result status: `3`; factor_analysis: `None`
- node formula: `Rsquare(CLOSE,60)`
- error: `run: 因子分析执行失败（无详细错误信息）`
- No platform RankIC, group return, turnover, or Top20 values are available; this local result is not an alignment pass/fail comparison.

## Local result

| metric | value |
|---|---:|
| valid periods | 241 |
| mean stock count | 4938.8 |
| RankIC | 0.004256 |
| IC mean | 0.003845 |
| gross selected return | 15.36% |
| gross excess | 3.57% |
| selected-group turnover | 29.59% |
| annual turnover cost | 8.95% |
| net excess | -5.37% |
| compounded period max drawdown proxy | -30.42% |
| monthly excess win rate | 51.67% |

The max drawdown is a diagnostic from compounded 5-day selected-group returns; it is not the platform daily max-drawdown series.
