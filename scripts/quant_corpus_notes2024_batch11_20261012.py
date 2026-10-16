from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '61.': (
        '取中证全指AA成分，剔除ST、停牌和上市不足365日；把每只股票自2023年以来的完整日收益序列直接组成矩阵，用t-SNE降到二维再KMeans分10簇，仅输出每簇中心样本及其行业/市值/EPS。没有交易规则或未来滚动信号。',
        't-SNE(return-history) + KMeans(10) exploratory clustering; no stock-selection factor。',
        '全历史日收盘、指数成分、行业、市值、EPS；t-SNE/KMeans。',
        'unsupervised_exploration_no_factor',
        '使用固定历史窗口做无监督可视化，没有把簇标签转成可交易截面因子；不应纳入因子池。'
    ),
    '62.': (
        '先取全A过滤次新/ST/科创北交，按流通市值<25亿元，再剔除近300日有涨停、近30日接近涨停、近15日单日振幅>2.5%的股票；保留收盘创15日新高且接近60日高点(>92%)者，盘中价格位于涨停价94.5%~97.5%时买入。卖出依赖15分钟尖峰回落、持有天数、放量滞涨和止盈。',
        'small-cap<25 + no limit-up(300d/30d) + low recent amplitude + 15d breakout & close>92% of 60d high; intraday entry/exit。',
        '日线/15分钟/10分钟OHLCV、流通市值、涨停价；盘中执行。',
        'breakout_intraday_blocked',
        '日频部分可抽取“低波后15日突破且接近60日高点”，但策略收益依赖涨停价区间和盘中卖出，暂不做标准因子回测。'
    ),
    '63.': (
        '剔除创业/科创/北交/ST/停牌及流通市值≥150的股票；昨日未涨停且过去300日收盘最高点不超过昨收20%、过去50日最高点不超过20%、过去10日最高点不超过10%，300日振幅<200%、10日振幅≤50%。次日若1分钟收盘由非涨停跃升至涨停则买入，盘中按涨停持续时长、开盘缺口、成本收益和尾盘条件卖出。',
        'near-breakout constraints: close_t within 20% of 300d/50d highs and 10% of 10d high, range10≤50%, range300<200%; first-minute limit-up trigger。',
        '日线300日OHLC、1分钟涨停/高低价、流通市值、实时交易状态。',
        'limitup_breakout_intraday_blocked',
        '核心是首板/一进二事件和分钟涨停触发，不能与标准日频因子直接比较；仅保留近高位突破约束作为研究线索。'
    ),
    '64.': (
        '每月滚动6个截面训练XGBoost分类器：因子含EP/BP/SP/NCFP、现金流/利润/增长、ROE/ROA/毛利率/周转、杠杆/流动性、Alpha/Beta、1/3/6/12月动量、换手加权收益、FF3特质波动、波动率、价格、PSY/RSI/BIAS/MACD等；先MAD去极值、行业填补、行业+市值中性化和标准化，按未来一个月收益两端各30%构造标签，取测试集概率前10%后按流通市值升序选股。',
        'rolling 6-month XGBoost on broad value-quality-growth-momentum-volatility feature set, industry/size neutralized; top10% probability then small-cap tie-break。',
        '大量PIT财务/估值、行业中性化、60个月回归、240日换手/收益、FF3残差、技术指标；XGBoost实现。',
        'external_ml_broad_feature_model_blocked',
        '源码没有固定训练模型权重，且特征工程庞大、字段定义和TTM连接需逐项对齐；不能把模型概率当成单一新因子，避免重复本地复现。'
    ),
    '65.': (
        '先取总市值最小500并过滤停牌/ST/科创；次日若低开1%~8%、低于昨日最低，近4日振幅≤20%，且昨收高于5日EMA则买入5只；次日无条件卖出。',
        'microcap500 + gap-down below prior low (-1%~-8%) + 4d range≤20% + prev close>EMA5; next-day exit。',
        '总市值、日线OHLC、实时开盘；日内/隔夜执行。',
        'microcap_gap_intraday_duplicate',
        '与2024/20、既有低开小市值剥头皮同式，市值暴露和执行时点主导，不新增标准日频因子。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
