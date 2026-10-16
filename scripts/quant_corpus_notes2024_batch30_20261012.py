from quant_corpus_semantic_review_20261012 import add_authored
E={
'76.':('股票ETF篮子与国债，正常30/70、净值回撤2.5%后40/60、5%后50/50；指数分段均线下行或近高点跌8/15%全债。','index trend/crash gate + NAV drawdown-dependent allocation。','指数日线、ETF和组合净值。','etf_risk_control_not_alpha','回撤越深股票目标越高，不是简单降低风险；三个分段均线切片各19条，不是连续MA20。无个股排序。'),
'77.':('主板近20日收盘最大/最小>1.3且离20日最高高价<约9.1%，按幅度取前3；排除昨日极端涨跌，次日高开0~4.5%买，日内弱势退出。','high range20 near-high momentum × modest opening gap。','日线高低开收、当日开盘与分钟执行。','leader_momentum_gap_candidate','ST判断用证券代码startswith(ST)错误；可提取近高点×动量，但买入用当日开盘须延迟到当日可知时点；高换手执行收益不能套固定周期。'),
'78.':('HS300排地产、残差波动降序前80%；9项FScore>6后ROA变化>.002按变化降序；月更新池、日RSRS18/600状态迟滞阈值择时。','FScore>=7 × improving ROA, excluding bottom20% residual vol。','PIT连续财报、调整利润、增发公告、Barra残差波动。','fscore_quality_variant','并非低特质波动策略；财报TTM helper与2023/28完全一致，需确认源季度字段语义，正式用还原TTM；bool Series相加须显式转int确保计分而非逻辑OR；roa_chg里的spo_score未用。'),
'79.':('主题概念与30~500亿市值池，29观测首尾斜率年化×绝对拟合优度排名1；该股最近5自然日期计算信号衰减至少2次则卖。','endpoint log slope29 × abs(pseudo-R²); negative signal-diff count5。','历史概念成分、日线、分钟止损。','endpoint_momentum_stability_candidate','不是OLS斜率：除29而非28、截距首价，abs(R²)保留坏拟合放大；RSRS/MACD/KDJ虽计算但实际不进BUY/SELL；可提取路径稳定性，须去重同源策略2/25。'),
'8.':('MA5下穿MA10、MA20/30仍上升，成交量MA5/10约束、MACD双正且DIF略高DEA、前两日涨跌异号，次日低开后最多持1日。','trend pullback × volume retention × MACD proximity × return-sign alternation。','日线OHLCV、开盘、分钟执行。','trend_pullback_event_candidate','条件是死叉不是金叉；change_pct是涨跌幅而非主力净流入；ST过滤误在整个Series中判断字符串成员；部分日期用自然日前一日导致非交易日重复。日频原子可提取但稀疏/换手需检验。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
