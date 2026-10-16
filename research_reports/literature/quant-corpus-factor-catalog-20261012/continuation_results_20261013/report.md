# 2026-10-13 持续本地复现，按实际产物汇总

任务仍在进行，尚未穷尽可执行配方，尚未认证新的独立 alpha。用户已授权连续本地研究，无需逐轮确认；平台算力消耗0，正式池未改动。

本表纳入源码批次25起已完成审计的133个目录、484条规格记录，其中6条旧语义实现保留但排除有效排名。这是规格记录数量，包含代理、对照、窗口变体和重复项，不能解释为同数量独立因子或新簇。全库818文件源哈希一致；直接存在原子产物的来源315，不等于完整策略已回测。粗粒度执行前沿0个，不能据此判断已经跑完；仍有0个来源需要精确关联或补测、215个来源需要复核数据障碍与可用部分；57个rzrk未解码。

各列是扣除单边0.30%成本的算术年化多头净超额百分比，DD为多头扣费日频最大回撤。dual同时剥离市值和20日反转秩，triple再剥离既有低IVOL；两者是独立信息诊断，不是平台已验证公式。

| key | raw_five_net | raw_recent_net | dual_five_net | dual_recent_net | triple_five_net | triple_recent_net | raw_five_dd |
|---|---|---|---|---|---|---|---|
| threeleg77_highpe10pct_small | 18.75 | 16.97 | — | — | — | — | 46.00 |
| membership144_positivePB_priority | 18.11 | 11.08 | 7.36 | -1.52 | -5.23 | -15.02 | 44.80 |
| micro18_positivePB_literal | 18.07 | 11.23 | — | — | — | — | 44.83 |
| small43_size5_300_priority_fullA | 17.71 | 12.94 | 9.94 | 5.79 | 0.91 | -12.55 | 44.69 |
| small34_size5_50_priority_fullA | 17.71 | 12.94 | 6.19 | 0.95 | 0.07 | -15.03 | 44.69 |
| nonlinear32_lowlog_full_totalmv_proxy | 17.70 | 12.63 | 6.34 | 4.97 | 2.80 | -1.51 | 44.50 |
| smallstep50_size25_dailygate_priority | 17.16 | 12.57 | -11.11 | -30.18 | -21.34 | -27.12 | 44.73 |
| membership144_size_control | 17.13 | 12.57 | — | — | — | — | 44.73 |
| framework9_small_literal_quality | 16.99 | 6.39 | — | — | — | — | 43.93 |
| small59_PEgt1_literal | 16.91 | 7.05 | — | — | — | — | 44.29 |
| size70_no_crossunder_priority_fullA | 16.67 | 12.76 | -4.59 | -19.02 | -12.62 | -30.47 | 44.80 |
| quakecat_lowlog_full_size_proxy | 16.29 | 9.43 | 4.67 | 3.48 | 1.70 | -3.26 | 42.20 |
| lowlog2_totalmv_weights1682_proxy | 16.25 | 9.35 | 4.70 | 4.27 | 1.02 | -2.41 | 42.53 |
| partial26_PEGpm3_conditional_lowprice_priority | 16.18 | 11.38 | -18.12 | -5.28 | -17.43 | -20.31 | 43.45 |
| svr_booleanquery5_undervaluation | 15.92 | 2.61 | 1.32 | -9.01 | 3.24 | -7.55 | 42.62 |


布尔查询SVR五年约15.92%，dual约1.32%，近期dual约−9.01%，且仍有资格/市值暴露；不能当作强新簇。正PB微盘资格等原始正收益较高的新增条目仍按市值排序，属于旧风格的资格变体；纯市值残差退化不是资格无效的证据，也不能证明新独立信息。部分原始财务模型五年正收益也未在独立信息诊断中稳定保留。原先FF3风格解释比例/低IVOL稳定组合仍是既有研究候选，没有因为增加新批次而获得进池认证。

补充共同全A支持与相同基准下的资格增益，以下为相对纯SIZE的变化（pp）。正PB优先五年仅增加约0.99pp，近期减少约1.49pp；低留存正EPS、固定线性评分资格、报告ROE资格均未同时改善两个窗口。来源140资格子集的15.16%/25.31%不能作为优于全A SIZE的证据。残差退化不用于否定资格价值，此处使用实际同支持组合对照；仍未取得当前规则的正式池ΔComb证明。

