# LEGMIX7 复合候选审计（2026-09-28，本地零算力）

贪心前向选择（39 腿库，窗口全部 ≤60 交易日，平台可表达）产物。

## 因子级三元组（全 A / qfq / label-1 / cycle=10）

| 窗口 | n | ic | icir | win | s_i |
|---|---:|---:|---:|---:|---:|
| 5y 2021-09-07..2026-09-07 | 120 | 0.1228 | 0.820 | 0.792 | **0.0797** |
| 1y 2026-01-01..2026-09-07 | 16 | 0.0968 | 0.533 | 0.688 | 0.0355 |

top-decile 逐期换手 = 0.579；top-quintile = 0.456

## 成分与符号

| 腿 | 方向 | 公式 |
|---|---:|---|
| intr20 | 反向 | `-MA((CLOSE-OPEN)/OPEN,20)` |
| amt60 | 反向 | `-MA(AMOUNT,60)` |
| maxret20 | 反向 | `-TS_MAX(RETURNS(CLOSE,1),20)` |
| retrev5 | 反向 | `-RETURNS(CLOSE,5)` |
| pvcorr20 | 反向 | `-CORR(HIGH,VOLUME,20)` |
| t_std10_60 | 反向 | `-DIV(STD(TURNOVER,10),STD(TURNOVER,60))` |
| amihud20 | 正向 | `MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)` |

## 提交公式

`LEGMIX7 ~ (RANK(-MA((CLOSE-OPEN)/OPEN,20)) + RANK(-MA(AMOUNT,60)) + RANK(-TS_MAX(RETURNS(CLOSE,1),20)) + RANK(-RETURNS(CLOSE,5)) + RANK(-CORR(HIGH,VOLUME,20)) + RANK(-DIV(STD(TURNOVER,10),STD(TURNOVER,60))) + RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20))) / 7 ~ 1`

## size 暴露与现役席重叠（近 24 期截面秩相关均值）

| 参照 | corr | n |
|---|---:|---:|
| SIZE(RANK(MARKET_CAP)) | -0.502 | 24 |
| SEAT:1-MA(T,21)/MA(T,504) | +0.551 | 24 |
| SEAT:1-RETURNS(C,40) | +0.505 | 24 |
| SEAT:Amihud60 | +0.561 | 24 |
| SEAT:VWAP250Dev | +0.515 | 24 |
| SIZE-ONLY-seat(RANK(MV)) | -0.502 | 24 |
