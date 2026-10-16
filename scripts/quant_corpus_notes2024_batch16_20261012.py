from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '96.': (
        '用4只海外/商品ETF的日线OHLCV展开为特征，叠加上证指数日期特征和46日窗口均值、极值、标准差、方差，训练5个LightGBM回归器预测上证指数未来5日开收均价，再用5日CUSUM阈值画指数/ETF信号；没有形成全A横截面选股。',
        'macro/ETF feature window statistics (mean, max, min, std, var over 46d) + LightGBM price forecast + CUSUM(5d, threshold=0.1) regime signal。',
        '上证指数、4只ETF历史OHLCV、外部LightGBM/XGBoost/TA-Lib；日期特征用当前系统日期；模型训练未做滚动样本外切分。',
        'aggregate_index_ml_leakage_blocked',
        '不是标准股票横截面因子；模型把整段历史同时用于训练并预测未来，特征/标签窗口对齐和当前日期写法也不适合正式回测，CUSUM只可作为宏观择时诊断。'
    ),
    '97.': (
        '逐交易日计算沪深300历史成分股PE中位数，与中国10年国债收益率合成FED估值指标(100/PE−10Y yield)和格雷厄姆比率((100/PE)/10Y yield)，再与沪深300ETF价格同图观察极端分位；源码没有交易规则或个股排序。',
        'index-median earnings yield minus 10Y sovereign yield; earnings-yield / 10Y yield (Graham ratio) macro valuation regime signals。',
        'PIT沪深300成分、PE、外部中国债券收益率网页、510300价格；收益率抓取依赖网络且日期对齐/缺失处理粗糙。',
        'macro_valuation_timing_external_pending',
        '宏观指数择时信息与已有估值/市场状态观察重复，不属于可直接提交的全A截面alpha；如研究市场暴露可另建宏观开关，但当前不纳入因子池。'
    ),
    '98.': (
        '在Piotroski FScore基础上保留7个正向会计信号：ROA水平、ROA同比变化、经营现金流/资产(TTM)、应计项反向、长期负债率下降、毛利率同比改善、资产周转率同比改善；每项大于0记1分，合成RFScore 0–7。源码还单独检查CFOA、应计、负债率变化、流动性变化、毛利率和周转率变化，并用PB交叉分组。',
        'RFScore7 = I(ROA>0)+I(ΔROA>0)+I(OCFOA>0)+I(ACCRUAL>0)+I(−Δleverage>0)+I(Δgross_margin>0)+I(Δasset_turnover>0); ancillary CFOA/Δmargin/Δturn/Δleverage components。',
        'PIT季度财务报表、TTM现金流/资产、ROA、毛利率、营业收入、长期负债；原文使用聚宽Factor和本地CSV中间结果，部分资产平均写法需按平台PIT规则重建。',
        'quality_fscore_variant_duplicate',
        '核心是已知FScore/质量簇的删减重构，不构成新独立簇；可作为质量轴的可解释配方，若复现只测试RFScore7和OCFOA/Δmargin/Δturn原子，避免把PB交叉和评分阈值误当新信息。'
    ),
    '99.': (
        '从沪深300期权分钟盘口计算Black/BSM隐含波动率，过滤无套利报价后拟合SVI波动率微笑，数值微分得到局部波动率，并用有限差分、Heston、Merton和Bates模型定价；全文是期权定价教程，没有股票横截面选股信号。',
        'implied volatility surface, SVI smile parameters, local-volatility surface, Heston/Merton/Bates calibration errors and Greeks。',
        '期权合约、分钟tick买卖价、沪深300现货/IF期货、利率、SciPy优化与数值积分；需要期权专有数据和高频数据。',
        'options_volatility_pricing_not_stock_factor',
        '不属于当前全A股票因子池；隐含波动率/波动率曲面可作为衍生品或市场状态研究，但平台支持和本地对齐数据均不足，暂不复现。'
    ),
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
