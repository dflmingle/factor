from quant_corpus_semantic_review_20261012 import add_authored
E={
'37.':('全A分三腿低ROA8y、低留存每股、低非线性市值各取10%后正EPS和小流通市值前5并集；CSI500 EMA2-EMA4<0则清仓。','low roa_ttm_8y∪low retained_earnings_per_share∪low nonlinear_size, each10%, positive EPS→small cap; CSI500 EMA2/4 bearish veto。','聚宽因子、PIT EPS、市值、指数日线。','low_quality_smallcap_timing_duplicate','三个腿均小市值；因子方向按ascending=True为低值；指数EMA信号可拆市场开关，非个股alpha。'),
'38.':('ETF短25日回归得分减1/6长200日回归得分，得分差15至0.1才候选；再要求RSRS18斜率高于过去250日beta均值-2σ。','ETF score=slope25_ann*R² - slope200_ann*R²/6；WLS/RSRS18 beta lower band。','ETF OHLC。','etf_momentum_longshort_duplicate','仅ETF；get_rank缺initialize上下文；beta均值/标准差窗口实现依赖；不转全A。'),
'39.':('过滤FCF/市值>2%、调整利润>0、ROE>3、净利率>10、净利增长>5，按FCF/市值和ROE各行业+市值中性标准化后相加，取前10月调仓持8。','quality_cashflow=neutralized_z(FCF/marketcap)+neutralized_z(ROE)。','PIT现金流/财务、市值、行业。','fcf_roe_quality_pending','源码get_fundamentals(date=None)潜在未来；FCF为经营现金流−投资现金流；中性化适配需平台代理。'),
'4.':('昨日涨停、近10日非连续涨停、60日相对位置<=0.5、当日低开4%~3%买；11:28盈利且未涨停卖，14:50清仓。','first-limitup rebound=prior limitup∩not consecutive limitup10∩relative_position60<=.5∩open gap[-4%,-3%]。','日/分钟OHLC、涨停价。','limitup_reversal_intraday_blocked','纯盘中事件；get_relative_position close/high/low时点要冻结；适合minute proxy，不作日频标准池。'),
'40.':('中证全指ROE>4，PB升序前100，净利增速升序筛前50；过去约2000日每20日采样均线mas与全均线mal差<0才买。','low PB∩high profit_growth within ROE>4; sampled MA20 minus long MA<0 mean-reversion gate。','PIT PB/ROE/利润增速，qfq日线。','value_meanreversion_pending','先低PB后高增长的顺序筛选；均线采样代码复杂且买入低于长期均值，和趋势策略方向相反。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
