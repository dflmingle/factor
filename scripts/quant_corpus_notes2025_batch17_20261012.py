from quant_corpus_semantic_review_20261012 import add_authored
E={
'66手':('当前1000日平均成交>5000万元ETF，用239日收益向量KMeans30类每类取最早上市，再相关>.85去重并排2020后上市，绘2017起走势。','ETF return-vector clustering and correlation pruning。','ETF历史、点时上市/退市与成交。','etf_clustering_universe_method','当前日数据选池不能回填2017；union集合合并未严格并查集，重叠集合需传递闭包；可借鉴去冗余流程，不新增股票alpha。'),
'67大':('PB<1、经营流入/调整利润>10万且利润增长正，三年股息率前50%后股票名含爱/我/中/华任一字，月调。','dividend/value quality × stock-name characters。','PIT分红、名称和财务。','name_filter_spurious_composite','未设标题大市值约束；字符筛选无经济机制且可重复；不可用今天名称回填历史，不推荐该名称腿。'),
'68wy':('昨日首板排连板，60日高低相对位置≤.5，今日开盘/昨收.96~.97，空仓时等权买；11:28盈利或14:50未封板卖。','first-limitup × low range-position60 × gap −4%~−3%。','涨停/开盘、盘中执行。','known_first_limitup_gap_variant','get_hl_stock_at_time与filter_low_limits未调用；低开与卖出依赖盘中数据，不当标准10日因子收益。'),
'69“':('4ETF按25日加权趋势得分，过滤0<score≤5，否则货基，最高1日轮；其余3函数与38ETF等匹配。','bounded weighted logtrend25 × fit quality。','ETF日线。','bounded_etf_momentum_duplicate','收益得分上下界是风控约束，不把新增阈值认新簇；原持仓换仓流程已审匹配。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
