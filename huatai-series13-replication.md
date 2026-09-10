# Huatai Multifactor Series 1-13: PandaAI replication register

## Common settings

- Formal screening window: 2021-09-07 to 2026-09-07 (five years)
- Rebalance cycle: 5 trading days
- Groups: 10 deciles
- One-way transaction cost used for local net calculation: 0.30%
- Long-side convention: direction `1` holds the top decile; direction `0` holds the bottom decile.
- Financial fields are TTM public-financial proxies. They are not claims of exact Wind/MRQ timing equivalence.
- `TS_RANK` uses trading-day windows; 126 and 756 days approximate two and six quarterly periods.

## Candidate register

| Candidate | Source report | Reproduction status | Direction | Parameters / interpretation |
| --- | --- | --- | --- | --- |
| HT13-VALUE-BP | 2, value | close proxy | 1 | book-to-market TTM; high is cheap |
| HT13-VALUE-EP | 2, value | close proxy | 1 | earnings yield TTM; high is cheap |
| HT13-VALUE-SP | 2, value | close proxy | 1 | sales yield TTM; high is cheap |
| HT13-VALUE-OCFP-LOW-PCF | 2, value | inverse-field proxy | 0 | operating P/CF TTM; low is high OCF yield |
| HT13-GROWTH-NP | 3, growth | close proxy | 1 | net-profit YoY growth TTM |
| HT13-GROWTH-OCF | 3, growth | close proxy | 1 | operating-cash-flow YoY growth TTM |
| HT13-REVERSAL-20D | 4, momentum | close proxy | 1 | `1 - RETURNS(CLOSE,20)`; prior-month reversal |
| HT13-MOMENTUM-120D | 4, momentum | close proxy | 1 | 120-day return; medium-term momentum |
| HT13-TURN-BIAS-1M | 5, turnover | approximation | 0 | 21-day turnover / 504-day turnover - 1; low deviation |
| HT13-TURN-STD-1M | 5, turnover | approximation | 0 | 21-day turnover standard deviation; low is preferred |
| HT13-VOL-STD-1M | 6, volatility | close proxy | 0 | standard deviation of 1-day returns over 21 days |
| HT13-QUALITY-ROE | 8, financial quality | close proxy | 1 | ROE TTM; original report preferred quarterly variants |
| HT13-QUALITY-CASH-DEBT | 8, financial quality | close proxy | 1 | operating cash flow / debt TTM |
| HT13-HIST-EP-2Q | 13, historical percentile | time-scale proxy | 1 | 126-day TS_RANK of EP |
| HT13-HIST-ROA-6Q | 13, historical percentile | time-scale proxy | 1 | 756-day TS_RANK of ROA |
| HT13-ALPHA3 | 11, technical | formula close | 1 | 10-day ranked open-volume correlation |
| HT13-ALPHA13 | 11, technical | formula close | 1 | 5-day ranked close-volume covariance |
| HT13-ALPHA15 | 11, technical | formula close | 1 | 3-day high-volume correlation summed over 3 days |
| HT13-ALPHA16 | 11, technical | formula close | 1 | 5-day ranked high-volume covariance |
| HT13-ALPHA44 | 11, technical | formula close | 1 | 5-day high-ranked-volume correlation |
| HT13-ALPHA50-TP | 11, technical | VWAP proxy | 1 | 5-day volume-typical-price correlation, 5-day max |
| HT13-ALPHA55 | 11, technical | formula close | 1 | 12-day channel position vs 6-day volume correlation |
| HT13-VALUE-EQ | 10, synthesis | rank-sum proxy | 1 | equal rank sum of BP, EP, SP and inverse PCF |
| HT13-STYLE-EQ | 10, synthesis | rank-sum proxy | 1 | equal rank sum of value, growth, quality, reversal, turnover and volatility |

## Not strict single-formula reproductions

- Report 7 funds-flow factors require the Wind order-flow database. PandaAI's formula field list does not expose the cited `mfd_*` fields; MFI/OBV would be a separate price-volume proxy, not a replication.
- Report 9 consensus-expectation factors require Chaoyang Yongxu/I/B/E/S-style analyst forecasts. Public financial growth fields are not forecast revisions and are kept separate above.
- Report 10 historical-return, RankIC, constrained IC-IR optimization and PCA weights are dynamic portfolio-level procedures. The two rank-sum candidates test only the report's equal-weight idea.
- Report 12 is a structured risk model with factor covariance, residual risk and portfolio constraints. It cannot be represented by one `factor_create --formula` expression.
- Report 1 is the framework and factor taxonomy; reports 2-13 provide the individual tests or methods represented above.

The candidate formulas themselves are in `huatai-series13-candidates.txt`; this register is the pre-backtest interpretation and does not contain performance conclusions.
