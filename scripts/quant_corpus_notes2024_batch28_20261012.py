from quant_corpus_semantic_review_20261012 import add_authored
E={
'64.':('ETF近13观测价格比实际12交易日动量，正收益且高于MA10取最强1只；13:30使用60分钟MA止损。','positive RET12 & C>MA10 ETF rotation。','ETF日线及60分钟。','etf_momentum_ma_duplicate','与策略2/16同主逻辑，ETF映射含指数代码作交易标的需修正；不能把盘中止损收益当截面alpha。'),
'65.':('沪深300、黄金、国债、纳指四ETF，120日收益左尾1%经验ES倒数归一化配置；约30日或价格偏离15%再平衡。','w_i ∝ 1/ES120,left1%。','ETF历史日收益和持仓成本状态。','etf_tail_risk_allocation','所谓money_fund实际为纳指ETF；resample日历日引入周末零收益，1.2条尾样本却纳入2条并除1.2，ES非标准估计；补仓需价格高于成本、25%偏离门槛。可提取尾险控制，未提供个股排序。'),
'66.':('ETF20观测归一价格线性斜率取最大；指数C/MA60的MA10最近30条z阈值±4决定状态，亏10%清仓。','slope20 normalized close + z30(MA10(C/MA60)) regime。','ETF与指数日线。','etf_bias_timing_variant','get_rank返回[stock,score]而adjust_position按标的列表遍历，可能把数值分数当股票；指数信号不是个股新簇。'),
'67.':('全A非ST，每月标准化并5/93分位截尾 residual_volatility、VROC12、size，相加升序取50。','low Z(residual_volatility)+Z(VROC12)+Z(size)。','Barra残差波动/size、12日量变。','low_idio_vol_volume_size_candidate','growth和momentum虽读取但不入评分；这是低特质波动×低量变×小规模组合，须测试净增量。Barra无字节等价需proxy；1D数组axis=1可能不兼容。'),
'68.':('中小板指数成分按流通市值最小100初筛，ST/涨跌停过滤后持最小5只，周调仓。','small circulating market cap within 399101。','历史成分、市值、交易状态。','small_size_duplicate','mkt_list的停牌过滤没有用于check_out_lists；标题高胜率不是新增信号。'),
'69.':('最终固定中小300ETF159905；历史高点后回撤占此前上涨幅度>68.2%开70%仓，每月按价值路径增加约0.5%目标调整，浮盈回撤止盈。','deep retracement entry + monthly value averaging。','指数及ETF日线、分钟执行、成本路径。','etf_grid_value_averaging','前两组指数/ETF赋值被后组覆盖；375/625观测count使用浮点可能不兼容；单资产定投/状态策略，不能等同股票截面因子。'),
'7.':('四ETF按120日1%经验左尾ES的倒数分仓，30日或价格偏离15%调仓，偏离和成本条件限制补仓。','inverse ES120 allocation。','ETF日线、持仓成本。','etf_tail_risk_duplicate','完整源码与本批65相同主逻辑，纳指被命名money_fund；日历日零收益及尾样本/分母问题相同。')}
if __name__=='__main__':add_authored(E,'2024年度精选策略2')
