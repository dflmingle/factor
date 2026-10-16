from quant_corpus_semantic_review_20261012 import add_authored
E={
'70.':('每周全市场高growth前10%，EPS>0后流通市值升序持5；上市250自然日等状态过滤。','high Barra growth × positive EPS × small size。','PIT成长综合字段/EPS、市值。','growth_size_duplicate','growth为供应商综合字段，不能等同sales_growth或净利润同比；代理应单列，不能重复当新簇。'),
'71.':('IF主力日收益差两期均值决定方向，分钟典型价(H+L+C)/3的MA5/20交叉且MA20连续上/下，偏离>3ATR退出，日终平仓。','minute typical-price MA crossover with ATR14 exit。','股指期货主力分钟OHLC、日线。','futures_minute_cta_blocked','ATR为TR的简单MA14；日频迁移只能标proxy，不当精确原策略回测。'),
'72.':('HS300约300日每30日样本截面标签取收益最高/最低30%；50树RF预测20项行业/市值中性特征，15日持5、60日重训，最小方差优化。','RF on BP/SP/CFP, profitability/growth, price momentum/volatility, main-money-flow and log circulating cap。','PIT财务与分季字段、主力资金流、历史成分、训练样本及优化器。','multifactor_ml_recipe_inventory','训练收益标签区间均截至当时日期，不能凭ML名声断言前视；MOM_N用iloc[1]导致day−2间隔；ROA_TTM实际为季度ROA变化均值/波动，非TTM；VSTD为原始量标准差；资金流无本地等价。原子需去重，整体并非现成公式。'),
'73.':('净利润同比>0.2，近两日实体完全向下跳空股票按行业候选数量最高3行业过滤，再按利润增长降序取5，每30次调用更新。','profit growth × downside body gap × industry event concentration。','PIT利润同比、两日开收盘、历史行业。','profit_gap_candidate_implementation_broken','min(旧O,C)>max(新O,C)是向下跳空；set(temp.keys())顺序生成jump后按行赋值，代码股票错配；dapan_stoploss未调用。修正映射才能测试适配版，不能复现错配收益。'),
'74.':('高sales_growth前10%，小流通市值30内EPS>0，再按4*(MAC120−1)/6+(MAC20−1)降序周持10。','high sales_growth × small size × [2/3 MAC120+MAC20]。','供应商MAC120/MAC20定义、PIT成长/EPS、市值。','size_growth_ma_momentum_candidate','14函数已审一致；MAC字段先核对定义再重构，不把标题动量或归一常数误写成RET120/20；测试时需控制市值/成长重复。'),
'75.':('三ETF27观测对数回归年化斜率×R²选1；RSRS18/600与MA20五日差控制，仅沪深300ETF另加北向流入高于运行中位数门槛，亏50%止损。','ETF trend27 × RSRS/MA regime × northbound conditional filter。','ETF/指数日线、北向。','etf_momentum_external_variant','北向中位数为截至当前运行历史，初值15/下限5；持仓调量把金额减股数，量纲错误。无本地北向不按日线替代。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
