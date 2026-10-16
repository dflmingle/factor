from quant_corpus_semantic_review_20261012 import add_authored
E={
'04首板低开策略代码提速':('18函数匹配旧首板低开策略，竞价低开与盘中止盈清仓。','first-board low-open intraday。','竞价/分钟/涨停。','exact_auction_duplicate','7fd5a3566e0b9cf7证明。'),
'05追首板':('21函数匹配首板追涨框架，昨日涨停与竞价高开，盘中止损。','first-board chase auction。','竞价/分钟/涨停。','exact_auction_duplicate','be67de268a395f75证明。'),
'06首板低开策略2025':('14函数匹配首板低开策略，日内开盘和11:28退出。','first-board low-open intraday。','竞价/分钟/涨停。','exact_auction_duplicate','688cf3703e89a682证明。'),
'07-首板回调n日介入':('首板后3交易日内回撤8%至12%、收盘站MA10；低点止损、风险距离2倍止盈。','first-limit-up then 8–12% pullback above MA10。','涨停事件/日内价格。','daily_pullback_candidate_time_issue','14:50才发现首板并用当日close，存在时点错配。'),
'08上升趋势-回档买入':('MA5>MA20，近10日回撤5~15%，ATR14/价≤5%，价在MA5上；随机抽样最多200，每次买一只10%仓，死叉/止损/跟踪止损退出。','trend MA5>MA20 × pullback5–15% × low ATR14。','日线OHLCV。','random_execution_candidate','随机抽样不可复现且只交易首个合格股。'),
'09涨停回调止盈止损':('过去10日曾涨停但≤2次，连续站MA10并MA5回收、放量1.3倍、均线距>1%、近5日回撤>5%；止盈10~15%、止损3%。','recent limit-up × MA reclaim × volume surge × pullback。','日线涨停价/OHLCV。','limitup_pullback_daily_candidate','可提取日频原子，需PIT涨停价和现有回调簇去重。'),
'实10-首板竞价三模式':('14函数匹配首板竞价三模式。','first-board auction three modes。','竞价/分钟/涨停。','exact_auction_duplicate','bdf8bacf0e430458证明。'),
'实11-红利涨停轮动':('股息率前25%后质量/PEG筛选，月调并盘中补仓。','dividend yield25% × quality/PEG × limit-up execution。','PIT分红/财务/分钟。','dividend_limitup_intraday_blocked','e7f5162c232eede9证明；方向和PIT需核。'),
'聚宽使用说明':('聚宽平台使用指南，无策略公式。','无。','无。','platform_user_guide_no_factor','不计候选。'),
'01龙头股-最高板':('连续涨停天数接近全市场最高，再按市值/成交量因子排序，持3；分层止盈止损。','limit-up streak near maximum × low market cap/volume ranking。','PIT涨停、因子值、日内。','leaderboard_intraday_blocked','c6368034f819b942证明；最高板是事件型且竞价执行，不能日频标准池。'),
'02涨停板多头策略-25年负':('昨日涨停股票中要求MA5>MA10>MA20>MA60且收盘站MA5，按小市值排序，持5；止盈止损。','limit-up yesterday × multi-MA alignment × low market cap。','PIT涨停/均线/市值。','limitup_ma_daily_candidate','4d3be69c31630c05证明；策略标题负收益，和已有涨停趋势重叠。'),
'02涨停板多头策略-优化版':('昨日涨停后，5日涨幅<20%、距MA20<10%、近3日首次多均线金叉，竞价不超过昨收+5%，按市值排序；分段止盈。','limit-up × recent multi-MA golden cross × early-stage filter。','PIT涨停/日线/竞价。','limitup_ma_intraday_candidate','代码仅部分函数新，竞价和order时点需核；仍是已有涨停趋势族。'),
'03-234板介入':('2~4连板候选，最大连续板≤4，按自由流通市值小者，指数MA/涨停广度环境门控，成交额上限15%并止损。','multi-limit streak2–4 × low free float cap × market breadth veto。','PIT涨停、自由流通股东、日内。','multi_board_intraday_blocked','86fc068374b9c225证明；free cap需股东披露PIT，买入容量与竞价不可日频等价。'),
'03-234板介入-优化':('2~4连板、90日最大连板≤4、换手≤30%、量比≤1.8、距历史高点回撤≤5%，自由流通市值排序，指数环境可选；开盘买。','multi-limit streak × turnover/volume cap × low free cap。','PIT涨停/换手/股东/竞价。','multi_board_intraday_blocked','优化版改变执行但无新原子。'),
'04龙头弱转强战法-25年负':('龙头从高点回撤30~45%，量缩，开盘高于昨收、盈利20%止盈/8%硬止损/50%跟踪；指数跌5%恐慌。','leader pullback30–45% × volume contraction × open strength。','日线与盘中。','leader_pullback_intraday_blocked','facb1a5557758f46证明；盘中执行且标题负收益。'),
'04龙头弱转强战法-优化版':('30日高点上涨≥20%后回撤30~45%，近6日不放量；开盘涨幅≤5%且价格未封板买，止盈20%、硬止损8%、从高点回撤50%卖。','rise20 then pullback30–45% × volume contraction × open≤5%。','日线与盘中。','leader_pullback_intraday_blocked','竞价和盘中止损，不纳入日频因子池。'),
'05昨日涨停今日追高':('昨日涨停后，MA5>MA10>MA20>MA60，次日开盘追高，分级止损止盈。','limit-up yesterday × MA alignment × next-open chase。','PIT涨停/日内。','exact_limitup_trend_duplicate','abef0930284399b4证明；事件和执行重复。'),
'聚宽使用说明':('聚宽平台使用指南，无策略公式。','无。','无。','platform_user_guide_no_factor','不计候选。')}
if __name__=='__main__':
 add_authored({k:v for k,v in E.items() if k in ['04首板低开策略代码提速','05追首板','06首板低开策略2025','07-首板回调n日介入','08上升趋势-回档买入','09涨停回调止盈止损','实10-首板竞价三模式','实11-红利涨停轮动','聚宽使用说明']},'量化策略/量化策略/首板回调买入策略2026')
 add_authored({k:v for k,v in E.items() if k in ['01龙头股-最高板','02涨停板多头策略-25年负','02涨停板多头策略-优化版','03-234板介入-23年盈利','03-234板介入-优化版v1.0','04龙头弱转强战法-25年负','04龙头弱转强战法-优化版','05昨日涨停今日追高','聚宽使用说明']},'量化策略/量化策略/龙头追涨策略2026')
