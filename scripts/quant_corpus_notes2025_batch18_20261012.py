from quant_corpus_semantic_review_20261012 import add_authored
E={
'6国':('沿用国九正利润/营收质量小盘，市值10~1e8亿、MA10乖离调3~6只、周调；1/4月货基与9%成本止损/5%市场止损；审计默认关。','small size × positive quality × seasonal/position-count gates。','PIT财务、成分、市值、分钟。','known_smallcap_quality_execution_variant','new_num==0分支按已有函数不会触发；名义上限1e8亿实际不起约束，非新增大小市值信号。'),
'70动':('20日调：审计/收入利润/分红过滤后小市值10%，XGB拟合当期截面过去20日涨跌筛特征，GMM1~10 BIC选最大簇，三组交叉保形回归流通市值，实际与预测差/实际排序；平均区间宽<1.4取负残差3只否则反向5只。','conformal cross-sectional circMV residual with width-dependent sign。','PIT财务/分红/审计、供应商技术因子、日线。','conformal_valuation_residual_candidate_bugged','财务列改名净利增长与毛利率错位；技术dict.values/价格list无股票键连接证据；g.if_trade_stoploss==False非赋值；width阈值在截面MinMax尺度上；当期涨跌标签非未来收益，须验证增量，不能称时间样本外预测。'),
'71（':('股票40%低价正EPS小盘+三年股息增长，商品30%与QDII30%按250日最小方差分配；QDII价/NAV<1.1降序前10；成本亏3.82%退出。','small size/dividend blend × ETF minimum-variance allocation。','PIT财务/分红、ETF NAV与日线。','stock_etf_allocation_framework_bugged','free_stock_position实际等于ETF候选数，初期0可能除零；hold_stock_num可负；QDII成交过滤DataFrame仅置NaN未删行；NAV筛选降序偏最高溢价，不是低折价。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
