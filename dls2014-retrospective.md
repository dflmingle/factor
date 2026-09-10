# Da, Liu & Schaumburg (2014) factor test

Source: Da, Liu & Schaumburg, "A Closer Look at the Short-Term Return Reversal", Management Science (2014). The public working-paper version is "Decomposing Short-Term Return Reversal", NY Fed Staff Report 513.

## Paper signal

The paper's benchmark sorts stocks within industry on prior-month discount-rate news:

```text
DR(t) = return(t) - expected_return(t) - cash_flow_news(t)
```

The long side is the lowest prior-month DR and the short side is the highest. Its nonparametric robustness check instead buys past losers with upward earnings-forecast revisions and sells past winners with downward revisions.

## PandaAI proxies

PandaAI formula mode exposes neither I/B/E/S forecast revisions nor an industry classification. The tested proxies therefore use 20 trading days for the prior month, full-A cross-sectional ranking, and `gr_net_profit_ttm` as a public earnings-improvement proxy:

```text
standard reversal = 1 - RETURNS(CLOSE,20)
non-cash-flow proxy = RANK(1 - RETURNS(CLOSE,20)) + RANK(gr_net_profit_ttm)
```

Both used direction 1, 5-day rebalancing, 10 groups, 0.30% one-way cost, and the 2021-09-07 to 2026-09-07 screening window. The three-month probe window was 2026-01-01 to 2026-03-31.

## Results

| candidate | Rank IC | IC p-value | monotonicity | long excess | turnover | annual cost | net excess | long Sharpe | max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| standard reversal | 0.0624 | 0.0000 | 0.69 | 7.21% | 52.46% | 15.86% | -8.65% | 0.5697 | 40.64% |
| non-cash-flow proxy | 0.0434 | 0.0104 | 0.65 | 2.71% | 34.73% | 10.50% | -7.79% | 0.4715 | 37.02% |

The two-sided paper-inspired proxy is statistically below the study reference threshold p < 0.025, but its cost-adjusted long-side result is negative. The standard reversal has stronger Rank IC but materially higher turnover and is also negative after cost.

## Decision

Abandon both for the current competition pool. Keep the factor definitions and raw runs as research records. This is a China A-share proxy test, not an exact reproduction of the paper's I/B/E/S-plus-industry DR strategy, and the five-year window is a screening sample rather than independent out-of-sample evidence.

## Run records

- Standard reversal: factor `6a9e65c3fada315e619d3912`, run `6a9e65c47f3a31832eb8bd17`.
- Non-cash-flow proxy: factor `6a9e6614b2a0c66c6431019c`, run `6a9e66149a167ed86a7f1b6b`.
- Raw results: `dls2014-full-candidates.results/`.

## Additional public-fundamental proxies

To approximate the unavailable forecast revision, I also tested public TTM year-over-year growth fields without repeating the prior net-profit-only proxy:

```text
OPCF proxy = (RANK(gr_oper_profit_ttm) + RANK(gr_ocf_ttm)) / 2 - RANK(RETURNS(CLOSE,20))
broad proxy = (RANK(gr_revenue_ttm) + RANK(gr_oper_profit_ttm) + RANK(gr_net_profit_ttm) + RANK(gr_ocf_ttm)) / 4 - RANK(RETURNS(CLOSE,20))
```

| candidate | Rank IC | IC p-value | monotonicity | long excess | turnover | annual cost | net excess | long Sharpe | max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| OPCF proxy | 0.0510 | 0.0020 | 0.76 | 3.69% | 37.30% | 11.28% | -7.59% | 0.5112 | 36.75% |
| broad proxy | 0.0515 | 0.0018 | 0.71 | 2.86% | 37.56% | 11.36% | -8.50% | 0.4714 | 38.22% |

The OPCF proxy is the best of these new variants, but remains negative after the same 0.30% one-way cost assumption and is materially weaker than the existing paper-derived Composite. Decision remains abandon for the current competition pool.

- OPCF proxy: factor `6a9e68c3b2a0c66c643101a6`, run `6a9e68c3b2a0c66c643101a7`.
- Broad proxy: factor `6a9e691752393bc2bd995cb8`, run `6a9e69189a167ed86a7f1b73`.
- Raw results: `dls2014-fundamental-candidates.results/`.
