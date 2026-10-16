from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '79.': (
        '月初先在沪深主板流通市值0~30亿元中取100只并过滤ST/次新；每周在池内用估值、ROA、营收和技术指标(DMA/HSL/MA/BIAS/MTM)训练SVR预测市值，取实际市值相对预测值最低的5只。',
        'small-cap30 + SVR residual using PE/PB/PS/ROA/revenue and DMA/HSL/MA/BIAS/MTM。',
        'PIT估值/ROA/收入、日线技术指标、SVR；主板小市值池。',
        'svr_smallcap_buggy_duplicate',
        '核心仍是小市值残差；源码factor为单列DataFrame后list(factor.sort_index(...))很可能只返回列名market_cap而非股票代码，原策略实现存在致命代码问题；不复现。'
    ),
    '81.': (
        '基于过去20日收益构造传统20日动量/反转，再以个股20日波动率相对全市场均值识别“可知/不可知”并翻转因子符号；另用换手率日变化相对市场均值翻转20日收益；日内收益和隔夜收益分别做同样波动率/换手率校正，截面zscore后六项相加形成final_factor。',
        'knowledge-conditioned momentum reversal: sign(ret20) by relative 20d return volatility; turnover-change conditioned ret20; analogous intraday and overnight components; zscore sum。',
        '复权/未复权日线OHLCV、流通股本换手率；外部price_not_fq.hdf/fin_df.hdf和back_trade实现。',
        'conditional_momentum_reversal_external_pending',
        '思路具有潜在新信息：低波动个股保留动量、高波动个股取反转，并加入换手变化状态；但原文数据文件与回测实现缺失，先保留为候选研究线索，不能声称已复现。'
    ),
    '82.': (
        '全A指定行业池过滤ST/停牌/退市后，按营收年增>20%、净利润年增>0、年度净利增>40%筛选，按总市值升序取7只；买入/卖出分别每20/10日执行，并以买入后最高价回撤14%止损。',
        'low market cap within industry universe ∩ revenue_yoy>20 ∩ net_profit_yoy>0 ∩ annual_net_profit_growth>40; 14% peak-to-trough stop。',
        'PIT年度/同比财务、市值、行业、持仓路径。',
        'growth_smallcap_duplicate',
        '基本面高增长+小市值与已有增长小市值簇重复；止损是组合执行规则，不形成新因子。'
    ),
    '83.': (
        '执行器每天从外部Signal_for_trade_YYYY-MM-DD.csv读取买入列表；用中小300指数分钟级10日均线判断牛熊，牛市股票100%、熊市股票50%并补债券；个股退出依赖外部信号、最短持有10日和最高价回撤3%止盈。',
        'external multi-factor signal file + minute MA10 bull/bear stock-bond switch + 3% trailing stop。',
        '外部每日信号CSV、指数分钟线、持仓路径；信号生成源码不在文件内。',
        'external_signal_executor_unreproducible',
        '只有执行器，没有因子生成逻辑；无法提取或复现可用因子。'
    ),
    '84.': (
        '从日线全市场数据识别涨停股及连续涨停数，构造市场最大连板数、一字板数量、涨停数量、次日涨停溢价及其3日滚动均值/极值/波动；再按概念统计涨停龙头概念数量和龙头股票列表，标注个股是否属于概念龙头。',
        'limit-up market regime: consecutive-board counts, limit-up breadth, next-day premium distribution, 3d rolling stats, and hot-concept leader flag。',
        '日线涨跌停、次日开盘、概念成分、ST和上市日；事件/概念数据。',
        'limitup_concept_regime_research_pending',
        '这是市场情绪/连板生态研究，不含完整交易规则；可作为事件择时诊断变量，暂不并入标准日频股票因子池。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
