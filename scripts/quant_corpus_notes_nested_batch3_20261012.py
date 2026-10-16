from quant_corpus_semantic_review_20261012 import add_authored
E={
'04多标的版ETF策略-重构':('34ETF按20条涨幅5~20%、MA5>MA20取3；超过20%或连续两天跌出前8退出，每日09:25信号09:30交易。','bounded momentum19 × MA gate + two-day rank8 exit buffer。','ETF日线。','etf_rank_persistence_method','buy_list未剔除已有持仓，现金分摊目标可能反向缩仓；排名缓冲为换手方法非新股票alpha。'),
'05动量最强':('34ETF先筛20日均成交额≥千万；25条log价加权斜率年化×自写R²取2，日轮。','weighted trend25 × R² with amount20 liquidity gate。','ETF日线成交额。','etf_liquidity_trend_method','polyfit损失权重w²而R²用w及普通均值；无正分门槛；全池不合格不清仓；只买新增不再平衡。'),
'06-EPO':('34ETF上市满30日，以250日逆方差权重与全段收益秩各半作signal，相关矩阵向I收缩60%后逆协方差求长仓、月调。','normalize(max(inv(cov_shrunk(.6)) @ (.5*invvar+.5*momentum_rank),0))。','ETF长日线宽表。','etf_covariance_shrinkage_method','panel=False后仅取close变单列长表，未按日期股票pivot；pct_change可能跨证券，权重维度错配；run_optimization2未调用；不应直接复现标题收益。'),
'07多品种':('34ETF按34条log价年化斜率×R²筛正分前三；匹配2025/17的1200日逆方差锚定EPO收缩20%，月调，空目标清仓。','trend34 selection + anchored EPO(.2)。','ETF1200日价格宽表。','etf_epo_parameter_duplicate','b9452a45a8b773cf完整AST证明；只换标的池与空目标处理，非新alpha。'),
'08ETF动量':('6函数精确匹配旧策略，13观测动量与MA10门槛选单ETF，修改固定标的映射。','momentum13 + MA10 filter。','ETF/指数日线及映射。','exact_etf_ma_duplicate','3f8c9a2a32372b40证明；399006映射仍为指数，需改成可交易ETF，部分g.local_stocks与map不一致。'),
'09ETF动量':('9函数精确匹配原ETF动量MA乖离择时，34ETF取20日动量第一，14:50轮动并开盘风控。','momentum20 × MA deviation timing。','ETF日线与盘中价。','exact_etf_bias_duplicate','500119c128a823fa证明；非新股票alpha。'),
'10ETF策略':('3函数完整匹配已核验核心资产ETF轮动，无新增执行函数。','existing core-asset ETF momentum rotation。','ETF日线。','exact_etf_core_duplicate','0feb22c38c4b0b51证明；不重复计新因子。'),
'聚宽使用说明':('聚宽注册、策略编辑、回测指标和模拟交易使用指南，无策略公式。','无。','无需行情。','platform_user_guide_no_factor','纯操作文档完整阅读，不按标题假造因子。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/ETF轮动策略2026')
