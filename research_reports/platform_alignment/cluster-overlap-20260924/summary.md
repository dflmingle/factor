# GP 新候选 × 2026-09-19 旧分簇：相关重叠检查

- 口径：signal-date 面板 → 按日横截面 Spearman 算术平均；阈值 `|rho| >= 0.8`；每日最少 100 只股票；窗口 2021-09-07 至 2026-08-10（120 个信号日，沪深全 A，qfq + total_mv）
- 快速通道为整日矩阵（同日秩、共同有效集）近似；`|rho| >= 0.6` 的配对已用逐日 pairwise-complete 逐对重算（重算 582 对）
- 新候选 205/253 条成功物化；旧簇成员 84/107 条成功物化
- 簇口径：2026-09-19 all-factor 扩充分簇（B01-B12 / N01-N33），可见复合因子仅注释、不构成簇；未入簇成员命中记作 `未入簇`
- 未物化：候选 48 条、成员 23 条；其中本地缺字段 58 条、本地不支持的平台算子/宏/语法 13 条
- 缺失字段：bs_accu_depr, bs_bond_payable, bs_fin_lease_payable, bs_inventory, bs_total_cur_assets, cfd_surplus_cash_multi_ttm, cfs_fix_asset_depr, current_assets, current_liabilities, deferred_expense_amortization, ev_no_cash_lf, ev_no_cash_lyr, ev_no_cash_ttm, ev_to_ebitda_lyr, fixed_asset_depreciation, gr_revenue_ttm, gr_roe_ttm, inputs, inventory, is_biz_tax_surchg, is_oth_affecting_tp, is_total_profit, lease_liabilities, long_term_liabilities_due_one_year, oper_roa_net_ttm, oper_roe_adj_ttm, ratio_ev_ebitda_lyr, ratio_ev_ebitda_ttm, ratio_ev_no_cash_ebit_ttm, ratio_ev_no_cash_lf, ratio_ev_no_cash_ttm, sales_tax
- 本地不支持的平台算子/宏/语法（示例：AS_FLOAT, BIAS, RSI, TS_ZSCORE, beta, literature, profitability, residual_volatility）；明细见 `panels/failures_shard*.tsv`

## 分档结果

| 换手档 | 条数 | 重发现(任一成员>=0.80) | 部分重叠(0.60-0.80) | 全新(<0.60) | max abs(rho) | 中位 abs(rho) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 40_60 | 72 | 23 | 18 | 31 | 1.000 | 0.701 |
| 30_40 | 22 | 13 | 7 | 2 | 0.941 | 0.807 |
| le30 | 58 | 19 | 0 | 39 | 1.000 | 0.455 |
| gt60 | 53 | 1 | 6 | 46 | 0.850 | 0.202 |

## `40_60` 档 Top12（按 net_y2026 降序）

