from quant_corpus_semantic_review_20261012 import add_authored
E={
'47.':('外部predict.csv每日给出股票预测值，取前5，MinVariance240优化权重；不包含预测因子构造。','external ML prediction top5 + min variance optimizer。','缺predict/target CSV和训练特征。','ml_external_blocked','MAE滚动误差算出但未用于排序；两次initialize定义；无法提取可验证因子。'),
'48.':('创业板/中证1000指数内市值升序前100，过滤ST/涨跌停/上市不足250日，取前5每日调仓。','low circulating_market_cap100→smallest5 within399101。','日市值、交易状态、历史成分。','smallcap_size_duplicate','filter_new_stock条件方向错误：start_date-current_date<=250几乎保留所有老股；纯市值轴。'),
'49.':('全A仅60/00股票，价格>=5，按91日收益降序取10只，每日调仓。','RET91 momentum top10 with price floor。','日收盘、股票池。','momentum91_pending','get_momentum用min_dict误取最小收益而非最大，源码实际反转腿；需分别保留原执行和意图适配。'),
'5.':('三个固定机器学习线性组合：price_no_fq、利润成本比、存货周转，系数均负，总分前10%后正EPS小市值；每周调仓。','weighted composite of price_no_fq, profit/cost, inventory_turnover; coefficients fixed negative。','聚宽因子、PIT EPS/市值。','ml_smallcap_composite_duplicate','系数训练数据/样本外不可见；与2024/1同类复合，价格和市值主导。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
