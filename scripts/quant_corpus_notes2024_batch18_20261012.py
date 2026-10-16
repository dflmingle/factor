from quant_corpus_semantic_review_20261012 import add_authored
E = {
    '1.': (
        '剔除次新/ST/科创板后，分别取sales_growth最低10%后小流通市值、四项增长率加权前10%后小市值、PEG最低20%再取turnover_volatility最低50%后小市值，三支合并最多100只，每周调仓并保留近期涨停股。',
        'small size × low sales-growth branch; weighted growth score (0.10 revenue + 0.35 total profit + 0.15 net profit + 0.40 earnings growth); low PEG × low turnover volatility。',
        '聚宽预计算成长/PEG/turnover_volatility因子、流通市值、EPS、涨停和行业过滤；和2024策略1/35源码高度近似。',
        'small_size_growth_turnover_exact_duplicate',
        '与策略1/35基本为同一选股逻辑的改版复制，已由已有审阅覆盖；不新增复现规格。'
    ),
    '10.': (
        '盘中扫描前一日涨停、连板和首阴形态，结合开盘价、前高/前收、实时价格、涨停价和分钟走势在9:30–10:30买入，尾盘按盈利回撤、跌破阈值、持有时间和涨停状态卖出；属于事件驱动短线。',
        'limit-up streak count + first-negative-day/intraday breakout conditions + real-time drawdown exits。',
        '日线与分钟OHLCV、涨跌停价、实时tick/持仓状态；需要盘中数据和交易时序，无法用日频平台因子等价。',
        'intraday_limitup_event_not_standard_factor',
        '事件/盘中策略，不是可稳定提交的横截面因子；数据频率与竞赛平台定义不匹配，暂不复现。'
    ),
    '100.': (
        '从仓库内trade.csv读取外部“金股”/分析师推荐目标，在目标日期等权持仓，非目标卖出，每日执行；源码自身没有分析师推荐概率的计算。',
        'external analyst recommendation membership / recommendation probability proxy from prebuilt CSV。',
        '外部trade.csv、公告或研报推荐记录、股票代码映射；没有原始推荐生成规则和PIT审计。',
        'external_analyst_data_blocked',
        '输入信号完全来自外部文件，无法从源码提取可复现因子；不纳入标准因子池。'
    ),
    '11.': (
        '实现缠论笔/线段和MACD辅助的买卖点状态机，使用B1/B2/S1/S2等缠论拐点信号和分批买卖资金；源码主要处理单标的K线序列，没有全A横截面排序。',
        'Chan fractal/segment turning-point state machine + MACD(12,26,9) confirmation。',
        '单标的OHLCV序列、缠论状态维护、分钟或日线事件；参数和笔段定义依赖实现细节。',
        'single_asset_chan_timing_not_cross_sectional',
        '单标的择时技术法，与已有趋势/反转技术轴重叠且无法直接转为平台横截面因子，暂不复现。'
    ),
    '12.': (
        '全A过滤停牌/涨跌停后，先取低资产负债率70%、不良资产率中间80%、优质资产周转率前75%，再取近四个季度ROA改善前20%，最后PB>0.7、PS<3并按PB升序选股；不择时、低频基本面选股。',
        'low leverage × middle bad-asset ratio × high good-asset turnover × 4-quarter ROA improvement × low PB/PS。',
        'PIT资产负债表、应收/商誉/无形资产/存货/在建工程、营业收入、季度ROA、PB/PS；不良资产与优质资产公式需按合并口径重建。',
        'quality_asset_efficiency_value_duplicate',
        '有明确质量/资产效率/估值组合，但各原子都已有质量、价值和成长簇；整体可能作为质量+PB配方候选，暂记录为重复变体，不立即扩充测试。'
    ),
    '13.': (
        '统计过去10个交易日个股触及涨停的次数，选择连板/高连板股票，再观察未来3日高低价、收盘收益、最大浮盈浮亏和持有结果；仅做涨停事件收益统计。',
        '10d limit-up count / consecutive-limit event; 3-day post-event max gain, max loss and close return。',
        '日线收盘、涨停价、上市日期、ST状态；原文是2019–2020事件窗口，缺少全样本横截面回测交易规则。',
        'limitup_event_not_standard_factor',
        '短线事件研究与连板动量已有事件簇重叠，且平台支持字段/窗口不匹配，暂不复现。'
    ),
}
if __name__ == '__main__': add_authored(E, '2024年度精选策略2')
