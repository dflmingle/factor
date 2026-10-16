from quant_corpus_semantic_review_20261012 import add_authored
E = {
    '35.': (
        '先从行业内20日均线上方股票占比筛出近期强势行业，再分三支选股：营业收入增长率最低10%后按小流通市值取股；四个增长字段加权(营业收入0.10、利润总额0.35、净利润0.15、盈利增长0.40)取前10%后按小流通市值；PEG最低20%再取换手波动率最低50%后按小流通市值。三支合并，每周调仓。',
        'hot-industry breadth = pct(CLOSE > MA20) by industry; small-cap legs conditioned on low sales-growth, weighted growth score, or low PEG × low turnover_volatility。',
        '聚宽行业成分、sales_growth/operating_revenue_growth_rate/total_profit_growth_rate/net_profit_growth_rate/earnings_growth/PEG/turnover_volatility、流通市值、EPS；行业和平台因子定义需PIT核对。',
        'small_size_growth_turnover_duplicate',
        '主要是既有小市值、成长、PEG和低换手稳定性轴的组合变体；行业广度C>MA20可作为已有趋势/行业状态的代理，但没有独立横截面新簇，暂不单独复现。'
    ),
    '36.': (
        '全A过滤后取过去一年现金分红/总市值最高25%，再要求PB<3且源码把PE/净利润增速<0作为PEG条件，随后按总市值升序取小盘股并剔除高价/停牌/ST等；月度调仓。',
        'dividend_yield_1y = trailing cash bonus / market_cap; high dividend yield × PB<3 × negative PEG condition × low market cap。',
        'PIT分红公告、总市值、PE、净利润同比、PB；分红查询需处理披露滞后，原PEG条件符号疑似作者错误且可能筛出负增长。',
        'dividend_value_size_duplicate',
        '高股息+低市值+低PB已有红利/价值簇；若修正PEG符号也只是已有质量/成长约束，未见新信息，不入新增候选。'
    ),
    '8.': (
        '剔除新股、科创板、ST后，分别取8年ROA最低10%、每股留存收益最低10%、非线性市值最低10%的股票，再各取5只小流通市值，合并去重后持有；源码标题“科技与狠活”与实际条件无关。',
        'low roa_ttm_8y × small size; low retained_earnings_per_share × small size; low non_linear_size × small size。',
        '聚宽预计算因子roa_ttm_8y/retained_earnings_per_share/non_linear_size、流通市值、EPS；长期ROA和留存收益字段需平台可用性验证。',
        'small_size_factor_duplicate',
        '最终排序几乎完全由小市值决定，三个低质量/非线性市值筛子只提供候选池；与已有SIZE及低ROA/价值路线重复，暂无独立因子。'
    ),
    '9.': (
        '每月在全A中剔除科创板/ST，要求PB>0、ROE>0、营收和净利润同比>0、经营现金流/营业利润>5，再按总市值升序持有95只，并保留涨停股。',
        'small market cap × positive ROE × positive revenue/profit growth × OCF/operating-profit > 5 × positive PB。',
        'PIT估值和财务指标、流动性/涨停状态；OCF/营业利润阈值量纲和极端值处理需要核查。',
        'small_size_quality_duplicate',
        '是大容量小市值叠加基本面正向过滤，与已有小市值、质量/现金流簇高度重复；未发现新可分簇信息。'
    ),
}
if __name__ == '__main__': add_authored(E, '2024年度精选策略1')
