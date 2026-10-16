from quant_corpus_semantic_review_20261012 import add_authored
E={
'98热点':('行业/概念看板：日涨9%数量与成分占比、MA20广度、各档净资金/股票数/净额比；近热点概念内按10日大涨次数取3，展示累计简单收益排序。','category attack count/fraction × stock attack_count10; optional net money-flow aggregates。','20240928概念CSV、当前行业、各档资金流、日线。','concept_breadth_dashboard_data_blocked','不是策略回测；概念静态快照和当前行业不能回填历史；所谓累计收益是pct_change.cumsum非复利；score_by_return_at_dt iloc[return_days:]删股票行非日期列；比率分母为各档净额和非总成交额。'),
'99韶':('创科上市30天非ST昨日封板，9:24~9:25:10竞价tick价比>.94、量比>2.5、额>1000万且对昨收>1.05，半仓等权买，次日尾盘未封板卖。','prior_limitup × auction tick volume acceleration × gap>5%。','竞价tick盘口a1/成交、涨停、分钟。','auction_tick_acceleration_blocked','量比混用末成交量与初卖一量，不能用日量替代；空tick和零分母未防护；不作日频平台候选。'),
'9干':('大/小20股10条均收益择强，均弱则5境外ETF；大盘ROIC/质量低估值3腿并集，小盘ROE ROA约束最小市值最多9；月调和8%止损后补幸存落后股。','size-relative momentum10 × large quality/value or small-size quality。','PIT成分/财务、ROIC、ETF/指数日线与分钟。','size_value_etf_framework_variant','ROIC_BIG市值>300亿，与48>500亿不同；三池并集和small*3导致3非最终持股上限；没有可直接认新簇的独立信号。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
