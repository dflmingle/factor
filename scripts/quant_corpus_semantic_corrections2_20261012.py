"""Source-verified corrections to notes; does not classify unreviewed sources."""
import json
from quant_corpus_semantic_review_20261012 import NOTES, refresh
n=json.loads(NOTES.read_text())
# False passed as ascending is descending: fix both prose and formula.
for k,v in n.items():
 if '/2024年度精选策略' in k:
  for f in ('logic','factor_recipes'):
   v[f]=v[f].replace('sales_growth最低10%','sales_growth最高10%').replace('营业收入增长率最低10%','营业收入增长率最高10%').replace('low sales-growth','high sales-growth').replace('low sales_growth','high sales_growth')
def fix(group,prefix,**kw):
 keys=[k for k in n if '/'+group+'/' in k and k.rsplit('/',1)[-1].startswith(prefix)]
 assert len(keys)==1,(prefix,keys)
 n[keys[0]].update(kw)
fix('2024年度精选策略2','16.',logic='五类ETF分别选收益最高且价格在MA10上方者；moment_period=13，但close[-1]/close[-13]实际跨度12交易日。收盘21:00计算，次日9:32交易，各类预算1/5。',factor_recipes='12-trading-day ETF return>0 AND CLOSE>MA10; category-wise top1。')
fix('2024年度精选策略2','24.',logic='沪深300/中证500/创业板按29观测对数价格回归年化斜率×R²排名；RSRS18的标准化历史分别700/800/500期，score=z×R²^(2×收益波动率历史分位)，阈值分别0.7/1/0.4。',factor_recipes='trend29=(exp(250*slope(log C))-1)*R²; damped_RSRS=z_M(beta18)*R²^(2*TS_PERCENTILE(STD18(return),M))。',warnings='此前误写18日排名/600期；池中原始代码用指数代码交易，可交易ETF映射须另标适配。')
fix('2024年度精选策略2','25.',logic='概念股市值30–1000亿，读取100根120分钟close；用29观测首尾对数变化/29作斜率，乘拟合质量绝对值，计算5个错位分数，选最强1只；RSRS14/600、MA7和评分变化择时。',factor_recipes='120m bars: (exp(250*(logC[-1]-logC[-29])/29)-1)*abs(pseudo_R²); RSRS14/600。',warnings='此前误写20/60/120日；首尾斜率不等于OLS斜率，截距另拟合且绝对R²放大不良拟合，分钟适配不能冒充日频。')
fix('2024年度精选策略2','28.【回顾2】小市值成长股策略更新FROEC',logic='正EPS、正PB中取低PB50%；5季ROE列按4*ROE[4]−sum(ROE[0:4])降序取10%，再排除指定行业，按小流通市值排序。',factor_recipes='low PB50% + top10%(4*ROE[4]−sum(ROE[0:4])) + low circulating_mv。',warnings='此前写20%错误；须核实API季度返回顺序，不把5季统计说成简单同比。')
fix('2024年度精选策略2','30.',logic='120日收盘计算MA55；过去40日的前20个观测在MA55上方次数为1–3，最近3日至少一次在上方，实时价高于当期MA55，且近10日最低收盘等于近60日最低收盘。筛流通市值>50、ROE>0按ROE降序最多10，只持5。',factor_recipes='COUNT(C>MA55,old20 of last40) in [1,3]; COUNT(last3 C>MA55)>=1; current C>MA55; MIN10(C)=MIN60(C); high ROE and circMV>50。',warnings='此前把另一策略的20日振幅条件误记为本篇买点，已撤销；实时价条件不能无标注换成日收盘。')
fix('2024年度精选策略2','31.',logic='沪深300内按90观测log价格回归年化斜率×R²排序前60；价格>=MA100，100日内LOW/HIGH.shift(2)−1最大值<=15%。指数>MA200才买，ATR20风险配仓。',factor_recipes='trend90=(exp(250*slope90(log C))-1)*R²; C>=MA100; MAX100(L/DELAY(H,2)−1)<=.15; ATR20 inverse risk sizing。')
fix('2024年度精选策略2','34.',logic='加载外部LightGBM主板/创业板两个pkl；12个40日价格/量/MACD/涨停特征，40日峰值位置10–35且模型raw score第二类>0.75时入选。注释提及2次涨停/30%上涨/20%回撤，但活动代码不强制这些阈值。',warnings='不能把注释阈值当执行筛选；未知训练样本无法证实或排除前视，标题自述过拟合不是独立泄漏证据。')
fix('2024年度精选策略2','55.',data_requirements='日线/行业指数价格；technical_analysis_patterns外部模块缺失，负责核回归、极值及滚动形态识别；源码仅提供几何条件描述与事件统计调用。',warnings='不能宣称已有完整可执行形态算法；江淮汽车示例错误使用data1而非data2，必须修复后标适配。')
fix('2024年度精选策略2','56.',warnings='与39同经济路线但实现不等价：statDate查询未按公告日PIT且直接累加累计季报，TTM重复计数风险；换手函数排序df却返回df_all，所称低波筛选实际未执行。')
fix('2024年度精选策略2','57.',logic='上证指数昨日跌幅<=−1.5%且当前14:55跌幅<=−1.4%时由国债ETF切换中证1000ETF；持有计数到20的倍数卖出转国债，开关清零。',factor_recipes='market two-day selloff rebound: r_prev<=−.015 AND r_intraday<=−.014; hold counter~19 calls then bond switch。')
fix('2024年度精选策略1','96.',warnings='预测当前之后的日期本身不构成泄漏；未提供滚动样本外验证，不能认定历史有效；CUSUM的S_h/S_l未更新累加，实际不是标准累积CUSUM。',status='aggregate_index_ml_unvalidated',logic='4只ETF当日OHLCV与上证46日窗口统计及日历变量训练LightGBM五个0–4日价格预测器；仅画当前之后预测，不做历史滚动回测。标准化代码已注释；没有已证实的全样本标准化泄漏。')
NOTES.write_text(json.dumps(n,ensure_ascii=False,indent=2)+'\n');refresh()
