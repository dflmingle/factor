# quant 策略库因子阅读索引

文件总数：818；可解码文本：755。每个源文件均保留在 `source_inventory.csv/json`。
索引程序读取全部可解码文本并提取证据，但不等同于逐行人工语义审阅。字段指纹仅用于导航，不是独立因子或相关性簇。rzrk 是不透明二进制，不能宣称已阅读。

本地104项因子/对照的五年、近期测试及旧簇相关性见[复现报告](../../platform_alignment/quant-corpus-source-reproduction-20261012/summary.md)。逐文件阅读层级见[source_review.csv](source_review.csv)，尚未复现字段见[unreproduced_field_recipes.csv](unreproduced_field_recipes.csv)。

## 状态统计

- `diagnostic_only_or_unavailable`：353
- `candidate_for_daily_local_reproduction`：216
- `candidate_if_field_mapping_exists`：155
- `unreadable_proprietary_binary`：57
- `model_recipe_requires_rebuild`：31
- `supporting_asset`：6

## 字段导航（不能作为统计分簇）

| fingerprint | files | tags | dependencies | examples |
|---|---:|---|---|---|
| 897bf9ea061b | 63 |  |  | quant/20-24目录.xlsx；quant/2025年策略目录.xlsx；quant/Qmt策略/IC法分析.rzrk |
| 60c24a3cc4e6 | 8 | event_short;intraday;size;turnover | daily_stock_fields | quant/2024年度精选策略1/11.低价小盘简单有效.txt；quant/2024年度精选策略1/20.有赚就好-小市值剥头皮改进 2年3.86%回撤.txt；quant/2024年度精选策略1/65.低开买入小市值策略（剥头皮策略）3.0 总结.txt |
| 0ac0c6f4253c | 5 | etf_macro;intraday;technical;turnover;volatility | non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/聚宽使用说明.txt；quant/量化策略/量化策略/小市值策略2026/聚宽使用说明.txt；quant/量化策略/量化策略/首板向上趋势策略2026/聚宽使用说明.txt |
| 6f45b9dc517c | 5 | event_short;growth;intraday;quality;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/35 投资学作业——简单多因子选股策略.txt；quant/2020年度精选策略/36 投资学作业——简单多因子选股策略改进.txt；quant/2020年度精选策略/47 次新小盘策略.txt |
| 9840f9e6f973 | 5 | intraday | daily_stock_fields | quant/2020年度精选策略/39 因子分析——利用JoinQuant因子分析模块选取因子并封装为策略.txt；quant/2022年度精选策略/67.来自JPMorgan的VaR+EXPMA风险仓位控制.txt；quant/2023年度精选策略/61.分享一个最近两年非常有效的因子.txt |
| 528ca88a168c | 4 | etf_macro;intraday | intraday_data;non_stock_asset | quant/2021年度精选策略/57.股指期货套利，这段时间都没有交易分享给大家.txt；quant/2021年度精选策略/58.严格资金管理，股指期货套利.txt；quant/2022年度精选策略/25.股指期货套利策略.txt |
| 6f78042ec87a | 4 | etf_macro;intraday;momentum_reversal;quality;technical;turnover | non_stock_asset | quant/2021年度精选策略/18.6年17倍的etf+分级b的轮动趋势策略跟随感悟.txt；quant/2021年度精选策略/21.策略coding吐槽帖——以“网红”ETF轮动为例.txt；quant/2021年度精选策略/68.蒋老师吐槽了之后，我也想说说对ETF轮动策略的看法.txt |
| 82870d8978c5 | 4 | etf_macro | non_stock_asset | quant/2021年度精选策略/6.iAlpha 基金投资策略.txt；quant/2023年度精选策略/8.iAlpha 基金投资策略.txt；quant/2024年度精选策略1/70.致敬市场(12)——赚钱的策略.txt |
| 83b726399b11 | 4 | etf_macro;event_short;intraday;momentum_reversal;size;technical;turnover;value;volatility | non_stock_asset | quant/2023年度精选策略/15.动量ETF轮动RSRS择时-升级.txt；quant/2023年度精选策略/16.8年13倍的ETF动量轮动策略，有滑点，无未来函数，回撤小！.txt；quant/2023年度精选策略/4.8年10倍，回撤小，有滑点！ETF动量简单轮动策略！.txt |
| c982ad1fdee3 | 4 | etf_macro;growth;intraday;momentum_reversal;value | non_stock_asset | quant/2024年度精选策略1/3.【回顾3】ETF策略之核心资产轮动.txt；quant/聚宽2025年精选/14安全摸狗策略.txt；quant/聚宽2025年精选/38ETF策略之核心资产轮动（线性增加权重）.txt |
| c99b1666e698 | 4 | event_short;growth;intraday;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/28 收益策略.txt；quant/2020年度精选策略/32 测试策略1.txt；quant/2020年度精选策略/34 成长策略.txt |
| d22c96a7b813 | 4 | event_short;intraday;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/26 向导式-1.txt；quant/2020年度精选策略/37 个股止损.txt；quant/2020年度精选策略/53 小市值策略.txt |
| dfd1ff0e7ff1 | 4 | event_short;intraday;quality;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/64 12年年化34%，Sharpe1.2，银行股轮动.txt；quant/2020年度精选策略/70 蓝筹&均线.txt；quant/2020年度精选策略/75 财务因子策略.txt |
| fbc9a82967b6 | 4 | event_short;intraday | daily_stock_fields | quant/2021年度精选策略/20.冲天炮最高板策略，收益惊呆了我.txt；quant/2021年度精选策略/95.冲天炮最高板策略迭代.txt；quant/聚宽2025年精选/78首板低开策略-终极版 最大回撤15%，年化50%.txt |
| ff3520622eb8 | 4 | intraday | intraday_data | quant/2020年度精选策略/30 基于LSTM模型预测股票价格走势.txt；quant/2020年度精选策略/40 kdj指标配合accer过滤.txt；quant/2020年度精选策略/48 再测一支.txt |
| 043e6818fafc | 3 | event_short;intraday;size | daily_stock_fields | quant/2024年度精选策略2/22.菜场大妈选股法.txt；quant/聚宽2025年精选/68wywy1995 首板低开策略代码优化，提快速度.txt；quant/量化策略/量化策略/首板回调买入策略2026/04首板低开策略代码提速-25年9.37.txt |
| 2240aec5603a | 3 | etf_macro;intraday;momentum_reversal;size;technical;turnover;value;volatility | intraday_data;non_stock_asset | quant/2024年度精选策略2/50.ETF动量轮动RSRS择时-V2.1.txt；quant/2024年度精选策略2/58.ETF动量轮动RSRS与北上择时-股债平衡-盘中止损.txt；quant/2024年度精选策略2/60.ETF动量轮动RSRS择时-v2.txt |
| 23a878d6e4b6 | 3 | etf_macro;intraday | non_stock_asset | quant/2022年度精选策略/1.易方达二八轮动测试.txt；quant/2022年度精选策略/45.股指期货跨合约套利.txt；quant/2024年度精选策略2/76.ETF-控制回撤性能拉满（国债ETF增强).txt |
| 270de990870c | 3 | event_short;intraday;quality;size;turnover;value | industry_or_concept | quant/2024年度精选策略1/7.连板龙头策略.txt；quant/聚宽2025年精选/2连板龙头策略.txt；quant/聚宽2025年精选/88WY大神的“龙头打板”策略小改.txt |
| 4bdd230e2d0e | 3 | etf_macro;intraday;momentum_reversal;size;technical;turnover;value;volatility | non_stock_asset | quant/2023年度精选策略/37.ETF动量轮动RSRS择时-魔改4-低通滤波.txt；quant/2023年度精选策略/7.ETF动量轮动RSRS择时-魔改3小优化.txt；quant/2024年度精选策略2/2.ETF动量轮动RSRS择时-魔改3小优化.txt |
| 5b232410c6a4 | 3 | event_short;growth;intraday;size;value | pit_financial_or_valuation | quant/2024年度精选策略1/29.高增股池小市值轮动.txt；quant/聚宽2025年精选/46高增股池小市值轮动.txt；quant/量化策略/量化策略/小市值策略2026/05高增股池小市值轮动-25年收益92.82.txt |
| 7f90b02eb326 | 3 | event_short;intraday;size;turnover;volatility | intraday_data | quant/2023年度精选策略/42.二板排板战法研究.txt；quant/2023年度精选策略/84.对 二板排板战法 的部分优化.txt；quant/2023年度精选策略/9.10倍-二板排板战法优化-无未来函数.txt |
| 87337963221c | 3 | etf_macro;event_short;growth;intraday;quality;size;turnover;volatility | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/15小市值排除3个bug版，22年至今收益506.txt；quant/聚宽2025年精选/6国九小市值策略【年化100.5】.txt；quant/聚宽2025年精选/8国九条后中小板微盘小改，年化135.40.txt |
| 91bd1e3004f8 | 3 | event_short;growth;intraday;quality;size;turnover;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略1/35.5年12倍-小市值.txt；quant/聚宽2025年精选/63.5年12倍-小市值.txt；quant/量化策略/量化策略/小市值策略2026/04-五年12倍小市值-25年收益95.85.txt |
| a0ed184cd316 | 3 | event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略1/13.5年15倍的收益，年化79.93%，可实盘，拿走不谢！.txt；quant/聚宽2025年精选/3、5年15倍的收益，年化79.93，可实盘，拿走不谢！.txt；quant/量化策略/量化策略/小市值策略2026/06价投小市值涨停因子策略-25年收益61.31.txt |
| a5096fe14a7d | 3 | etf_macro;intraday;turnover | intraday_data;non_stock_asset | quant/2021年度精选策略/71.【股指策略】【研报复现】周内与日内结合CTA.txt；quant/2024年度精选策略1/76.基金溢价（模拟效果好！）.txt；quant/聚宽2025年精选/62基金溢价（模拟效果好！）.txt |
| a81293fe4535 | 3 | etf_macro;intraday;momentum_reversal;price_volume;technical | non_stock_asset | quant/聚宽2025年精选/74趋势筛选后相关性最小etf轮动.txt；quant/聚宽2025年精选/97趋势筛选后相关性最小etf轮动-加速10倍版.txt；quant/量化策略/量化策略/ETF轮动策略2026/01趋势筛选后相关性最小etf轮动25年40.txt |
| ba695fa6dd7a | 3 | event_short;intraday;size | intraday_data | quant/2021年度精选策略/1.龙回头3.0回测速度优化版.txt；quant/2021年度精选策略/89.2020年效果很好的策略-龙回头策略v3.0.txt；quant/2023年度精选策略/25.这个可入得了你们法眼.txt |
| c65934bd0123 | 3 | event_short;intraday;turnover | intraday_data | quant/2023年度精选策略/5.87.5%胜率之分歧反包二板.txt；quant/2023年度精选策略/76.半年6.5倍--次新股排板一式.txt；quant/2024年度精选策略2/10.龙头首阴战法改版二.txt |
| d7073a2ec702 | 3 | etf_macro;event_short;intraday;size;turnover | daily_stock_fields | quant/聚宽2025年精选/21【原创】年化123涨停弱转强竞价战法.txt；quant/聚宽2025年精选/59追板策略，今年收益已翻倍，低操作低回撤高收益可实盘.txt；quant/量化策略/量化策略/首板回调买入策略2026/05追首板-高质量代码框架-23年144-25年负-43.57.txt |
| dd55cc66d618 | 3 | etf_macro;event_short;intraday;size;technical;turnover;value | daily_stock_fields | quant/2021年度精选策略/13.7年40倍，模拟超过两年，年化高回撤低.txt；quant/2023年度精选策略/0.7年40倍，模拟超过两年，年化高回撤低.txt；quant/2024年度精选策略2/42.实盘出现的问题和解决办法.txt |
| f30b9b19b3d3 | 3 | event_short;intraday | daily_stock_fields | quant/2024年度精选策略1/4.首板低开策略.txt；quant/聚宽2025年精选/1首板低开策略.txt；quant/聚宽2025年精选/72量化进阶学习笔记——打板策略.txt |
| 013173330986 | 2 | growth;intraday;machine_learning;quality;size;turnover;value;volatility | model_training;pit_financial_or_valuation | quant/2023年度精选策略/75.机器学习策略分享.txt；quant/2024年度精选策略2/72.随机森林 - 多因子模型.txt |
| 04324c298cd7 | 2 | etf_macro;intraday;momentum_reversal;value | daily_stock_fields | quant/2021年度精选策略/3.一个简单而持续稳定的懒人超额收益策略.txt；quant/2023年度精选策略/10.一个简单而持续稳定的懒人超额收益策略.txt |
| 081b1ce95e8a | 2 | etf_macro;intraday;technical;turnover | non_stock_asset | quant/聚宽2025年精选/85稳健型ETF策略.txt；quant/量化策略/量化策略/ETF轮动策略2026/02稳健型ETF策略-25年21.txt |
| 09f9e676330d | 2 | etf_macro;intraday;technical;turnover;volatility | daily_stock_fields | quant/2020年度精选策略/38 一个简单的跟踪聪明钱策略.txt；quant/2023年度精选策略/40.再改进可实盘-默默赚钱系列-风险控制-增强版本-V5.0.txt |
| 0a36c3a2d08a | 2 | etf_macro;intraday;technical;value | non_stock_asset;pit_financial_or_valuation | quant/2020年度精选策略/09 商品期货 多品种日频双均线模型 作为给入门者的小礼物.txt；quant/2020年度精选策略/49 海龟克隆优化.txt |
| 0d5a60ec8a23 | 2 | etf_macro;intraday;technical | non_stock_asset | quant/2024年度精选策略1/21.一种宏观数据的中长线策略，年化15%，最大回撤9%.txt；quant/2024年度精选策略2/48.一种宏观数据的中长线策略，年化15%，最大回撤9%.txt |
| 125c255a34b2 | 2 | growth;machine_learning;size | model_training | quant/2020年度精选策略/03 机器学习多因子策略.txt；quant/2020年度精选策略/06 为什么股票市值是当前的样子？.txt |
| 12d997f06d21 | 2 | event_short;intraday;momentum_reversal;quality;size;turnover | intraday_data;pit_financial_or_valuation | quant/2023年度精选策略/43.集合竞价摸奖策略1.0-致敬2022.txt；quant/2024年度精选策略2/4.集合竞价摸奖策略1.0-致敬2022.txt |
| 141969de53a5 | 2 | etf_macro;intraday;momentum_reversal;technical;turnover | intraday_data;non_stock_asset | quant/2024年度精选策略2/64.ETF轮动策略升级-增加盘中止损.txt；quant/量化策略/量化策略/ETF轮动策略2026/08ETF动量均线轮动策略-调优版-25年96.txt |
| 1dd54321ffa7 | 2 | etf_macro;event_short;intraday;turnover | non_stock_asset | quant/2021年度精选策略/72.【股指期货】收盘折溢价策略.txt；quant/2023年度精选策略/87.【股指期货】收盘折溢价策略.txt |
| 1de4ccc60945 | 2 | event_short;intraday;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/56 爱神的箭放声大哭.txt；quant/2020年度精选策略/90 MA均线金叉买入，死叉卖出.txt |
| 226f066cbd50 | 2 | etf_macro;intraday;momentum_reversal;price_volume;technical;turnover | intraday_data;non_stock_asset | quant/量化策略/量化策略/实盘2026/Ptrade/pt版01趋势强+低相关ETF轮动策略.txt；quant/量化策略/量化策略/实盘2026/Ptrade/pt版05动量最强ETF轮动策略.txt |
| 25f356b45a14 | 2 | intraday;technical;value;volatility | intraday_data;money_flow_or_event | quant/2022年度精选策略/27.海龟交易体系-多资产版.txt；quant/2022年度精选策略/93.海龟交易体系（股票版）.txt |
| 298df36d3e1b | 2 | etf_macro;growth;intraday;quality;size;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/35.精选价值策略.txt；quant/2021年度精选策略/87.穿越牛熊基业长青的价值精选策略（小资本也有大作为）.txt |
| 2c0037bacb9b | 2 | intraday;turnover | daily_stock_fields | quant/2024年度精选策略1/41.人工智能强化学习DQN交易智能体（回馈社区公开训练代码）.txt；quant/聚宽2025年精选/27人工智能强化学习DQN交易智能体（回馈社区公开训练代码）.txt |
| 2ff37adc906b | 2 | etf_macro;growth;intraday;momentum_reversal;technical;value;volatility | non_stock_asset | quant/2024年度精选策略1/31.动量因子加RSRS择时和ETF轮动每日调仓.txt；quant/2024年度精选策略1/38.ETF核心资产轮动-添油加醋.txt |
| 374df2c6997f | 2 | etf_macro;intraday;machine_learning;turnover | model_training | quant/2023年度精选策略/38.随机森林策略，低换手率，年化近50%.txt；quant/2024年度精选策略2/5.随机森林策略，低换手率，年化近50%.txt |
| 3879a5054c18 | 2 | event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略1/36.【菜场大妈】股息率小市值策略,10年206倍,5年10.8倍.txt；quant/聚宽2025年精选/35【菜场大妈】股息率小市值策略,10年206倍,5年10.8倍.txt |
| 38ec28595ce7 | 2 | intraday;value;volatility | intraday_data | quant/2020年度精选策略/13 招行_海天配对策略-改进版.txt；quant/2020年度精选策略/55 中小板-中证500配对交易.txt |
| 3ac6709b9746 | 2 | event_short;intraday;size | intraday_data | quant/2024年度精选策略1/63.怎么让龟速变奔跑？以“首版突破一进二”为例.txt；quant/聚宽2025年精选/55怎么让龟速变奔跑？以“首版突破一进二”为例.txt |
| 40a537591343 | 2 | event_short;growth;intraday;quality;size;turnover;volatility | pit_financial_or_valuation | quant/2024年度精选策略1/50.新策略，一种新思路，超额376%！.txt；quant/2024年度精选策略2/1.一颗耀眼的星—【回顾2】小市值成长股策略更新—改.txt |
| 449d92009e60 | 2 | event_short;intraday;size;turnover | daily_stock_fields | quant/2024年度精选策略1/8.科技与狠活.txt；quant/2024年度精选策略2/17.科技与狠活.txt |
| 47fbe61d6a9c | 2 | etf_macro;intraday;momentum_reversal;size;technical;turnover;value;volatility | intraday_data;non_stock_asset | quant/2024年度精选策略1/10.多因子宽基ETF择时轮动改进版-高收益大资金低回撤.txt；quant/聚宽2025年精选/36快过年了。不想呆在小市值的，可以拿这个策略躲一躲.txt |
| 4a5732e22945 | 2 | etf_macro;intraday;momentum_reversal;price_volume;volatility | non_stock_asset | quant/聚宽2025年精选/17多品种ETF动量轮动+EPO优化.txt；quant/量化策略/量化策略/ETF轮动策略2026/07多品种ETF动量轮动EPO-调优版-25年112.txt |
| 4aa935da0cef | 2 | etf_macro;intraday;momentum_reversal;technical;value | non_stock_asset;pit_financial_or_valuation | quant/2020年度精选策略/04 趋势交易能赚钱吗？商品期货动量效应挖掘初探.txt；quant/2020年度精选策略/17 商品期货截面动量模型，真的靠谱吗？.txt |
| 4e133f282297 | 2 | intraday;volatility | intraday_data | quant/2020年度精选策略/27 RSRS指标择时（30分钟线）.txt；quant/2020年度精选策略/69 阻力支撑相对强度（RSRS）指标择时策略.txt |
| 537d1fa2164c | 2 | etf_macro;intraday;momentum_reversal;quality;technical;turnover | non_stock_asset | quant/2021年度精选策略/81.无杠杆，稳定盈利的etf轮动，06年开始3000%收益.txt；quant/2023年度精选策略/6.21年度6.为了挣点积分自己实盘的策略分享出来.txt |
| 58b553dd974a | 2 | event_short;growth;intraday;quality;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/60 投资期末作业.txt；quant/2020年度精选策略/61 向导式策略生成器生成的成长股精选策略.txt |
| 5b944681afad | 2 | event_short;growth;intraday;quality;size;turnover;volatility | pit_financial_or_valuation | quant/2024年度精选策略2/28.【回顾2】小市值成长股策略更新SG-MS-PEG-HL.txt；quant/量化策略/量化策略/小市值策略2026/08小市值成长股策略更新SG-MS-PEG-HL-25年收益97.92.txt |
| 5f6779dd113f | 2 | etf_macro;event_short;intraday;size;turnover;volatility | intraday_data | quant/2024年度精选策略1/34.韶华研究之十八，201系列.txt；quant/聚宽2025年精选/57韶华研究之十八，201系列.txt |
| 629ddee99fa6 | 2 | etf_macro;growth;intraday;quality;size;technical;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/33 买入每个行业市值最大的股票.txt；quant/2024年度精选策略2/89.年化收益55.7%， 超高胜率 0.799.txt |
| 62a59252f316 | 2 | intraday;momentum_reversal;technical;turnover | daily_stock_fields | quant/2023年度精选策略/50.缠论交易策略.txt；quant/2024年度精选策略2/11.缠论交易策略.txt |
| 680536872dc3 | 2 | event_short;intraday;quality;size;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略2/28.【回顾2】小市值成长股策略更新FROEC-PB-CAP-HL.txt；quant/量化策略/量化策略/小市值策略2026/09小市值成长股策略更新FROEC-PB-CAP-HL-25年收益107.76.txt |
| 6be7ddcd9ecd | 2 | etf_macro;intraday;technical;value | intraday_data;non_stock_asset;pit_financial_or_valuation | quant/2020年度精选策略/20 分钟K线数据重构 ATR自适应通道 请高手来迭代.txt；quant/2020年度精选策略/22 海龟交易法则升级版---（分钟级回测+合约变更移仓）.txt |
| 6dd77e6ab6ab | 2 | etf_macro;intraday;momentum_reversal | non_stock_asset | quant/2021年度精选策略/19.简单到发指的股指策略(2013到现在收益10949%).txt；quant/2023年度精选策略/22.简单到发指的股指策略(2013到现在收益10949%).txt |
| 799934f19a71 | 2 | etf_macro;intraday;momentum_reversal;price_volume;size;technical;turnover;value;volatility | non_stock_asset | quant/2023年度精选策略/47.动量ETF轮动-RSRS择时-卡尔曼滤波.txt；quant/2024年度精选策略2/18.动量ETF轮动-RSRS择时-卡尔曼滤波.txt |
| 7b0729bd05eb | 2 | event_short;intraday;quality;size;turnover | intraday_data | quant/2024年度精选策略1/62.分享一种K线小碎步后突破的分钟级打法.txt；quant/聚宽2025年精选/50分享一种K线小碎步后突破的分钟级打法.txt |
| 7d56f5b0c5e7 | 2 | event_short;intraday;size;turnover | industry_or_concept;money_flow_or_event | quant/聚宽2025年精选/96首版+2版龙虎榜挖掘V2.0，年化1400.txt；quant/量化策略/量化策略/首板回调买入策略2026/01首版2版龙虎榜23年1043.txt |
| 8338d2208eed | 2 | intraday;momentum_reversal;turnover;volatility | daily_stock_fields | quant/2024年度精选策略2/65.神级策略：桥水全天候策略-7年最大回撤仅3.5%.txt；quant/2024年度精选策略2/7.致敬经典作品——小兵哥《一致性风险度量》——极速版.txt |
| 8a4d43330567 | 2 | etf_macro;event_short;intraday;price_volume;technical;turnover | intraday_data;non_stock_asset | quant/2021年度精选策略/90.超稳+翻倍，贝塔值只有0.048的期指策略.txt；quant/2023年度精选策略/34.超稳+翻倍，贝塔值只有0.048的期指策略.txt |
| 8c759db4347a | 2 | event_short;intraday;size;technical;turnover;value | daily_stock_fields | quant/量化策略/量化策略/首板向上趋势策略2026/02-首板高开趋势策略-25年163-24年122-23年44-22年433-21年92.txt；quant/量化策略/量化策略/首板向上趋势策略2026/03-首板弱转强策略-25年54-24年87-23年10-22年66.txt |
| 8ced6920296e | 2 | intraday;technical | non_stock_asset | quant/2021年度精选策略/85.易方达中小盘（魔改版）.txt；quant/2022年度精选策略/72.年化15.48%，盈亏比3.818的双均线策略.txt |
| 8d4ebe2d4d6e | 2 | event_short;intraday;turnover;volatility | daily_stock_fields | quant/2024年度精选策略2/77.龙头弱转强战法.txt；quant/量化策略/量化策略/龙头追涨策略2026/04龙头弱转强战法-25年负-26.txt |
| 8ee51f342041 | 2 | event_short;growth;intraday;size;value | intraday_data;pit_financial_or_valuation | quant/2024年度精选策略1/19.高股息低市盈率高增长的价投策略.txt；quant/聚宽2025年精选/4高股息低市盈率高增长的价投策略.txt |
| 96a68a9b76ec | 2 | size | daily_stock_fields | quant/2024年度精选策略1/53.微盘400每日再平衡.txt；quant/聚宽2025年精选/73微盘400每日再平衡.txt |
| 974d348733c8 | 2 | intraday;value;volatility | intraday_data | quant/2020年度精选策略/02 我好像破解了聚宽擂台排第一的策略？！.txt；quant/2020年度精选策略/19 招行_海天配对策略（学习招行伊利配对）.txt |
| 979947ba2a42 | 2 | etf_macro;growth;intraday;momentum_reversal;technical;turnover;volatility | money_flow_or_event;non_stock_asset | quant/2021年度精选策略/93北向Boll带_ETF组合宝付费策略.txt；quant/2023年度精选策略/31.北向Boll带_ETF组合宝付费策略.txt |
| 98be1cbf1a40 | 2 | etf_macro;event_short;growth;intraday;quality;size;turnover;value | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/64大小外择时小市值3.0.txt；quant/聚宽2025年精选/83大小外择时小市值.txt |
| 990d3ecf0af9 | 2 | etf_macro;growth;intraday;technical | daily_stock_fields | quant/2022年度精选策略/57.宏观指标择时检测.txt；quant/2022年度精选策略/6.择时，还是宏观数据靠谱（宏观择时集合）.txt |
| 9b3b1b0eadb8 | 2 | event_short;intraday;size;turnover;volatility | daily_stock_fields | quant/2024年度精选策略1/6.高股息低杠杆小市值轮动策略.txt；quant/2024年度精选策略2/15.高股息低杠杆小市值轮动策略.txt |
| 9c0fae1153ae | 2 | etf_macro;intraday;price_volume;volatility | daily_stock_fields | quant/2023年度精选策略/95.【复现】高频价量相关性，意想不到的选股因子.txt；quant/2024年度精选策略2/19.【复现】高频价量相关性，意想不到的选股因子.txt |
| ad4a471987db | 2 | etf_macro;technical;value | non_stock_asset | quant/聚宽2025年精选/58Debug-输出信息-多标的版ETF策略(ETF复现之三）.txt；quant/量化策略/量化策略/ETF轮动策略2026/04多标的版ETF策略-25年13.txt |
| b00e178d89b8 | 2 | etf_macro;intraday;momentum_reversal;size;technical;turnover;value;volatility | non_stock_asset | quant/2024年度精选策略2/66.ETF动量轮动MA乖离择时.txt；quant/量化策略/量化策略/ETF轮动策略2026/09ETF动量轮动MA乖离择时-25年62.txt |
| b4b052426db0 | 2 | etf_macro;event_short;intraday;momentum_reversal;size;technical;turnover;value;volatility | industry_or_concept;non_stock_asset | quant/2024年度精选策略2/25.年初至今4倍，极致的Day Trading，56.8%胜率.txt；quant/2024年度精选策略2/79.实盘一周50%的妖股探测器.txt |
| b8d610c8f564 | 2 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;value | pit_financial_or_valuation | quant/2023年度精选策略/99.全市场选股？7年5倍不择时，回撤30%左右.txt；quant/2024年度精选策略2/12.全市场选股？7年5倍不择时，回撤30%左右.txt |
| bb2f4952057a | 2 | intraday;momentum_reversal;quality;size | pit_financial_or_valuation | quant/2023年度精选策略/92.【超跌反弹v1.0】3年2.3倍的超跌反弹小牛股.txt；quant/2024年度精选策略2/30.【超跌反弹v1.0】3年2.3倍的超跌反弹小牛股.txt |
| bb3df97c4e0a | 2 | size | daily_stock_fields | quant/2024年度精选策略1/87.山寨红利.txt；quant/聚宽2025年精选/87山寨红利.txt |
| c3ef2cc39265 | 2 | etf_macro;growth;intraday;momentum_reversal;technical | non_stock_asset | quant/2023年度精选策略/12.【不含未来！】宽基etf轮动8年50倍年化60%.txt；quant/2023年度精选策略/72.优化了一下宽基etf追涨的策略，值得深入研究.txt |
| c5d96240ea47 | 2 | intraday | daily_stock_fields | quant/2020年度精选策略/29 KD指标量化交易策略.txt；quant/2023年度精选策略/17.20行代码8年胜率100%躲过了牛年第一场大跌.txt |
| cadf6290c86d | 2 | event_short;intraday;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/58 MACD金叉买入，死叉卖出.txt；quant/2022年度精选策略/88.一个简单策略，看起来还行。.txt |
| d2cb2c575f8b | 2 | etf_macro;event_short;intraday;size;turnover;value | daily_stock_fields | quant/2023年度精选策略/21.截止到21年12月依然有效的小市值适配因子.txt；quant/2024年度精选策略2/3.截止到21年12月依然有效的小市值适配因子.txt |
| d8c573b3b06a | 2 | event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略1/16.大市值价值投资，从2005年至今超额稳定.txt；quant/2024年度精选策略1/55.Ahfu的大市值价值投资加自定义邮箱推送.txt |
| dff32d7cc6a9 | 2 | etf_macro;growth;intraday;momentum_reversal;technical | non_stock_asset | quant/2021年度精选策略/92.敢于直接实盘的—八仙过海V2.txt；quant/2023年度精选策略/45.敢于直接实盘的—八仙过海V2.txt |
| e12a8b16b1db | 2 | size | daily_stock_fields | quant/2020年度精选策略/11 酒股地中短线策略.txt；quant/2020年度精选策略/14 抗击熊市的中短期低市值策略.txt |
| e374b6a39af1 | 2 | etf_macro;event_short;growth;intraday;quality;size;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/48.【漂亮50 2.0止损版本】为了降低回撤，加入择时止损模块.txt；quant/2024年度精选策略2/98.【漂亮50】“漂亮50”策略复现以及股息率排序函数.txt |
| e4c79ee824a8 | 2 | event_short;growth;intraday;quality;size;turnover;value | industry_or_concept | quant/聚宽2025年精选/93.234板介入-2023年14倍-无未来.txt；quant/量化策略/量化策略/龙头追涨策略2026/03-234板介入-23年盈利15倍222425年巨亏-95以上.txt |
| e4d461e2905e | 2 | intraday;momentum_reversal;size;turnover | daily_stock_fields | quant/2024年度精选策略1/49.年化62%的动量策略.txt；quant/2024年度精选策略2/59.年化62%的动量策略.txt |
| e697adadfdd9 | 2 | etf_macro;growth;intraday;machine_learning;momentum_reversal;size;technical;turnover;value;volatility | industry_or_concept;model_training;non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略1/66.SVR机器学习上证综指择时中小板财务选股策略.txt；quant/聚宽2025年精选/41SVR机器学习上证综指择时中小板财务选股策略.txt |
| e7a846f5cde6 | 2 | event_short;intraday;size;turnover | industry_or_concept | quant/2024年度精选策略1/15.10年52倍，年化59%，全新因子方法超稳定.txt；quant/聚宽2025年精选/10.10年52倍，年化59，全新因子方法超稳定.txt |
| eb173c3a7ab3 | 2 | etf_macro;intraday;momentum_reversal | non_stock_asset | quant/2024年度精选策略1/43.ETF轮动：年化收益82.68%，最大回撤13.54%.txt；quant/量化策略/量化策略/ETF轮动策略2026/10ETF策略之核心资产轮动-25年53.txt |
| f68d4a9e1917 | 2 | etf_macro;event_short;intraday;turnover | daily_stock_fields | quant/2021年度精选策略/98.追涨大师（超额142）.txt；quant/2023年度精选策略/26.追涨大师（超额142）.txt |
| fadb3e9d3b5c | 2 | event_short;intraday;machine_learning;quality;size;turnover | model_training | quant/2024年度精选策略1/23.wywy1995大神机器学习策略年化提升35pt.txt；quant/2024年度精选策略1/5.尝试用机器学习批量生产小盘策略.txt |
| fd8300eae654 | 2 | intraday;momentum_reversal;quality;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略1/59.基于Gyro^.^大神的小市值策略的因子匹配研究.txt；quant/聚宽2025年精选/89基于Gyro.大神的小市值策略的因子匹配研究.txt |
| fdb7d7c4562a | 2 | event_short;growth;intraday;quality;size;value | pit_financial_or_valuation | quant/2024年度精选策略1/28.正黄旗大妈选股法，修改版，年化92%.txt；quant/聚宽2025年精选/84正黄旗大妈选股改进-加入涨停卖出后的买入，提高资金利用率.txt |
| 00ba89571068 | 1 | intraday;quality;value | intraday_data;pit_financial_or_valuation | quant/2020年度精选策略/97 银行翻倍策略.txt |
| 0121d290cbdc | 1 | event_short;intraday;quality;size;turnover | pit_financial_or_valuation | quant/聚宽2025年精选/5四大搅屎棍策略.txt |
| 01ac1e6b9cf0 | 1 | etf_macro;event_short;growth;intraday;machine_learning;momentum_reversal;quality;size;technical;turnover;value;volatility | industry_or_concept;intraday_data;model_training;pit_financial_or_valuation | quant/2021年度精选策略/28.XGBoost模型多因子策略分享.txt |
| 0200791ad605 | 1 | growth;intraday;quality;size;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/11.多因子选股策略——基于传统分析.txt |
| 027778d91fa8 | 1 | event_short;growth;intraday;quality;size;turnover | pit_financial_or_valuation | quant/聚宽2025年精选/31蛇皮走位小市值策略V1.0.txt |
| 0312d2066cc4 | 1 | intraday;size;value | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/67 多因子回测完整模板（筛选和买卖条件强于‘策略生成器’）.txt |
| 033893e18a21 | 1 | etf_macro;intraday;momentum_reversal;technical;turnover | non_stock_asset | quant/2022年度精选策略/28.etf轮动的优化，680%收益.txt |
| 036b07695272 | 1 | quality | pit_financial_or_valuation | quant/2024年度精选策略1/86.根据连续亏损预判st股票.txt |
| 03a0b3f00df8 | 1 | intraday | intraday_data | quant/2021年度精选策略/0.回测提速十倍,过滤ST,退市,停牌,新股优化方法.txt |
| 04c2e889e3c4 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;technical;turnover;value;volatility | pit_financial_or_valuation | quant/2023年度精选策略/29.价值成长轮动策略.txt |
| 04e8b04b63d7 | 1 | etf_macro;intraday;turnover;volatility | non_stock_asset | quant/2023年度精选策略/11.致敬市场--5 定投ETF之躺平赢.txt |
| 05462c1c1271 | 1 | etf_macro;event_short;intraday;momentum_reversal;size;turnover;value | daily_stock_fields | quant/2024年度精选策略2/74.【动量应用V1】12年120倍，根据研报思路调整.txt |
| 05ac49926edf | 1 | growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略1/14.四年多翻9倍，年化73%，成长因子评分筛选.txt |
| 06447133863b | 1 | etf_macro;intraday;volatility | intraday_data;non_stock_asset | quant/2021年度精选策略/83.识别趋势震荡之神器 MESA最大熵谱分析（一）：滤波器建立.txt |
| 069f70baa4f5 | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;value | intraday_data;pit_financial_or_valuation | quant/2020年度精选策略/31 低PB价值投资策略分享.txt |
| 06d86f05b57a | 1 | growth;intraday;size;turnover;value | daily_stock_fields | quant/聚宽2025年精选/53TSmall-100, 微盘三正.txt |
| 075432b70100 | 1 | growth;intraday;quality;turnover;value | pit_financial_or_valuation | quant/2023年度精选策略/91.致敬市场--4 解析细节.txt |
| 0798c8b85e5a | 1 | event_short;intraday;size;turnover;value | intraday_data | quant/2024年度精选策略2/32.追高概率涨停策略, 2022年化350%.txt |
| 080fa0e2f630 | 1 | etf_macro;intraday;momentum_reversal;technical;value;volatility | daily_stock_fields | quant/2021年度精选策略/44.借助JqData搭建简易回测框架.txt |
| 0811e957af85 | 1 | intraday;turnover | daily_stock_fields | quant/2024年度精选策略2/45.真真正正的诚意之作-2021超十倍.txt |
| 084b8fbc3b09 | 1 | etf_macro;intraday;momentum_reversal;price_volume;turnover;volatility | industry_or_concept | quant/2024年度精选策略1/93.【复现】国信投资者情绪指数择时模型.txt |
| 093cacd1c553 | 1 | etf_macro;intraday;quality;size;volatility | industry_or_concept | quant/2023年度精选策略/88.韶华研究之二，顺势而为，年化140.txt |
| 09406e1f8284 | 1 | event_short;growth;intraday;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/63 向导式.txt |
| 09b176b3bf62 | 1 | etf_macro;growth;intraday;machine_learning;quality;size;technical;value;volatility | model_training;pit_financial_or_valuation | quant/2022年度精选策略/82.RSRS择时+机器学习选股.txt |
| 09f079f6f4cb | 1 | intraday;quality;size;technical | daily_stock_fields | quant/2021年度精选策略/70.超稳的股息率+均线选股策略.txt |
| 0ae8b1dd1e20 | 1 | etf_macro;intraday;momentum_reversal;value;volatility | industry_or_concept;intraday_data | quant/2024年度精选策略2/55.【复现】技术指标形态识别.txt |
| 0c329612298a | 1 | etf_macro;growth;intraday;machine_learning;momentum_reversal;price_volume;quality;size;value | model_training;pit_financial_or_valuation | quant/2024年度精选策略1/33.年化46.77，alpha191因子选股.txt |
| 0c81fe43fa2b | 1 | event_short;growth;intraday;size;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略1/30.挖掘中国特色的估值体系投资机会，年化150%+.txt |
| 0d862836b1e0 | 1 | event_short;intraday;size;technical;turnover | intraday_data | quant/2023年度精选策略/2.多策略融合-80倍-无未来函数.txt |
| 0e3069f860ec | 1 | intraday;machine_learning;momentum_reversal;turnover;volatility | model_training | quant/2020年度精选策略/98 机器学习SVM用法示例策略.txt |
| 0e549a27994d | 1 | growth;intraday;quality;size;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/26.稳定高回报周期股策略2.txt |
| 0ec0656257af | 1 | event_short;intraday;quality;technical;turnover;volatility | intraday_data | quant/2023年度精选策略/70.回踩均线搏反弹，21年来70%，无未来（测试第一弹）.txt |
| 0f00f5af2557 | 1 | intraday;technical;volatility | daily_stock_fields | quant/2023年度精选策略/82.势的度量.txt |
| 0f7ea2454ebb | 1 | intraday;quality;size;technical | pit_financial_or_valuation | quant/2024年度精选策略1/40.14年初到23年7月，年化37，夏普1.25，稳健高收益！.txt |
| 0ffebe238d93 | 1 | etf_macro;intraday;momentum_reversal;price_volume;size;volatility | industry_or_concept;intraday_data | quant/2022年度精选策略/21.股价日内模式中蕴藏的选股因子.ipynb |
| 107d9c471902 | 1 | etf_macro;event_short;intraday;quality;size;turnover | non_stock_asset | quant/聚宽2025年精选/43小市值再优化【年化98 回撤27】无未来函数.txt |
| 117caf6a73e4 | 1 | intraday;technical;turnover | daily_stock_fields | quant/2020年度精选策略/76 MACD——大盘择时.txt |
| 12bb60b673ad | 1 | etf_macro;event_short;intraday;momentum_reversal;quality;size;technical;turnover | daily_stock_fields | quant/聚宽2025年精选/37微盘股扩散指数双均线择时.txt |
| 1308769ecfbd | 1 | etf_macro;event_short;intraday;momentum_reversal;price_volume;size;turnover;volatility | daily_stock_fields | quant/2022年度精选策略/19.a股跳一跳复现v4.txt |
| 13647c19d6a1 | 1 | event_short;intraday;size;technical | industry_or_concept | quant/量化策略/量化策略/龙头追涨策略2026/02涨停板多头策略-25年负-47.txt |
| 13720cd9cdf4 | 1 | etf_macro;event_short;size | daily_stock_fields | quant/2022年度精选策略/2.高收益中小板小流通市值次新股策略无择时.txt |
| 15254c83d31d | 1 | etf_macro;event_short;intraday;momentum_reversal;quality;size;technical;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/23大盘择时，逻辑简单.txt |
| 153b82d48f03 | 1 | etf_macro;event_short;intraday;quality;size;technical;turnover;value;volatility | money_flow_or_event;pit_financial_or_valuation | quant/2020年度精选策略/54 中长线买入卖出点选择.txt |
| 162f9120a3cd | 1 | event_short;growth;intraday;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/24 自选策略1.txt |
| 16421e0aed93 | 1 | size;value | non_stock_asset | quant/2022年度精选策略/80.小盘价值股策略2.01，年化131%，回撤8.8%.txt |
| 16c8723250a2 | 1 | event_short;intraday;price_volume;size;technical;turnover | intraday_data | quant/量化策略/量化策略/实盘2026/Ptrade/pt版实10首板竞价三模式.txt |
| 17b7c7182f3d | 1 | etf_macro;growth;intraday;momentum_reversal;price_volume;technical;turnover;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略2/82.可转债知识总结.txt |
| 17fea5328d7b | 1 | etf_macro;intraday;technical;turnover | non_stock_asset | quant/2022年度精选策略/84.MACD新研究，配合ETF十年稳稳的幸福.txt |
| 19cdb3f54206 | 1 | event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/聚宽2025年精选/39干积分-大小盘反复横跳V2.0.txt |
| 19e3c56c7b69 | 1 | intraday;volatility | non_stock_asset | quant/2021年度精选策略/7.股债波动平衡.txt |
| 1a279f499d84 | 1 | etf_macro;intraday;momentum_reversal;technical;turnover | non_stock_asset | quant/2024年度精选策略2/91.【复现】特征分布建模择时.txt |
| 1b9656521d3c | 1 | intraday;technical;volatility | intraday_data | quant/2023年度精选策略/19.人人可躺平16年3400%.txt |
| 1bdb5d1fcbf1 | 1 | etf_macro;growth;intraday;momentum_reversal;quality;size;technical;value;volatility | pit_financial_or_valuation | quant/2022年度精选策略/39.个股择时有效？因子选股+双均线择时效果初步尝试.txt |
| 1be40078d136 | 1 | etf_macro;intraday;quality;technical;value;volatility | pit_financial_or_valuation | quant/2020年度精选策略/05 兄台且慢，去天台排队不如看看这个策略先.txt |
| 1c7d86ea3b47 | 1 | intraday;size;turnover | daily_stock_fields | quant/2020年度精选策略/10 追三板策略.txt |
| 1cae9c1e5d29 | 1 | event_short;intraday;quality;size;turnover | industry_or_concept;non_stock_asset;pit_financial_or_valuation | quant/2021年度精选策略/17.基金跟随策略，19年年化60%.txt |
| 1cb297a8d443 | 1 | etf_macro;intraday;momentum_reversal;technical;turnover;volatility | non_stock_asset | quant/2022年度精选策略/87.RSI衍生指标择时轮动A股ETF.txt |
| 1cfe14fded63 | 1 | event_short;size | money_flow_or_event | quant/2021年度精选策略/49.根据北上资金买股票的最佳持股时间探讨.txt |
| 1d7e47e10bbd | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;technical;turnover;volatility | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/47多策略整合大E小十年百倍（年化64）.txt |
| 1e22f10b281f | 1 | etf_macro;intraday;technical | non_stock_asset | quant/2021年度精选策略/30.ETF宽基轮动修改版-1.0.txt |
| 1e2bb38b21d2 | 1 | etf_macro;intraday;momentum_reversal | industry_or_concept;intraday_data | quant/2021年度精选策略/2.板块轮动打分与热度追踪.txt |
| 1f633528ef31 | 1 | etf_macro;intraday;momentum_reversal;price_volume;technical;volatility | intraday_data;non_stock_asset | quant/2024年度精选策略2/43.ETF动量因子评估.txt |
| 219b273150b9 | 1 | event_short;intraday;size;turnover | daily_stock_fields | quant/聚宽2025年精选/7追首板涨停 过去两年年化304%.txt |
| 21a999cfdc84 | 1 | etf_macro;intraday;size;turnover | intraday_data | quant/2024年度精选策略2/47.别人恐惧我贪婪——重视大盘择时.txt |
| 21b6cec94e73 | 1 | event_short;growth;intraday;quality;size;turnover | pit_financial_or_valuation | quant/2024年度精选策略1/32.非线性市值（非小市值）组合4只.txt |
| 21c15f346402 | 1 | intraday;turnover | intraday_data | quant/2022年度精选策略/23盘口信息获取与判断.txt |
| 225bdef121fc | 1 | event_short;intraday;price_volume;size;technical;turnover | intraday_data | quant/量化策略/量化策略/实盘2026/Ptrade/pt版02首板高开趋势策略.txt |
| 22d0c7052bd3 | 1 | intraday;momentum_reversal | intraday_data | quant/2022年度精选策略/50.K线形态识别与验证-升级.txt |
| 24240444630c | 1 | etf_macro;growth;intraday;volatility | industry_or_concept;intraday_data;non_stock_asset | quant/2023年度精选策略/56.韶华研究之五-ETF轮动，躺赚，夏普2.txt |
| 243022fb4d8b | 1 | event_short;intraday;price_volume;size;technical;turnover | industry_or_concept;intraday_data | quant/2024年度精选策略2/96.集合竞价量比策略V1.txt |
| 244750930e87 | 1 | etf_macro;growth;intraday;momentum_reversal;price_volume;quality;technical;turnover;value;volatility | industry_or_concept;intraday_data;non_stock_asset | quant/2021年度精选策略/63.【复现】华泰证券-波动率和换手率构建牛熊指标.txt |
| 24dd3a72ed92 | 1 | event_short;intraday | intraday_data | quant/2021年度精选策略/56.大盘一路向上时，追总龙头2个月3倍.txt |
| 254364b099e2 | 1 | etf_macro;volatility | daily_stock_fields | quant/2024年度精选策略2/62.【重构】C-VIX 中国版 VIX 编制手册.txt |
| 2563a2f1bab1 | 1 | etf_macro;intraday;turnover | intraday_data;non_stock_asset | quant/2024年度精选策略2/44.！！！最易上手的网格策略v2.0，设置几个参数就可以直接使用.txt |
| 26b1592cc7c7 | 1 | event_short;intraday;momentum_reversal;quality;technical;turnover | intraday_data | quant/量化策略/量化策略/首板向上趋势策略2026/04首板-固定点入场-教科书复盘.txt |
| 270bb718d39a | 1 |  | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略1/68.业绩预告小工具--已更新.txt |
| 274044702ca8 | 1 | growth;intraday;momentum_reversal;quality;size;turnover;value;volatility | industry_or_concept;intraday_data;pit_financial_or_valuation | quant/2021年度精选策略/10.多因子选股.txt |
| 278c1ef9dbd2 | 1 | etf_macro;intraday;momentum_reversal;price_volume;size;volatility | non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/06-EPO低相关ETF轮动策略-25年47.txt |
| 27a87692ab83 | 1 | event_short;growth;intraday;quality;size;turnover | pit_financial_or_valuation | quant/聚宽2025年精选/67大市值价投高股息爱国者策略（爱我中华）.txt |
| 27e80ad799ba | 1 | etf_macro;growth;intraday;technical;turnover | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略2/73.实现净利润跳空策略.txt |
| 2a6babbaabc1 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;technical;turnover;value | industry_or_concept;non_stock_asset | quant/2023年度精选策略/62.3年复合200+%收益+超低回撤11%以内，无惧大跌.txt |
| 2ac6414b7fa3 | 1 | technical | daily_stock_fields | quant/2021年度精选策略/23.玩趋势交易的看进来~~~~2.txt |
| 2af62fce67c3 | 1 | etf_macro;intraday;turnover;volatility | intraday_data | quant/2022年度精选策略/41.【研报复现】一梦春秋.txt |
| 2bbf3720ab16 | 1 | intraday;technical | daily_stock_fields | quant/2021年度精选策略/91.欧奈尔 RPS选股战法回测.txt |
| 2c5bd9386709 | 1 | etf_macro;event_short;intraday;price_volume;turnover;volatility | intraday_data;non_stock_asset | quant/2021年度精选策略/73.基于期权PCR与标的波动率价差的股指期货套利.txt |
| 2d0b686a59f0 | 1 | event_short;growth;intraday;size;turnover;volatility | industry_or_concept | quant/2024年度精选策略2/49.修改成一创版本.txt |
| 2db7d825ab4e | 1 | event_short;growth;intraday;quality;volatility | pit_financial_or_valuation | quant/2023年度精选策略/64.韶华研究之七--不可多得的基本面三角.txt |
| 2de27ccdf0b2 | 1 | etf_macro;intraday | non_stock_asset | quant/2021年度精选策略/64.【复现】C-VIX 中国版 VIX 编制手册.txt |
| 2ed97942a959 | 1 | event_short;intraday | daily_stock_fields | quant/2022年度精选策略/60.2019年3月以来的前日涨停昨日未涨停今日大涨的追涨策略.txt |
| 303e580c28b7 | 1 | etf_macro;growth;intraday;quality;size;technical;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略1/45.[原创]价值投资+期货对冲V4.0,无惧市场大跌.txt |
| 30ad4acf48fa | 1 | event_short;intraday;size;technical;turnover;value | daily_stock_fields | quant/2021年度精选策略/47.高收益低回撤的小市值策略.txt |
| 320cf58ef6b7 | 1 | etf_macro;event_short;intraday;size;technical;turnover;value | daily_stock_fields | quant/量化策略/量化策略/小市值策略2026/实02小市值-技术过滤-25年收益129.03.txt |
| 3235342fb624 | 1 | volatility | daily_stock_fields | quant/2024年度精选策略2/94.FoF, all in.txt |
| 3251280600cd | 1 | intraday;momentum_reversal;size | daily_stock_fields | quant/2024年度精选策略1/18.微盘股研究.txt |
| 33d3e9660f51 | 1 | etf_macro;intraday;momentum_reversal;value | non_stock_asset;pit_financial_or_valuation | quant/2020年度精选策略/72 基金定投-沪深300-5年回测.txt |
| 354bba145815 | 1 | intraday | intraday_data | quant/2024年度精选策略2/86.可转债双低策略.txt |
| 35d2bda2b381 | 1 | etf_macro;growth;intraday;machine_learning;momentum_reversal;price_volume;quality;size;technical;value;volatility | industry_or_concept;model_training;pit_financial_or_valuation | quant/2022年度精选策略/8.多因子策略研究代码框架.txt |
| 36726e2731c4 | 1 | intraday;technical;turnover | intraday_data | quant/2023年度精选策略/73.MACD多周期共振，精准打击！.txt |
| 36fb9ff23ead | 1 |  | daily_stock_fields | quant/2023年度精选策略/69.选取向上趋势的股票.txt |
| 372cd7ef6cb3 | 1 | etf_macro;intraday;momentum_reversal | non_stock_asset | quant/2021年度精选策略/74.迪马克TD趋势反转指标.txt |
| 3733eb4e31b1 | 1 | etf_macro;growth;intraday;quality;size;technical;value | pit_financial_or_valuation | quant/2021年度精选策略/55.价值投资改进版-6年9.5倍.txt |
| 379896b3df66 | 1 | etf_macro;intraday | daily_stock_fields | quant/2021年度精选策略/65.【分享】多因子指数增强.txt |
| 37c7a27ae948 | 1 | etf_macro;intraday;technical | daily_stock_fields | quant/2022年度精选策略/76.向云帆致敬—— 宏观数据择时策略——极速版代码.txt |
| 3807c057619b | 1 | etf_macro;intraday;size;technical;volatility | non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/04多标的版ETF策略-重构优化版-25年70.txt |
| 38174be125bf | 1 | etf_macro;event_short;growth;intraday;machine_learning;size;turnover | industry_or_concept;model_training | quant/2024年度精选策略1/82.实盘模拟的小盘股策略，低频，带基本面优化以及个股风控.txt |
| 385e8745574b | 1 | etf_macro;event_short;growth;intraday;size;turnover | intraday_data;non_stock_asset | quant/2022年度精选策略/34.N进N+1打板策略1.2版.txt |
| 385f16502bcc | 1 | event_short;intraday;technical;turnover | intraday_data | quant/2023年度精选策略/1.龙头底分型战法-两年23倍.txt |
| 38a3ecf2a0aa | 1 | intraday;technical;volatility | money_flow_or_event | quant/2021年度精选策略/86.北上詹姆斯.txt |
| 3989b6bb090d | 1 | etf_macro;event_short;growth;intraday;quality;technical;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/86.【基本面三角3.0】看过之前策略的就略过吧.txt |
| 39b617850221 | 1 | event_short;intraday;quality;size;technical;turnover;volatility | intraday_data | quant/2023年度精选策略/49.【7日趋势】交易策略.txt |
| 39b9bf825f4d | 1 | intraday;volatility | daily_stock_fields | quant/2020年度精选策略/50 简单配对交易.txt |
| 3a144e68ee80 | 1 | etf_macro;intraday;size;technical;turnover | non_stock_asset | quant/聚宽2025年精选/29穿越牛熊2.0(非小市值)年化50%的cta策略.txt |
| 3a73d86ab24f | 1 | intraday;size;technical | daily_stock_fields | quant/2023年度精选策略/44.海龟突破系统，19-21年化150，无未来函数和过拟合.txt |
| 3ba25c06636d | 1 | event_short;intraday;quality;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/16 投资学作业.txt |
| 3ebc0d289d43 | 1 | etf_macro;intraday;momentum_reversal;technical;volatility | intraday_data | quant/2023年度精选策略/80.趋与势的量化定义.txt |
| 3f25699eee5d | 1 | growth;intraday;momentum_reversal;quality;size;turnover;value | intraday_data;pit_financial_or_valuation | quant/2021年度精选策略/38.python搭建简单交易系统.txt |
| 3f39cf615c6e | 1 | etf_macro;growth;intraday;size;turnover;value | intraday_data;non_stock_asset | quant/2024年度精选策略2/69.场内基金定投价值平均增强策略，年化30%+.txt |
| 40032a703316 | 1 | intraday;price_volume;turnover;volatility | daily_stock_fields | quant/2021年度精选策略/40.基于遗传算法挖掘因子2.txt |
| 403cbb2e3e23 | 1 | intraday;quality;size;technical;turnover;value | non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/14.银行股价值定投.txt |
| 410a2df8717b | 1 | etf_macro;intraday;momentum_reversal;technical;turnover;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/62.商品期货多因子 全市场对冲模型.txt |
| 42c6a3d179eb | 1 | intraday;turnover | non_stock_asset | quant/2024年度精选策略2/84.多大规模的基金收益最好？偏股基金规模研究.txt |
| 42d7041557c6 | 1 | event_short;intraday;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/99 一个中信证券的向导策略.txt |
| 4303a298fd52 | 1 | etf_macro;intraday;momentum_reversal;size;turnover;volatility | industry_or_concept;money_flow_or_event | quant/聚宽2025年精选/56基于趋势、拥挤、景气的行业轮动，及行业强势个股的选择.txt |
| 4398ccbb71f4 | 1 | intraday;volatility | daily_stock_fields | quant/2022年度精选策略/66.【配对交易】基于zscore的配对交易策略（胜率88.2%）.txt |
| 44d60949c30c | 1 | etf_macro;growth;intraday;momentum_reversal;technical;turnover | non_stock_asset | quant/2024年度精选策略1/85.【深度解析 七】BBI指标-大盘涨跌-宽基轮动模型.txt |
| 44ee0007275f | 1 | event_short;growth;intraday;quality;size;turnover;value;volatility | pit_financial_or_valuation | quant/2024年度精选策略1/71.小试多因子策略，年化65%.txt |
| 44fd74905c8b | 1 | growth;intraday;machine_learning;price_volume;quality;size;technical;value;volatility | industry_or_concept;intraday_data;model_training;pit_financial_or_valuation | quant/2021年度精选策略/12.机器学习用于量化分析.txt |
| 459c90b2caf2 | 1 | intraday;momentum_reversal;turnover | industry_or_concept | quant/2023年度精选策略/63.A股最强板块动量趋势（最终版）.txt |
| 45ae81960cf0 | 1 | event_short;growth;intraday;size;turnover;value | intraday_data;pit_financial_or_valuation | quant/量化策略/量化策略/实盘2026/Ptrade/pt版08多因子成长小市值轮动策略.txt |
| 45cc6636e7a8 | 1 | event_short;growth;intraday;quality;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/44 新手初来，写了一个价值投资策略.txt |
| 46a2ba77ae17 | 1 | etf_macro;intraday;machine_learning;turnover | industry_or_concept;intraday_data;model_training;non_stock_asset | quant/2022年度精选策略/77.TensorFlow 学习之循环神经网络（RNN）.txt |
| 46a334f8e9a2 | 1 | etf_macro;size | daily_stock_fields | quant/2020年度精选策略/25 简单市值轮动策略-学习.txt |
| 472d4fb46a5e | 1 | event_short;intraday;size;turnover | daily_stock_fields | quant/聚宽2025年精选/13首板高开-低开-弱转强混合策略（今年收益1138.61）.txt |
| 4762f6064425 | 1 | intraday;machine_learning;technical;volatility | industry_or_concept;model_training | quant/2022年度精选策略/7.中文自然语言处理--情感分析.txt |
| 48504f55e7ba | 1 | etf_macro;event_short;growth;intraday;quality;size;technical;turnover;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略2/78.ffscore选股加rsrs择时.txt |
| 4966a6434a19 | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover | intraday_data;non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略1/46.【深度解析 四】聚宽三因子基本面 模型.txt |
| 49cf2e018be7 | 1 | etf_macro;intraday;technical;turnover;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/89.MACD+波动率过滤+追踪止损 期货择时汇总.txt |
| 4b9120d9edb0 | 1 | intraday;quality;size;technical;turnover;value | pit_financial_or_valuation | quant/2023年度精选策略/65.PB-POE+双均线--加入jq以来第一个成功的交易策略 一.txt |
| 4b96085a087c | 1 | etf_macro;growth;intraday;machine_learning;momentum_reversal;price_volume;quality;size;turnover;value | model_training;pit_financial_or_valuation | quant/2024年度精选策略2/41.手把手教你“机器学习-动态多因子选股”(附保姆级教程).txt |
| 4b98b9a07838 | 1 | etf_macro;intraday;size;technical | industry_or_concept;intraday_data | quant/2021年度精选策略/45.市场宽度.txt |
| 4bd5d8e02657 | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/44国九条 年化130.74% 回撤11% 众神Debug版.txt |
| 4beecdb432f0 | 1 | event_short;growth;intraday;quality;size;turnover | pit_financial_or_valuation | quant/2024年度精选策略1/39.大资金优质股策略，总收益1217%！无小市值因子！.txt |
| 4cb40ee273c8 | 1 | event_short;growth;intraday;quality;size;turnover;value | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/9干积分-量化策略简易框架.txt |
| 4d068f25d9e6 | 1 | event_short;intraday;machine_learning;size;turnover | industry_or_concept;model_training | quant/2024年度精选策略1/56.双人工智能配合，样本外夏普3.9.txt |
| 4db23de21a48 | 1 | etf_macro;event_short;intraday;momentum_reversal;price_volume;turnover;volatility | industry_or_concept;intraday_data;non_stock_asset | quant/2023年度精选策略/55.【分享】券商金股组合增强.txt |
| 4de11d983f96 | 1 | intraday;technical;volatility | daily_stock_fields | quant/2020年度精选策略/12 【均值回归】基于zscore的均值回归策略（胜率100%）.txt |
| 4e808afc0cd4 | 1 | intraday;size;value | daily_stock_fields | quant/聚宽2025年精选/82回报社区——基于Gyro老师策略的思考.txt |
| 4e945f3d778e | 1 | etf_macro;event_short;intraday;size;value;volatility | non_stock_asset | quant/2022年度精选策略/24.龙头低波市值平均轮动策略.txt |
| 4e9a3d4fecfd | 1 | intraday;technical;value;volatility | money_flow_or_event;non_stock_asset | quant/2023年度精选策略/46.年化46%的北向资金+20日涨幅的创业板策略.txt |
| 4ef9c30051e5 | 1 | etf_macro;intraday;technical;turnover;volatility | daily_stock_fields | quant/2020年度精选策略/77 RSRS大盘择时优化.txt |
| 4f5466ba5c83 | 1 | etf_macro;intraday;momentum_reversal;turnover | non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/05动量最强ETF轮动策略-调优版-25年83.txt |
| 515b94c2a477 | 1 | intraday;momentum_reversal | intraday_data | quant/2022年度精选策略/5.高频策略研究（一）——基于开盘情况预测走势-Copy1.txt |
| 51d73a1243ef | 1 | etf_macro;intraday;size;technical | daily_stock_fields | quant/2021年度精选策略/61.【复现】扩散指标择时.txt |
| 51e7b8f2a0f7 | 1 | event_short;growth;intraday;quality;size;turnover;value | daily_stock_fields | quant/聚宽2025年精选/24大容量低回撤价值投资-排除小市值因子.txt |
| 52016d8fb44e | 1 | etf_macro;momentum_reversal;price_volume;quality;technical;turnover;volatility | daily_stock_fields | quant/2021年度精选策略/59.【复现】RSRS择时改进.txt |
| 5278c195c04f | 1 | etf_macro;intraday;technical;volatility | daily_stock_fields | quant/2020年度精选策略/93 RSRS——大盘择时.txt |
| 538a9d7f4c85 | 1 | intraday;technical;volatility | daily_stock_fields | quant/2020年度精选策略/52 布林带1.txt |
| 539bc3364dde | 1 | growth;intraday;machine_learning;quality;size;value | industry_or_concept;model_training;pit_financial_or_valuation | quant/2022年度精选策略/97.基于机器学习的多因子选股策略.txt |
| 553825701eaa | 1 | intraday;turnover;volatility | intraday_data | quant/聚宽2025年精选/94别人“拿的住”的股票最赚钱.txt |
| 55605687359d | 1 | etf_macro;event_short;intraday;size;technical;turnover | daily_stock_fields | quant/聚宽2025年精选/16集合竞价三合一，今年收益1067.txt |
| 55b577d22785 | 1 | event_short;growth;intraday;machine_learning;momentum_reversal;quality;size;turnover;value | model_training;pit_financial_or_valuation | quant/2024年度精选策略1/79.SVR选股的小市值策略.txt |
| 56dd263ecbbc | 1 | intraday;size | daily_stock_fields | quant/2022年度精选策略/36.年化70%，近三年还有效的小市值策略.txt |
| 56e03e42ea35 | 1 | growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/聚宽2025年精选/48投资回报率ROIC中等市值.txt |
| 57042fb745f5 | 1 | intraday;machine_learning;turnover | model_training | quant/2020年度精选策略/91 Stoch（KDJ）——大盘择时.txt |
| 57078556dcd0 | 1 | etf_macro;event_short;intraday | daily_stock_fields | quant/2024年度精选策略1/58.融券做空,3年35倍多！已模拟2年半，动态跑盘收益惊人！.txt |
| 57ee8b128f7e | 1 | growth;intraday;momentum_reversal;size;turnover;value | daily_stock_fields | quant/聚宽2025年精选/11低风险中等收益策略.txt |
| 582a2de0a0ec | 1 | intraday;value | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/85 【第一次玩】我就是要买便宜股系列.txt |
| 5856be563206 | 1 | etf_macro;intraday;momentum_reversal;technical | industry_or_concept;non_stock_asset | quant/2024年度精选策略2/21.行业ETF轮动+择时，15年至今年化收益35%，回撤16%.txt |
| 58e43a850994 | 1 | etf_macro;event_short;intraday;technical;turnover | non_stock_asset | quant/2022年度精选策略/10.期货macd简单择时，atp止损.txt |
| 58eae40ba55b | 1 | intraday | intraday_data | quant/2022年度精选策略/22.多因子系列：基于多因子框架的收益预测模型.txt |
| 599f8e307383 | 1 | etf_macro;growth;intraday;momentum_reversal;quality;size;turnover;value;volatility | industry_or_concept;intraday_data;pit_financial_or_valuation | quant/2024年度精选策略1/98.FScore9因子模型改进——RFScore7因子.txt |
| 59b4b385817c | 1 | event_short;intraday;technical | intraday_data | quant/2021年度精选策略/75.最近2年年化100%以上回撤12%的打板策略-验证策略.txt |
| 59db63de8f6e | 1 | event_short;intraday;size | money_flow_or_event | quant/2021年度精选策略/52.根据北上资金买A股策略Python3版（北向、港资、外资）.txt |
| 5c39088a2d42 | 1 | event_short;intraday;size | daily_stock_fields | quant/2024年度精选策略1/48.低代码迁移成本的实盘方案jqtrade+one quant.txt |
| 5cd7e631c6c5 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;size;technical;turnover;value | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/71（乱改一版）股票加“钱粮”ETF组合.txt |
| 5d4b6c1df828 | 1 | etf_macro;intraday;quality;technical;value;volatility | industry_or_concept | quant/2021年度精选策略/33.【研报复现】基于风险溢价的沪深300择时-目前依然有效.txt |
| 5df2e98ed8fc | 1 | etf_macro;intraday;value | non_stock_asset | quant/2022年度精选策略/63.螺纹钢供需轮动策略（带止损）.txt |
| 5ebb73fab6b7 | 1 | event_short;intraday;quality;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/80 向导式 价值分析(一),成功避开股灾,大盘震荡跌时小涨.txt |
| 5edfdda80a81 | 1 | event_short;intraday | intraday_data | quant/2023年度精选策略/89.2019年到现在90多倍的新策略.txt |
| 5ee22a75afbf | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/聚宽2025年精选/42国九条：三年分红5千万以下且占净利润30以下将被ST.txt |
| 5f6c52ceadd3 | 1 | etf_macro;intraday;momentum_reversal | intraday_data;non_stock_asset | quant/聚宽2025年精选/91ETF-T0动量策略，年化 18%，回撤3.31%.txt |
| 626f1c1b8a1f | 1 | etf_macro;size;value | pit_financial_or_valuation | quant/2020年度精选策略/59 小市值轮动，修改了内容，剔除了停牌股，同时PE要求为正的股票。.txt |
| 6323150a0a24 | 1 | etf_macro;intraday;technical;volatility | intraday_data;non_stock_asset | quant/2022年度精选策略/91.基于主成分分析 沪深300个股一致性IF股指交易策略.txt |
| 6409273381f5 | 1 | event_short;intraday;size;turnover;value | daily_stock_fields | quant/2021年度精选策略/24.现在便宜的300就是最好的，收益惊人！【结束了】.txt |
| 6579949067bc | 1 | event_short;intraday;price_volume;quality;size;technical;turnover;value | daily_stock_fields | quant/量化策略/量化策略/首板回调买入策略2026/实10-首板竞价三模式-25年206.7.txt |
| 66345a350db6 | 1 | intraday;size | industry_or_concept;intraday_data | quant/2023年度精选策略/96.市场宽度20210622.txt |
| 66d36a8389e7 | 1 | etf_macro;intraday;momentum_reversal | non_stock_asset | quant/2022年度精选策略/52.用指数战胜指数，ETF二八轮动对冲模型.txt |
| 66dbbd496c61 | 1 | intraday;price_volume;technical | non_stock_asset | quant/2021年度精选策略/16.缠论工具（笔， 线段）.txt |
| 66ee22766cae | 1 | etf_macro;intraday;technical;volatility | intraday_data | quant/2022年度精选策略/53.【指标研究】MACD日、周、月以及分别级别研究（包含低位二次金叉算法）.txt |
| 672a217239f6 | 1 | growth;intraday;momentum_reversal;price_volume;size;technical;turnover;value;volatility | industry_or_concept;intraday_data | quant/2022年度精选策略/42.【研报复现】再论动量因子Ian666.txt |
| 678ecba449d3 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;technical;turnover;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略1/27.根据大小盘相对强弱选择合适的板块股票进行交易.txt |
| 67a62f151177 | 1 | etf_macro;intraday;price_volume;technical;turnover | daily_stock_fields | quant/2022年度精选策略/35.量价MACD组合择时-帮你把握股市中的大趋势.txt |
| 682a2639a1fa | 1 | event_short;intraday;quality;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/57 黄泽森策略.txt |
| 68d82d2cee22 | 1 | etf_macro;growth;intraday;momentum_reversal;value | non_stock_asset | quant/聚宽2025年精选/22带上止损的核心资产轮动才更安心，低回撤，高收益率.txt |
| 6929cdc979bb | 1 | etf_macro;event_short;intraday;size;technical;turnover;value;volatility | daily_stock_fields | quant/2023年度精选策略/78.EPS+MS因子的大盘蓝筹策略.txt |
| 6985333d8f9d | 1 | event_short;intraday;technical;turnover | daily_stock_fields | quant/量化策略/量化策略/首板回调买入策略2026/07-首板回调n日介入.txt |
| 698b8110ff98 | 1 | etf_macro;event_short;growth;intraday;quality;turnover;volatility | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/79.过滤两个因子，12年15倍的roa选股500指数增强.txt |
| 6bed8c240b40 | 1 | intraday;momentum_reversal;quality;size;volatility | pit_financial_or_valuation | quant/2022年度精选策略/98.复现东方证券研报--特质波动率因子研究.txt |
| 6c5f9c8fd842 | 1 | intraday;momentum_reversal | daily_stock_fields | quant/2022年度精选策略/64.传统反转因子的改进与实测.txt |
| 6cee35d423b5 | 1 | etf_macro;intraday | intraday_data;non_stock_asset | quant/2021年度精选策略/84.ETF网格交易策略.txt |
| 6d43d4cc6734 | 1 | etf_macro;event_short;intraday;size;turnover;volatility | daily_stock_fields | quant/聚宽2025年精选/28韶华研究之十九，一致性用在微盘控制回撤.txt |
| 6d7546f85ef9 | 1 | etf_macro;event_short;intraday;machine_learning;turnover | model_training;non_stock_asset | quant/聚宽2025年精选/95学习贴《一个完整的-深度学习-神经网络pipeline》.txt |
| 6e664cc78fe6 | 1 | growth;intraday;quality;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/48.买不到710亿爆款基金怎么办？自己做一个量化价值成长策略吧.txt |
| 6e6b0b36de1a | 1 | etf_macro;intraday;size | industry_or_concept | quant/2020年度精选策略/81 申万行业轮动策略.txt |
| 6e7700f4fc87 | 1 | event_short;intraday;size | intraday_data | quant/2024年度精选策略2/97.【涨停研究一】具有哪些因子的股票更容易涨停.txt |
| 6f4c94e37471 | 1 | event_short;intraday;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/94 PE和PB策略.txt |
| 6fab4abbcd4c | 1 | etf_macro;growth;intraday;momentum_reversal;quality;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/90.一个月轮动股票换仓，内日做T，相对高频交易.txt |
| 6fbeeba7a0b2 | 1 | event_short;intraday;size;technical;turnover;value | daily_stock_fields | quant/2021年度精选策略/15.小市值策略之再优化，年化接近翻倍.txt |
| 6fe3ceea6832 | 1 | event_short;intraday;price_volume;turnover;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略1/84.【社区研究】连板龙头策略-wywy：复现与研究.txt |
| 70e0249be6f5 | 1 | etf_macro;momentum_reversal;price_volume;volatility | non_stock_asset | quant/聚宽2025年精选/26波动率过滤后相关性最小etf轮动.txt |
| 7153afe9933d | 1 | etf_macro;intraday;machine_learning;size;technical;turnover;volatility | intraday_data;model_training | quant/2024年度精选策略1/94.大市值小市值今年的一些分析，然后尝试预测小市值行情.txt |
| 72163194f852 | 1 | etf_macro;growth;intraday;quality;size | pit_financial_or_valuation | quant/2020年度精选策略/07 穿越牛熊基业长青的价值精选策略.txt |
| 724d8a107b33 | 1 | event_short;growth;intraday;machine_learning;momentum_reversal;quality;size;technical;turnover;value;volatility | industry_or_concept;intraday_data;model_training;pit_financial_or_valuation | quant/2024年度精选策略1/64.基于XGBoost6m滚动选股策略.txt |
| 7408239b2e5f | 1 | event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/聚宽2025年精选/45此消彼长.txt |
| 74f27b769c82 | 1 | event_short;growth;intraday;quality;size;turnover | pit_financial_or_valuation | quant/聚宽2025年精选/51“四大搅屎棍策略”学习笔记-有魔改.txt |
| 7534c2262244 | 1 | etf_macro;event_short;intraday;size | daily_stock_fields | quant/2024年度精选策略2/13.【涨停研究三】连板股票收益统计与回测.txt |
| 7572290b6412 | 1 | turnover | non_stock_asset | quant/聚宽2025年精选/100使用K-means 聚类对基金分类.py |
| 766b18dd1caa | 1 | etf_macro;intraday;momentum_reversal;size;technical;turnover;value;volatility | money_flow_or_event;non_stock_asset | quant/2024年度精选策略2/38.ETF动量轮动RSRS择时-魔改3-北向资金择时-再优化.txt |
| 7730148e2a46 | 1 | intraday;price_volume;technical;turnover;volatility | daily_stock_fields | quant/2022年度精选策略/78.RSRS系列一：完整复现版(自带快速回测框架).txt |
| 777cd4d25b5e | 1 | etf_macro;growth;intraday | pit_financial_or_valuation | quant/2024年度精选策略2/93.因子看板多因子模型---由量化课堂多因子模型修改.txt |
| 793c6eb8ea00 | 1 | growth;intraday;technical;turnover | daily_stock_fields | quant/2022年度精选策略/55.【策略研发】三进兵策略（变形版）.txt |
| 7ae124b65fd4 | 1 | growth;intraday;momentum_reversal;quality;size;value | pit_financial_or_valuation | quant/2021年度精选策略/39.因子分析系列文章（八）：多因子策略（多元线性回归）.txt |
| 7b0c7dd2728e | 1 | event_short;growth;intraday;quality;size;turnover;volatility | pit_financial_or_valuation | quant/2024年度精选策略2/39.绩优小市值量化君也-模拟交易年化333.75%.txt |
| 7b4de502458b | 1 | event_short;growth;intraday;size;turnover;value | daily_stock_fields | quant/2023年度精选策略/60.抄底神器2.0，低回撤，高成功率，无未来函数.txt |
| 7d01618d5cd9 | 1 | event_short;growth;intraday;machine_learning;quality;size;turnover | model_training;pit_financial_or_valuation | quant/聚宽2025年精选/52机器学习滚动训练价投策略.txt |
| 7e50d7ea604d | 1 | etf_macro;growth;intraday;quality;value | pit_financial_or_valuation | quant/2022年度精选策略/11.林奇PEG选股轮动，十年20倍，有止损模块.txt |
| 7edf07b734a5 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;size;technical;turnover;value;volatility | pit_financial_or_valuation | quant/2024年度精选策略1/44.分享一个兼顾业绩增长和PEG指标的股票策略.txt |
| 7f8d67f52b81 | 1 | growth;intraday;quality;size;value;volatility | pit_financial_or_valuation | quant/2022年度精选策略/74.基本面单因子测试——以BP因子为例.txt |
| 804178ca7dcd | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;technical;turnover;value | industry_or_concept;money_flow_or_event;non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略2/85.价值策略重开，再次向Jqz1226致敬.txt |
| 8072cd02af39 | 1 | etf_macro;intraday;quality;technical;turnover;volatility | daily_stock_fields | quant/2021年度精选策略/67.RSRS择时改进-【成交量加权-钝化-右偏】.txt |
| 818ba95f19be | 1 | event_short;intraday;momentum_reversal;technical;turnover | industry_or_concept;intraday_data;money_flow_or_event | quant/聚宽2025年精选/98热点行业和热点概念-成分股-及龙一龙二龙三.py |
| 81b7bdc4d023 | 1 | intraday;machine_learning;volatility | model_training | quant/2023年度精选策略/71.lightGBM.txt |
| 822c3f5adb8d | 1 | intraday | intraday_data | quant/2021年度精选策略/76.日内交易策略R-breaker - 300346.XSHE.txt |
| 829ad7681d6d | 1 | intraday | daily_stock_fields | quant/2020年度精选策略/41 多因子模型（三）-交易回测.txt |
| 8305d565a0b8 | 1 | etf_macro;intraday;turnover | non_stock_asset | quant/2022年度精选策略/43.股指期货&quot;蜘蛛网策略&quot; ——从成交持仓表中捕捉知情投资者行为.txt |
| 838b0355b3e0 | 1 | intraday;size;turnover | daily_stock_fields | quant/2022年度精选策略/59.【策略】夏普超过2.0，后市靠定增一步步往上爬.txt |
| 83909c649793 | 1 | etf_macro;event_short;growth;intraday;machine_learning;size;technical;turnover;value;volatility | industry_or_concept;model_training;non_stock_asset;pit_financial_or_valuation | quant/2021年度精选策略/36.市场底部特征研究.txt |
| 847af2365a67 | 1 | etf_macro;intraday;momentum_reversal;price_volume;turnover | intraday_data;non_stock_asset | quant/2021年度精选策略/66.【复现】A股日内动量效应（一）半小时 涨跌幅间的规律.txt |
| 8571982ed28f | 1 | etf_macro;event_short;growth;intraday;size;turnover | daily_stock_fields | quant/2024年度精选策略2/70.（股票交易模板）小市值-EPS-成长因子选股.txt |
| 867b382c75ec | 1 | etf_macro;intraday;quality;size;value;volatility | pit_financial_or_valuation | quant/2021年度精选策略/5.价值低波（下）--十年十倍（2020拜年）.txt |
| 86949db5d9cd | 1 | etf_macro;growth;intraday;quality;size | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/79.【多因子选股模型框架】(单因子各项指标评分细则).txt |
| 87e181664bf0 | 1 | etf_macro;intraday;momentum_reversal;price_volume;quality;technical;turnover;value;volatility | intraday_data;non_stock_asset | quant/2022年度精选策略/18.期权突破策略研究 v1.txt |
| 88de2a7665e8 | 1 | intraday;turnover | daily_stock_fields | quant/2023年度精选策略/23.低AH溢价选股.txt |
| 89150dba0fed | 1 | etf_macro;event_short;intraday;technical;value | non_stock_asset | quant/2024年度精选策略2/40.RSI学习贴.txt |
| 893116b84962 | 1 | etf_macro;intraday;price_volume;technical;turnover | non_stock_asset | quant/2022年度精选策略/75.量价MACD组合择时——极速版.txt |
| 893935048336 | 1 | etf_macro;growth;momentum_reversal;volatility | daily_stock_fields | quant/2022年度精选策略/15.A股-宏观动量-v5-Clone1.txt |
| 894711c3d2d0 | 1 | etf_macro;event_short;growth;intraday;price_volume;quality;size;technical;volatility | industry_or_concept | quant/2022年度精选策略/40.第三期研报复现——Eden666.txt |
| 8a5a81b125e5 | 1 | etf_macro;intraday;price_volume;quality;technical;value;volatility | pit_financial_or_valuation | quant/2022年度精选策略/92.黄金避险有效？量化实测黄金资产真实收益.txt |
| 8aa2b7e13bcb | 1 | etf_macro;intraday;machine_learning;volatility | model_training | quant/2024年度精选策略2/20.【复现】因子择时？？？.txt |
| 8aaf69e3abaf | 1 | etf_macro;intraday;quality;size;volatility | pit_financial_or_valuation | quant/2020年度精选策略/71 【投资学】CAPM单因子回归模型+ROE股票池（含止损）.txt |
| 8ad317c64b8f | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;volatility | non_stock_asset;pit_financial_or_valuation | quant/量化策略/量化策略/小市值策略2026/10改进版小市值策略-25年收益71.35.txt |
| 8c8030258b25 | 1 | etf_macro;intraday;value | industry_or_concept;intraday_data;pit_financial_or_valuation | quant/2024年度精选策略1/97.大周期顶底判断：FED指标+格雷厄姆指数一次搞定.txt |
| 8d49847c3969 | 1 | etf_macro;intraday;momentum_reversal;technical;turnover;value;volatility | intraday_data;non_stock_asset | quant/2024年度精选策略1/42.大盘ETF动量轮动RSRS择时策略-无纳指（5年半861%）.txt |
| 8dfbd6153e0f | 1 | etf_macro;event_short;intraday;momentum_reversal;price_volume;size;turnover;value;volatility | industry_or_concept;intraday_data | quant/2021年度精选策略/8.因子分析 营业利润TTM.txt |
| 8e8c1ba47e3c | 1 | event_short;intraday;size;turnover | daily_stock_fields | quant/2023年度精选策略/94.可转债回测.txt |
| 8edc192614e0 | 1 | event_short;intraday;size;volatility | daily_stock_fields | quant/2024年度精选策略2/88.打首板策略，今年收益达到40%，绝无未来函数（必回）.txt |
| 8f105cd1995a | 1 | etf_macro;intraday;technical;value;volatility | pit_financial_or_valuation | quant/2022年度精选策略/90.相信波动率还是相信基本面？波动与估值因子A股驱动力测试.txt |
| 8fd470ab564e | 1 | intraday;machine_learning | model_training | quant/2022年度精选策略/86.长江机器学习股票趋势预测.txt |
| 8fed89afa46f | 1 | event_short;intraday;turnover;value | industry_or_concept | quant/2024年度精选策略1/54.追市场热点策略.txt |
| 901223c5ac72 | 1 | etf_macro;intraday;momentum_reversal;quality;turnover;volatility | industry_or_concept;intraday_data | quant/2022年度精选策略/20.行业轮动的黄金律：日内动量与隔夜反转.txt |
| 9065b8828cdc | 1 | etf_macro;event_short;intraday;momentum_reversal;size;technical;volatility | daily_stock_fields | quant/2024年度精选策略2/31.《趋势永存》持续16年跑赢大盘的真正靠谱策略.txt |
| 90a4b6be4dad | 1 | etf_macro;event_short;intraday;size;technical;turnover;value | intraday_data | quant/2024年度精选策略2/14.为实盘做的更新：分钟级别和盘中止损.txt |
| 90d2c8d70246 | 1 | etf_macro;intraday;momentum_reversal;quality;size;technical | intraday_data | quant/2024年度精选策略1/83.回测“一创模拟盘2号”，最终优化，年化39%.txt |
| 90d7b9f05e2c | 1 | etf_macro;intraday;momentum_reversal;technical;value | non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/99.量化定投，工薪族逆袭之路(附定投模型）.txt |
| 916631a6442e | 1 | etf_macro;growth;intraday;machine_learning;size;value | model_training;pit_financial_or_valuation | quant/2024年度精选策略1/12.致敬聚宽机器学习多因子50只持仓14年37倍.txt |
| 920f509746f6 | 1 | event_short;intraday;quality;size;turnover | industry_or_concept | quant/量化策略/量化策略/龙头追涨策略2026/01龙头股-最高板策略.txt |
| 9295e6259a64 | 1 | intraday;turnover;volatility | daily_stock_fields | quant/2023年度精选策略/3.苦咖啡-默默赚钱系列-改.txt |
| 92a87b88b709 | 1 | event_short;intraday;quality;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/95 资金流策略.txt |
| 9357cb4bb767 | 1 | intraday;size;technical;volatility | intraday_data | quant/2020年度精选策略/82 次新+小市值+KAMA择时 轮动.txt |
| 93b542b12ccd | 1 | etf_macro;intraday;technical;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2020年度精选策略/01 AdaptiveMA自适应均线 过滤器 期货多品种模型 收益稳定增长.txt |
| 93bcb84b4e82 | 1 | etf_macro;event_short;intraday;size;turnover;value | intraday_data | quant/量化策略/量化策略/实盘2026/Ptrade/pt版01小市值精细风控策略.txt |
| 93f770036e0e | 1 | event_short;intraday;technical;turnover | daily_stock_fields | quant/2023年度精选策略/85.最新解密--追涨龙头打板策略-适合近期实盘行情.txt |
| 952a5ca4a34b | 1 | etf_macro;event_short;growth;intraday;quality;size;technical;value | pit_financial_or_valuation | quant/2022年度精选策略/29.价值投资优选标的，虽然慢，还是有收益的.txt |
| 953a7b4037a9 | 1 | intraday;technical;turnover | daily_stock_fields | quant/2020年度精选策略/45 布林带策略.txt |
| 961817ad1093 | 1 | etf_macro;event_short;intraday;quality;size;technical;turnover | daily_stock_fields | quant/量化策略/量化策略/龙头追涨策略2026/03-234板介入-优化版v1.0.txt |
| 967bae5e64ff | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;value;volatility | pit_financial_or_valuation | quant/2024年度精选策略2/9.分享几个截止2022年3月仍有效的策略.txt |
| 96874afaab4c | 1 | growth;momentum_reversal;quality;size;turnover;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略2/29.【策略.行业轮动】趋势-拥挤-景气度模型看行业轮动.txt |
| 96c204fee018 | 1 | intraday;momentum_reversal | daily_stock_fields | quant/2023年度精选策略/66.基于动量和反转效应的沪深300成分股策略.txt |
| 97c6aae6a8e4 | 1 | etf_macro;intraday;technical | non_stock_asset | quant/2023年度精选策略/39.低风险高收益的期货策略.txt |
| 97e26f0fc9cd | 1 | etf_macro;volatility | money_flow_or_event;non_stock_asset | quant/2021年度精选策略/62.【复现】北向资金交易能力一定强吗.txt |
| 992104d52a71 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;value | pit_financial_or_valuation | quant/2024年度精选策略1/73.稳健趋势策略，回测小，无未来函数.txt |
| 99db0a648839 | 1 | etf_macro;intraday;momentum_reversal;price_volume;quality;value | industry_or_concept;non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略2/51.行业反转效应（年化32%回撤8%).txt |
| 9a5a5a6bc46e | 1 | etf_macro | non_stock_asset | quant/2024年度精选策略2/36.致敬市场(6) ，指数期货贴水.txt |
| 9aabc6f4f37c | 1 | etf_macro;event_short;intraday;price_volume;turnover;volatility | intraday_data | quant/聚宽2025年精选/99韶华研究之二十，竞价异动.txt |
| 9ac1c7b8c7cd | 1 | event_short;intraday;size;turnover | industry_or_concept;money_flow_or_event | quant/量化策略/量化策略/首板向上趋势策略2026/05龙虎榜首板二板策略-23年1043.txt |
| 9bfdb0100a43 | 1 | intraday;quality;size | industry_or_concept | quant/2022年度精选策略/4.自带仓位控制的股息率策略，超稳.txt |
| 9c47eb6737d1 | 1 | etf_macro;event_short;growth;intraday;quality;size;value | pit_financial_or_valuation | quant/量化策略/量化策略/首板回调买入策略2026/实11-红利涨停轮动策略-25年115.txt |
| 9c813ccbea8c | 1 | event_short;growth;intraday;quality | pit_financial_or_valuation | quant/2023年度精选策略/52.筹码选股.txt |
| 9cdb51b6f2d6 | 1 | etf_macro;intraday;value;volatility | non_stock_asset | quant/2022年度精选策略/38.【期货策略】钢厂利润模型-螺纹钢铁矿石焦炭套利.txt |
| 9d319355eab2 | 1 | etf_macro;event_short;intraday;quality;turnover | daily_stock_fields | quant/量化策略/量化策略/龙头追涨策略2026/04龙头弱转强战法-优化版-25年51.txt |
| 9d51bb608344 | 1 | intraday | industry_or_concept;intraday_data | quant/2024年度精选策略2/52.市场宽度——简洁版.txt |
| 9e6ac3612561 | 1 | growth;intraday;price_volume;quality;size;technical;value;volatility | pit_financial_or_valuation | quant/2020年度精选策略/23 Principle by Jim Slater 祖鲁法则在A股的实现与改进.txt |
| 9e78998c6747 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;turnover | pit_financial_or_valuation | quant/2024年度精选策略1/24.凑波热闹，也来试试多因子线性回归.txt |
| 9ea12e2c611a | 1 | intraday | daily_stock_fields | quant/2020年度精选策略/83 沪深300ETF-1060双均线.txt |
| 9fbc4cde2c97 | 1 | etf_macro;event_short;growth;intraday;quality;size;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/75大市值价值投资优化一波.txt |
| 9ff644057352 | 1 | growth;intraday;momentum_reversal;price_volume;quality;size;technical;turnover;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2022年度精选策略/95.医疗行业多因子模型及单行业多因子测试代码模板.txt |
| a161cf940283 | 1 | event_short;intraday;machine_learning;momentum_reversal;turnover | industry_or_concept;model_training | quant/2024年度精选策略1/69.人工智能早晨十字星模型反转形态预测.txt |
| a1a4fdb6c201 | 1 | etf_macro;event_short;intraday;momentum_reversal;quality;turnover;value;volatility | intraday_data;money_flow_or_event | quant/2024年度精选策略1/90.【复现】凸显度因子.txt |
| a20c38299c1d | 1 | etf_macro;event_short;intraday;price_volume;quality;size;technical;turnover;value;volatility | pit_financial_or_valuation | quant/2022年度精选策略/65.价值选股与RSRS择时 py3版本.txt |
| a22c93c3c06c | 1 | event_short;intraday;quality | daily_stock_fields | quant/量化策略/量化策略/首板回调买入策略2026/06首板低开策略2025年-9.95.txt |
| a427aafb8514 | 1 | etf_macro;event_short;growth;intraday;quality;size;technical;value | pit_financial_or_valuation | quant/2021年度精选策略/54.价值投资策略-大盘择时.txt |
| a45701e740f9 | 1 | etf_macro;event_short;intraday;technical | intraday_data | quant/2021年度精选策略/50.昨日炸板股策略.txt |
| a64852602e56 | 1 | etf_macro;intraday;momentum_reversal;price_volume;volatility | non_stock_asset | quant/聚宽2025年精选/32EPO优化低相关etf组合.txt |
| a6baf9d79d6d | 1 | etf_macro;event_short;intraday;technical;turnover | non_stock_asset | quant/2022年度精选策略/31.再次抛砖.txt |
| a6c5a691e715 | 1 | etf_macro;intraday;momentum_reversal;quality;size;technical;value;volatility | pit_financial_or_valuation | quant/2023年度精选策略/83.韶华研究之一，布林突破+均线金叉，四年五倍.txt |
| a76dca858e2c | 1 | etf_macro;growth;intraday;quality;size;technical;turnover;value | pit_financial_or_valuation | quant/聚宽2025年精选/80基本面01加RSI择时.txt |
| a7b4dcaa36bf | 1 | event_short | money_flow_or_event | quant/2020年度精选策略/73 跟着港资（北向资金）买A股.txt |
| a8da655ab489 | 1 |  | daily_stock_fields | quant/2023年度精选策略/41.大盘拥挤率极速版-180天3秒.txt |
| a912833b9221 | 1 | etf_macro;value | daily_stock_fields | quant/2022年度精选策略/54.指数估值自动报表系统——源代码.txt |
| a9145d70da1a | 1 | etf_macro;growth;intraday;momentum_reversal;quality;technical;turnover;value;volatility | industry_or_concept;non_stock_asset | quant/2021年度精选策略/14.FOF养老成长基金-v2.0.txt |
| aa50e28ab60f | 1 | intraday;momentum_reversal;technical;volatility | daily_stock_fields | quant/2022年度精选策略/61.最简单的动量模型，能否应对A股暴涨？(二).txt |
| aa6b13ceee05 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;turnover;volatility | pit_financial_or_valuation | quant/2024年度精选策略1/1.差不多得了.txt |
| aa909b58b2a7 | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;volatility | non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/79国九条-新的红利因子，修正「审计意见」函数.txt |
| aab638e971cb | 1 | etf_macro;event_short;growth;intraday;quality;value | intraday_data;non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略1/60.【深度解析 二】资产负债与ROA模型.txt |
| ab815eefc0ee | 1 | intraday;price_volume;quality;size;technical;volatility | daily_stock_fields | quant/2023年度精选策略/57.韶华研究之四-菲阿里四阶在T+1的短线策略应用.txt |
| aba343dd2484 | 1 | event_short;intraday;price_volume;quality;size;technical;turnover;value | daily_stock_fields | quant/量化策略/量化策略/首板向上趋势策略2026/01-涨停板接力策略-25年166-24年260-23年24-22年672.txt |
| abb0cf65baef | 1 | etf_macro;intraday;machine_learning;momentum_reversal;price_volume;turnover;volatility | industry_or_concept;model_training;non_stock_asset | quant/2024年度精选策略1/51.【复现】行业有效量价因子与行业轮动策略.txt |
| abe1c30d15f2 | 1 | event_short;growth;intraday;quality;technical;volatility | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/59.可能是最接近实盘的“基本面三角.txt |
| accd5b89a056 | 1 | etf_macro;intraday;technical;turnover;volatility | daily_stock_fields | quant/2022年度精选策略/85.年化20%+的极简指数增强，受RSRS和LLT启发.txt |
| ace63c85edf8 | 1 | event_short;growth;intraday;momentum_reversal;price_volume;quality;size;turnover;value;volatility | pit_financial_or_valuation | quant/2024年度精选策略1/78.国盛证券多因子.txt |
| acf9fec73f77 | 1 | event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略1/22.菜场大妈皇城大妈年化108大妈吉祥.txt |
| ade124753afc | 1 | event_short;intraday;price_volume;size;turnover | daily_stock_fields | quant/2024年度精选策略2/35.自适应量化终极算法2.0 （全新升级).txt |
| ae027d0b6898 | 1 | etf_macro;intraday;technical;turnover;value;volatility | daily_stock_fields | quant/2022年度精选策略/46.指数择时与仓位管理策略初探.txt |
| ae5faf3e2def | 1 | etf_macro;intraday;size;turnover;value;volatility | pit_financial_or_valuation | quant/2022年度精选策略/58.100%胜率！历史PE估值价值投资择时交易.txt |
| ae83a42862ae | 1 | etf_macro;event_short;intraday;quality;size;technical;turnover;volatility | intraday_data | quant/2024年度精选策略2/26.近几年一直有效的股票BOLL择时策略.txt |
| ae97706546af | 1 | etf_macro;event_short;intraday;momentum_reversal;size;turnover | intraday_data;non_stock_asset | quant/2024年度精选策略1/74.形态识别_单边上涨v3.txt |
| aeebb74aa130 | 1 | etf_macro;intraday;size;technical;turnover;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2021年度精选策略/53.基于大盘PE标准差偏离度的聪明基金定投策略.txt |
| af2622f22e31 | 1 | etf_macro;intraday;size;value | daily_stock_fields | quant/量化策略/量化策略/小市值策略2026/03小市值轮动阈值调仓-25年收益97.51.txt |
| af52c00fde2a | 1 | etf_macro;intraday;momentum_reversal;price_volume;technical;turnover;value;volatility | intraday_data;non_stock_asset | quant/2024年度精选策略1/99.波动率交易的前言——期权定价.txt |
| afd35f8b6013 | 1 | intraday;volatility | daily_stock_fields | quant/2021年度精选策略/34.套利三年，我的本金翻了10倍.txt |
| b05da530b6d7 | 1 | intraday;size;turnover | industry_or_concept | quant/2021年度精选策略/37.处置效应的CGO因子（行为金融学因子）.txt |
| b1c019d1c5b7 | 1 | etf_macro;event_short;intraday;quality;technical;turnover;volatility | industry_or_concept;intraday_data | quant/2021年度精选策略/99.最新龙回头5.0速度优化版+风险控制版本.txt |
| b1dd024ad7ea | 1 | event_short;growth;intraday;quality;size;turnover;volatility | pit_financial_or_valuation | quant/2024年度精选策略2/56.一创PEG+EBIT+turnover_volatility.txt |
| b23fe7f6e2a9 | 1 | event_short;intraday;machine_learning;technical;turnover;volatility | intraday_data;model_training | quant/2024年度精选策略2/34.【回撤二波2.0】透过一次过拟合的机器学习摸底策略的收益上限.txt |
| b240814ec858 | 1 | size;value | daily_stock_fields | quant/2022年度精选策略/100.实战型小盘价值策略--14年30倍.txt |
| b2ea96e905f0 | 1 | event_short;intraday;size;technical;turnover;volatility | daily_stock_fields | quant/量化策略/量化策略/龙头追涨策略2026/02涨停板多头策略-优化版v1.0.txt |
| b39a63c5a73a | 1 | etf_macro;event_short;growth;intraday;quality;size;technical;turnover;value;volatility | pit_financial_or_valuation | quant/2024年度精选策略2/6.PEG+成长+小市值+RSRS择时.txt |
| b4e70316c68a | 1 | etf_macro;intraday;momentum_reversal;technical;volatility | non_stock_asset | quant/2021年度精选策略/88.基于动量因子的ETF轮动加上RSRS择时.txt |
| b51ed2f58e3d | 1 | etf_macro;intraday;size;technical | daily_stock_fields | quant/2022年度精选策略/70.年化64%的市值选股策略（有止损模块）.txt |
| b5264f2e3574 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;technical;value | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略2/53.超跌网格交易大法V1.2：稳健跑赢大盘-年化13%回撤7%.txt |
| b57850e76706 | 1 | etf_macro;event_short;growth;intraday;machine_learning;momentum_reversal;quality;size;turnover;volatility | model_training;pit_financial_or_valuation | quant/聚宽2025年精选/19机器学习线性回归小市值.txt |
| b5f030d57b76 | 1 | growth;intraday;machine_learning;quality;size;value | industry_or_concept;intraday_data;model_training | quant/聚宽2025年精选/49干货贴《机器学习5折保形回归》 .py |
| b60e7276fb00 | 1 | intraday;quality;size;value | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/77.超强单因子策略（EBIT,EV）.txt |
| b65b10ae1e60 | 1 | event_short;growth;intraday;size;turnover | daily_stock_fields | quant/2024年度精选策略1/2.“7年40倍”策略扩容到50只.txt |
| b6a219d98294 | 1 | event_short;intraday;technical;turnover | daily_stock_fields | quant/2024年度精选策略2/80.短线策略-2022年两个半月收益45%-无未来函数.txt |
| b776a89c4d01 | 1 | etf_macro;intraday;momentum_reversal;technical;turnover;volatility | daily_stock_fields | quant/2021年度精选策略/60.【分享】对RSRS模型的一次修改.txt |
| b7faa744d8ef | 1 | etf_macro;intraday | daily_stock_fields | quant/2023年度精选策略/81.拥挤率指标-择时大盘顶底-Clone1-第二版.txt |
| b8aeb3938fea | 1 | etf_macro;intraday | industry_or_concept;non_stock_asset | quant/2022年度精选策略/32.行业指数轮动.txt |
| b8d66aa8487b | 1 | intraday;momentum_reversal;value | daily_stock_fields | quant/2024年度精选策略1/72.桥水 全天候策略 增加一致性度量ES 风险控制.txt |
| b99184cec53b | 1 | growth;intraday;size;technical | daily_stock_fields | quant/2021年度精选策略/41.均线黏合，突破前三十个交易日最高点选股法.txt |
| ba0ad77f58c8 | 1 | etf_macro;intraday;technical;volatility | money_flow_or_event;non_stock_asset | quant/2021年度精选策略/32.北向资金A股择时策略（5年16倍）.txt |
| bac46f0e9fee | 1 | etf_macro;intraday;technical;volatility | daily_stock_fields | quant/2020年度精选策略/15 基于多期限的选股策略（一）.txt |
| bb1eb82a9bad | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;value | intraday_data;pit_financial_or_valuation | quant/2024年度精选策略1/26.【深度解析 六】高股息率-低PEG-低股价 模型.txt |
| bb83b1ab8308 | 1 | etf_macro;growth;intraday;momentum_reversal | non_stock_asset | quant/2023年度精选策略/68.宽基BBI动量追涨，完美避开这波大跌~.txt |
| bb92871776c5 | 1 | event_short;intraday;size;turnover;value | pit_financial_or_valuation | quant/2024年度精选策略2/81.低PB小市值低换手策略总结.txt |
| bb92ed4d236b | 1 | growth;intraday;quality | pit_financial_or_valuation | quant/2023年度精选策略/28.F_Score 选股，年化80%+.txt |
| bbcc63caa19b | 1 | etf_macro;intraday | non_stock_asset | quant/2022年度精选策略/49.LLT低延迟趋势线择时交易初探.txt |
| bc7e6a3d7daa | 1 | event_short;intraday;turnover | intraday_data | quant/2023年度精选策略/13.胜率65%之缩量分歧反包战法.txt |
| bcde7d157dab | 1 | intraday;size;technical;turnover | intraday_data | quant/量化策略/量化策略/实盘2026/Ptrade/pt版02小市值技术过滤策略.txt |
| bdca43811e2d | 1 | etf_macro;intraday;momentum_reversal;technical | intraday_data;non_stock_asset | quant/聚宽2025年精选/81搞市场最靓的仔！指数ETF动量轮动策略-2.txt |
| bee4d03c1dba | 1 | intraday;quality;size;technical;turnover;value;volatility | pit_financial_or_valuation | quant/2023年度精选策略/97.韶华研究之六，简单不一样的发现趋势，3年6倍.txt |
| bff06dec26a9 | 1 | etf_macro;intraday;momentum_reversal;technical;turnover | non_stock_asset | quant/2024年度精选策略2/16.ETF轮动策略升级-多类别-低回撤.txt |
| c029a7ca7d95 | 1 | intraday;turnover | intraday_data | quant/2022年度精选策略/56.胜率为100%，盈亏比90000+的单品种倍投策略.txt |
| c0bf009fb487 | 1 | etf_macro;intraday;momentum_reversal;turnover | intraday_data | quant/2021年度精选策略/94.小资金短线策略.txt |
| c0f6d727273a | 1 | event_short;intraday;size;technical;volatility | daily_stock_fields | quant/2023年度精选策略/93.布林线追龙头战法.txt |
| c1acd2b8b4ac | 1 | intraday;technical;turnover;volatility | intraday_data | quant/2021年度精选策略/96.分享一个简单的选股器.txt |
| c24face8bebd | 1 | event_short;intraday;size;turnover | intraday_data | quant/2023年度精选策略/51.龙头战法之单阳不破.txt |
| c2670b89bccc | 1 | intraday;size;technical;turnover;value | daily_stock_fields | quant/2022年度精选策略/44.简单有效的次新投机策略，年化200%+.txt |
| c2cd4f66204e | 1 | etf_macro;intraday;momentum_reversal;price_volume | intraday_data | quant/2022年度精选策略/96.宏观择时多空组合——十年收益12倍，最大回撤6.7%.txt |
| c31441458b78 | 1 | etf_macro;event_short;intraday;quality;size;technical;volatility | industry_or_concept;non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/69.RSRS择时加基本面选股策略优化.txt |
| c369768b45ff | 1 | etf_macro;intraday;momentum_reversal;price_volume;size;turnover;value;volatility | daily_stock_fields | quant/2024年度精选策略1/81.方正证券-多因子选股系列研究之四：“球队硬币”.txt |
| c3854104d444 | 1 | intraday | daily_stock_fields | quant/2024年度精选策略1/25.低价股优化，18年至今10625.40%，已加防未来函数.txt |
| c4225656cc73 | 1 | etf_macro;intraday;size | daily_stock_fields | quant/2022年度精选策略/71.年化42%的市值选股与阶梯调仓策略.txt |
| c53e6e683926 | 1 | event_short;growth;intraday;quality;size;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/聚宽2025年精选/92行业宽度轮动研究.txt |
| c53fb1dfad12 | 1 | growth;intraday;quality;size;value | pit_financial_or_valuation | quant/2020年度精选策略/92 多因子选股策略.txt |
| c695cf1ad982 | 1 | etf_macro;intraday;momentum_reversal;price_volume;size;technical;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2024年度精选策略1/100.全市场归因.txt |
| c93880c77296 | 1 |  | daily_stock_fields | quant/2020年度精选策略/21 果核量化出品 -- BIAS_QL乖离率策略指数择时1.0.txt |
| c990b2434004 | 1 | etf_macro;intraday;machine_learning;turnover | model_training;non_stock_asset | quant/聚宽2025年精选/61BiLSTM for ETF.txt |
| c9e58b7abfb9 | 1 | etf_macro;event_short;intraday;size;turnover | daily_stock_fields | quant/2024年度精选策略1/37.【择时模块实际效果】--论坛随便选了个策略加装.txt |
| ca306adac541 | 1 |  | daily_stock_fields | quant/2024年度精选策略2/92.利用myTT库整合通达信公式——以“飞鹰优选”选股公式为例.txt |
| ca517cbb2bfe | 1 | etf_macro;intraday;price_volume;technical;volatility | industry_or_concept | quant/2024年度精选策略1/88.韶华研究之十六，指数增强.txt |
| ca72ca5bd0f9 | 1 | event_short;growth;intraday;quality;size;turnover;volatility | daily_stock_fields | quant/2024年度精选策略1/17.5年超额收益1055%，K线处理大阴线，无未来.txt |
| caace71e536b | 1 | etf_macro;machine_learning;price_volume;turnover;volatility | model_training;non_stock_asset | quant/聚宽2025年精选/86手把手教你构建ETF策略候选池优化版.txt |
| caad5b706960 | 1 | event_short;intraday;quality;size;technical;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/74 基于沪深300的增强.txt |
| cab6b9c55459 | 1 | etf_macro;event_short;growth;intraday;momentum_reversal;quality;size;turnover;value;volatility | intraday_data;non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/65搭建量化交易模型从零开始——择时，选股，仓位管理和因子分析.txt |
| caf35f40cf4b | 1 | intraday;momentum_reversal;turnover | intraday_data | quant/2022年度精选策略/9.高频Tick频率策略分享.txt |
| cb524ddddba7 | 1 | etf_macro;intraday;momentum_reversal;technical;volatility | intraday_data;non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/03指数ETF动量轮动策略-25年27.txt |
| cbad05f5e623 | 1 | etf_macro;growth;intraday;quality;size;technical;turnover;value;volatility | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/97.稳定高回报周期股策略2-RSRS择时.txt |
| cbec9eade1e1 | 1 | etf_macro;intraday;turnover | non_stock_asset | quant/2021年度精选策略/22.“开弓”ETF轮动模型——改.txt |
| cbf511d54bb0 | 1 |  | daily_stock_fields | quant/2024年度精选策略2/100.【复现】金股组合增强—分析师推荐概率.txt |
| ccdb28366545 | 1 | etf_macro;intraday;technical | daily_stock_fields | quant/2020年度精选策略/46 Get API 新技能，研究中写策略并回测.txt |
| cd447e804db9 | 1 | etf_macro;event_short;intraday;size | money_flow_or_event | quant/2021年度精选策略/29.北上资金（北向资金港资外资）因子分析与策略分享.txt |
| cd8b4ec2f6d8 | 1 | event_short;intraday;technical;turnover | intraday_data | quant/2024年度精选策略2/37.三阳三阴战法.txt |
| ce022ba32d12 | 1 | etf_macro;size;volatility | non_stock_asset | quant/2023年度精选策略/53.利用聚宽的数据库，研究基金.txt |
| ce0c2d54c9cc | 1 | etf_macro;event_short;growth;intraday;quality;size;technical;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略2/27.中证500指增+CTA，胜率52%盈亏比1.9。不输顶尖私募.txt |
| ce346ec91797 | 1 | etf_macro;growth;intraday;machine_learning;quality;size;technical;value;volatility | industry_or_concept;intraday_data;model_training;pit_financial_or_valuation | quant/2021年度精选策略/78.机器学习模型大比拼!.txt |
| cedd551e83ea | 1 | etf_macro;intraday;momentum_reversal;size;technical;volatility | non_stock_asset | quant/2024年度精选策略2/24.宽基ETF动量轮动钝化RSRS择时-回撤小.txt |
| cff51c48cc76 | 1 | size | daily_stock_fields | quant/2021年度精选策略/4.红利搬砖，年化29%.txt |
| d013cb7a871b | 1 | etf_macro;growth;intraday;momentum_reversal;price_volume;technical;turnover;value;volatility | intraday_data;model_training;non_stock_asset;pit_financial_or_valuation | quant/2024年度精选策略1/91.【复现】多任务时序动量策略.txt |
| d025cf87f4b2 | 1 | intraday | intraday_data | quant/2020年度精选策略/66 高于MA10买入低于MA20卖出回测半年收益率20.4%.txt |
| d13127e51c9b | 1 | intraday;size | non_stock_asset | quant/2021年度精选策略/80.公募基金抱团.txt |
| d30fa05763cc | 1 | event_short;growth;intraday;momentum_reversal;price_volume;turnover;volatility | intraday_data | quant/2024年度精选策略1/75.【复现】个股动量效应的识别及球队硬币因子.txt |
| d33ce781af50 | 1 | event_short;intraday;size;technical;turnover | industry_or_concept;pit_financial_or_valuation | quant/2021年度精选策略/46.大盘股也能穿越牛熊市.txt |
| d36cbf116aa4 | 1 | growth;intraday;machine_learning;price_volume;quality;size;technical;value;volatility | industry_or_concept;intraday_data;model_training;pit_financial_or_valuation | quant/2022年度精选策略/47.基于随机森林和XGBoost的多因子模型分析.txt |
| d3a65735fe2b | 1 | event_short;intraday;machine_learning;price_volume | model_training | quant/2024年度精选策略1/47.随机森林量价多因子选股 短线交易.txt |
| d42c2004239c | 1 | etf_macro;intraday;technical | non_stock_asset | quant/2022年度精选策略/33.ETF单均线跟踪轮动.txt |
| d436ae39f6e2 | 1 | event_short;intraday;quality;size;turnover | daily_stock_fields | quant/聚宽2025年精选/25冷饭热吃之三，14年至今年华99.99.txt |
| d5c411e91cec | 1 | event_short;growth;intraday;size;value | pit_financial_or_valuation | quant/聚宽2025年精选/77研报三因子II-新规高分红小市值-年化60回撤19.txt |
| d5f6d36120a5 | 1 | intraday;technical | money_flow_or_event | quant/2023年度精选策略/74.勾股神器2代码40行，年化一百点.txt |
| d65ac679a50e | 1 | etf_macro;event_short;intraday;size;turnover | non_stock_asset | quant/聚宽2025年精选/76小市值止损策略【年化104.11】.txt |
| d73552312276 | 1 | event_short;intraday | money_flow_or_event | quant/2021年度精选策略/51.北上资金持股比选股策略（北向、港资、外资）.txt |
| d73853083551 | 1 | etf_macro;intraday | daily_stock_fields | quant/2020年度精选策略/78 GFTD第二版.txt |
| d77f6f11ae91 | 1 | etf_macro;growth;intraday;value | intraday_data;pit_financial_or_valuation | quant/2024年度精选策略2/90.大师策略——柯林·麦克连成长价值优势投资法.txt |
| d84cf269a0df | 1 | etf_macro;intraday;momentum_reversal;price_volume;technical;turnover;volatility | intraday_data;non_stock_asset | quant/量化策略/量化策略/实盘2026/Ptrade/pt版07ETF动量加EPO平衡策略.txt |
| d8668abad526 | 1 | intraday;size | daily_stock_fields | quant/2023年度精选策略/35.最简强者恒强策略.txt |
| d868cf708504 | 1 | etf_macro;event_short;intraday;technical;turnover;value;volatility | intraday_data;non_stock_asset | quant/2024年度精选策略2/63.生猪期货CTA策略.txt |
| d88c93b9368e | 1 | growth;intraday;momentum_reversal;quality;size;technical;value | industry_or_concept;pit_financial_or_valuation | quant/2022年度精选策略/81.有脑子，会调整权重的动态多因子模型.txt |
| d98528b54c31 | 1 | etf_macro;event_short;intraday;size;turnover;value | intraday_data | quant/2024年度精选策略1/80.【深度解析 一】经典小市值模型.txt |
| d9888dc29e13 | 1 | etf_macro;growth;intraday;price_volume;quality;size;technical;turnover;value;volatility | industry_or_concept;non_stock_asset;pit_financial_or_valuation | quant/2021年度精选策略/31.RSRS择时+货币基金--6年8倍行业周期股策略.txt |
| da0fe7740786 | 1 | event_short;intraday;price_volume;size;turnover | industry_or_concept;intraday_data | quant/量化策略/量化策略/龙头追涨策略2026/05昨日涨停今日追高策略-23年191-24年69-25年负-24.txt |
| da52cfe36b5d | 1 | event_short;intraday;size;turnover | industry_or_concept | quant/聚宽2025年精选/40高股息策略.txt |
| db44806d62a8 | 1 | etf_macro;growth;intraday;quality;size;technical;value;volatility | non_stock_asset;pit_financial_or_valuation | quant/2021年度精选策略/9.持续跑赢大盘-真蓝筹v2(资金容量千万以上).txt |
| db620f63ed22 | 1 | etf_macro;intraday;technical | daily_stock_fields | quant/2022年度精选策略/68.RSRS模型深入研究3-二八轮动策略及其探究分析.txt |
| db9c9e1541a1 | 1 | etf_macro;intraday;machine_learning;technical;volatility | intraday_data;model_training | quant/2024年度精选策略1/96.大盘预测器v1.1--引入世界数据.txt |
| dc186ebf560e | 1 | etf_macro;event_short;intraday;momentum_reversal;price_volume;size;technical;turnover;value;volatility | industry_or_concept | quant/2022年度精选策略/37.Barra模型初探，A股市场风格解析.txt |
| dcbb75c56e7e | 1 | etf_macro;intraday;technical;volatility | money_flow_or_event | quant/2023年度精选策略/58.北向RSRS与布林带择时.txt |
| dd04e1248ba7 | 1 | event_short;intraday;quality;size;turnover | daily_stock_fields | quant/聚宽2025年精选/60高股息V1.0（小程序公开股池）.txt |
| de13a85b2dd1 | 1 | intraday;technical | daily_stock_fields | quant/2020年度精选策略/42 低估值+TRIX+RSI 低回撤策略.txt |
| de32ec5b28f2 | 1 | intraday;momentum_reversal;quality;technical;turnover;volatility | intraday_data | quant/量化策略/量化策略/首板回调买入策略2026/02上升途中回调到位-优化版-25年42.txt |
| dede98a916cb | 1 | etf_macro;growth;intraday;quality;size;technical;turnover | pit_financial_or_valuation | quant/2021年度精选策略/42.市值，研发支出，roe，三因子，跑赢大盘.txt |
| df540dd4c67f | 1 | etf_macro;intraday;technical | daily_stock_fields | quant/2021年度精选策略/69.（12.3更新v1.2）朱虽自用1号（神虽顶底+趋势）.txt |
| dfbb092d36f1 | 1 | etf_macro;event_short;intraday;momentum_reversal;quality;size;technical;turnover;value;volatility | money_flow_or_event;non_stock_asset | quant/2024年度精选策略2/75.ETF轮动策略-入门2.0.txt |
| e0633a25c013 | 1 | etf_macro | non_stock_asset | quant/2021年度精选策略/43.ETF资源收集整合（附代码与excel表格）.txt |
| e0c79a2ddefa | 1 | etf_macro;intraday;value | non_stock_asset;pit_financial_or_valuation | quant/2020年度精选策略/65 8只基金按PE调仓.txt |
| e18ed9a000ea | 1 | etf_macro;event_short;intraday;technical;turnover | non_stock_asset | quant/2024年度精选策略2/61.简单ETF策略，年化97%.txt |
| e23bf9f1f9fb | 1 | intraday;size;technical;volatility | non_stock_asset | quant/2023年度精选策略/30.跟着基金报团！！！174% 回撤 7.33%.txt |
| e37af804bda9 | 1 | etf_macro;event_short;intraday;momentum_reversal;size;turnover;value | non_stock_asset | quant/2023年度精选策略/27.从相关系数角度探讨etf轮动的可行性.txt |
| e3b5c1342b73 | 1 | etf_macro;intraday;machine_learning;price_volume;technical;turnover;volatility | intraday_data;model_training;non_stock_asset | quant/2022年度精选策略/26.Xgboost 50ETF 2.0 分钟级回测.txt |
| e53792646e60 | 1 | etf_macro;event_short;intraday;technical;turnover;volatility | daily_stock_fields | quant/2024年度精选策略2/46.韶华研究之十二--还算可以的竞价研究.txt |
| e53da9ef07f3 | 1 | event_short;growth;size | daily_stock_fields | quant/2024年度精选策略1/9.持仓95只大容量小市值，媲美金元顺安元启.txt |
| e54465145569 | 1 | event_short;intraday;momentum_reversal;quality;size;technical;turnover | intraday_data | quant/量化策略/量化策略/首板回调买入策略2026/09涨停回调止盈止损-25年30.62.txt |
| e60e144fd05e | 1 | etf_macro;growth;intraday;momentum_reversal;price_volume;technical;value;volatility | non_stock_asset | quant/2024年度精选策略1/52.增强型投资组合优化（EPO）方法试用.txt |
| e6c0a5eff21d | 1 | etf_macro;growth;intraday;quality;size | daily_stock_fields | quant/2022年度精选策略/13.利用股息率长线选股【超稳】.txt |
| e7062592a877 | 1 | intraday;technical;volatility | daily_stock_fields | quant/2021年度精选策略/27.基于RSRS的趋势交易与网格交易相结合的尝试.txt |
| e8dc64d297a1 | 1 | etf_macro;growth;intraday;machine_learning;momentum_reversal;price_volume;quality;size;technical;turnover;value | model_training;pit_financial_or_valuation | quant/聚宽2025年精选/70动态保形回归小市值策略改进.txt |
| e94ccf623fd8 | 1 | intraday;momentum_reversal | intraday_data | quant/2020年度精选策略/79 DMI——大盘择时.txt |
| e9e587d57552 | 1 | etf_macro;growth;intraday;machine_learning;momentum_reversal;price_volume;quality;size;technical;turnover;value | intraday_data;model_training;pit_financial_or_valuation | quant/2024年度精选策略1/92.【机器学习研究】动态多因子选股策略研究.txt |
| ea5b0e41d1e6 | 1 | etf_macro;technical | daily_stock_fields | quant/2020年度精选策略/89 test1：简单的多均线择时.txt |
| ec06e7999338 | 1 | growth;intraday;size | intraday_data;pit_financial_or_valuation | quant/2023年度精选策略/98.欧奈尔CANSLIM策略初探三.txt |
| ec15f1c68c7f | 1 | event_short;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/聚宽2025年精选/18国庆节献礼：实例说明白马股攻防转换策略.txt |
| ec1ea74570c7 | 1 | event_short;intraday;size;turnover | industry_or_concept;pit_financial_or_valuation | quant/2020年度精选策略/08 MACD单因子多头策略.txt |
| ed22f132366a | 1 | etf_macro;intraday;momentum_reversal;technical;turnover | non_stock_asset | quant/2021年度精选策略/25.基本不耍六毛的ETF轮动策略.txt |
| ed3d610beb0a | 1 |  | daily_stock_fields | quant/2024年度精选策略2/99.计算每日全A市场个股创新高比例(改).txt |
| eda733af3ccd | 1 | etf_macro;growth;intraday;price_volume;quality;size;turnover;value;volatility | intraday_data;non_stock_asset;pit_financial_or_valuation | quant/2022年度精选策略/17.多因子系列-多因子模型体系之因子组合的确定.txt |
| efaf0a5d6bbe | 1 | etf_macro;intraday;turnover | daily_stock_fields | quant/2023年度精选策略/33.趋势交易5.0 无择时-2年5倍不是梦.txt |
| f08f55ce6fc8 | 1 | etf_macro;event_short;intraday;size;turnover;value | daily_stock_fields | quant/2024年度精选策略2/54.sales_growth今年最优版.txt |
| f0a2c1fd0dfe | 1 | event_short;intraday;momentum_reversal;technical;turnover;volatility | daily_stock_fields | quant/量化策略/量化策略/首板回调买入策略2026/08上升趋势-回档买入-25年0.78.txt |
| f0b7ef4ac79e | 1 | intraday;machine_learning;momentum_reversal;size | industry_or_concept;model_training | quant/2024年度精选策略1/61.聚类算法分析股票，看看今年大体能分出哪几类.txt |
| f0c91dd76d96 | 1 | event_short;intraday;quality;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/32.最适合上班族的策略-神奇公式策略.txt |
| f193084ffef5 | 1 | size | non_stock_asset | quant/2024年度精选策略1/95.基金的最爱与最恶.txt |
| f19b6b6d3d39 | 1 | etf_macro;event_short;intraday;quality;size;turnover | daily_stock_fields | quant/聚宽2025年精选/34十年回测 年化103.32% 最大回撤23.89%.txt |
| f1b2e3e08246 | 1 | intraday;technical;turnover | daily_stock_fields | quant/2024年度精选策略2/8.14个月200%，超短线实盘交易策略！无未来函数.txt |
| f24cc4708d3d | 1 | intraday;momentum_reversal;quality;technical;turnover;value | industry_or_concept;money_flow_or_event | quant/2024年度精选策略1/77.【复现】筹码分布因子.txt |
| f26b72bcfb2b | 1 | event_short;intraday;turnover | intraday_data | quant/2024年度精选策略2/33.胜率88.9%之君正集团策略-大阳分歧反包.txt |
| f373a4d4c7a8 | 1 | etf_macro;intraday;momentum_reversal;quality;value;volatility | industry_or_concept;non_stock_asset | quant/2024年度精选策略1/89.【复现·水】市场情绪指标专题行业指数顶部和底部信号.txt |
| f39fc096d802 | 1 | event_short;intraday;quality;turnover;value | pit_financial_or_valuation | quant/2023年度精选策略/24.ROE+PB模型的优化.txt |
| f41cbff20670 | 1 | event_short;growth;intraday;machine_learning;quality;size;technical;turnover;value;volatility | industry_or_concept;model_training;pit_financial_or_valuation | quant/聚宽2025年精选/33回馈社区顺便搞积分《一个完整的机器学习pipeline》.txt |
| f431d8a35d3c | 1 | etf_macro;intraday;size;technical;turnover | non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/02稳健型ETF策略-调优版-25年27.txt |
| f4cee01d1ebc | 1 | intraday;technical;turnover | daily_stock_fields | quant/2020年度精选策略/86 5日线穿十日线策略（供初学）.txt |
| f4e32aa2bf44 | 1 | event_short;intraday | daily_stock_fields | quant/2024年度精选策略2/87.北上净买入策略.txt |
| f5ada7086a2b | 1 | etf_macro;event_short;intraday;technical;turnover | intraday_data;non_stock_asset | quant/2024年度精选策略2/71.期货日内策略三价均线结合ATR指标.txt |
| f61cb18c446d | 1 | etf_macro;intraday;size;technical;turnover | daily_stock_fields | quant/2022年度精选策略/83.穿越十年牛熊：沪深300成分股配合macd的价投择时策略.txt |
| f65078d171e6 | 1 | event_short;size | daily_stock_fields | quant/2022年度精选策略/3.次新无止损-暂时最优策略.txt |
| f6812a890469 | 1 | growth;intraday;size;technical;value | intraday_data | quant/2022年度精选策略/12.回馈社区，分享市盈率股息率选股+均线止盈交易策略.txt |
| f6f79845b0a6 | 1 | intraday;momentum_reversal;size;volatility | industry_or_concept;intraday_data | quant/2022年度精选策略/16.选股因子系列研究(十八) — 价格形态选股因子.txt |
| f7fa4b8d1610 | 1 | intraday;momentum_reversal;turnover | money_flow_or_event;non_stock_asset | quant/2023年度精选策略/20.北向资金股票轮动-优质策略可直接实盘.txt |
| f8076980ef42 | 1 | etf_macro;growth;machine_learning;size | industry_or_concept;model_training | quant/2020年度精选策略/43 无模型评估的多因子模型.txt |
| f9a11442f5f5 | 1 | etf_macro;intraday;size | daily_stock_fields | quant/量化策略/量化策略/小市值策略2026/实01小市值精细风控-25年收益117.98.txt |
| faa23c63197f | 1 | etf_macro;momentum_reversal;price_volume;turnover;volatility | non_stock_asset | quant/聚宽2025年精选/66手把手教你构建ETF策略候选池.py |
| fb0d1f53213c | 1 | etf_macro;growth;intraday;momentum_reversal;price_volume;quality;technical;turnover | non_stock_asset | quant/量化策略/量化策略/ETF轮动策略2026/01趋势筛选后相关性最小etf轮动-调优版-25年62.txt |
| fb60d517f8fc | 1 | growth;technical;value;volatility | model_training;non_stock_asset | quant/2024年度精选策略1/57.【复现】技术分析算法、框架与实战之二：识别“圆弧底”.txt |
| fc03d9082d8a | 1 | etf_macro;event_short;growth;intraday;machine_learning;size;technical;turnover;value;volatility | intraday_data;model_training;pit_financial_or_valuation | quant/2020年度精选策略/51 HS300--随机森林拐点识别.txt |
| fc3b06ad74d6 | 1 | intraday;momentum_reversal;volatility | daily_stock_fields | quant/2024年度精选策略2/67.三因子策略年化21%简单多因子策略框架.txt |
| fc45902feee1 | 1 | intraday;momentum_reversal;technical;volatility | daily_stock_fields | quant/2020年度精选策略/18 均值回归策略分享.txt |
| fd716d904d33 | 1 | growth;intraday;quality;size;turnover;value | industry_or_concept;intraday_data;pit_financial_or_valuation | quant/2022年度精选策略/94.量化排雷—一个实用排雷系统.txt |
| fd908c72ac80 | 1 | etf_macro;intraday;turnover | intraday_data;non_stock_asset | quant/2024年度精选策略2/57.别人恐惧我贪婪3——年化20%的股债组合.txt |
| fe11160bf640 | 1 | etf_macro;growth;intraday;quality;turnover;value | industry_or_concept;pit_financial_or_valuation | quant/2023年度精选策略/18.【复现】FFScore财务模型.txt |
| fe459c229d64 | 1 | event_short;growth;intraday;quality;size;value | pit_financial_or_valuation | quant/2024年度精选策略2/95.首席质量因子-Gross Profitabilit（简化版）.txt |
| fe5fdcefd302 | 1 | etf_macro;event_short;growth;intraday;machine_learning;momentum_reversal;quality;size;technical;turnover;value;volatility | model_training;non_stock_asset;pit_financial_or_valuation | quant/聚宽2025年精选/12用子账户模拟多策略分仓.txt |
| ff4bf50ab142 | 1 | intraday;turnover | non_stock_asset | quant/2023年度精选策略/77.【基金增强思考2.0】优秀基金的持续性与周期的关系密不可分.txt |
| ff99a41db6ed | 1 | intraday;momentum_reversal;size;volatility | daily_stock_fields | quant/2020年度精选策略/68 板块轮动不动？.txt |
| ffb95f5f0f80 | 1 | etf_macro;event_short;growth;intraday;quality;size;turnover;value | pit_financial_or_valuation | quant/2023年度精选策略/36.PEG+EBIT对小市值因子的优化.txt |
| ffbbf391d788 | 1 | etf_macro;growth;intraday;turnover | intraday_data | quant/2022年度精选策略/30.优质股高抛低吸策略.txt |
