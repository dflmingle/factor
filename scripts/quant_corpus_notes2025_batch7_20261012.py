from quant_corpus_semantic_review_20261012 import add_authored
E={
'32EPO':('10只ETF250日收益估计协方差，逆方差归一向量作为signal；相关矩阵60%向单位阵收缩，solve逆协方差后截负归一，每月调仓。','positive normalized inv(shrunk_cov) @ inverse_variance_signal。','ETF日线与历史可交易状态。','portfolio_covariance_shrinkage_method','shrunk_cov变量计算后未使用，实际solve(cov_tilde)；不是新股票alpha，权重全负或零时归一有风险；退出池ETF未显式清仓。'),
'33回':('46项基本面/量价特征预处理后调用外部model_baseline.pkl predict_proba[:,1]降序买5，每月轮换；其余17函数与已审来源精确匹配。','external model probability on PIT/technical features。','模型权重、训练标签/日期及聚宽特征映射。','external_ml_pipeline_blocked','完整pipeline标题不能替代缺失训练链；没有模型和训练边界不能复现预测或确认样本外。'),
'34十':('中小板市值5~50亿升序、股价≤80，选5；周二换仓，1/5~2/5及4/5~4/30停；个股跌7%与市场开收平均绝对变动≥5%退出。','bounded small-size selection × seasonal and loss gates。','PIT指数成分、市值、日线/盘中执行。','smallcap_seasonal_duplicate','市场abs会在大涨也清仓；reason_to_sell使用is比较字符串；昨日涨停留仓与打开涨停卖是执行，不新增因子。'),
'35【菜':('20个函数AST精确复用已审2024策略1/36：一年股息率前25%、PB<3及源码负PEG条件，再最小总市值，月调。','dividend_yield1y × lowPB × negativePEG × small size。','PIT分红、PE/PB、利润增长、市值。','exact_dividend_value_size_duplicate','证明fe67b7c1cd43308c；保留源码PEG负号缺陷，不凭标题收益认新簇。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
