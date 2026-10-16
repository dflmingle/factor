# star_coin_prediction：复刻档案

继续搜索，未达到参照标准

综合积分名次 8，周期 5 日，历史与现役合计 10 个因子版本。

## 候选公式

|因子|方向|候选|
|---|---|---|
|b2-N5-M03|negative|`(-LOG(MAX(ABS((RANK((-MARKET_CAP))+MEAN(RANK((-CLOSE)),RATIO_CFP_TTM))),1e-12)))`|
|N2-V01|negative|`RANK(STDDEV(((CLOSE/OPEN)--1),22))`|
|b2-N5-M04|negative|`EMA(ZSCORE((-(RANK((-SMA(VOLUME,1,1)))+RANK((-LOW))))),3)`|
|N2-L01|negative|`TS_MEAN(TURNOVER,20)`|
|N2F-B02|positive|`((0.975*ZSCORE(BOOK_TO_MARKET_RATIO_LF))+(0.025*ZSCORE(RANK(BOOK_TO_MARKET_RATIO_LF))))`|
|b2-N5-M01|negative|`MARKET_CAP`|
|N2F-S01|negative|`MARKET_CAP`|
|N2-X01|negative|`(CLOSE/TS_MEAN(OPEN,10))`|
|b2-N5-M02|negative|`TS_MEAN((MARKET_CAP-RANK((RANK((-(-TS_MEAN(TS_MEAN(RATIO_EP_TTM,1),20))))-(-TS_MEAN(TS_MEAN((2/TS_KURT(RATIO_SP_TTM,20)),1),18))))),20)`|
|N2F-B01|positive|`RATIO_EP_TTM`|

## 各榜误差

|榜单|本地代理|对手|相对绝对差|
|---|---:|---:|---:|
|quality|0.338585673|0.3378528144113196|0.2169%|
|rex|9.679042381|8.574618563054765|12.8802%|
|robust|3.616604023|2.9083206887994635|24.3537%|
|points|43874.824171361|48305.45006206933|9.1721%|

所有公开日期已参与回顾性搜索；财务字段和平台内部执行是代理。五年A按每条腿独立计算，公开端点日期角色按收益结束日推算，尚未确认。近期指标与五年A分别保存。当前未创建平台因子或运行付费回测。

逐期误差、持仓、月度账本和未通过项见 verified_best.json。
