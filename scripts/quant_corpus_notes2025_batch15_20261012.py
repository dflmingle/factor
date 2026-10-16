from quant_corpus_semantic_review_20261012 import add_authored
E={
'60高':('三年股息率前20%，ROIC_TTM>.08，按应付账款周转天数最高取5；月调。','high dividend3y × ROIC gate × high accounts_payable_turnover_days。','PIT分红、ROIC、应付账款周转字段。','payables_days_quality_dividend_candidate','3%止损与Stop_Loss定义未调度；最高应付天数可表示供应链议价亦可支付困难，需字段/方向验证，不当作自动高质量。'),
'61Bi':('60日ETF6维OHLCV逐窗口MinMax，外部双向LSTM权重输出降序取3，上市375×3天、每天量≥1000万，周轮。','BiLSTM on past60 normalized OHLCV。','model_baseline_BiLSTM.pt、训练标签/分割与ETF日线。','external_bilstm_blocked','forward每次随机hidden/cell未固定，eval也不保证确定；双向网络仅在已知历史窗口内不等于未来泄漏，但权重训练日期不明。'),
'62基':('8函数匹配2024策略1/76：开盘/外部网页单位NAV折价前2、额>1000万、复权因子1及|溢价|<20%，折价阈值2.5%可降1.5%。','ETF opening discount to external NAV。','ETF开盘、点时NAV/IOPV与网页历史。','exact_etf_nav_external_duplicate','证明ecc21238d7af51cd；缺历史网页点时数据，不能复现股票因子或把当前NAV回填过去。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
