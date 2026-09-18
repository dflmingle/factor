# Orthogonal fundamental net-excess candidates

This is a local Tushare reproduction using the canonical alignment rules. No
PandaAI factor was created or run in this round.

## Fixed research settings

- Window: `2021-09-07..2026-09-07`, 241 aligned 5-day signal dates.
- Universe: 沪深全A, qfq prices, `total_mv`, label offset `1`, 10 groups.
- Cost: `0.30%` one-way, `0.60%` round-trip.
- Search objective: annualized top-decile gross excess minus turnover cost.
- Candidate independence screen: maximum absolute daily cross-sectional Spearman
  correlation below `0.45` against the existing positive-net set.

## Candidate records

| Candidate | Formula | Full net | Early net | Late net | Turnover | Max abs corr | Closest existing handler | Decision |
|---|---|---:|---:|---:|---:|---:|---|---|
| F-NET01 | `1 / CONTRACT_LIABILITIES_LYR` | 5.33% | 2.40% | 10.95% | 1.16% | 0.4300 | `value_sp` | escalate |
| F-NET02 | `1 / NET_PROFIT_PARENT_COMPANY_TTM` | 5.17% | 6.30% | 2.59% | 2.99% | 0.2298 | `size_only` | escalate |
| F-NET03 | `1 / REF(EV_NO_CASH_TTM,10)` | 3.91% | 3.71% | 3.48% | 3.27% | 0.3020 | `size_only` | escalate |
| F-NET04 | `RETURNS(CONTRACT_LIABILITIES_LYR,30)` | 1.61% | 2.47% | 0.36% | 8.66% | 0.0576 | `asset_growth` | observe |
| F-NET05 | `BOOK_TO_MARKET_RATIO_LF` | 0.68% | n/a | n/a | 4.03% | 1.0000 | `value_bm` | abandon: duplicate |
| F-NET06 | `CURRENT_ASSETS_LYR / MA(CURRENT_ASSETS_LYR,50)` | -0.63% | n/a | n/a | 9.55% | 0.1803 | `asset_growth` | abandon: negative net |

The complete pairwise matrix is in
`research_reports/platform_alignment/gp-candidates-vs-positive-20260915-signal.pairs.csv`.
The GP report and coverage details are in
`quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare/orthogonal-fundamental-net-fast-20260915/`.
