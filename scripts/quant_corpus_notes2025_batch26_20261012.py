from quant_corpus_semantic_review_20261012 import add_authored
E={
'92行':('军工/食品饮料/煤炭/银行/通信5行业内MA20上方占比最高1行业，买其10条收盘收益最差5，周调。','industry breadth top1 among5 × within-industry reversal9。','PIT行业成分/分类、日线。','industry_breadth_reversal_candidate','10条收盘是9个收益间隔；不同于5/51的银行领先清仓，这是强行业内部反转，可记录独立组合假设但未验证。'),
'93.234':('昨非一字的连续2/3/4板且更早排封板，之前90日最大连板1~3；换手<30、昨额/前额<1.875后最小自由流通市值取1，开盘低4%/8%与盈利/2日退出。','limitup_streak2~4 × turnover/amount cap × shareholder-adjusted free float size。','PIT前十大股东与总股本、涨停、分钟。','shareholder_freefloat_event_blocked','actual_turnover过滤列表计算未赋回；max_free_market_cap未用于筛选；fallback volume/circMV单位错，价格qfq与股数混用也需修正；不能以标题无未来证明代码正确。'),
'94别':('每股20天分钟开收收益用log成交量加权波动，日波动序列std/mean为UID，再截面对20日日收益波动回归残差，低值选10；市场20日均量>250日量25分位才买。','UID=std20(weighted_minute_vol)/mean20(...); residualize daily_vol20; low。','完整分钟OHLCV、点时沪深300与指数日线。','minute_volatility_stability_candidate_blocked','每日报第2~236条分钟；weighted_std中心为普通均值非加权均值；股票序列polyfit应按symbol对齐；日线无法恢复此特征。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
