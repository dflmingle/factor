# Huatai Multifactor Series 1-13: five-year retrospective

## Screen

- Window: 2021-09-07 to 2026-09-07
- Rebalance: 5 trading days
- Groups: 10; each result uses the direction-selected extreme decile
- Cost: 0.30% one-way, with buys and sells charged separately
- Candidates tested: 24; formula failures: 0
- Multiple-testing reference: `p < 0.05 / 24 = 0.0021`
- Account usage reported by the completed runs: 74 credits; balance after settlement: 810.185838

The full candidate table is in `huatai-series13-candidates.report.csv` and the sorted Markdown
view is in `huatai-series13-candidates.report.md`. The ranking is by long-side excess after the
turnover haircut, not by the long-short headline.

## Result

| candidate | Rank_IC | IC p | mono | long excess | turnover | annual cost | net excess | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| HT13-TURN-BIAS-1M | -0.0652 | 0.0001 | 0.87 | +11.17% | 15.68% | 4.74% | +6.43% | escalate |
| HT13-VALUE-BP | +0.0524 | 0.0985 | 0.88 | +3.36% | 4.17% | 1.26% | +2.10% | orthogonalize |
| HT13-VALUE-SP | +0.0333 | 0.4893 | 0.80 | +1.00% | 2.94% | 0.89% | +0.11% | abandon |

Only `HT13-TURN-BIAS-1M` passes both the rough multiple-testing reference and the positive
cost-adjusted long-side screen. It is a research survivor, not a validated submission: this is a
single five-year in-sample selection window and no non-overlapping out-of-sample run was done.

## Survivor review

### HT13-TURN-BIAS-1M

- Formula: `MA(TURNOVER,21) / MA(TURNOVER,504) - 1`; direction `0`
- Mechanism: stocks whose recent one-month turnover is unusually low relative to their own two-year history may have less crowded ownership and slower, more persistent return behavior.
- Factor ID: `6a9e8b253e7967143f8fa933`; run ID: `6a9e8b263e7967143f8fa934`
- Highest correlation with existing set: not measured; factor-value CSV download was not available from the result response. Its mechanism is different from the prior value/profitability composite, but no numeric orthogonality claim is made.
- Falsification test: compare relative turnover deviation with raw one-month turnover-volatility proxy.
- Result: bias proxy net excess `+6.43%` versus `HT13-TURN-STD-1M` net excess `-4.25%` at the same five-year window, cycle and cost. This supports the relative-to-history definition rather than generic low turnover dispersion, but it is not an independent holdout.
- Visible cumulative-excess curve changes before the annual cost haircut: 2023-06 to year-end `+7.06%`, 2024 `+11.56%`, 2025 `+13.13%`, 2026 through 2026-08 `+1.73%`. The curve starts in 2023 because the 504-day lookback needs a warm-up; these are chart changes, not official competition C returns.
- Decision: `escalate` to a pre-submission validation or a separately fixed competition workflow; do not tune its lookback on this same result.

### HT13-VALUE-BP

- Formula: `ratio_bm_ttm`; direction `1`
- Mechanism: high book-to-market selects cheaper stocks, matching the strongest historical value result in Huatai report 2.
- Factor ID: `6a9e891a0f6165ec8f7f33d9`; run ID: `6a9e891acffa1665a2100bcd`
- Highest correlation with existing set: not measured; likely high with `paper-derived-composite` because that existing factor explicitly contains a book-to-market component. Treat it as a value sleeve, not a new independent axis.
- Falsification test: compare BP with EP, SP and low-PCF value proxies in the same batch.
- Result: BP was the only value standalone with a material positive net result (`+2.10%`), but IC p-value `0.0985` fails the multiple-testing reference and is far weaker than the turnover-bias survivor.
- Visible cumulative-excess curve changes: 2021 partial `+1.35%`, 2022 `+13.46%`, 2023 `+4.85%`, 2024 `+10.98%`, 2025 `-12.94%`, 2026 through 2026-08 `+3.15%`. These are before the local annual cost haircut.
- Decision: `orthogonalize` against the existing composite and use only as a possible low-turnover supporting sleeve; do not submit BP alone from this screen.

## What failed the cost test

- The 20-day reversal had IC p-value below the reference and long excess `+7.21%`, but turnover `52.46%` produced net excess `-8.65%`.
- All seven selected report-11 technical Alpha formulas had positive raw long-side excess and small IC p-values, but turnover `78.14%` to `86.58%` produced net excess `-18.04%` to `-22.26%`.
- The 120-day momentum proxy had significant negative IC (`-0.0562`) and net excess `-32.86%`; its sign was adverse under direction `1` in this window.
- The style equal-rank composite had Rank_IC `+0.0667`, but turnover `20.23%` reduced net excess to `-5.71%`. Equal-weight rank combination alone did not solve the cost problem.
- Growth, TTM quality, historical percentile and low-volatility proxies were either negative after cost or statistically weak. The TTM fields and trading-day historical-rank mapping are only approximations to the report data and frequency.

## Boundary

Reports 7, 9 and 12 were registered but not falsely represented as single-formula reproductions:
Wind order-flow fields, analyst-consensus revisions and structured risk-model optimization are not
available in the PandaAI formula interface used here. Report 10's dynamic historical IC/IR and PCA
weights were reduced to the two explicitly labeled equal-rank proxies.
