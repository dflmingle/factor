from quant_corpus_semantic_review_20261012 import add_authored
E={
'27.':('上证50与小盘指数89观测log(low)斜率年化×R²决定风格；大盘腿先高流通股数50%，流动比率与ROE高于全池中位数，四季FCF>0、营业利润增长>10%、净利润高于正利润中位数两倍，低PB排序；小盘腿正ROE/增长/现金利润比后小总市值。','style=trend89(log LOW); quality value=MIN4q(OCF−capex)>0 plus growth>10%; low PB; small-cap positive-quality branch。','PIT四季财务、total_mv、circulating_cap股数、指数LOW、盘中OHLC。','style_quality_value_duplicate','circulating_cap是股数而非流通市值；四季报告口径、公告时点须对齐。风格择时不是独立个股因子，质量腿可映射已有簇。'),
'32.':('正PE/PB/ROE/增长后按总市值取最大70%；FScore>7，按ROE排序初筛；每日按低价、低5日成交量、低60观测价格比、低流通市值/总市值对数加权[2,1,1,4,4]排名，持4只。','score=−2log(price)−log(sumV5)−log(C/Cpast60)−4log(circMV)−4log(totalMV); FScore>7。','PIT财务与增发公告、日线OHLCV、分钟价、流通市值。','fscore_size_weighted_duplicate','标题非线性市值实际未调用non_linear_size；仍强规模权重。候选为空可能除零，bool相加评分需核对pandas版本；源策略风控不得混入单因子。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
