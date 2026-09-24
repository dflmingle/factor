# High-IC composite seat search (2026-09-23)

- rule version: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate3`
- members: 55; composites searched: 0; turnover cap 14% per rebalance
- local vs platform S_i on the 54 known singles: corr 0.982, MAE 0.00185

## Pool scenarios (top 12 by proxy Comb)

| tag | members | NA | NB | NC | Comb | net 5y | turnover/rebalance | pool S |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+growth_revenue+f_i10_01 | 0.241 | 0.446 | 1.000 | 0.654 | 23.43% | 14.67% | 0.02675 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact | 0.262 | 0.427 | 0.999 | 0.651 | 22.89% | 15.16% | 0.02564 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact | 0.261 | 0.427 | 0.999 | 0.651 | 22.89% | 15.16% | 0.02564 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact | 0.261 | 0.427 | 0.999 | 0.651 | 22.89% | 15.16% | 0.02564 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+growth_roe+f_i10_01 | 0.242 | 0.434 | 1.000 | 0.650 | 24.50% | 14.79% | 0.02607 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact | 0.253 | 0.427 | 0.999 | 0.649 | 22.89% | 15.16% | 0.02564 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+asset_growth+f_i10_01 | 0.233 | 0.437 | 1.000 | 0.649 | 23.74% | 14.25% | 0.02620 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+impact_abs_return60+growth_revenue | 0.236 | 0.429 | 1.000 | 0.647 | 22.72% | 14.64% | 0.02573 |
| replace-SIZE | size_only+t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+asset_growth | 0.227 | 0.434 | 1.000 | 0.647 | 23.37% | 14.48% | 0.02601 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+quality_net_margin_tsrank378+f_i10_01 | 0.244 | 0.423 | 1.000 | 0.647 | 24.26% | 15.33% | 0.02540 |
| add-6th | size_only+t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+asset_growth | 0.223 | 0.434 | 1.000 | 0.646 | 23.37% | 14.48% | 0.02601 |
| replace-SIZE | t10_size_plus_impact_bm+book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact+f_i10_01 | 0.259 | 0.412 | 1.000 | 0.646 | 24.30% | 14.06% | 0.02474 |

## Top single composites by local S_i (turnover <= cap)

| selection | size | S_i 5y | S_i recent | rank_ic 5y | ic_ir 5y | win 5y | turnover/rebalance | net 5y |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| book_to_market_lf_minus_size+impact60 | 2 | 0.01932 | 0.00638 | 0.0817 | 0.3502 | 0.675 | 9.35% | 20.90% |
| impact60+book_to_market_lf_plus_impact | 2 | 0.01901 | 0.00605 | 0.0785 | 0.3586 | 0.675 | 9.49% | 19.26% |
| book_to_market_lf_minus_size+impact60+book_to_market_lf_plus_impact | 3 | 0.01885 | 0.00519 | 0.0827 | 0.3421 | 0.667 | 9.27% | 19.82% |
| book_to_market_lf_minus_size+impact60+book_to_market_lf_div_oper_main_profit_ttm | 3 | 0.01833 | 0.00752 | 0.0772 | 0.3393 | 0.700 | 8.31% | 16.87% |
| book_to_market_lf_plus_impact+f_i10_01 | 2 | 0.01829 | 0.00619 | 0.0786 | 0.3408 | 0.683 | 8.93% | 20.83% |
| impact60+book_to_market_lf_plus_impact+book_to_market_lf_div_oper_main_profit_ttm | 3 | 0.01808 | 0.00818 | 0.0759 | 0.3488 | 0.683 | 8.35% | 16.78% |
| size_only+impact60+book_to_market_lf_plus_impact | 3 | 0.01802 | 0.00724 | 0.0757 | 0.3398 | 0.700 | 8.55% | 21.26% |
| book_to_market_lf_minus_size+impact60+impact_abs_return60 | 3 | 0.01802 | 0.00743 | 0.0751 | 0.3426 | 0.700 | 8.75% | 21.19% |
| book_to_market_lf_minus_size+f_i10_01 | 2 | 0.01801 | 0.00546 | 0.0782 | 0.3289 | 0.700 | 9.18% | 22.04% |
| impact60+book_to_market_lf_plus_impact+paper_composite | 3 | 0.01766 | 0.00425 | 0.0818 | 0.3320 | 0.650 | 9.39% | 19.05% |
| size_only+book_to_market_lf_minus_size+impact60 | 3 | 0.01766 | 0.00659 | 0.0754 | 0.3304 | 0.708 | 9.08% | 22.56% |
| impact60+paper_composite | 2 | 0.01742 | 0.00409 | 0.0789 | 0.3396 | 0.650 | 9.74% | 19.98% |
| book_to_market_lf_minus_size+impact60+paper_composite | 3 | 0.01740 | 0.00396 | 0.0827 | 0.3278 | 0.642 | 9.47% | 19.32% |
| impact60+book_to_market_lf_plus_impact+impact_abs_return60 | 3 | 0.01713 | 0.00781 | 0.0725 | 0.3499 | 0.675 | 9.28% | 19.70% |
| impact60+book_to_market_lf_div_oper_main_profit_ttm+paper_composite | 3 | 0.01710 | 0.00604 | 0.0761 | 0.3329 | 0.675 | 8.61% | 16.48% |