| # | candidate | net | turnover | net_y2026 | corr_size | max abs(rho) | 最近旧成员 | 旧簇 | >=0.80 成员数 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |
| 1 | cand0000 | 0.1249 | 0.4365 | 0.2770 | 0.330 | 0.333 | SIZE-ONLY-20260911 | B01 | 0 |
| 2 | cand0001 | 0.0481 | 0.4861 | 0.1288 | 0.029 | 0.061 | REPORT-HIST-ASSETTURN-6Q-10D-20260910 | N30 | 0 |
| 3 | cand0002 | 0.1446 | 0.5536 | 0.1107 | 0.848 | 0.825 | SIZE-ONLY-20260911 | B01 | 1 |
| 4 | cand0003 | 0.1049 | 0.4533 | 0.1013 | 0.478 | 0.501 | VERIFY-G260910-13 | B01 | 0 |
| 5 | cand0004 | 0.0624 | 0.4114 | 0.0956 | 0.038 | 0.554 | OSR3-RET40-BP-INTERACT | 未入簇 | 0 |
| 6 | cand0005 | 0.0778 | 0.4359 | 0.0936 | 0.022 | 0.051 | OSR-DD20-20D | N20 | 0 |
| 7 | cand0006 | 0.1352 | 0.4531 | 0.0897 | 0.774 | 0.807 | T10-ADD-G13-20260911 | 未入簇 | 2 |
| 8 | cand0007 | 0.1274 | 0.4011 | 0.0865 | 0.806 | 0.828 | F-NET01-PLAT-20260914 | B06 | 1 |
| 9 | cand0009 | 0.0935 | 0.4054 | 0.0792 | 0.718 | 0.705 | SIZE-ONLY-20260911 | B01 | 0 |
| 10 | cand0010 | 0.1510 | 0.4015 | 0.0750 | 1.000 | 1.000 | SIZE-ONLY-20260911 | B01 | 1 |
| 11 | cand0011 | 0.1047 | 0.4246 | 0.0737 | 0.590 | 0.869 | T10-ADD-DOWNSIDE-IMPACT-20260911 | 未入簇 | 5 |
| 12 | cand0013 | 0.1165 | 0.4242 | 0.0695 | 0.335 | 0.287 | H03-T10-SINGLE | B01 | 0 |

候选公式：

1. `cand0000` `Inv(Sub(a_share_market_val,TsStd(TsMax(is_operate_profit,10),30)))`
2. `cand0001` `Div(Div(Div(Div(Div(TsSkew(oper_total_asset_turnover_ttm,50),cal_20d_amt_ma),bs_total_assets),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)`
3. `cand0002` `Div(Div(Div(Div(Div(Div(ratio_bm_lyr,lma3),cal_5d_max_high_idx),bs_total_assets),cal_20d_vol_std),qtyr_5_20),bs_total_assets)`
4. `cand0003` `Div(Div(Div(Div(davol5,cal_30d_ret_vol_corr),cal_20d_amt_ma),amount),bs_total_assets)`
5. `cand0004` `Div(Div(Div(TsDelta(TsSum(book_to_market_ratio_lf,10),40),bbiboll_down),cal_20d_amt_ma),bs_total_assets)`
6. `cand0005` `Div(Div(Div(Div(Div(Div(TsSkew(TsMinMaxDiff(ratio_bm_ttm,40),50),vma250),cal_20d_amt_ma),bs_total_assets),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)`
7. `cand0006` `Div(Div(Div(Div(ratio_bm_lyr,bbiboll_down),cal_20d_amt_ma),bs_total_assets),TsRank(sp_ratio_ttm,30))`
8. `cand0007` `Div(Div(Div(Div(ratio_bm_lyr,bbiboll_down),cal_20d_amt_ma),Ref(rsi6,20)),bs_total_assets)`
9. `cand0009` `Div(Div(Div(Div(ratio_bm_lyr,TsMinDiff(ratio_peg_ttm,40)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)`
10. `cand0010` `Inv(Greater(a_share_market_val,TsDiv(TsSkew(TsMad(TsMinMaxDiff(cal_5d_return,50),10),10),10)))`
11. `cand0011` `Div(Inv(macr1),amount)`
12. `cand0013` `Div(Div(Div(TsCorr(asi,vma3,30),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)`

## 旧簇吸并情况

| 旧簇 | 被命中次数（|rho|>=0.80 的候选×成员对） |
| --- | ---: |
| B01 | 78 |
| 未入簇 | 43 |
| B06 | 3 |
| N01 | 1 |

## 失败候选（本地缺字段，未参与比较）

