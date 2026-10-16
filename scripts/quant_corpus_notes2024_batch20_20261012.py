from quant_corpus_semantic_review_20261012 import add_authored
E = {
    '20.': (
        '读取外部月度因子暴露与因子收益矩阵，用宏观变量(TS、CS、CPI、PPI、期限/信用利差、M1、短债收益率)滚动24期回归R²，并以SVM/Logistic/随机森林预测未来因子收益方向；按预测方向和过去36期符号调整因子权重，再合成综合因子选前50只。',
        'macro-conditioned dynamic factor timing: rolling 24m R² + classifier prediction of factor-return sign + 36m sign agreement weight adjustment。',
        '外部datas/因子收益矩阵/宏观数据、月频因子暴露、sklearn/statsmodels；源码未提供这些输入文件和固定训练样本。',
        'external_dynamic_factor_timing_blocked',
        '属于外部多因子择时框架，不是单一可复现股票因子；数据文件、因子定义和滚动训练边界缺失，不能纳入本地正式复现。'
    ),
    '21.': (
        '在多类行业ETF中计算周期动量、当前周期涨幅及BBI(21/34/55/89)相对价格，按周选择各类最强ETF，并用指数日内涨幅/沪深300牛熊信号决定上午或下午开仓，熊市切债券ETF。',
        'ETF category top momentum + BBI(21,34,55,89) trend state + intraday index breadth timing。',
        '行业/宽基ETF日线和日内价格、固定分类清单、指数信号；资产配置而非股票截面。',
        'etf_momentum_bbi_asset_allocation',
        '与已有ETF轮动和RSRS/均线择时重复，不进入标准股票因子池。'
    ),
    '22.': (
        '全A过去一年现金分红/总市值最高25%，再按总市值升序取小盘股，剔除高价、停牌、ST和涨跌停，每月持有；没有PEG或杠杆约束。',
        'trailing 1y dividend yield top 25% × low market cap × low price filter。',
        'PIT分红登记日、总市值、价格和交易状态；与策略1/36和2/15同源。',
        'dividend_size_exact_duplicate',
        '已知高股息+小市值红利簇的简化复制，不新增测试。'
    ),
    '23.': (
        '过滤次新/ST/科创板后，先取price_no_fq最低10%，再在其中按流通市值升序取最多10只，每周调仓。',
        'low raw price (price_no_fq) × small circulating market cap。',
        '聚宽价格因子、流通市值、EPS和交易状态；price_no_fq为未复权价格，存在价格水平与拆股敏感性。',
        'low_price_size_duplicate',
        '与已有低价/小市值簇重复，且未复权价格可产生结构性偏差；不新增复现。'
    ),
    '24.': (
        '在宽基ETF池按18日高低价RSRS斜率×R²年化收益选最强ETF，以18日RSRS zscore与近期收益波动分位数共同调节阈值，并在弱信号/下跌时切债券ETF。',
        'ETF RSRS18 slope×R² rank + volatility-quantile adaptive threshold + bond defensive switch。',
        'ETF OHLCV、RSRS高低价回归、600期斜率历史和波动分位数；资产级择时。',
        'etf_rsrs_defensive_duplicate',
        '与既有RSRS/ETF动量路线同源，不是股票横截面新簇。'
    ),
    '25.': (
        '在市值30–1000亿概念股池内，用20日/60日/120日价格回归斜率×R²及RSRS择时排序，每次只买1只；盘中依据排名变化、RSRS信号、止损止盈交易。',
        'multi-horizon price-trend slope×|R²| score + RSRS18/600 timing + rank-change trigger。',
        '概念成分、个股OHLC、实时价格、RSRS历史斜率；单股日内交易，回测成本和成交约束较强。',
        'single_stock_trend_intraday_duplicate',
        '是趋势/RSRS/日内交易路线的组合，非稳定低换手截面因子；不进入标准因子池。'
    ),
    '26.': (
        '在中证1000成分中先按流通市值取50只小盘股，对每只计算20日布林带；昨日收盘跌破下轨后回升且高于此前8日低点买入，持仓跌破动态止损或上轨反转卖出。',
        'BOLL20 mean±2σ oversold rebound above prior 8d low, with small-cap universe and dynamic stop。',
        '中证1000成分、流通市值、日线收盘/滚动均值/标准差、价格状态；单股择时而非横截面排序。',
        'boll_reversal_smallcap_duplicate',
        '短周期布林反转属于已有技术反转簇，且策略主要靠个股状态机和止损；不新增标准因子。'
    ),
}
if __name__ == '__main__': add_authored(E, '2024年度精选策略2')
