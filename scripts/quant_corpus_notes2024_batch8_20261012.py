from quant_corpus_semantic_review_20261012 import add_authored
E={
'20.':('市值最小500中取满足近4日振幅<=10%、前收>EMA5、昨低>今开的一只，盘中低买高卖，日内剥头皮。','low market_cap500 + 4d range<=10% + prev_close>EMA5 + prev_low>today_open。','日/50m OHLC、市值。','microcap_intraday_blocked','单票日内执行，不适合标准日频因子；市值轴为主。'),
'21.':('宏观PMI曲线斜率、供需/库存分位和沪深300年线、MA5/10/20/30做ETF/债券切换；不是个股alpha。','PMI quadratic slope + supply-demand percentiles + index MA regime。','宏观PMI、指数/ETF/债券。','macro_timing_external_pending','宏观字段本地没有完整PIT版本；仅记录为市场开关。'),
'23.':('固定三因子线性组合price_no_fq/利润成本/存货周转，系数负，总分前10%后正EPS；与5完全同式，增加日内补仓。','same weighted composite as 2024/5。','聚宽因子、PIT EPS、市值。','ml_smallcap_composite_duplicate','不再重复测试。'),
'24.':('三组机器学习线性组合：ARBR/SGAI/利润/留存；Price1Y/成本/VOL120；负债/成本率/DAVOL20/未复权价/sales_growth，固定系数总分前10%且总分>0，正EPS小市值。','weighted composite score with fixed coefficients; top positive decile→small cap。','聚宽因子、PIT EPS、市值。','multi_composite_weighted_duplicate','与2024/1同族但系数不同；系数来源不明，市值后处理主导。'),
'25.':('全A过去5日平均收盘价排序，挑最低且均值>=1.5的首只；10:20~14:55用50分钟K线低买高卖。','lowest 5d mean close subject to mean>=1.5。','50m OHLC。','lowprice_intraday_blocked','原代码时间/逐笔执行，非日频。'),
'26.':('近1年股息率前25%，PEG代理PE/净利同比在(-3,3)，按市值升序，过滤价格高25%分位，月调仓20。','high dividend_yield1y25∩-3<PE/profit_growth<3→low market cap; exclude top25% price。','PIT分红、财务、估值。','dividend_peg_smallcap_duplicate','与19/28同族；PEG约束宽且不含正增长要求。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
