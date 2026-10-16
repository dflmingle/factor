from quant_corpus_semantic_review_20261012 import add_authored
E={
'55.':('与16完全同式的大市值价值投资，新增邮件通知。','PB<1∩CFO>1m∩adjusted_profit>1m∩ROA>15%∩profit_growth>0，ROA降序。','PIT财务、估值。','high_roa_lowpb_duplicate','邮件配置为占位符；不新增因子。'),
'56.':('外部XGBoost以16个技术因子和行业哑变量预筛，再用三个PyTorch模型对60日K线张量打分，取前三；模型文件外部依赖。','external ensemble probability on boll/EMA/MAC/MFI/price + 60d OHLC tensor。','模型权重、外部文件、技术因子。','deep_ml_external_blocked','模型文件与训练标签未提供；预测先按技术因子再按张量二次筛选，无法本地因果复现。'),
'57.':('外部CSV调用find_RoundingBottom识别圆弧底及买点，仅做图形识别。','rounding_bottom pattern boolean。','外部pattern_detect和CSV。','pattern_external_blocked','没有算法源码、窗口或买卖时点，不提取标准因子。'),
'58.':('融资融券股票池中，按当日振幅/(涨停价-昨收)>1.5筛选，振幅降序前10，5分钟交易；做空/平仓执行。','intraday_range / limit_room >1.5, rank range/close。','融资融券权限、5分钟和涨停价。','margin_intraday_blocked','做空策略，不属于当前多头全A口径；清仓函数未实现。'),
'59.':('过滤流通股本异常值后取第一、第二个十等分区间，PB>0、ROE>0、ROA>45%，再市值升序10只，每日持5。','mid-small cap bucket + ROA>45% + ROE>0 + low market cap。','PIT ROA/ROE、流通股本、市值。','high_roa_smallcap_duplicate','ROA>45%极端阈值；divide_list分块余数/空块风险；核心仍是小市值。'),
'6.':('近3年股息率前50%，低换手波动前80%，低杠杆MLEV前50%，市值升序前15，每周调仓。','dividend_yield3y50∩low turnover_volatility80∩low MLEV50→small cap。','PIT分红、换手波动、MLEV、市值。','dividend_lowlev_smallcap_pending','与高股息低PE/低波组合相关；MLEV字段需对齐，可能提供低杠杆约束新信息。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略1')
