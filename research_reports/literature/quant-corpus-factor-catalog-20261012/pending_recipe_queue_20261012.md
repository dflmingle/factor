# 新增可复现候选队列（逐篇阅读后整理）

本队列只记录已逐篇核对源码、但尚未正式本地回测的候选；不等同于已验证alpha。

## breakout_recipe_pending: quant/2021年度精选策略/41.均线黏合，突破前三十个交易日最高点选股法.txt

- 公式/规则：breakout=close>max(close[-30:-1])；MA13>MA34>MA55；过去约10日和19日三组均线相对差绝对值≤3%；(max30−min30)/close<0.2；close>=open；持仓连续3日收盘低于MA13卖出。
- 数据条件：日线OHLC，PIT股票池和停牌/ST/退市过滤；突破使用前一日窗口避免把当日纳入最高点。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## dividend_yield_pending: quant/2021年度精选策略/4.红利搬砖，年化29%.txt

- 公式/规则：div_ratio=0.33*0.01*sum(近3年分红金额)/market_cap；PB、PE>0；年中更新，取div_ratio最高。
- 数据条件：PIT分红公告/除权、估值和市值；需按公告日而非当前分红表连接。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## dynamic_volume_breakout_pending: quant/2020年度精选策略/54 中长线买入卖出点选择.txt

- 公式/规则：长横盘低振幅×成交量跃升，窗口由最近高量事件决定；辅助cow=num_fall*num_cross/(PB*sqrt(circMV))未被实际路径调用。
- 数据条件：日OHLCV可提取动态区间，skip_paused及财务换手定义需proxy标记；盘中执行另需。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## market_breadth_recipe_pending: quant/2021年度精选策略/36.市场底部特征研究.txt

- 公式/规则：low_price_fraction=#股票收盘<2/当日股票总数；low_pb_fraction=#PB<1/总数；另计算M2、上证收益和中位市值变化，源码多为探索性绘图。
- 数据条件：全A历史股票池、复权/未复权收盘、PIT估值、宏观M2、指数；需按当日可见股票池。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## market_breadth_recipe_pending: quant/2021年度精选策略/45.市场宽度.txt

- 公式/规则：breadth_industry_t=100*count(BIAS20>0)/count；同时BIAS60、BIAS120可扩展；源码当前只保留BIAS1并绘热图。
- 数据条件：PIT行业成分、复权收盘和行业分类；需冻结指数成分日期。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## northbound_flow_pending: quant/2021年度精选策略/49.根据北上资金买股票的最佳持股时间探讨.txt

- 公式/规则：net=buy−sell；window=nday日累计（由g.nday设定）；rate=sum(net)/1e8/circulating_market_cap；降序取3。
- 数据条件：PIT沪深港通每日成交/买卖额、流通市值和股票池；需确定nday各值及披露时点。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_lowvol_composite_pending: quant/2021年度精选策略/5.价值低波（下）--十年十倍（2020拜年）.txt

- 公式/规则：universe=HS300；PE<20、PB/PE>0.1；weight_i=(std241(daily_return_i))^{-1}/sum；market filter index_close>MA61，否则treasury。
- 数据条件：PIT指数成分/PE/PB、qfq日线收盘、国债基金；低波权重可改造成个股原子。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_value_composite_pending: quant/2021年度精选策略/26.稳定高回报周期股策略2.txt

- 公式/规则：PE<25且>0、负债资产<0.9、上市>500天；近4个季度利润和三期利润比hb=qr01/qr23、tb=qr01/qr45；应收周转>6或<=0；综合分=PE百分位+0.5*hb百分位+0.3*tb百分位。
- 数据条件：PIT季度财务、估值、上市日期、行业排除；需按报告期和公告日还原。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_value_composite_pending: quant/2021年度精选策略/31.RSRS择时+货币基金--6年8倍行业周期股策略.txt

- 公式/规则：指数signal=z1100*beta*R²，买入>0.7、卖出<-0.7；股票筛选PE<20、连续正利润/营收、应收周转>6，hb=近两季利润/前两季、tb=近两季/去年同期，综合=PE百分位+0.5hb+0.4tb。
- 数据条件：指数OHLC、PIT季度财务、PE/市值、行业排除、货币基金；完整RSRS历史从2005开始。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_value_composite_pending: quant/2021年度精选策略/35.精选价值策略.txt

