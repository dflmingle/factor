from quant_corpus_semantic_review_20261012 import add_authored
E={
'03小市值':('中小板流通市值前15，过滤ST/停牌取5；周一开盘等权，偏离目标>5%才再平衡。','small float cap + rebalance tolerance .05。','PIT指数/流通市值。','size_rebalance_tolerance_method','阈值只控制同一持仓权重调整，离开目标仍全卖，不代表硬池级换手上限。'),
'04-五年':('20函数AST匹配旧35主路径：热门行业MA20广度，SG最高10%、四增长MS最高10%、PEG最低20%后换手波动最低一半三腿再小流通市值取9。','high SG/MS or low PEG×turnover-volatility → small size。','PIT行业/财务/PEG/换手波动。','exact_growth_size_duplicate','c311fcf3952c59a7证明；10天持仓涨停禁重买；MS估值查询未传昨天日期，需PIT审计。'),
'05高增':('13函数精确匹配2024/29：PE≤30、调整利润正、营收增≥15%、PEG≤1，再小市值持10周调。','growth and PEG gate → small cap。','PIT营收/调整利润/PE。','exact_growth_size_duplicate','167bcd5b0c80089d证明；增速按自然日同期和abs分母，不是标准供应商增长字段。'),
'06价投':('23函数匹配2024/13，实际ROE>.15、ROA>.1后小市值，月末持10，涨停保护。','quality ROE/ROA gate → small cap。','PIT质量/市值/涨停。','exact_quality_size_duplicate','cc75a7b873ae87c4证明；get_peg无PEG筛选，分红未调用；.15/.1单位与百分比需查供应商。'),
'07小市值':('12函数匹配2024/68：399101流通市值最小100筛ST/涨跌停，取5周调。','small circulating cap in index。','PIT指数与流通值。','exact_size_duplicate','3d2f782363edb0db证明；停牌过滤变量未用于目标。'),
'08小市值':('18函数匹配SG/MS/PEG-HL旧28，销售增长/成长合成/PEG换手稳定性各腿小盘，周调。','SG + MS + PEG×low turnover volatility → small size。','PIT聚宽财务/波动字段。','exact_growth_size_duplicate','02a4b301b76f4796证明；不重复计新簇。'),
'09小市值':('低正PB半池且EPS正，五季度4*ROE第五列−前四列之和取最高10%，排指定行业，再最小流通市值；18函数旧式匹配。','ROE quarter acceleration × low positive PB → small size。','PIT季度ROE顺序/行业/PB。','exact_roe_pb_size_duplicate','90c12e59e0a1c6c3证明；需核查季度序，非全样本未来标准化；20天涨停禁重买。'),
'10改进':('中小板10~100亿、归母/净利正/营收>1亿、价≤50，股数自适应、1/4月退出，9%个股/5%市场止损。','profit/revenue gate → small cap with market execution veto。','PIT财务与指数日线/盘中。','exact_profit_size_duplicate','1ddb39d465dda3bf证明；audit默认False，即使开启构建df_audit未替换df；无新审计alpha。'),
'实01小市值':('399101流通值前15筛ST停牌后取5，每周等权按100股整手调整。','small cap with round-lot rebalance。','PIT成分/流通值。','size_execution_no_new_factor','精细风控标题实际主要日志和整手交易；无止损腿。'),
'实02小市值':('399101流通值前9过滤ST/涨跌停/停牌后取3，14:30每日交易；开仓执行MA5过滤由旧函数控制。','small cap + intraday MA gate。','PIT成分与盘中价。','size_ma_execution_duplicate','25cb6a6c14d1cb76证明；adjust_position修复不存在持仓get，备用adjust_position2未修；需按调用路径记录MA而非名字。'),
'聚宽使用说明':('完整同文聚宽新手指南，包含注册、编辑、回测和模拟交易流程。','无因子。','无行情。','platform_user_guide_no_factor','不参与候选计数。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/小市值策略2026')
