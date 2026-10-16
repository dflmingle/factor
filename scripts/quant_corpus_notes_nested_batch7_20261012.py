from quant_corpus_semantic_review_20261012 import add_authored
E={
'01首版2版龙虎榜':('14函数精确匹配已有龙虎榜首二板策略；龙虎榜与涨停回调事件，缺细节数据。','existing LHB first/second board。','PIT龙虎榜、竞价/分钟。','exact_lhb_intraday_duplicate','1335abce6451020b证明；不以moneyflow代理。'),
'02上升途中回调':('30日窗口前23日涨幅>20%，后7日从高点回撤10~20%；近3日振幅<3%、跌幅/量缩、低点不创新低且收盘不弱，09:45买；20%止盈/80%止损。','strong rise20 → 10–20% retrace + 3-day stabilization/volume contraction。','qfq日线与09:45价。','daily_pullback_stabilization_candidate','函数先定义check_stabilize_signal(prices)又重定义带context版本，调用后者；买入时price为当前盘中，不能用日收严格复现；随机备选函数未调用。'),
'03首板低开':('20函数精确匹配已有首板低开/高开混合，昨日涨停后60日位置≤.5、开盘低开约3~4.5%，盘中盈利卖。','first-board low-open pullback。','竞价/分钟/涨停。','exact_auction_duplicate','6b5877437cfb896a证明；不进日频因子池。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/首板回调买入策略2026')
