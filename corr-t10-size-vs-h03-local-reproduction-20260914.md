# Local reproduction of PandaAI factor correlation

This is an offline reproduction using cached Tushare data. It does not contact PandaAI or spend compute credits.

## Platform reference

- Workflow: `6aa371b551cdfe29b2e0bc34`; run: `6aa371b5ecb163ea7228d004`; correlation task: `3e07308fd6664f1096e128d2bc6b70c3`.
- Node: `FactorCorrelationCalculationControl`.
- Window: `2021-09-07..2026-09-07`.
- Saved platform correlation: `0.4151352929`.

## Inputs

### T10-SIZE

```text
(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP)))) / 4
```

### H03-T10-SINGLE

```text
RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))
```

## Local calculation

The primary calculation intersects valid T10-SIZE and H03 values on each date, computes the cross-sectional correlation across stocks, and takes the arithmetic mean across dates. Pandas average ranks are used for Spearman ties.

| Calculation | Local value | Delta vs platform | Daily observations |
|---|---:|---:|---:|
| Daily cross-sectional Spearman mean | 0.416293 | 0.001158 | 1211 |
| Daily cross-sectional Pearson mean | 0.426838 | 0.011703 | 1211 |
| Pooled Spearman over all stock-day rows | 0.423267 | 0.008132 | 5368681 rows |
| Pooled Pearson over all stock-day rows | 0.433262 | 0.018127 | 5368681 rows |

The closest local result is `daily_cross_sectional_spearman_mean` at `0.4162929759`, with a signed difference of `+0.0011576830`.

## Data and fidelity

- Universe: `沪深全A`; qfq prices; `daily_basic.total_mv`; local warm-up starts `2018-01-01`.
- Loaded `9,401,373` rows for `5,456` instruments; valid pair rows: `5,368,681` across `1,211` dates.
- Mean valid stocks per date: `4433.26`.
- Market-field sources recorded by the loader: `{'high_qfq': 'cached', 'low_qfq': 'cached', 'amount': 'cached'}`.
- Correlation does not use the forward-return label, rebalance cycle, grouping, turnover, or transaction cost.
- A close match identifies the most likely aggregation method; it does not establish byte-level equivalence of PandaAI's internal data and missing-row handling.

## Reproduction

```bash
python scripts/replicate_platform_correlation.py
```

Artifacts: `/data/games/factor_/corr-t10-size-vs-h03-local-reproduction-20260914.json`, `/data/games/factor_/corr-t10-size-vs-h03-local-reproduction-20260914.daily.csv`.
