from quant_corpus_semantic_review_20261012 import add_authored
E={
'84正':('全A股息率最高25%后PEG在−3~3取最小市值，月初选择10；盘中涨停卖后若有旧仓且不足10补股，最近卖出不重买。','high dividend top25% × bounded PEG × small size × replenishment rules。','PIT分红/PE/利润增长、市值、盘中。','peg_size_replenishment_variant','PEG可负，不是正盈利增长价值约束；ROE/PB虽查询不用于过滤；补买在卖出前执行，今日卖后的补仓实际等下一日。'),
'85稳':('5腿ETF初始12.5/12.5/25/25/25%，月线MACD切科创/纳指/红利/黄金/国债；红利年内跌超6%切国债，国债与货基两腿固定；年初清仓重置。','monthly MACD regime × YTD drawdown gate × defensive allocation。','ETF月线、日线与持仓账本。','etf_defensive_allocation_method','unit1M是月线非分钟；非定期目标权重再平衡，换腿用当时全部现金可能污染腿资金；不能推断股票alpha。'),
'86手':('ETF上市2021前且当前存续，300日额>1000万，449日收益KMeans24类每类最老，相关>.85集合去重；输出候选池。','ETF clustering24 × correlation pruning。','ETF历史与PIT可交易池。','etf_clustering_variant','与66同方法换参数；silhouette_score把cluster_id列也作为特征导致评分污染；当前选池不能用于过去回测，未输出策略收益。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