| idx | band | 错误 | 公式 |
| ---: | --- | --- | --- |
| 8 | 40_60 | KeyError: 'PandaAI field cfs_fix_asset_depr is unavailable in the local cache: catalog-fie | `Inv(Greater(a_share_market_val,TsStd(TsDelta(cfs_fix_asset_depr,40),30)))` |
| 12 | 40_60 | KeyError: 'PandaAI field is_biz_tax_surchg is unavailable in the local cache: catalog-fiel | `Div(Div(Div(Log(is_biz_tax_surchg),Ref(TsMinDiff(cal_5d_vol_net_chg,40),40)),cal_20d_amt_ma),bs_total_assets)` |
| 15 | 40_60 | KeyError: 'PandaAI field is_biz_tax_surchg is unavailable in the local cache: catalog-fiel | `Div(Div(Div(Div(Div(TsSum(TsDiv(matrix,30),20),Log(is_biz_tax_surchg)),cal_20d_amt_ma),bs_total_assets),cal_20` |
| 24 | 40_60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(TsIr(TsMax(TsPctChange(ev_no_cash_ttm,30),20),30),Ref(TsSum(bbiboll_down,40),40)),cal_20d_amt_ma),` |
| 27 | 40_60 | KeyError: 'PandaAI field ratio_ev_no_cash_ttm is unavailable in the local cache: catalog-f | `Div(Log(ratio_ev_no_cash_ttm),amount)` |
| 29 | 40_60 | KeyError: 'PandaAI field is_oth_affecting_tp is unavailable in the local cache: catalog-fi | `Div(Div(Div(Div(Div(TsSkew(is_oth_affecting_tp,20),cal_20d_amt_ma),cal_20d_amt_ma),bs_total_assets),qtyr_5_20)` |
| 30 | 40_60 | KeyError: 'PandaAI field ratio_ev_no_cash_ebit_ttm is unavailable in the local cache: cata | `Sub(ratio_ev_no_cash_ebit_ttm,amount)` |
| 31 | 40_60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Div(Div(Sign(ev_no_cash_ttm),Log(is_biz_tax_surchg)),cal_20d_amt_ma),TsRank(bbiboll_up,10)),cal_20` |
| 32 | 40_60 | KeyError: 'PandaAI field current_assets is unavailable in the local cache: source column i | `Inv(Sub(a_share_market_val,TsDelta(TsCov(amp60,current_assets,20),40)))` |
| 39 | 40_60 | KeyError: 'PandaAI field is_biz_tax_surchg is unavailable in the local cache: catalog-fiel | `Div(Div(Div(TsSkew(TsMin(TsPctChange(Pow(cal_30d_max_high_ratio,lma20),40),10),20),Log(is_biz_tax_surchg)),cal` |
| 45 | 40_60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),Log(is_biz_tax_surchg)),cal_20d_amt_ma),TsStd(TsMax(TsMinDiff(udl,10),40),40)` |
| 49 | 40_60 | KeyError: 'PandaAI field is_biz_tax_surchg is unavailable in the local cache: catalog-fiel | `Div(Div(Rank(lwr2),cal_20d_amt_ma),Log(is_biz_tax_surchg))` |
| 52 | 40_60 | KeyError: 'PandaAI field fixed_asset_depreciation is unavailable in the local cache: sourc | `Div(Div(Div(Div(TsIr(Greater(Pow(TsIr(davol10,40),TsIr(cal_5d_turnover_sum,20)),TsCov(TsSkew(fixed_asset_depre` |
| 53 | 40_60 | KeyError: 'PandaAI field ev_no_cash_lyr is unavailable in the local cache: derived-field i | `Inv(TsVar(ev_no_cash_lyr,20))` |
| 59 | 40_60 | KeyError: 'PandaAI field long_term_liabilities_due_one_year is unavailable in the local ca | `Inv(Sub(a_share_market_val,TsStd(TsWMA(TsMax(long_term_liabilities_due_one_year,20),40),30)))` |
| 65 | 40_60 | KeyError: 'PandaAI field ev_no_cash_lf is unavailable in the local cache: derived-field in | `Div(TsDiv(TsMaxDiff(vol10,50),10),TsMin(TsVar(ev_no_cash_lf,10),20))` |
| 78 | 40_60 | KeyError: 'PandaAI field inventory is unavailable in the local cache: source column is abs | `Sign(TsPctChange(inventory,50))` |
| 84 | 40_60 | KeyError: 'PandaAI field bs_fin_lease_payable is unavailable in the local cache: catalog-f | `Inv(Sub(a_share_market_val,TsStd(Ref(TsWMA(bs_fin_lease_payable,20),30),30)))` |
| 90 | 30_40 | KeyError: 'PandaAI field bs_accu_depr is unavailable in the local cache: catalog-field inp | `Inv(Sub(market_cap_3,TsDelta(TsVar(TsWMA(bs_accu_depr,10),20),10)))` |
| 91 | 30_40 | KeyError: 'PandaAI field is_oth_affecting_tp is unavailable in the local cache: catalog-fi | `Inv(Greater(a_share_market_val,Ref(TsVar(is_oth_affecting_tp,20),10)))` |
| 93 | 30_40 | KeyError: 'PandaAI field ratio_ev_no_cash_ttm is unavailable in the local cache: catalog-f | `Inv(Greater(a_share_market_val,TsMad(ratio_ev_no_cash_ttm,30)))` |
| 94 | 30_40 | KeyError: 'PandaAI field bs_inventory is unavailable in the local cache: catalog-field inp | `Inv(Greater(a_share_market_val,TsMinMaxDiff(bs_inventory,20)))` |
| 96 | 30_40 | KeyError: 'PandaAI field ratio_ev_no_cash_ttm is unavailable in the local cache: catalog-f | `Inv(Greater(a_share_market_val,TsCov(TsSum(TsMax(ratio_ev_no_cash_ttm,20),20),TsDiv(TsIr(ema30,10),10),30)))` |
| 97 | 30_40 | KeyError: 'PandaAI field lease_liabilities is unavailable in the local cache: source colum | `Inv(Sub(a_share_market_val,TsStd(TsMin(lease_liabilities,50),30)))` |
| 98 | 30_40 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),TsStd(lwr2,30)),cal_20d_amt_ma),Log(is_biz_tax_surchg))` |
| 101 | 30_40 | KeyError: 'PandaAI field bs_bond_payable is unavailable in the local cache: catalog-field  | `Div(Div(Div(Div(Div(Div(ratio_bm_lyr,vma250),cal_20d_amt_ma),bs_total_assets),Add(TsIr(hma30,10),TsRank(bs_bon` |
| 116 | 30_40 | KeyError: 'PandaAI field bs_fin_lease_payable is unavailable in the local cache: catalog-f | `TsRank(bs_fin_lease_payable,20)` |
| 119 | 30_40 | KeyError: 'PandaAI field is_biz_tax_surchg is unavailable in the local cache: catalog-fiel | `Div(Div(TsMinMaxDiff(SLog1p(Ref(TsSum(bbiboll_down,40),40)),40),cal_20d_amt_ma),Log(is_biz_tax_surchg))` |
| 120 | 30_40 | KeyError: 'PandaAI field current_liabilities is unavailable in the local cache: source col | `Div(Div(Div(Sub(current_liabilities,cal_30d_close_std_ratio),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)` |
| 121 | 30_40 | KeyError: 'PandaAI field is_total_profit is unavailable in the local cache: catalog-field  | `Div(Div(Div(Div(Div(Div(ratio_bm_lyr,vma250),cal_20d_amt_ma),cal_20d_amt_ma),TsWMA(TsDelta(TsEMA(is_total_prof` |
| 123 | 30_40 | KeyError: 'PandaAI field bs_total_cur_assets is unavailable in the local cache: catalog-fi | `Sign(TsMaxDiff(bs_total_cur_assets,50))` |
| 147 | le30 | KeyError: 'PandaAI field ev_to_ebitda_lyr is unavailable in the local cache: derived-field | `Sign(ev_to_ebitda_lyr)` |
| 148 | le30 | KeyError: 'PandaAI field ev_to_ebitda_lyr is unavailable in the local cache: derived-field | `Sign(Sign(ev_to_ebitda_lyr))` |
| 149 | le30 | KeyError: 'PandaAI field ratio_ev_ebitda_lyr is unavailable in the local cache: catalog-fi | `Sign(Sign(ratio_ev_ebitda_lyr))` |
| 150 | le30 | KeyError: 'PandaAI field deferred_expense_amortization is unavailable in the local cache:  | `Sign(deferred_expense_amortization)` |
| 151 | le30 | KeyError: 'PandaAI field bs_fin_lease_payable is unavailable in the local cache: catalog-f | `Sign(SLog1p(TsMax(TsVar(bs_fin_lease_payable,40),20)))` |
| 191 | gt60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),cal_30d_price_vol_corr),Log(is_biz_tax_surchg)),cal_20d_amt_ma)` |
| 199 | gt60 | KeyError: 'PandaAI field ratio_ev_no_cash_lf is unavailable in the local cache: catalog-fi | `Div(Div(Div(TsStd(TsStd(TsMinMaxDiff(Ref(ratio_ev_no_cash_lf,50),50),20),10),cal_20d_amt_ma),qtyr_5_20),bs_tot` |
| 202 | gt60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),TsEMA(TsDelta(cal_daily_rise,50),10)),cal_20d_amt_ma),bs_total_assets)` |
| 209 | gt60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),TsSkew(ratio_peg_lyr,10)),cal_20d_amt_ma),bs_total_assets)` |
| 211 | gt60 | KeyError: 'PandaAI field sales_tax is unavailable in the local cache: source column is abs | `Div(Div(Div(TsDiv(TsCorr(cal_5d_close_std_ratio,sales_tax,30),40),cal_20d_amt_ma),bs_total_assets),bs_total_as` |
| 216 | gt60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),Div(dpo,madkx)),cal_20d_amt_ma),Log(is_biz_tax_surchg))` |
| 218 | gt60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Div(Sign(ev_no_cash_ttm),bbiboll_down),cal_20d_amt_ma),TsMinDiff(davol20,50))` |
| 219 | gt60 | KeyError: 'PandaAI field oper_roe_adj_ttm is unavailable in the local cache: catalog-field | `Div(Div(Div(Div(TsCov(Div(ratio_bm_lyr,cal_20d_vol_std),ema10,10),oper_roe_lyr),cal_20d_amt_ma),oper_roe_adj_t` |
| 221 | gt60 | KeyError: 'PandaAI field lease_liabilities is unavailable in the local cache: source colum | `Div(Div(TsCorr(Greater(TsCorr(Div(oper_roe_diluted_adj_ttm,lease_liabilities),Constant(2.0),40),osc),cal_20d_a` |
| 222 | gt60 | KeyError: 'PandaAI field current_assets is unavailable in the local cache: source column i | `Inv(Greater(a_share_market_val,TsStd(TsDelta(TsMin(current_assets,20),40),30)))` |
| 235 | gt60 | KeyError: 'PandaAI field ev_no_cash_ttm is unavailable in the local cache: derived-field i | `Div(Div(Sign(ev_no_cash_ttm),cal_20d_amt_ma),wr)` |
| 241 | gt60 | KeyError: 'PandaAI field is_biz_tax_surchg is unavailable in the local cache: catalog-fiel | `Div(Div(TsPctChange(TsMad(mfi,20),50),Log(is_biz_tax_surchg)),cal_20d_amt_ma)` |

## 结论与局限

- 在可物化的 205 条新候选里，56 条与至少一个旧簇成员 `|rho| >= 0.80`（重发现），31 条落在 0.60-0.80（部分重叠），118 条低于 0.60（旧分簇未见）。
- `rho` 是逐日横截面 Spearman 的信号层相关，不是 PnL 相关；与 2026-09-19 分簇使用同一统计量、同一阈值。
- 本次未使用平台算力；两侧公式均为本地物化，缺本地 catalog 字段的候选无法参与比较（见上表）。
