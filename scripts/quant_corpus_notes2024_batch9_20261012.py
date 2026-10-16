from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '33.': (
        '中证全A筛选PE<100、总市值<1000且PEG代理较低的股票，加入alpha_006/015/026三项Alpha191，先对价量/基本面列做市值OLS残差，再用SVR多项式拟合市值残差，最后叠加10日Fisher门槛并持有3只。',
        'alpha_006 + alpha_015 + alpha_026 with market-cap neutralization and polynomial-SVR residual ranking; 10d Fisher>0 timing gate。',
        '聚宽Alpha191实现、SVR训练库、PIT估值/盈利、日线OHLC；Fisher代码含未使用FFT。',
        'external_complex_alpha191_svr_blocked',
        'Alpha191字段与SVR训练定义无法在当前标准日频平台逐字复现；样本内截面拟合市值残差，且只持有3只，不能作为独立因子结论。'
    ),
    '34.': (
        '全A去停牌/ST/次新后，先筛1日首板且近20日恰好1次涨停，再剔除一字/T字和尾盘封板弱，按近5日涨幅<1.1、竞价相对昨收9.45%~98.5%区间买入；买前要求20日最高量/倍量条件，次日非涨停尾盘卖出。',
        'one-limit-up-in-20d + non-board/late-seal filters + 5d return<10% + auction gap band + 20d/240d volume burst filters。',
        '日线涨停价、分钟K线、竞价、成交量、实时价格；依赖盘中执行。',
        'limitup_intraday_blocked',
        '首板/竞价/分钟择时与次日尾盘退出，属于事件驱动短线，不能并入标准日频因子池。'
    ),
    '41.': (
        '单一000065.XSHE标的的DQN动作策略；输入最近7日日收益率（dropna后6个值），读取外部tgt_net.pt模型输出持有/买入/卖出动作。',
        'external DQN(6 inputs, 3 actions) on 000065.XSHE 7d return state。',
        '外部PyTorch模型文件tgt_net.pt、单股日线；无可审计训练样本和权重。',
        'external_ml_model_unreproducible',
        '模型文件未随策略提供，且不是横截面因子；不能复现或纳入因子池。'
    ),
    '42.': (
        '在沪深300ETF、上证50ETF、创业板50三只ETF中，以20日相对MA90乖离序列的线性拟合斜率作为动量排名；大盘用18日high-low OLS斜率、600日zscore、8日zscore斜率和指数8日斜率做RSRS择时，并以60分钟MA20止损。',
        'ETF 20d slope of close/MA90 bias + RSRS(high~low slope, 600d zscore, 8d slope) timing。',
        'ETF/指数日线与60分钟线、技术分析函数WR/EMA/ATR。',
        'etf_rsrs_duplicate',
        '与既有ETF动量/RSRS簇完全同轴；仅参数和止损细节不同，不形成新的个股因子簇。'
    ),
    '43.': (
        '固定14只行业/大宗/海外ETF池，每日计算25日log(close)线性回归斜率，转成年化收益后乘R²排序，只持有得分最高的一只。',
        '25d log-price regression annualized return × R² ETF momentum。',
        'ETF日线收盘价；不涉及个股基本面。',
        'etf_momentum_duplicate',
        '标准ETF动量轮动的同式变体，和既有ETF动量簇重复。'
    ),
    '45.': (
        '70%股票子账户、30%中证1000期货对冲；股票腿在399317成分中要求PB<3、ROE>10%、现金/短贷>0.4、ROA>0且ROA>0.05ROE、收入和净利润增速>10%、正PE/PS/PCF，再按近3年累计分红/市值排序取5只；期货腿用IC 2/5日EMA趋势、20/50日ATR波动仓位和5日高低点ATR止损。',
        'quality + growth + dividend_yield_3y/market_cap within 399317, with IC futures EMA/ATR hedge。',
        'PIT财务、分红公告、指数成分、IC期货连续合约、EMA/ATR；股票与期货双账户。',
        'dividend_quality_with_futures_hedge',
        '股票腿可抽取为质量/成长/红利组合，但现有质量红利簇已有重叠；期货对冲不属于个股因子，暂不单独复现。'
    ),
    '46.': (
        '全A去科创/北交/ST/次新后，分别取DEGM_8y、每股净资产、非线性市值最小10%，每腿再按流通市值升序取5只并集，要求EPS>0；周调仓并保留涨停股。',
        'low DEGM_8y ∪ low net_asset_per_share ∪ low non_linear_size, each 10% then small circulating-cap top5, EPS>0。',
        '聚宽因子值DEGM_8y/net_asset_per_share/non_linear_size、PIT EPS、流通市值。',
        'growth_value_smallcap_duplicate',
        '与2024/37及既有小市值/低PB轴重复；三腿并集后仍由小市值主导，不新增独立信息。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
