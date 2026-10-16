from quant_corpus_semantic_review_20261012 import add_authored
E={
'29穿':('铁矿石主连价<MA20<MA60时退出，否则持多；月末倒数第5交易日换次近月，名义仓位权益/(价格×100)。','futures long with MA20/60 regime gate。','期货全合约、主连与保证金。','futures_roll_trend_data_blocked','股票日频缓存不能还原期货滚动与杠杆，不作为新股票排序簇。'),
'2连':('完整20个函数与2024策略1/7及/4已审源码AST精确匹配：20日最大连板筛选后VOL5排序前10，持有至少2交易日或盈利卖出。','limitup_streak_max20 × VOL5 rank。','涨停价格、成交量、盘中执行。','exact_reviewed_duplicate','精确证明rendered_cores/27fede6dc4805362.txt；不是新增因子，概念/情绪辅助函数未实际调用。'),
'30错':('中小板最小流通市值5只周更，用当前目标回溯100日等权收益造指数，10日高点跌22%恐慌；10:40低于开盘及昨收股票不超70%时买；持超10天且昨日指数跌或当日跌2%卖。','microcap drawdown22% × intraday recovery breadth。','点时市值、微盘指数重建、10:40价格。','microcap_panic_gate_state_bug','同日多次gen_small_stock_index重复乘入昨日收益；当前指数用当日价/前日pre_close基准不一致。可研究风险开关，原实现不能直接信任。'),
'31蛇':('最小流通市值20只前日收益L2归一，方差<.02且均值>0才选；上市250天、价<10、ROE>.15/ROA>.1后总市值升序取10；正浮盈和≥.4清仓。','microcap return coherence gate × quality-constrained small size。','日线、市值、PIT ROE/ROA及持仓成本。','quality_size_with_coherence_gate','get_peg名称不对应PEG；仅累计盈利持仓，负浮盈未进入清仓判定，不是组合损失止损。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
