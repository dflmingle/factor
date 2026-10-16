from quant_corpus_semantic_review_20261012 import add_authored
E={
'50分':('38个函数AST精确复用已审小碎步分钟突破来源，全部等价证明35558fa6c4307dff。','minute small-step consolidation breakout。','分钟OHLCV、竞价/涨停与执行数据。','exact_minute_breakout_duplicate','日频无法原样复现分钟事件；不以重复文章扩大候选分母。'),
'51“四':('行业MA20上方占比最高行业非银行/有色/煤炭/钢铁时买002质量小盘5只，否则PB<1、经营流入/调整利润正且ROA>.15按ROA降序只持1只。','industry breadth leadership gate × small-quality / value-quality regimes。','PIT行业、日线、财务。','industry_breadth_regime_candidate','不是“最高四行业”而是最高1行业与4类做成员判断；经营流入非净现金流；防御腿max_hold_stocknum=1易集中。'),
'52机':('滚动300交易日每30日采样，9段收益标签取截面最高/最低各10%训练XGB；5流动性/量价特征预测前20%，交易过滤后按ROA降序取20，月调。','XGB(liquidity,VDIFF,VEMA26,WVAD,money_flow20) → ROA。','供应商流动性/量价字段精确定义、PIT财务、分钟过滤。','rolling_ml_features_pending','训练最后标签到上一日，未见显式越界未来；仍需时间分组验证，不能随机CV；使用当前日分钟过滤，不能当作前日已知信息；尺度/货币流字段不可凭名假造。'),
'53TS':('399317股票内PB>0、inc_return>0、ocf_to_revenue>0，最小市值120候选，持仓每只目标1%，旧仓在120名内不卖，现金够1.5个单位才加。','quality positive gates × small-size rank100/120 holding buffer。','PIT财务、市值、指数成分、盘中可交易状态。','small_size_buffer_portfolio_method','候选120/目标100降低边界换手可借鉴；未直接调整旧仓到1%，实际持股数量与权重随漂移变化；inc_return不能替ROE。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
