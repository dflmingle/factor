from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '91.': (
        '研究传统时间序列动量：过去252日收益方向乘以60日指数衰减波动率目标缩放，再在多资产上等权；后续用多任务时序模型和超参数优化替代简单规则。',
        'TSMOM sign(252d return) × target_vol / 60d EW volatility; multi-asset sequence model extension。',
        '多资产日线收益、指数衰减波动、外部时序模型/优化器。',
        'multi_asset_tsmom_external',
        '资产级时间序列动量，不是全A股票截面因子；和已有ETF/指数动量重复，暂不纳入股票因子池。'
    ),
    '92.': (
        '在截面基本面/估值/技术特征上比较决策树、随机森林、线性/RBF SVR等模型，用模型重要性挑选特征，再以预测市值残差和多因子排名选股；特征包含PE/PB/PS、ROE/ROA、成长、现金流、动量和技术指标。',
        'ML feature selection + predicted market-cap residual / composite ranking across value-quality-growth-momentum features。',
        '聚宽基本面、技术指标、外部机器学习模型实现；训练/验证切分和特征权重未固定。',
        'external_ml_broad_feature_model_blocked',
        '与33/64/79同属复杂模型市值残差路线；没有稳定权重和可审计滚动训练定义，不能当作新独立因子复现。'
    ),
    '93.': (
        '用31个申万一级行业5日收益和相对沪深300的滚动Beta，分别做50日滚动秩，再计算行业收益秩与Beta秩的滚动Spearman相关，形成GSISI情绪指数；连续两次超过±0.301确认沪深300多空方向，参数搜索得到window=35、pct_window=15。',
        'GSISI = rolling Spearman(rank(industry 5d return), rank(industry beta)); double-confirmed ±0.301 market timing。',
        '申万行业历史成分/价格、沪深300、外部回测框架和参数优化。',
        'industry_sentiment_external_pending',
        '属于行业市场情绪择时，不是股票横截面alpha；行业历史成分与优化结果需独立防前视审计。'
    ),
    '94.': (
        '先比较微盘与大盘股票指数，使用5日CUSUM检测价格均值偏移；随后用日期特征、近期价格统计和XGBoost回归预测未来5日均价，并对微盘/大盘合成序列做买卖信号和收益差异检验。',
        '5d CUSUM regime detection + XGBoost future-price prediction for aggregated microcap/largecap series。',
        '聚合股票价格、日线OHLCV、XGBoost；源码把多只股票数据错误相加，非标准截面因子。',
        'aggregate_regime_ml_broken',
        '不是可交易个股因子；聚合DataFrame构造和未来日期预测存在明显实现问题，放弃复现。'
    ),
    '95.': (
        '在指数成分股中读取季度基金持仓市值，汇总每只股票在基金组合中的持仓权重，与指数官方权重相减；超配为“基金最爱”，低配为“最恶”，只做横截面展示，没有交易回测。',
        'fund-holding weight minus benchmark index weight (institutional overweight/underweight)。',
        '季度基金持仓披露、指数权重、报告期公告；PIT基金数据。',
        'fund_overweight_external_pending',
        '有潜在机构拥挤/反转信息，但报告期频率低、披露滞后且当前项目缺完整PIT基金持仓；先记录，不入标准因子池。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
