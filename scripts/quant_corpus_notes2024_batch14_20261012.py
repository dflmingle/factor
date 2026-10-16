from quant_corpus_semantic_review_20261012 import add_authored

E = {
    '85.': (
        '在多只宽基指数及对应ETF中计算30分钟BBI(3/6/12/24)与当前价比值，选周期动量最弱的指数；再比较上证、深成指、创业板、中证1000、红利指数的当日涨幅，若最强指数涨幅>0且最弱指数BBI比值<1则买入该最弱指数对应ETF，否则清仓。',
        '30m BBI ratio cross-index ranking + strongest-index daily return regime。',
        '指数/ETF分钟线和日线、上市日期。',
        'etf_bbi_code_broken',
        '源码df_incre列名不一致(初始化大盘代码/当前价格，追加大盘指数/当前数值，后续访问前者)，实际运行会KeyError；且选最弱BBI指数买入逻辑与注释相反，不能复现。'
    ),
    '86.': (
        '在2022-11-01至2023-02-07逐日检查主板非ST且上市超过500日股票，利用过去三年11个季度净利润和扣非净利润的年度和，若连续三年两者较低者均为负则列为潜在ST；随后剔除已发布扭亏预告或最新年报已盈利的股票。',
        'three-year consecutive negative min(net_profit, adjusted_profit) risk flag for ST prediction。',
        'PIT季度财务、业绩预告、ST状态、上市日；公告发布日期。',
        'st_risk_filter_external_pending',
        '属于风险过滤而非收益因子；源码y3/y3a误用了fqd[1][3]而非fqd[2][3]，存在实际计算错误，不能直接复现。'
    ),
    '87.': (
        '全A过滤PB>0、净资产收益率指标inc_return>0后，计算最近3年除权登记日累计分红金额/总市值，按股息率降序取前10%，再去交易状态异常并等权持有30只，月调仓。',
        '3y dividend cash / total market cap top10% ∩ positive inc_return; equal-weight30 monthly。',
        'PIT分红登记日、总市值、ROE/收益指标、交易状态。',
        'dividend_quality_duplicate',
        '与已有高股息簇重复，但3年累计分红/市值是可复现的红利定义；inc_return字段语义需确认，暂不单独建簇。'
    ),
    '88.': (
        '中证500股票池每日用20日收盘价线性回归斜率除以均值作归一趋势系数，取正趋势并按系数排序；再过滤20日内相对指数涨幅不超过1.5倍的股票，持有前5。对持仓用20日高点回撤25%、RSI<50等参数做损控。',
        'normalized 20d close slope (OLS slope / mean price) >0 + 20d relative-rise cap vs CSI500; top5。',
        '中证500成分、日线收盘、指数涨幅、RSI/均线等技术指标。',
        'trend_normalized_slope_duplicate',
        '归一化斜率和涨幅约束与已有趋势/动量轴高度重叠；损控属于执行层，不新增独立因子。'
    ),
    '89.': (
        '按中信一级行业统计上市超过1年的股票中，收盘价高于过去52周至前一周最高收盘价的数量减去低于对应最低收盘价的数量，再除以行业有效股票数，形成行业NH-NL净新高占比；用±20/30%(小行业±30/40%)阈值定义贪婪/恐惧，极端状态回到阈值内时做行业反转并以5日高低点止损、30日到期、1周后止损移至成本。',
        'industry NHNL=(new 52w closing highs - new 52w closing lows)/eligible stocks, with extreme-to-normal reversal signal。',
        '行业历史成分、上市日、日线收盘；原文使用外部knight_scr数据库和固定截面行业成分。',
        'industry_breadth_reversal_external_pending',
        '行业广度反转可能提供新信息，但成分使用最近截面回填历史，存在成分前视；当前全A标准池没有中信行业历史成分，需先做PIT成分代理后再评估。'
    )
}

if __name__ == '__main__':
    add_authored(E, '2024年度精选策略1')
