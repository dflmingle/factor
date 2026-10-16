from quant_corpus_semantic_review_20261012 import add_authored
E = {
    '14.': (
        '先从PB区间和流通市值最小1000只建立候选，再过滤停牌/ST/次新/昨日涨幅过高和卖出冷却；按总市值、流通市值、当前价格、5日成交量、60日涨幅的对数相对最小值加权排序，盘中用指数现价相对10日均线切换牛熊，并带6.5%个股止损和30%组合回撤清仓。',
        'small-cap/value pool × weighted log inverses of market_cap, circulating_mv, price, 5d volume, 60d return; intraday index MA10 regime filter。',
        'PB、总/流通市值、日/分钟价格成交量、沪深300/指数10日均线、实时价格；盘中数据和交易风控不可由标准日频因子完整复现。',
        'small_value_momentum_intraday_duplicate',
        '排序轴是已有小市值、低价、低换手/成交量和短期动量的加权重复，新增信息主要来自盘中择时/止损，暂不纳入标准因子池。'
    ),
    '15.': (
        '全A剔除次新/ST后，取过去一年股息率最高50%，再在其中保留turnover_volatility排序前80%（ascending=False，实际剔除最低20%波动者），再保留MLEV最低50%，最后按流通市值升序取15只，每周调仓。',
        'high trailing dividend yield × turnover_volatility above the bottom 20% × low MLEV × small circulating market cap。',
        'PIT分红登记日和bonus_amount、总市值、turnover_volatility、MLEV、流通市值；因子方向与“低波动”直觉相反，需按实际排序复核。',
        'dividend_leverage_size_variant',
        '与2024策略1/6的高股息×低换手波动×低杠杆×小市值同源，但本篇保留高波动尾部，属于已知红利/杠杆/规模簇的方向变体；不作为新簇。'
    ),
    '16.': (
        '将ETF按本地股票、全球股票、期货、全球期货、REITs分类，计算20日收益率和价格相对20日均线状态，只保留收益率和均线状态均为正者，每类选涨幅最高一个并等额交易。',
        'ETF cross-sectional 20d momentum × close−MA20 trend filter, category-wise top1。',
        '多类别ETF日线OHLC、固定分类表；属于资产配置/ETF轮动，不是全A个股横截面因子。',
        'etf_momentum_asset_allocation',
        '与已有ETF动量/均线/RSRS路线重复，且不纳入股票因子池。'
    ),
    '17.': (
        '与2024年度精选策略1/8同一源码逻辑：低8年ROA、低每股留存收益、低非线性市值各取10%后按小流通市值合并，周调仓。',
        'low roa_ttm_8y × size; low retained_earnings_per_share × size; low non_linear_size × size。',
        '聚宽预计算因子、流通市值、EPS；与策略1/8内容重复。',
        'small_size_factor_exact_duplicate',
        '已在策略1/8逐篇核验，内容重复，不新增测试。'
    ),
    '18.': (
        'ETF组合中用20日收益率经Kalman平滑后的末段线性斜率选最高者；同时对参考指数计算18日高低价RSRS斜率、600期zscore并乘R²，超过±0.7切换买卖，盘中止损。',
        'Kalman-smoothed 20d momentum slope + RSRS18/600 zscore×R² market timing。',
        'ETF日线OHLC、参考指数高低价、padasets KalmanFilter、600期暖机；ETF资产级时序信号。',
        'etf_kalman_rsrs_duplicate',
        '与2023策略/47及此前RSRS复现重复，属于ETF轮动/市场择时，不是新股票截面因子。'
    ),
    '19.': (
        '回测时读取外部cpv.csv中的预计算高频价量相关因子，支持直接取pv_corr或对多列价量特征做PCA得到pca_pv，再每日持有因子最小的若干股票；源码不计算高频相关本身。',
        'external high-frequency price-volume correlation pv_corr; PCA compression pca_pv of precomputed price-volume features, low-tail selection。',
        '外部cpv.csv、分钟级价格/成交量特征、PCA；缺少特征构造、采样、去极值和PIT定义，无法从源码重建。',
        'highfreq_pv_external_blocked',
        '与2023策略/95同源，已明确为外部预计算字段，不能宣称找到可复现价量新因子；不纳入本地正式测试。'
    ),
}
if __name__ == '__main__': add_authored(E, '2024年度精选策略2')
