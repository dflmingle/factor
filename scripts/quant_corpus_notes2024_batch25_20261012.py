from quant_corpus_semantic_review_20261012 import add_authored
E={
'2.':('20观测归一价格斜率选ETF；RSRS18/600 z×R²阈值±.7择时。','normalized_price_slope20 + RSRS18/600。','ETF及指数日线。','etf_exact_duplicate','全部13个函数AST与已审2023/7等匹配，逐项等价证明保存在rendered_cores，不重复测试。'),
'3.':('高sales_growth10%且EPS>0后小流通市值前5，周调仓。','high sales_growth × small cap。','PIT成长/EPS、市值。','small_size_growth_exact_duplicate','全部16个函数匹配2023/21等已审实现；降序不是低增长。'),
'4.':('1板/3板候选按竞价相对昨收与连续涨停形态筛选，分钟与15分钟退出。','auction_gap + streak + intraday exit。','竞价tick、分钟与涨停行情。','call_auction_blocked','22个函数与已审2023/43完全匹配；缺竞价不能用日线替代。'),
'40.':('手选约40只股票内RSI6在(15,25)买入，RSI>85或<10卖出，按RSI升序最多持9。','RSI6 oversold bounded interval。','固定池qfq close与TA-Lib RSI。','rsi_reversal_duplicate','get_RSRS_signal实际不计算RSRS；异常分支ris拼写会保留旧rsi或未定义；固定池幸存者选择不能移植正式全A结论。'),
'41.':('沪深300当日财务技术特征预测过去约50自然日超市场收益二分类，随机森林挑5特征，再用随机森林回归当日市值取低估残差，10日换6只；指数近5自然日跌5%禁买。','RF feature selection on past returns + current market-cap prediction residual。','PIT财务、技术、每日市值，RF训练。','marketcap_ml_implementation_broken','训练StandardScaler变换X但预测原始X；特征可含市值目标自身；close列索引赋值未按code对齐，模型不作为可验证新因子。'),
'42.':('低PB候选按市值/价格/5日量/60日价格比对数加权；MA牛熊状态切换时变更保留数量，调整订单现金预扣和ST异常处理。','weighted inverse size-price-volume-return score。','财务、市值、分钟价量与市场均线。','small_size_execution_variant','19个函数与14等已审源码匹配；变更为执行/持仓问题处理，不新增经济信号。'),
'44.':('固定510500 ETF，以MA60附近±20%入初始仓；每跌5%固定2万元补仓，每回升一个网格减仓，记录成本调整。','fixed ETF grid around base price, step5%。','ETF分钟价和持仓状态。','grid_execution_not_factor','属于交易库存/成本路径，不提供股票截面排名。'),
'45.':('当日涨>5%，当前周价突破前44周高但最近3周未突破；周成交量超过前44周最大和最近3周最大且后者比率<2，按旧区间振幅升序。线性加权周MA5>MA10及上影过滤，持有分钟高点回撤15%止损。','weekly volume-confirmed breakout after consolidation; WMA5>WMA10。','周/日/分钟OHLCV；当周当前价量。','weekly_volume_breakout_candidate','EMA_ratio实际是WMA，不是EMA；买点9:32当前周量与完整历史周量相比偏时间尺度，日频改写须标适配。候选为量价突破而非确认新簇。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
