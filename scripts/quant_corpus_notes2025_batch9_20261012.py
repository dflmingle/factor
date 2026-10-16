from quant_corpus_semantic_review_20261012 import add_authored
E={
'3、5年':('23个函数AST复用2024策略1/13等：ROE>.15/ROA>.1、低价过滤后最小总市值，月末调仓。','quality constrained small-size; PEG/dividend inactive。','PIT财务与市值、盘中状态。','exact_quality_size_duplicate','5fa1fbf0feed6017保留完整匹配证明；标题收益不作为新增机制证据。'),
'40高':('过去连续5个365天窗口都有分红者，按最近一年股息率行业内取2；营业利润增长>0；持仓阈值3%、新买4%，最多10只周调。','five-year dividend persistence × industry top2 dividend yield × 3/4% hysteresis。','PIT分红登记、财务、申万一级行业、市值。','persistent_dividend_candidate','df.index.levels[1]未必等于分组筛选后实际index值，需remove_unused_levels核实；5年门槛是分红记录连续存在非连续增长；分红单位需核对。'),
'41SVR':('20个函数AST匹配2024策略1/66：399101股票内用财务/行业SVR拟合log市值，取负残差；RSRS18/600与指数斜率择时。','SVR log-size valuation residual × RSRS。','PIT财务、行业、指数日线。','exact_svr_size_residual_duplicate','证明d422d2e01181b097；截面拟合残差不等于样本外收益模型，未发现新原子。'),
'42国':('一年分红额>三年平均净利润30%或>5000万元筛选，再中小板5~50亿最小市值10只，周调和已审止损/季节开关。','trailing1y dividend cash > .3*mean(profit3y) OR >50m, then small size。','PIT分红/年度利润、总市值与交易状态。','dividend_policy_filter_candidate','标题三年分红，实际仅过去一年分红与三年平均利润比较；watch_date=None需PIT核查；p1/p2/is_small_to_big参数未用于分位筛选。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
