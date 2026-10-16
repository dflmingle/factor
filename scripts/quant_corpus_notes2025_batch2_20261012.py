from quant_corpus_semantic_review_20261012 import add_authored
E={
'14安全':('四ETF25观测加权log回归年化斜率×拟合优度，信号0~5间取最高1，每日换仓。','weighted log trend25 × weighted R², weights linear1→2。','ETF日线。','weighted_trend_etf_variant','polyfit的w按平方进入拟合，R²用w而非w²且均值未加权，非一致加权OLS；可提取近期趋势权重思路，尚不属新股票簇。'),
'15小':('中小板10~100亿市值，归母/总净利正且营收>1亿，市值最小；指数距MA10决定3~6持股，1/4月转货基；成本止损及指数日内普跌开关。','size × positive profit/revenue; market regime adjusts holdings。','PIT财务、市值、指数和分钟、可选审计。','small_size_quality_execution_variant','审计默认False，开启后df_audit也未返回；new_num不会为0；市场止损标注reason时stock可能残留/未定义。标题排bug不代表所有问题消除。'),
'16集合':('首板高开、低开、炸板弱转强三模式，竞价量占昨日>=3%、左压放量，金额/市值和60日位置等筛选，盈利/破MA5退出。','auction volume and gap × first-limit / failed-limit event。','真实竞价tick/涨停、分钟及市值。','three_auction_modes_variant_blocked','与13同轴，区别排前两日触板及现金>30%才新买；低开用day_open，其它用竞价[0]，时点需逐条核对。无竞价不原样测。'),
'17多':('13ETF按34观测log回归年化斜率×R²取正分前三，1200日收益协方差向相关单位阵收缩20%，以逆方差锚定EPO求长仓权重，月调。','trend34 selection + anchored EPO covariance shrinkage w=.2。','ETF日线长历史。','etf_epo_allocation_candidate','EPO为配置方法非新股票alpha；空目标/奇异协方差/全负权重未防护。可参考相关矩阵收缩和风险锚定进池配置研究。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
