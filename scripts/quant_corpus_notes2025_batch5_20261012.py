from quant_corpus_semantic_review_20261012 import add_authored
E={
'26波':('729观测基金收益年波动5~33%，按绝对相关均值最低取4；再25观测趋势分在−.5~4.5取最强1每日轮。','low mean absolute correlation universe × bounded trend25。','ETF长日线。','etf_low_correlation_universe_method','不是买4个分散资产，而是在4个低相关候选里只持1；可参考候选池去冗余，不证明个股alpha。'),
'27人工':('加载外部tgt_net.pt、6输入3输出DQN预测交易，模型类与2024策略1/41精确一致。','external DQN action scores。','模型权重与训练特征/奖励/滚动训练链。','dqn_external_exact_duplicate','7顶层函数及类方法已审匹配；本文没有标题所称完整训练代码，不能从权重文件名证明训练无泄漏。'),
'28韶':('中小板最小流通市值5只，微盘全A最小5%内收益落在截面中位±1σ的占比衡量一致性；弱市且普跌/高一致性清仓、强反弹恢复；1/4月空仓。','microcap return-concentration breadth × median-return regime。','全A日收益与市值、指数、交易状态。','microcap_consistency_risk_candidate','change_pct是收益并非资金流；df_all成交额读取未使用；check_signal未调度，平日信号改变不自动全仓操作，只周调整时落地。市场风险开关可研究，非新增个股排序。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
