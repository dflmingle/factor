from quant_corpus_semantic_review_20261012 import add_authored
E={
'28.':('近一年分红率前25%，PEG代理PE/净利增长在(-1,3)，市值<=100且升序，价<9/交易状态过滤；月调仓10，盘中成交量>MA10三倍止盈/换手。','high dividend_yield1y25 ∩ -1<PE/profit_growth<3 ∩ market_cap<=100→low cap。','PIT分红/估值/增长、分钟成交量。','dividend_smallcap_duplicate','get_fundamentals(date=None)未来风险；市值<=100近似小盘；分红前25与19相似。'),
'29.':('全A基本过滤后PE<=30、调整利润正，计算当日与去年同期营收/利润增速，PEG=PE/(利润增速*100)<=1且营收增长>=15%，按市值升序，周调仓10。','high revenue_growth>=15%∩high profit_growth>0∩PEG<=1→low market_cap。','PIT利润/营收、估值、市值。','high_growth_smallcap_duplicate','去年同期日期连接按自然日；profit_growth分母绝对值，负利润前期可失真；与增长小市值17同轴。'),
'3.':('四ETF按25日对数回归年化收益×R²排序，每日持1只；纯ETF动量。','ETF log-price slope25 annualized×R²。','ETF收盘。','etf_momentum_duplicate','与2024/10、31同族；不转全A个股。'),
'30.':('固定137只行业股票，growth因子降序前80%，四行业内按PB行业百分位*.8+PE全池百分位*.2，取最低6买4，周调仓；涨停回避。','growth top80%∩industry PB percentile*0.8 + PE percentile*0.2 low；industry=[801180,801780,801790,801720]。','PIT growth/PB/PE、行业。','industry_growth_value_pending','固定股票清单；growth因子方向可测试但池外不可宣称；行业内PB+全池PE混排名。'),
'31.':('四ETF25日动量排序，沪深300RSRS18/600 z×R²与MA20斜率联合买卖；每日调仓。','ETF momentum25 + index RSRS18/600 AND MA20 rising/falling。','ETF/指数日线。','etf_momentum_rsrs_duplicate','与10同族，RSRS择时执行部分已多次出现；无需单独本地全A测试。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