- 公式/规则：l1=流通市值>横截面均值；l2=current_assets/current_liabilities>均值；l3四期ROE均>均值；l4三年FCF>0；l5四期收入增速6%~50%；l6利润增速筛选但实现中误用df5覆盖df6；最终l1∩...∩l6后按市值降序。
- 数据条件：PIT季度财务、公告日、流通市值、行业和交易状态；需修正源码l6覆盖错误后再复现。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_value_composite_pending: quant/2021年度精选策略/38.python搭建简单交易系统.txt

- 公式/规则：pps=operating_profit/capitalization；graham_value=pps*(27+2*profit_growth/100)；outvalue_ratio=value/close；先取市值最小10，再取outvalue_ratio前3；double_time=log(2*PB,1+ROE/100)，取最小3，交集为空取翻倍时间3只。
- 数据条件：银行股财务、收盘、市值/PB/ROE，需PIT；框架使用开盘成交和固定滑点。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_value_composite_pending: quant/2021年度精选策略/54.价值投资策略-大盘择时.txt

- 公式/规则：market_cap>1.2*均值；current_assets/current_liabilities>均值；四期ROE>各自均值；三年FCF>0；收入和利润增速6%~50%；大盘风控结合MA5速度/RSI；源码另含止损。
- 数据条件：PIT季度财务、估值、市值、指数日线和交易状态。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## quality_value_momentum_composite_pending: quant/2021年度精选策略/39.因子分析系列文章（八）：多因子策略（多元线性回归）.txt

- 公式/规则：features=[LEV=assets/liabilities, INP_YOY, IR_YOY, ROE/PB, PE/INP_YOY]；训练标签为过去5日价格动量，OLS weights=regress(features at t−6, momentum at t)，score=X_t·weights，降序买20。
- 数据条件：PIT财务、5日价格、沪深985股票池；需要修正未来标签定义和滚动训练。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## small_cap_rd_quality_pending: quant/2021年度精选策略/42.市值，研发支出，roe，三因子，跑赢大盘.txt

- 公式/规则：factors=[market_cap,development_expenditure,roe]；每15日排名，权重[-1,-1,-1]表示三项越小综合排名越靠前，等权买9。
- 数据条件：PIT财务、研发支出、ROE、市值、股票池；需要确认development_expenditure口径和缺失值处理。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## turtle_breakout_recipe_pending: quant/2021年度精选策略/46.大盘股也能穿越牛熊市.txt

- 公式/规则：benchmark velocity=(close_t−close_t−5)/(MA5*5)，范围[-0.008,0.1]且RSI(30)>47.5；个股buy when close>MAX60(high)−2*ATR60；sell when drawdown from max(买入价,MAX60)>15%且持有>30日或持有>90日；候选价格>50。
- 数据条件：分钟/日线OHLC、ATR/RSI、沪深300成分、PE/市值、行业过滤。
- 当前决定：先做字段可用性与因果检查，再按正式/近期双窗口复现。

## 2022 年新增待复现候选（2026-10-12 补读）

### apm_intraday_pending — `quant/2022年度精选策略/21.股价日内模式中蕴藏的选股因子.ipynb`

`stat` 先对最近20日的上午/下午个股收益与对应指数收益做40点回归，计算残差差值的 t 统计量；再对 `stat ~ ret20` 做横截面回归，取残差作为 APM；另有对数流通市值和行业哑变量中性化版本。需要120分钟数据，暂不能按正式日频全A口径测试。

### downside_vol_value_pending — `quant/2022年度精选策略/90.相信波动率还是相信基本面？波动与估值因子A股驱动力测试.txt`

`wave = 0.5*z(std63(ret)) + 0.5*z(std_down63(ret))`，其中 `std_down63` 只统计低于均值的日收益波动；价值腿为 `z(PB)+z(PE)+z(PS)` 的均值。两腿都按信号日横截面标准化，低值方向。该候选可用日频数据重构，但与 39 的价值腿有重叠。

### value_downside_vol_composite_pending — `quant/2022年度精选策略/39.个股择时有效？因子选股+双均线择时效果初步尝试.txt`

同一框架包含8类因子，源码可确认的价值腿是 `(zPB+zPE+zPS)/3`，波动腿为63日历史波动与下行波动的等权标准化；另有反转、市值、股息、成长、质量、beta实现。该来源是测试框架，不把未调用的因子实现当成已验证组合。

