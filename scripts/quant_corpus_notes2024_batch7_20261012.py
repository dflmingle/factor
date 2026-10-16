from quant_corpus_semantic_review_20261012 import add_authored
E={
'66.':('399101中证1000内，SVR用净资产/净利/研发/PE/经营现金流及行业哑变量拟合log市值，取负残差极端；RSRS18/600+指数斜率择时开关。','SVR size residual low × RSRS timing。','PIT财务、行业、RSRS日线。','svr_residual_external_pending','同12的SVR残差变体；截面内拟合严重过拟合；不进入本地候选。'),
'68.':('业绩预告查询和利润历史可视化，未形成交易选股公式。','earnings_forecast surprise data explorer。','财务预告公告。','earnings_forecast_tool_only','默认date=datetime.today和end_date>=date查询有未来口径，仅工具。'),
'69.':('外部深度模型直接对60日K线张量输出前三股票，未使用56的16因子预筛。','deep CNN/LSTM 60d OHLC tensor score。','三个.pt模型文件。','deep_ml_external_blocked','模型权重缺失；无法复现；不提取伪因子。'),
'7.':('最近20日连续涨停次数最高股票，再按VOL5排序前10；持有至少2交易日或盈利即卖。','limitup_streak_max20 × VOL5 rank。','日涨停价/成交量。','limitup_streak_intraday_blocked','情绪/概念函数未调用；短线涨停事件，不能并入标准日频因子池。'),
'70.':('399310指数股票不筛因子，按每年资金提取、40%国债基金、5%现金、余下等权50只；资产配置策略。','index equal-weight50 + treasury allocation。','指数成分、国债基金。','asset_allocation_not_equity_alpha','无选股alpha。'),
'71.':('全A依次高净利增速10%、低EBIT40%、高ROE_TTM全量，正EPS后按小流通市值；周调仓。','high net_profit_growth10 ∩ low EBIT40 ∩ high ROE_TTM→small cap。','PIT增长/EBIT/ROE、市值。','growth_quality_smallcap_duplicate','g.sort3=False取高ROE；三腿顺序筛选；与2023/36、2024/17同轴。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
