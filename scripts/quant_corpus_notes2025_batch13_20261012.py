from quant_corpus_semantic_review_20261012 import add_authored
E={
'54发':('市值最小500候选，过去5日不停牌、4日高低幅≤20%、昨收>EMA5且今日开盘<昨低，9:26买至5；13:06未涨停卖，日内涨6.5%未封板也卖。','open<lag1(low) × lag1(close)>EMA5 × range4≤20% × small size。','9:26竞价/开盘字段、日线、分钟执行。','gap_down_short_term_candidate','9:15用day_open筛选、9:26day_open可用时点需核查；高收益依赖竞价成交，不能用日收盘标签宣称复现；日频信号原子可单独适配。'),
'55怎':('5个函数与已审首板突破一进二精确匹配，保留b077baf97253423e证据。','first-limit-up next-session breakout event。','涨停日线、分钟/竞价与执行状态。','exact_first_limitup_duplicate','标题速度优化不新增选股机制；日频缺盘中成交不可恢复完整策略。'),
'56基':('行业大流通市值盈利股估计60日Sharpe、DAVOL20、长期预期增长、近25自然日北向持股比均值；行业总分升序取2；每行业个股按20日收益×量最高5日对应行业涨幅指数权和降序各取10。','industry score=−z(Sharpe60)+z(DAVOL20)−.5z(pred_growth)−z(HK_hold); stock=sum(2^(−i/4)*industry_ret_at_top5_ret_volume_days)。','PIT申万行业成分/指数、分析师长期预测、北向持股、日线。','industry_relative_event_candidate_data_blocked','北向是持股比例均值非净买额；日量/收益事件可适配但行业指数不可用全A冒充；原文外部预测字段与平台支持需核实。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