| key | window | delta_net_pp | delta_dd_pp | delta_turn_pp |
|---|---|---|---|---|
| membership144_positivePB_priority | five_year | 0.99 | 0.07 | -0.04 |
| membership144_positivePB_priority | recent | -1.49 | 0.30 | -0.12 |
| membership144_lowretained_positiveEPS_priority | five_year | -5.50 | -4.31 | -0.98 |
| membership144_lowretained_positiveEPS_priority | recent | -6.28 | -0.29 | -0.59 |
| linear5_positiveEPS_topscore_priority | five_year | -3.00 | -1.02 | -0.07 |
| linear5_positiveEPS_topscore_priority | recent | -0.70 | -0.14 | -0.19 |
| FROEC28_finalmembership_priority | five_year | -6.45 | -9.62 | 3.09 |
| FROEC28_finalmembership_priority | recent | -8.58 | 0.39 | 4.17 |
| small34_size5_50_priority_fullA | five_year | 0.59 | -0.04 | -0.12 |
| small34_size5_50_priority_fullA | recent | 0.37 | 0.19 | -0.22 |
| small43_size5_300_priority_fullA | five_year | 0.59 | -0.04 | -0.12 |
| small43_size5_300_priority_fullA | recent | 0.37 | 0.19 | -0.22 |
| partial36_negativePEG_PB3_priority | five_year | -3.30 | -2.19 | 2.72 |
| partial36_negativePEG_PB3_priority | recent | -2.33 | -2.79 | 2.56 |
| partial26_PEGpm3_conditional_lowprice_priority | five_year | -0.94 | -1.28 | 1.28 |
| partial26_PEGpm3_conditional_lowprice_priority | recent | -1.19 | -1.06 | 1.61 |
| guojiu6_positiveYTDNI_revenue_size_priority | five_year | -2.22 | -1.19 | 1.20 |
| guojiu6_positiveYTDNI_revenue_size_priority | recent | -2.78 | -2.18 | 0.87 |
| smallstep50_size25_dailygate_priority | five_year | 0.03 | 0.00 | 0.10 |
| smallstep50_size25_dailygate_priority | recent | -0.00 | 0.00 | 0.00 |


现金流/净债务及现金流/总债务日频最近其它锚点已保存，覆盖1211日、13个旧锚点，未覆盖主簇全集。原始值与来源67保存信号面板逐值核对通过。加6席与换各旧席的56行双窗口诊断全部留档；加6席五年净超额均下降。旧五席来自qualitygate3保存档案，只是同支持集探索，不是当前规则的正式池重建，不推断官方Comb或排名。

| candidate | form | window | delta_net_excess_pct | delta_held_daily_max_drawdown_pct | delta_turnover_pct |
|---|---|---|---|---|---|
| ocf_netdebt_reported_high | raw | five_year | -0.01 | 0.08 | 0.02 |
| ocf_netdebt_reported_high | raw | recent | -0.53 | 0.12 | -0.34 |
| ocf_netdebt_reported_high | triple_residual | five_year | -0.60 | 0.11 | -0.11 |
| ocf_netdebt_reported_high | triple_residual | recent | 0.75 | -0.05 | 0.13 |
| ocf_debt_reported_high | raw | five_year | -1.16 | -1.21 | 0.00 |
| ocf_debt_reported_high | raw | recent | -0.26 | -0.54 | 0.13 |
| ocf_debt_reported_high | triple_residual | five_year | -0.90 | -0.70 | 0.06 |
| ocf_debt_reported_high | triple_residual | recent | 0.81 | -0.71 | 0.64 |


质量交集70/74以及Boll事件76无有效期或仅少数有效期，结果不能称五年收益，也不能把evaluate返回的0称零收益。最新CSV把0有效期的收益/回撤/换手设为缺失。有效期少于114/120的记录明确标记覆盖不足；资格子集即使期数足够，也仍单独标记基准。

65号MACD背离的199状态项与LASTgreens分支错误，已用66号更正；89号滚动XGB分组边界及概率并列门槛，已用90号更正；原文件和旧结果保留，替代标记可审计。68号SVR原gated=False元数据，在汇总中更正为True，未修改冻结历史输出。新增财务字段按原始公告截断重放，技术数据按完整日序列截断重算；未使用全样本个股标准化。

正式窗口20210907—20260907，近期窗口20260101—最新缓存20260907；保存信号最后20260810、退出20260825。全沪深A/qfq/total_mv/20180101暖机/label1/10组/factor_valid成本口径固定。行业、指数、分钟、ETF及供应商内部字段不等价部分逐条写在fidelity内；没有独立未触碰的研究样本外。大量探索之后的正收益只作待证假设。

完整结果：[all_results.csv](all_results.csv)；逐项决策：[candidate_decisions.csv](candidate_decisions.csv)；公式和来源：[all_recipes.json](all_recipes.json)。完整覆盖及未完成队列在上级exhaustive_sweep_20261013目录。
