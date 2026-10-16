from quant_corpus_semantic_review_20261012 import add_authored
E={
'43小':('399101市值5~300亿最小9，1/4月停转货基；个股10%止损/翻倍止盈与市场开收绝对均变5%退出，涨停开板补仓。','bounded small size × seasonal and stop gates。','PIT成分/市值、分钟涨停和交易状态。','smallcap_seasonal_execution_duplicate','买货基复用按目标数量减总持仓数的逻辑可能不执行；is比较字符串；市场abs会在大涨清仓。'),
'44国':('10~10000亿市值、利润正/营收>1亿/ROE ROA正，审计异常排除；5月预案分红/价格升序，其它月排不分红；MA10乖离调3~6股，1/4月转货基。','small size × PIT audit/dividend quality gates × market bias position count。','审计意见公告、分红预案、财务、日线和盘中。','audit_dividend_smallcap_candidate','预期分红排序ascending=True选低股息；分红不足会补回原股而非硬约束；5月以外仅排明确不分红；买仓资金分配需独立账本核查。'),
'46高':('13个函数匹配已审2024策略1/29：PE≤30、调整利润正、PEG≤1、营收增长≥15%后小市值10只周调。','growth/PEG constraints × small size。','PIT营收/利润与估值。','exact_growth_size_duplicate','4237a0356a231966精确证明；保留利润增速绝对分母缺陷，不新增重复测试。'),
'47多':('白马冷暖ROA/PB、5ETF趋势曲率轮动、小市值国九条三腿；名义比例15/35/50；ETF用25/15日斜率R²、指数权曲率与RSI尾部修正；小盘5~30亿和10~50亿财务质量池拼接。','regime value-quality × ETF curvature-adjusted trend × small-size quality composite。','PIT财务、ETF/指数日线、解禁、分钟、子账户。','multi_strategy_framework_execution_blocked','缺set_subportfolios，比例只决定调度未实际创建分仓；RSI period参数未截取，取全30条；经营流入非净现金流，inc_return非可直接替换ROE；不能复现标题整体收益。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
