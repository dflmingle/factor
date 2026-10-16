from quant_corpus_semantic_review_20261012 import add_authored
E={
'1.':('全A过滤375日、非4/8/68和ST；5组手工线性组合因子按总分降序取前10%，再正EPS和最小流通市值；五组分别为ARBR/SGAI/净利营收/留存每股、Price1Y/利润成本/VOL120、未复权价/利润成本/存货周转、负债/成本收入/DAVOL20/未复权价/销售增长、TVSTD6/现金流每股/Sharpe120/非经营净利。','five composite weighted sums; top10%∩EPS>0→small cap；weekly.','PIT聚宽因子、估值、交易状态。','multi_composite_weighted_duplicates','系数疑似训练输出，未说明标准化；price_no_fq与qfq字段混用；四月停盘规则为执行开关。'),
'10.':('四ETF轮动，20日bias趋势评分，RSRS18/600与8期评分斜率择时，WR极值及60分钟MA20乖离止损；主因子为ETF相对动量。','ETF momentum20 on bias90 normalized slope + RSRS18/600 z*R² + WR21/14; choose max score.','ETF/index daily and 60m.','etf_momentum_rsrs_external_pending','仅ETF，不转全A个股；g.stock_motion初始索引存在窗口边界；运行路径交易重仓单票。'),
'100.':('Barra十因子在中证全指逐日提取，winsorize/standardize后行业+市值中性，鲁棒回归收益求因子收益；归因研究非选股策略。','size,beta,momentum,residual_volatility,nonlinear_size,BP,liquidity,earnings_yield,growth,leverage factor returns after neutralization.','Barra因子、行业、市值、日收益、指数成分。','barra_attribution_duplicate','样本仅2023-07约一周；源码factor_data get_factor_values end_date误用外层变量；不能当已验证alpha。'),
'11.':('全A过滤上市>375日、非4/8/68/ST，按price_no_fq最低10%，再市值升序前15、正EPS，每周持有10；另算收盘最低10%但未使用。','low price_no_fq10%∩EPS>0→small cap; weekly.','PIT价格/市值/EPS。','low_price_smallcap_duplicate','price_list2未使用；原文高收益主要是低价市值暴露，与现有size轴高度相关。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
