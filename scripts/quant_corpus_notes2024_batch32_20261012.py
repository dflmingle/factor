from quant_corpus_semantic_review_20261012 import add_authored
E={
'86.':('转债按价格+转股溢价率百分数双低升序取10，日轮动，对照全部可交易转债。','CB price+100*(CB price/(100*stock_price/conversion_price)−1)。','历史转债条款/行情、正股raw价格及转股价调整、外部网页。','convertible_double_low_blocked','检查date>=today的转股信息存在未来数据依赖；网页取当前评级/赎回价，虽返回主评分未使用，仍不构成完整PIT链；转债退市按原买价回款、现金未计NAV等回测问题。不能以正股低价替代。'),
'87.':('每月第7交易日取昨日沪/深股通活跃榜各净买入最高1只，亏16%换股，无榜单向更早日递归。','northbound top-active buy−sell rank。','PIT沪深股通活跃榜与分钟止损。','northbound_flow_blocked','活跃榜非全部股票净流入；缺本地逐股股通数据，不能以成交额/涨跌幅代理后称原式。递归需边界。'),
'88.':('昨日涨停且8日仅1次高价触板、60日新高且成交额较前日升；上午价格高于昨收且未涨停时买，盘中/尾盘回撤退出。','first limit-up × high60 breakout × rising amount。','真实涨停价、分钟价格及日内高点。','first_limitup_event_blocked','买卖主代码缩进都在上午买入条件分支，尾盘条件实际上到不了；不能把意图止损等同实际执行。ST过滤也错误判断Series成员。日频事件原子可提取，整执行不支持。'),
'89.':('只提供行业龙头/财务风险/配置等工具类，无initialize/handle_data等活动策略入口；核心函数与2020/33一致。','industry largest cap + ROE / goodwill filters are library recipes。','PIT行业财务、行情；具体调用缺失。','library_exact_duplicate','包括40余个类方法完整AST匹配2020/33，终端refs统计仅顶层不代表匹配总数。不能从标题推断实际组合或年化胜率。'),
'9.':('同文件拼接多套策略：中小板最小流通市值0.5%全A数量；低涨停频率+相对250日强势；低PEG/EBIT/换手稳定性小盘；五项成长固定加权后EPS正小盘。','count(limitup250)<.2*index_mean & relative_RET250>mean; growth=.1 revenue+.35 profit+.15 netprofit+.35 earnings+.05 sales。','真实涨停、历史成分、供应商复合成长及PIT财务。','concatenated_variants_candidate_inventory','同名initialize/get_stock_list反复覆盖，不能把文本多个独立片段当单一可执行策略；低PEG等与39精确匹配。强势但低涨停频率可提取事件约束，未实测不建新簇。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
