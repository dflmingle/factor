from quant_corpus_semantic_review_20261012 import add_authored
E={
'46.':('22/44/88观测收益各最高10%交集，250日曾涨停无跌停，60日上涨至少31次，昨日触板未封板，放量阳线与阴包阳过滤后筛竞价金额>100万、竞价价不低于近7日最高收盘，最多4只。','multi-horizon momentum intersection + volume-event + auction breakout。','日线OHLCV、真实涨跌停价、竞价金额与竞价价。','auction_momentum_candidate_blocked','get_score_filter返回未排序dict，实际前4不由分数决定；count10交易日[9]为昨日，均线比较并非10日前。日频动量原子可提取，竞价部分不能用当日收盘代替。'),
'47.':('中证500内最大流通市值50只；上证昨跌至少1.5%且今日14:55再跌至少1.5%买入，持有计数约19次后卖。','two-day market crash bounce × large size within CSI500。','历史成分、流通市值、指数盘中价。','market_crash_timing_duplicate','属于市场事件开关与规模选择；14:55条件无分钟数据不能原样复现，不能误称新个股alpha。'),
'48.':('宏观PMI生产订单库存曲线、分位及沪深300均线，配置股票ETF与债券。','PMI slope/supply-demand quantiles + index moving-average regime。','PIT宏观PMI、指数及ETF。','macro_timing_exact_duplicate','13函数与策略1/21完全匹配，证明见rendered_cores/5bbacbf7682f01d2.txt；本地缺完整PIT宏观。'),
'5.':('每月读取外部test_predict_300_q.pkl预测score，沪深300按score取前10%等权。','precomputed external random-forest score。','外部pickle、训练特征/标签/预测时间戳。','external_ml_exact_duplicate','6函数匹配2023/38，证明见rendered_cores/0ec7a473c32e5487.txt；源码无训练链，不能臆测特征或证明PIT。'),
'53.':('固定约34股票/ETF池，KDJ(9,3,3) J<0开约1/40初仓；跌约5%增仓，按90日最高收盘约97%目标及网格减仓。','KDJ J<0 oversold + path-dependent grid。','固定池日线OHLC、持仓与交易成本状态。','kdj_reversal_grid_duplicate','EBIT/EV、股息率、FScore定义但选股调用注释；90日high未进入活动买入阈值；reset的循环stock残留可能错配参数。固定池收益不可外推全A。'),
'58.':('最强20日ETF、纳指及国债ETF；北向最近2条净流入非负且RSRS18/600允许时以[20,20,.5]/40日截尾log收益方差分配，目标<5%清零再归一化；下午60分钟MA20止损。','inverse variance ETF allocation × northbound/RSRS market regime。','ETF日线/60分钟、北向净流入。','etf_risk_allocation_duplicate','11旧函数匹配；checktime2未调度。可记录逆方差配置，非新增个股截面簇。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
