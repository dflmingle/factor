from quant_corpus_semantic_review_20261012 import add_authored
E={
'pt版01小市值':('中小板成分按流通市值前15过滤后取5，4月仅暂停交易不清仓；实盘现金10%/目标，回测全组合等权。','small float_value in index399101。','PIT指数/流通市值及可交易状态。','size_execution_port_no_new_factor','实盘order_target_value用现金比例会缩现有仓；check_limit(stock)与1直接比较但其它文件认为返回dict；非原精细风控完整移植。'),
'pt版01趋势':('月初筛rank(RET20)+rank(C/MA60−1)前40%，245条收益绝对相关均值最低4再取2，每日检查持仓。','trend-strength prefilter + min mean absolute corr245。','ETF日线含日期对齐。','etf_trend_lowcorr_method','逐标的dropna后位置对齐可能错日期；持仓不再平衡，未取首次月初会现场初始化；不是新股票原子。'),
'pt版02小市值':('中小板流通市值前30过滤后先截3，再对这3筛14:55价>历史MA5，每日等权。','small float_value × intraday C>MA5。','PIT指数/流通市值、14:55价。','size_ma_port_no_new_factor','不是先过滤MA再从30取3；实盘现金10%目标与回测全资产不同；停牌/跌停执行假设另审。'),
'pt版02首板':('昨日首板非前日板；昨均价/昨收×1.1−1≥7%、成交5.5~20亿、总值≥70亿流通≤520亿，左压窗量>旧最大*.9，竞价高开0~6%且竞价量/昨量≥3%。','first-board × VWAP proximity × volume-pressure break × opening auction。','PIT涨停价/市值、竞价和分钟、T+1执行。','auction_intraday_blocked','分钟量*.34替竞价非等价；盘中盈利开板或MA5下方卖，不能日线伪复现原策略；新股50天。'),
'pt版05动量':('标题最强动量实际完整重复pt版01趋势低相关：月初RET20与BIAS60合秩前40%，corr245均绝对相关最小两只。','same trend+low-correlation ETF selection。','ETF日线。','duplicate_mistitled_etf_port','逐函数源码已对比；无25日加权回归动量；不按标题提取。'),
'pt版07ETF':('34条log斜率年化×R²筛正分前三，1000日协方差收缩20%，逆波动锚定EPO，月初轮动。','trend34 + anchored EPO1000 inverse-vol anchor。','ETF日线宽表。','etf_epo_port_variant','与聚宽原逆方差锚定不同；少列后权重仍按原target顺序会错配/越界；实盘现金而回测总资产配权；不新股票簇。'),
'pt版08多因子':('流通市值最小50中以营收增、成长MS=.1营收+.35总利+.15净利+.4归母增、正PE/正净利增的逆PEG三秩等权取5；40天持有且涨停者禁重买。','rank(rev_growth)+rank(MS)+rank(growth/PE) within float-size50。','PIT四项增长、PE、流通市值、涨停。','growth_composite_port_candidate','不足5回填小盘但不受相同成长约束；实盘weekly_adjustment run_daily而回测只周一；prepare可能重复调用污染40日计数；需PIT字段映射。'),
'pt版实10':('三模式：首板高开继承5.5~20亿/VWAP7%/左压量；首板低开需60日位置≤.5、昨额≥1亿、开盘.955~.97；炸板弱转强需3间隔涨≤28%、昨阴不低于−5%、VWAP/收≥.96、额3~19亿、左压量，所有模式竞价量≥3%。','first/broken board × VWAP/volume pressure × auction modes。','涨停价、竞价/分钟、PIT市值。','auction_intraday_blocked','弱转强把昨收×(1+limit_ratio)作参照并非昨实际涨停价；分钟*.34与累计快照量非竞价；盘中退出/T+1不作日线等价。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/实盘2026/Ptrade')
