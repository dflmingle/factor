from quant_corpus_semantic_review_20261012 import add_authored
E={
'78首':('昨封板两支：5%涨幅/价>2.5、15日相对位≤.3且今开涨0~1%；或昨涨9~22%且开收涨>5%、30日位≤.5且今低开3~4%；前日不封板，上市60天，盘中/成本止损退出。','first-limitup low range-position × separate ST-like/nonST gap bands。','涨停、开盘、日線/分钟。','first_limitup_two_gate_execution_variant','函数filter_st实际按涨幅proxy非PIT ST；当前日daily get_price开盘/昨收在9:30的服务返回边界需核查，未使用其它当日字段不直接断言泄漏。'),
'79国':('质量正利润/收入最小市值池乘数5；过去3年审计意见3/4/5/7排除；5月分红实施公告已知预案低股息升序，其它月排实施的不分红；MA10调股数，1/4月空仓。','quality small size × audit × implementation-known dividend gate。','PIT审计/分红实施公告、财务、分钟。','audit_dividend_policy_variant','与44预案披露门槛不同、改用implementation_pub_date；仍按低股息优先且不足补回，小市值优先非硬高分红过滤。'),
'7追':('昨封板前两日未封板，均价比/成交额/市值/左压倍量与竞价量≥3%、开涨0~6.02%筛；9:28买，11:28盈利或14:50退出。','first-limitup × auction volume/gap × dynamic historical pressure volume。','竞价与涨停、日线/分钟。','auction_first_limitup_variant','与59前两日曾触板排除不同，此处前两日收盘封板；after_code_changed调度入口而非新增initialize，需平台调用约定。'),
'80基':('PB0~10/PCF<5/ROE>.3/毛利率>.3/利润增长>1.5，最小市值50中RSI14<50取10月买，RSI>70日卖。','quality/value small-size × RSI buy/sell hysteresis。','PIT财务、日线RSI。','quality_rsi_size_variant','只取15条TA-Lib RSI14相当于短初值，不是长暖机递归RSI；阈值财务单位须保留供应商尺度。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
