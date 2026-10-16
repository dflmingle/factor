from quant_corpus_semantic_review_20261012 import add_authored
E={
'57韶':('14个完整函数匹配2024策略1/34：近20日恰好1次涨停、首板形态与5日涨幅/倍量过滤后竞价买，次日尾盘退出，证据4799f51985f0b5fe。','one-limitup20 × auction gap × volume burst。','日线涨停、竞价、分钟K线与执行。','exact_201_series_duplicate','无变更函数与参数；竞价和封板时刻不可用日线冒充，不按重复文章认新因子。'),
'58Debug':('18项ETF列表含重复512100；20条收益5%~20%、MA5>MA20，收益前2买，跌出前4或过热才卖；每日轮动。','bounded momentum20 × MA5>MA20 × top2/top4 holding buffer。','ETF日线及成交。','etf_momentum_buffer_method','512100重复令索引访问可能Series、持仓/排名重复；仅涨幅过热退出，没有与入场相同的MA下穿卖；缓冲是降低换手方法非新alpha。'),
'59追':('昨日封板前两日未曾触板，均价/收盘≥.96、成交7~19亿、总市值≥70亿/流通≤520亿、左压量比>.9；竞价量比≥3%、涨幅0~6%买；11:25盈利卖或14:50退出。','first_limitup × dynamic prior-high volume ratio × auction gap/volume。','PIT涨停、竞价明细、分钟、日线量与市值。','auction_first_limitup_blocked','auction_data[0]取区间第一条不是最后成交；左压回溯跳过最近前一条高点再加5天；不能用日成交替竞价。'),
'5四':('行业MA20上方广度最高1行业为银行/有色/煤炭/钢铁则空仓，否则中小板ROE>.15/ROA>.1后最小市值10，周调。','industry breadth top1 exclusion gate × quality small size。','PIT行业、成分、财务、日线。','industry_breadth_gate_variant','与51防御一股变体有区别，此处防御为空仓；不是四行业等权因子；可做池级风险开关独立验证。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