### apm_intraday / price_shape / downside_vol 的共同限制

以上日内候选均需单独标记 minute-data blocked 或 proxy；不得用日线替代120分钟收益，也不能与当前正式全A日频结果混排。

## 2022 年补读候选（已完成源码核对，尚未正式复现）

### momentum_variants_pending — `quant/2022年度精选策略/42.【研报复现】再论动量因子Ian666.txt`

日频候选包括 `RET20/60/120/240/480`、`TS_MAX(RET1,20)`、`MA20/60/120/240(CLOSE)/CLOSE`、流动性与自由流通市值中性化动量，以及对市场/SMB/HML回归后的动量残差。等成交量/成交额改造K线动量需要分钟数据，暂不纳入正式日频批次。

### small_cap_relative_reversal_pending — `quant/2022年度精选策略/59.【策略】夏普超过2.0，后市靠定增一步步往上爬.txt`

全市场最小市值50只内，计算 `rel126=RET126(stock)-RET126(index)`，保留 `rel126 < -0.5*abs(RET126(index))` 的超跌股；权重按超跌距离分配。需与纯市值、反转和低波簇做残差/相关性检查。

### value_rsrs_composite_pending — `quant/2022年度精选策略/69.RSRS择时加基本面选股策略优化.txt`

指数 `RSRS18/800` 右偏标准分 `z*beta*R²` 做市场开关；股票腿为 `rank(PB)+rank(1/ROE)`，并有行业/市值中性化版本。RSRS和股票腿分开评估，避免把指数择时收益归因给选股因子。

### downside_vol_value_pending — `quant/2022年度精选策略/90.相信波动率还是相信基本面？波动与估值因子A股驱动力测试.txt`

`wave=0.5*z(std63(ret))+0.5*z(std_down63(ret))`，价值腿为 `mean(z(PB),z(PE),z(PS))`；低波与价值两种方向均保留，按平台方向重新确认。

### financial_risk_filter_pending — `quant/2022年度精选策略/94.量化排雷—一个实用排雷系统.txt`

13项财务异常二元评分，含应收/收入、其他应收/资产、存货/资产、软资产、现金销售率、自由现金流、异常毛利、商誉和存贷双高；建议作为低风险排除腿，不作为独立多头alpha。

### industry_multifactor_pending — `quant/2022年度精选策略/95.医疗行业多因子模型及单行业多因子测试代码模板.txt`

医疗行业模板明确包含 `EP/BP/SP/NCFP/OCFP/G-PE/ROE/ROA/利润率/增长/周转/现金流质量/杠杆/beta/波动`，近12期截面IC动态加权。迁移全A前需去行业固定池并进行PIT审计。

### idiosyncratic_volatility_pending — `quant/2022年度精选策略/98.复现东方证券研报--特质波动率因子研究.txt`

CAPM、FF3、Carhart、FF5四种口径均为24个月日收益回归残差标准差年化；低特质波动率为候选多头方向。FF5还需要BP、ROE与再投资率，平台字段不足处标记proxy。

## 2023 年补读候选（2026-10-12，已逐篇核对）

### ffscore_quality_value_pending — `quant/2023年度精选策略/18.【复现】FFScore财务模型.txt`

实际启用 6 项 FFScore 指标：DELTA_ROE、ROA2、DELTA_MARGIN、DELTA_CATURN、DELTA_ROA2、DLTA_LIQUID；得分大于 4 后与 PB 正值横截面标准化/行业中性最低 20% 交集。源码声明 13 项但 `g.sel_fields` 只启用 6 项，ROA2 按源码括号定义需单独复核。

### roe_acceleration_value_pending — `quant/2023年度精选策略/24.ROE+PB模型的优化.txt`

低杠杆（负债/资产低于 75 分位）与坏资产比例中间 60% 过滤；最近 5 季度 ROE 加权窗口差值取改善最快 10%，再保留正 PB 并按 PB 升序。需 PIT 季度连接和与现有质量/价值簇相关性检查。

### fscore_quality_pending — `quant/2023年度精选策略/28.F_Score 选股，年化80%+.txt`

