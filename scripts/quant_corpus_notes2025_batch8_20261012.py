from quant_corpus_semantic_review_20261012 import add_authored
E={
'36快':('4只宽基ETF按C/MA90的20点归一OLS斜率排序，原持仓分×1.04；沪深300 RSRS18/600分及8点斜率择时，趋势加速>19或当日涨4.8%退出；另60分钟MA20止损。','bias90 slope20 × RSRS18/600 gate × holding hysteresis。','ETF/指数日线和60分钟。','etf_bias_rsrs_duplicate','RSRS为z(beta)×R²，不乘beta；门槛是大于−.68；check_lose亏90%才触发，不能误记常规9%止损。'),
'37微':('读取外部wp_ks_index.csv上一日signal>0清仓；选股Price1Y/利润成本/VOL120固定负权重前10%，正EPS后最小流通市值5。','breadth=sum(close_end>close_start)/N over20 obs; external breadth signal × known composite small size。','PIT中证1000成分、日线、外部signal生成规则。','breadth_external_signal_blocked','get_ks_index仅定义未调用，标题双均线生成代码不在本文件；_get_stocks含未定义context且未调用。不能把外部signal当已复现。'),
'38ETF':('4ETF25日log收盘线性权重1~2拟合，score=(exp(250*slope)−1)×自写加权R²，最高1每日轮动。','weighted log slope25 annualization × weighted fit quality。','ETF日线。','weighted_etf_momentum_duplicate','polyfit的w会平方进入残差目标，自写R²仅用一阶w且普通均值；保留源码定义，不称标准加权R²；文件math未显式import。'),
'39干':('月调；399303成分20条收益均值/399905均值>1.2切大盘低估值高质量，否则质量约束小盘5只；BIG实际查询用stocks而非过滤后choice。','relative index-constituent mean return ratio × size/value/quality switch。','点时成分、财务、市值、日线。','size_regime_gate_candidate','变量BIG/SMALL与指数规模含义不一致；收益比在分母负/近零时难解释；sell_stocks未调度，不能算入5%止损。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
