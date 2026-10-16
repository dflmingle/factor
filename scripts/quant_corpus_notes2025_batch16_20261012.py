from quant_corpus_semantic_review_20261012 import add_authored
E={
'63.5':('20函数匹配2024策略1/35：行业MA20广度预选后，营收增长、四增长加权、低PEG×低换手波动三腿各筛再取小流通市值，周调，证明38a87eb9ff4ec274。','sales_growth top10% / weighted_growth top10% / PEG bottom20% then turnvol bottom50%, each small size。','PIT行业/增长/PEG/换手波动、市值。','exact_smallcap_duplicate','四增长权重.10/.35/.15/.40；这些约束不是独立新簇，不能仅凭小盘收益确认增量。'),
'64大小':('月初比较沪深300最大20只与中小板最小20只10条收益，大盘领先且0~5%买白马、强于5%反切小盘，小盘领先且正买小盘，否则境外ETF池；周调，8%止损后加仓最弱幸存3只。','relative large/small momentum10 × cold/warm ROA/PB quality × small size。','PIT成分/财务、市值、ETF日线和盘中。','size_foreign_regime_execution_variant','g.stock_num=3却未用于monthly_adjustment截断，白马可6只/小盘可9只；ETF等权列表非动量轮动；亏损幸存者补仓是风险选择不是新alpha。'),
'65搭':('营收增长>30/利润>50/经营现金流利润比>10、PB>1/PE0~200后，五项log最小值/自身合成评分；144日指数low拟合动量决定每12次调用翻转规模权重；分三次买卖。','−log(turn)−sign_size*log(circMV)−log(price)−log(volume21)−log(return55_gross)。','PIT财务、市值、日线和分钟价格/当日K线。','known_five_component_low_value_variant','g.j按调用递增不是按日，一天多次选股改变权重；买前50条OHLC均价z分与仓位调整是执行；订单风控与log正值需核查。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