沪深 300 内 9 项财务信号：ROA、经营现金流/资产、ROA 变化、现金流相对 ROA、长期负债率变化、流动比率变化、普通股发行、毛利率变化、资产周转率变化；源码 `total>8` 实际要求 9 项全通过。适合作为质量排除/约束腿，需 PIT 资本变更公告。

### style_rotation_factor_pending — `quant/2023年度精选策略/29.价值成长轮动策略.txt`

指数 30 日对数回归斜率年化收益×R²做风格开关。价值分支为高正 EPS_TTM∩高正 margin_stability 后取大流通市值；成长分支为低 PEG∩低 EBIT 后取小流通市值。应拆成风格开关、价值腿、成长腿分别测试。

### small_cap_peg_ebit_pending — `quant/2023年度精选策略/36.PEG+EBIT对小市值因子的优化.txt`

低 PEG 前 10% → 低 EBIT 前 25% → 流通市值升序取前 5。保留源码低值方向，不按常见成长解释改写。

### hs300_5d_reversal_pending — `quant/2023年度精选策略/66.基于动量和反转效应的沪深300成分股策略.txt`

实际启用反转分支：约每 30 周在沪深 300 的 5 日聚合 K 线中计算 `close[-2]/close[1]-1`，取最低收益 25 只；动量分支调用被注释。需先确认 5 日桶定义再映射到日频反转。

### eps_margin_stability_largecap_pending — `quant/2023年度精选策略/78.EPS+MS因子的大盘蓝筹策略.txt`

沪深 300 内高 EPS_TTM 前 25%∩高 margin_stability 前 25%，再取大流通市值。与29价值分支同方向，但池、筛选比例和择时条件不同。

### roa_turnover_bias_pending — `quant/2023年度精选策略/79.过滤两个因子，12年15倍的roa选股500指数增强.txt`

中证500每20日更新；先低turnover_volatility前50%，再低BIAS10前50%，最后高ROA。原函数末尾存在return，此前缺return记录已撤销。

### industry_leader_size_pending — `quant/2023年度精选策略/35.最简强者恒强策略.txt`

5 个固定申万行业内各取市值最大股票，去重后形成行业龙头组合；属于行业/规模配置，不作为独立 alpha，若测试只做市值与行业约束的对照。

### volume_trend_breakout_pending — `quant/2023年度精选策略/49.【7日趋势】交易策略.txt`

总市值 30–500、换手率 2–10 的股票中，要求 MA13>MA21>MA55 持续、7 日内至少 3 次放量、最新日量放大且日涨幅超过 5%，再用均线箱体波动减多头排列得分排序。应拆分趋势、放量和形态腿。

### industry_breadth_momentum_pending — `quant/2023年度精选策略/63.A股最强板块动量趋势（最终版）.txt`

行业动量为过去 1/3/5/10/20 日涨幅超过阈值的行业内股票数量平方除以行业总数；可迁移为行业动量广度/拥挤度，但需历史行业和全 A 对齐。

### canslim_quality_momentum_pending — `quant/2023年度精选策略/98.欧奈尔CANSLIM策略初探三.txt`

剔除最小流通市值 20% 后，营业收入同比前 30%、RPS1 前 60%、机构持股比例增长前 30%，再叠加月线基底形态；可拆成收入增长、RPS、机构持股变化和形态过滤四腿。

### roa_acceleration_quality_value_pending — `quant/2023年度精选策略/99.全市场选股？7年5倍不择时，回撤30%左右.txt`

低负债、坏资产比例中间 80%、高优质资产周转率、当前季度 ROA 高于最近四季均值前 20%，再加 PB>0.7、PS<3 和低 PB 排序；与 24 高度相关但新增周转率和 PS/PB 约束。

### trend_slope120_pending — `quant/2023年度精选策略/3.苦咖啡-默默赚钱系列-改.txt`

沪深 300 内过滤 30 日回撤、近 7/180 日成交量比后，要求 120 日收盘回归 slope/intercept>0.005 且 r_value>0.9，按斜率取前 N；源码实际判断 `r_value`，不是注释所写 R²。

### etf_capm_alpha_pending — `quant/2023年度精选策略/11.致敬市场--5 定投ETF之躺平赢.txt`

ETF 对沪深 300 做 240 日 CAPM 残差，要求 alpha>0、beta 0.9–1.1、残差波动 <10 后按 alpha 排名；属于 ETF 相对强度/低残差波动诊断。

