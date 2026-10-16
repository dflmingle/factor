from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '72.': (
        '固定股票、债券、黄金、商品和海外ETF资产池及目标类别，月度再平衡；每只资产按近120日历史收益的99%尾部ES倒数分配权重，属于风险平价/全天候资产配置。',
        'inverse 120d ES weighting across fixed multi-asset ETFs。',
        'ETF日线收益、固定资产池、ES/历史排序。',
        'multi_asset_es_allocation',
        '不是个股截面因子；ES是仓位控制变量，不能纳入股票因子池。'
    ),
    '73.': (
        '全A过滤次新、停牌和涨跌停后，按低负债、坏资产率中间60%、优质资产周转率前75%、最近4季度ROA最新值减均值前20%筛选，要求PB>0.7、PS<3并按PB升序取10只，月度调仓。',
        'low leverage + middle bad-assets + high good-assets turnover + high ROA improvement + low PB/PS; monthly top10。',
        'PIT资产负债表/利润表、四季度历史ROA、PB/PS、市况状态。',
        'asset_quality_roa_value_duplicate',
        '与策略60同一源码家族，和2023/24、29质量价值簇重复；没有新增独立信息。'
    ),
    '74.': (
        '市值<160亿元的小盘池中，盘中要求从开盘到当前涨幅≥5.2%、成交量超过前5日均量2倍、OLS价格路径R²>0.8且斜率为正，最后一分钟不能涨停；将候选按昨日单日收益升序取最多10只，低于40%候选数则买黄金ETF替代。',
        'intraday monotonic-up OLS(R²>0.8, slope>0) + volume>2×5d mean + intraday return>5.2%, then low prior-day return。',
        '小市值、日线/分钟OHLCV、OLS；黄金ETF替代。',
        'intraday_trend_blocked',
        '形态/分钟突破策略，执行时点和ETF备用仓位决定结果；与日频趋势因子不直接可比。'
    ),
    '76.': (
        '每日抓取所有ETF昨日成交额和单位净值，计算开盘价相对净值的折溢价，过滤成交额>1000万、净值复权因子=1且|溢价|<20%，买入折价低于-2.5%的前2只ETF；无符合条件时阈值逐日降至1.5%，依赖东方财富网页爬虫获取当日净值。',
        'ETF opening discount to unit NAV, rank most negative premium; liquidity>10m and discount threshold。',
        'ETF开盘价、成交额、净值/IOPV外部网页、复权因子；跨市场基金。',
        'etf_premium_external_blocked',
        '外部网页净值和盘前执行不可在标准股票因子平台复现；不是全A股票横截面因子。'
    ),
    '77.': (
        '先用成交均价与换手率路径依赖构造60日调整换手权重，计算筹码相对收益的加权均值/方差/偏度/峰度ARC、VRC、SRC、KRC；再用三角分布筹码、均匀分布筹码及换手衰减筹码代理变量CYQK_C、ASR、CKDW、PRP训练Qlib Transformer/时序Transformer，并展示单因子分组和模型预测。',
        '60d turnover-weighted chip moments: ARC/VRC/SRC/KRC; triangular/uniform/turn-coefficient CYQ proxies CYQK_C/ASR/CKDW/PRP。',
        'Qlib csi300数据、close/high/low/vol/turnover_rate、外部scr自定义算子、Transformer训练模型；缺少当前全A平台字节等价物。',
        'chip_distribution_external_proxy_pending',
        '这是少数具有潜在新信息的资金行为轴，但原文依赖Qlib自定义算子和外部模型；可先按公式做日频代理诊断，正式结果必须标注proxy，不直接声称原策略复现。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
