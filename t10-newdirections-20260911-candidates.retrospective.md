# T10 New-Direction Combination Retrospective

- Window: 2021-09-07 to 2026-09-07
- Rebalance: 10 trading days
- Groups: 10
- One-way cost: 0.30%
- Baseline: `COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ`
- Baseline net excess: 16.3840%/yr
- All three results are in-sample screening results; no independent OOS test has been run.
- Cross-sectional Spearman correlation against the existing factors was not downloaded in this batch, so correlation is recorded as unmeasured rather than inferred from similar formulas.

| Candidate | Net excess %/yr | Delta vs baseline (pp) | Turnover % | Rank_IC | ICIR | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| T10-SIZE-PLUS-IMPACT | 18.1572 | +1.7732 | 30.64 | 0.1113 | 0.4524 | escalate |
| T10-SIZE-PLUS-IMPACT-WC | 17.4432 | +1.0592 | 27.36 | 0.1052 | 0.4421 | orthogonalize |
| T10-SIZE-PLUS-WC-MCAP | 14.5810 | -1.8030 | 32.07 | 0.1032 | 0.4395 | abandon |

## Interpretation

- `T10-SIZE-PLUS-IMPACT` adds the H260910-03-style 60-day intraday range divided by aggregate traded amount. It improves net excess by 1.7732 percentage points and reduces turnover versus the baseline, but it remains closely related economically to the existing chip and turnover sleeves.
- `T10-SIZE-PLUS-WC-MCAP` adds operating working capital relative to market capitalization. It reduces net excess by 1.8030 percentage points, so the new fundamental sleeve is not retained in this standalone form.
- `T10-SIZE-PLUS-IMPACT-WC` is above baseline but below the impact-only version. The working-capital sleeve does not add incremental net return in this test; retain only as a secondary candidate pending a correlation or exposure check.

The exact formulas and raw PandaAI result paths are recorded in [t10-newdirections-20260911-candidates.txt](t10-newdirections-20260911-candidates.txt) and [t10-newdirections-20260911-candidates.report.csv](t10-newdirections-20260911-candidates.report.csv).
