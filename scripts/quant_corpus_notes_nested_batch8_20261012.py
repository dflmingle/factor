from quant_corpus_semantic_review_20261012 import add_authored
E={
'实10首板':('14函数精确匹配向上趋势三模式首板竞价策略。','first-board auction three modes。','竞价/分钟/涨停/PIT。','exact_auction_duplicate','bdf8bacf0e430458证明。'),
'实11红利涨停':('9函数匹配红利涨停轮动：股息率前25%后质量/PEG筛选，月调并盘中补仓。','dividend yield25% × quality/PEG × limit-up execution。','PIT分红/财务、分钟价。','dividend_limitup_intraday_blocked','e7f5162c232eede9证明；get_dividend_ratio_filter_list方向和PIT需核，不能当日频纯因子。'),
'聚宽使用说明':('聚宽平台使用指南，无策略公式。','无。','无。','platform_user_guide_no_factor','不计候选。'),
'07首板回调n日':('首板后3个交易日内回撤−12%至−8%、收盘高于MA10，低点作止损、止盈为风险距离2倍。','first-limit-up then 8–12% pullback above MA10。','PIT涨停和日内价格。','daily_pullback_candidate_with_time_issue','find_limit_up_stocks在14:50才识别当日首板，随后用当日close可能含未来；不适合正式日频复现。'),
'08上升趋势回档':('20日MA上方股票中，近10日从高回撤5~15%、ATR14/价≤5%、MA5>MA20且当前价在MA5上，随机抽样最多200买10%，MA死叉/10%止损/5%跟踪止损。','trend MA5>MA20 + 5–15% pullback + low ATR14。','日线OHLCV。','trend_pullback_candidate_random_execution','随机抽样导致不可重现，且只买第一只；交易执行方法不是因子。'),
'09涨停回调':('过去10日曾涨停但≤2次、当前非涨停；收盘连续站MA10、MA5上穿且放量1.3倍、MA5/10距>1%、近5日回撤>5%，止盈10~15%/止损3%。','recent limit-up history × MA reclaim + volume surge × pullback。','日线涨停价/OHLCV。','limitup_pullback_daily_candidate','可提取日频原子，但涨停判定需PIT涨停价代理；正式测试前需去重现有回调簇。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/首板回调买入策略2026')
