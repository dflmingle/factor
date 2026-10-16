from quant_corpus_semantic_review_20261012 import add_authored
E={
'59.':('全A仅60/00股票、价格>=5，按91日收益降序每天持10只。','RET91 high momentum with price floor。','个股日线及上市/ST过滤。','momentum_exact_duplicate','11函数完全匹配策略1/49等，证明5e88eb3a97523c8f；不是标题所暗示的新动量定义。'),
'6.':('净利润增长率最高10%，再PEG最低50%，流通市值升序取4只，每日RSRS18/600修正z阈值±.7开关。','high net_profit_growth × low PEG × small size; RSRS market timing。','PIT利润增长/PEG、流通市值、指数高低价。','growth_peg_size_duplicate','16函数已审完全匹配，活动差异为筛选顺序、参数与每日调仓；增长降序为最高，不是最低。'),
'60.':('20日ETF动量轮动，RSRS18/600 z×R²，正值但低于最近12次信号均值时退出，否则高于−.7买；13:00按60分钟MA20止损。','ETF momentum + RSRS weakening exit + intraday MA20。','ETF和指数日线、60分钟。','etf_rsrs_execution_variant','g.checktime2未调度；不新增股票截面公式。'),
'61.':('固定ETF池，MA60连续两次不降、价格低于MA60且MA5转升买首只；均线交叉卖，最多1持仓。','long-trend pullback recovery: rising MA60 & C<MA60 & rising MA5。','ETF日线。','etf_pullback_candidate','可提取趋势内反转条件，但不是已实测新簇；2:00/3:00调度和固定池执行需核查。'),
'62.':('用50ETF期权与插值Shibor调用外部CVIX模块算VIX/skew；60日滚动85/20分位触发指数择时与未来收益分组研究。','option-implied VIX/skew quantile market regime。','全期权链、期限/行权价/无风险曲线、缺失scr与data_service模块。','option_implied_volatility_blocked','核心CVIX类不在该源码；不能用历史波动率冒充隐含波动率，也不能当现成个股因子。'),
'63.':('生猪主力tick突破开盘±5日平均高低差×.5~.7，MACD方向及牧原5观测涨跌确认，多空持仓止损止盈。','intraday range breakout × MACD × related-equity return。','期货主力映射、tick、日线及关联股票。','futures_tick_cta_blocked','5日高低总振幅>10%禁开仓；g.std初始化0且未更新，止损/止盈实际均受5%下限支配；MA仅改突破系数。可提取跨资产确认思路，缺期货tick不能原样复现。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