### smooth_trend120_pending — `quant/2023年度精选策略/14.2020年 267%年化 13%回撤 上涨趋势策略修改版.txt`

沪深 300 内过滤 30 日回撤≤10%、MA7/MA180 成交量比≤1.5、价格≤500，120 日回归 slope/intercept>0.005 且 R²>0.8；与 3 高度相关，需去重后再测。

### fund_overweight_rsrs_external_pending — `quant/2023年度精选策略/30.跟着基金报团！！！174% 回撤 7.33%.txt`

沪深 300 成分中以基金持仓市值权重相对指数权重的超配差排序取前 10，市场端叠加 RSRS18/480 右偏标准分开关；基金持仓披露需 PIT 公告日连接。

### pe_roa_magic_formula_pending — `quant/2023年度精选策略/32.最适合上班族的策略-神奇公式策略.txt`

沪深 300 中 PE 与 ROA 双排名组合取前 30。源码 `no_pe`/`no_roa` 的索引实现存在语义疑点，需先按原代码核验后再决定低 PE+高 ROA 适配方向。

### hs300_trend100_pending — `quant/2023年度精选策略/33.趋势交易5.0 无择时-2年5倍不是梦.txt`

100 日均线多头排列 + 100 日回归斜率/截距和 R 阈值，再加 30 日回撤、成交量比过滤；与 3/14 平滑趋势簇近似，先做相关性去重。

### market_crowding_rate_pending — `quant/2023年度精选策略/41.大盘拥挤率极速版-180天3秒.txt`

每日全市场成交额最高 5% 股票的成交额占比：`100*sum(money_top5%)/sum(money_all)`，可作为池级拥挤/风险开关；不当作个股 alpha。

### hs300_turtle_breakout_pending — `quant/2023年度精选策略/44.海龟突破系统，19-21年化150，无未来函数和过拟合.txt`

沪深300盘中价格突破前81日最高high且9观测收益<0，PE降序买1只；3日最大振幅的1倍止损/2倍止盈。日线适配应独立标注。

### industry_quality_growth_pending — `quant/2023年度精选策略/48.【漂亮50 2.0止损版本】为了降低回撤，加入择时止损模块.txt`

中证500内剔除最小流通市值25%及最大1只，各行业低PEG前70%→高净利润增长率前70%→高ROE前1/3，最后按流通市值降序；止损模块单独处理。

### short_trend_slope_pending — `quant/2023年度精选策略/57.韶华研究之四-菲阿里四阶在T+1的短线策略应用.txt`

基本面/价格筛选后raw OLS60斜率>0，raw OLS5斜率>2；斜率按3位小数舍入，价格尺度偏差需单独诊断。昨低买/昨高卖和T+1不混入日频因子。

### fundamental_triangle_pending — `quant/2023年度精选策略/59.可能是最接近实盘的“基本面三角.txt`

最近5季度 ROE、营收同比、经营现金流/营收均为正，并计算当前值相对前4期均值的变化；实际排序主用 ROE 改善，需与静态三因子版本区分。

### bottom_reversal_pending — `quant/2023年度精选策略/60.抄底神器2.0，低回撤，高成功率，无未来函数.txt`

PE/市值过滤后，要求价格接近 60 日低点和 10 日高点、5 日量高于30日量且30日量低于前段60日量、10日高点高于MA20，形成超跌反弹候选。

## 2026 嵌套策略补读候选（2026-10-12）

### roe_acceleration_value_nested_pending

来源：`量化策略/量化策略/小市值策略2026/09小市值成长股策略更新FROEC-PB-CAP-HL-25年收益107.76.txt`。

低正 PB 半池中，按最近 5 季度 ROE 加速 `4*ROE_t - (ROE_{t-1}+ROE_{t-2}+ROE_{t-3}+ROE_{t-4})` 取前 10%，剔除指定行业后按流通市值排序。与已有 `roe_acceleration_value_pending` 同族，先做字段和季度顺序核验，不重复测试。

### pullback_stabilization_daily_pending

来源：`量化策略/量化策略/首板回调买入策略2026/02上升途中回调到位-优化版-25年42.txt`。

