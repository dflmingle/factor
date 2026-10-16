from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '50.': (
        '全A去次新/科创/ST后，先取扣非利润占比最高30%，再用短期预期利润增长、长期预期利润增长、净利润增长、盈利增长的固定权重(0.2/0.4/0.2/0.2)取前8%；源码随后先计算PEG前20%，但立即被低turnover_volatility前80%覆盖，最终按流通市值升序取25。月调仓，并用MA20斜率<-2过滤明显下跌股。',
        'high adjusted_profit_to_total_profit30 ∩ weighted growth score top8 ∩ low turnover_volatility80 → low circulating market cap25; MA20 slope guard。',
        'PIT质量/增长/预期因子、PEG、turnover_volatility、流通市值、日线价格；预期增长字段定义依赖聚宽因子库。',
        'growth_quality_lowturn_smallcap_duplicate',
        'PEG筛选结果被下一行覆盖，实际未生效；公共主轴仍是增长+低换手+小市值，与2024/1、17及现有簇重复。'
    ),
    '52.': (
        '四只ETF(黄金、纳指100、创业板100、红利)每月用过去1200日收益协方差计算EPO；参数method=anchored、w=1、anchor=逆方差权重，因收缩相关矩阵退化为单位阵，信号项被完全关闭，最终权重等价于逆方差/低波动配置。',
        '1200d inverse-variance ETF allocation (EPO anchored w=1; signal term inactive)。',
        '四只ETF日收盘价，1200日历史；SciPy线性代数。',
        'etf_inverse_variance_allocation',
        '资产配置而非个股横截面alpha；w=1使EPO不再使用均值信号，不能纳入标准因子池。'
    ),
    '53.': (
        '每日从全A去科创/北交/ST后按总市值升序取最小400只，等权1/400每日再平衡。',
        'lowest total market cap400, equal weight, daily rebalance。',
        '日市值、交易状态。',
        'microcap_size_duplicate',
        '纯微盘规模暴露，与既有size轴完全重复；高换手且不含独立alpha。'
    ),
    '54.': (
        '每周按申万二级行业统计过去10日个股收益分布的分箱加权得分，选得分>500的前5个行业；行业内再以DMI(14,6)的PDI-MDI+ADX排序取强势股。次日对候选按昨日上涨且低开/盘中转强分早盘和午盘买入，涨停打开或单日跌2%卖出。',
        'industry 10d breadth-bin score >500 + stock DMI strength(PDI-MDI+ADX) + gap/limit-up intraday execution。',
        '申万行业成分、日线收益、DMI、实时开盘/分钟涨停状态。',
        'industry_momentum_intraday_blocked',
        '有可抽取的行业广度与DMI动量，但最终依赖竞价、盘中涨停和止损执行；与已有动量/行业轮动同轴，暂不进标准日频池。'
    ),
    '60.': (
        '全A过滤次新、ST、停牌和涨跌停后，先保留低负债率(负债/资产降序后后70%)，再保留坏资产率中间60%，再取优质资产周转率前75%；从最近4个季度ROA中取最新值减四季均值的改善前20%，最后要求PB>0.7、PS<3并按PB升序取5只。',
        'low leverage + middle60 bad_assets_ratio + high good_assets_turnover75 + high latest-minus-mean4q ROA20 + PB>0.7 + PS<3, final low PB。',
        'PIT资产负债表/利润表、四季度历史ROA、PB/PS、上市与交易状态；需公告日连接。',
        'asset_quality_roa_value_duplicate',
        '质量价值复合轴，与2023/24、2023/29及既有ROA/PB簇高度重叠；坏资产和优质资产周转率可作诊断腿，暂不独立建簇。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
