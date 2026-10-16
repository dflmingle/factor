from quant_corpus_semantic_review_20261012 import add_authored
E={
'21【':('前两日未触板的昨日首板，昨日VWAP/收盘×1.1−1>=7%、金额>=7亿、市值>=70亿、左压放量且竞价量>=昨量3%、高开0~6%买；分时阶梯止损与尾盘未封板卖。','first-board continuation × auction volume × left-overhang breakout。','真实竞价/涨停与分钟、OHLCV、市值。','auction_first_board_variant_blocked','9:30同时间调买/卖顺序须确认，get_call_auction起止等于当前时刻可能空；已有三模式中高开腿，未证明新簇。'),
'22带':('四核心ETF25观测趋势排名1，持仓昨日跌>=4%止损；同只重新入场需昨收>=MA4。','ETF trend25 + one-day crash/re-entry guard。','ETF日线、持仓状态。','etf_trend_stop_variant','cur2max10/cur2max100算而未用；换到新ETF不受sel_worth门槛，回撤控制只在继续持同一ETF时应用。'),
'23大':('沪深300月线MACD正时退出个股转300ETF，负时持PB在0~1、市值>500亿、ROA>.15且1年Beta<.7的高ROA股票5只。','monthly market MACD switch; large deep value quality × low beta。','指数月线、个股PIT财务和日收益。','quality_value_low_beta_candidate','unit=1M为月线不能误作1分钟；beta对两个reset整数索引收益直接cov未按日期连接，停牌/缺失会错配；本地修正需标proxy。'),
'25冷':('中小板总市值最小14候选周持7，1/4月空仓，指数昨日均价跌6%或个股亏12%卖出，涨停延卖并回补。','small total_mv × market stop/calendar overlay。','指数成分、日线和盘中。','small_size_stop_variant','EPS虽query但无正值筛选；HV_control False，其成交量峰退出未启用；filter_highprice_stock未调用。市场/执行overlay不视为新增alpha。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
