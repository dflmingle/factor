from quant_corpus_semantic_review_20261012 import add_authored
E={
'95学':('60日ETF6维历史窗口MinMax，经CNN1D/2D、多层双向LSTM与全连接，外部model_baseline.pt得分最高3，月调。','external CNN/LSTM ensemble OHLCV tensor score。','训练代码/标签/日期及模型权重、ETF日线。','external_deep_etf_model_blocked','所谓apply/redeem实际narrow OHLC列，不证明申赎数据；已知过去窗口内MinMax非全期泄漏，但训练边界不可审计；标题完整pipeline未含训练。'),
'96首':('龙虎榜净买正且buy_rate>4、概念重叠；18日封板1~2次、后三日均量/前15日4~6倍、换手<50，按流通市值降序；开盘≥昨涨停价1.04且未封板取1，日内多时点非板卖。','billboard buying × volume burst × limitup counts × high gap。','PIT龙虎榜/概念、竞价/分钟、涨停。','billboard_concept_event_blocked','HY_sum循环stock_code却get_concept(stock)残留变量，错误复制概念；标题收益无审计依据；按流通市值最高非最小。'),
'97趋':('与74相同趋势持续/绝对相关/动量轮动，将3500日趋势池初始化及月更缓存，日内相关/得分仍每日计算。','monthly trend-persistence universe cache × daily low correlation/trend25。','ETF长日线。','etf_method_cache_variant','改变池更新频率可能改变收益但无新原子；趋势计数含三角累加，保留原定义非普通上方比例。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