30 日窗口前 23 日上涨至少 20%，后 7 日从阶段高点回撤 10%–20%；近 3 日单日涨跌幅不超过 3%、成交量下降、低点不创新低且收盘不弱。原代码含重复函数定义，实际调用后者；09:45 盘中买入，先做日频信号代理并标注时点差异。

### trend_pullback_lowatr_pending

来源：`量化策略/量化策略/首板回调买入策略2026/08上升趋势-回档买入-25年0.78.txt`。

MA5>MA20，近 10 日回撤 5%–15%，ATR14/收盘≤5%，当前价站 MA5/MA20。随机抽样最多 200 只后只买首个合格标的，执行随机性必须剥离；日频条件可作为候选原子。

### limitup_reclaim_pullback_pending

来源：`量化策略/量化策略/首板回调买入策略2026/09涨停回调止盈止损-25年30.62.txt`。

近 10 日曾涨停但次数≤2，当前非涨停；连续站 MA10，MA5 从弱转强，最新成交量>20 日均量×1.3，MA5/MA10 距离>1%，近 5 日高点回撤>5%。该组合可做日频代理，但需使用 PIT 涨停价并与已有回调簇做残差相关。

### first_limit_delayed_reversal_pending

来源：`量化策略/量化策略/首板向上趋势策略2026/04首板-固定点入场-教科书复盘.txt`。

首板前 25 日无旧板，首板日放量>20 日均量×2、收盘在 MA60 的 0.9–1.3 倍；2–10 个交易日后回撤 6%–15%、量缩至首板的 60% 以下、收盘低于 MA20 2%，并满足反转 K 线或止跌条件。源码交易时点和 `datetime` 处理有缺陷，暂不进入正式测试。

### limitup_ma_alignment_daily_pending

来源：`量化策略/量化策略/龙头追涨策略2026/02涨停板多头策略-25年负-47.txt`。

昨日涨停且 `C>MA5>MA10>MA20>MA60`，按小市值排序，持 5；属于已有涨停趋势簇的日频变体，只有在去重相关性后才考虑。

### limitup_early_multi_ma_pending

来源：`量化策略/量化策略/龙头追涨策略2026/02涨停板多头策略-优化版v1.0.txt`。

昨日涨停、5 日涨幅<20%、距 MA20<10%，近 3 日首次出现 MA5/10 或 MA10/20 金叉，竞价涨幅≤5%，按市值排序。竞价部分不能用收盘替代；日频部分仅作候选原子。

其余嵌套策略以 ETF 动量、低市值、涨停竞价、龙头追涨或已登记旧代码为主，均已记录为重复、执行方法或分钟数据阻塞；没有新增可直接纳入当前正式股票因子池的独立簇。

## 持续本地授权后的队列更新（2026-10-12）

用户已授权多轮本地挖掘，无需逐轮再确认。新增50条已经完成 source6—source15 的五年/近期双窗口及市值反转归因；正式规格累计157，另2条窗口证伪规格。

| 来源机制 | 已执行状态 |
|---|---|
| 2024/28 季度ROE改善、2023/59 基本面三角、2025/60 应付天数 | source6 六条完成；未通过保留标准 |
| 2021/10 APARP、2024/39 现金质量、2023/79 ROA稳定乖离、2025/23 低beta价值、2023/65 ROE−PB | source7 八条完成；未保留 |
| 2024/77 筹码分布四阶矩 | source8 八个方向完成；未保留 |
| 低特质风险×价值/质量/反转 | source9 六条完成；进入归因核验后未认证独立增量 |
| 2022/98 固定组合CAPM/FF3/FF5、协方差与换手价值 | source10/source12 八条完成；以风险模型改进诊断保留，不称新簇 |
| 研发与毛利稳定性×低特质风险 | source11 四条完成；研发近期转负，毛利腿独立增量不足 |
| 2024/82 收入惊喜、2021/26 扣非盈利成长估值 | source13 四条完成；门控最高值仅2期，不作有效alpha |
| CAPM/FF3/FF5 风格解释比例 | source14 四个方向完成；FF3正向留候选，60/252日证伪均保住收益 |
| 风格解释比例×低特质风险 | source15 等权/乘积两条完成；留等权，乘积仅同源敏感性 |

保留方向、全部50条来源哈希、旧簇最近锚点和组合诊断已统一汇总在 [持续挖掘报告](continued_mining_report_20261012.md)。本次不认证新U簇，不修改正式池，平台算力消耗0。
