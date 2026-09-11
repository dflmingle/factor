# Factors Archived From `report(1).md`

本文件将 `report(1).md` 中的 15 个候选整理为可定位的本地索引。原始报告保留全部研究背景、逐轮机制、分年结果和成本口径；候选清单见 `report-1-candidates.txt`。

## 口径

- 来源报告：`report(1).md`
- 区间：20210909 至 20260908
- 调仓周期：5 日
- 分组：10 组
- 股票池：沪深全 A
- 单边成本：0.30%
- 结果性质：同一样本的历史研究代理，未完成独立样本外验证
- 保存状态：仅存档，未因本次整理重新创建或运行

方向 `1` 表示高值优先，方向 `0` 表示低值优先。方向按报告各轮机制中明确写出的预设高/低方向整理；不因结果反向调整。

## 候选索引

| 候选 | 方向 | 公式 | 状态 | Rank_IC | IC_IR | 净超额%/年 | 决策 |
|---|---:|---|---|---:|---:|---:|---|
| L260911-01 | 1 | `CLOSE / (SUM(CLOSE * VOLUME,120) / (SUM(VOLUME,120) + 1) + 0.000001) - 1` | completed | -0.0614 | -0.2211 | -37.6329 | abandon |
| L260911-02 | 0 | `TS_KURT(CLOSE / DELAY(CLOSE,1) - 1,60)` | completed | 0.0039 | -0.0288 | -9.8691 | abandon |
| L260911-03 | 0 | `CORRELATION(ABS(CLOSE / DELAY(CLOSE,1) - 1),ABS(DELAY(CLOSE,1) / DELAY(CLOSE,2) - 1),60)` | completed | -0.0146 | -0.1628 | -5.4771 | abandon |
| L260911-04 | 0 | `VAR(OPEN / DELAY(CLOSE,1) - 1,60) / (VAR(OPEN / DELAY(CLOSE,1) - 1,60) + VAR(CLOSE / OPEN - 1,60) + 0.000001)` | completed | -0.0101 | -0.1507 | -8.5278 | abandon |
| L260911-05 | 1 | `SUMIF(CLOSE < DELAY(CLOSE,1),VOLUME,60) / (SUM(VOLUME,60) + 1)` | completed | 0.0317 | 0.1825 | -3.2400 | abandon |
| L260911-06 | 1 | `CORRELATION(TURNOVER,DELAY(TURNOVER,1),60)` | completed | -0.0238 | -0.0809 | -17.2987 | abandon |
| L260911-07 | 0 | `CORRELATION(ABS(CLOSE / DELAY(CLOSE,1) - 1),LOG(AMOUNT + 1),60)` | completed | -0.0157 | -0.2204 | -1.9528 | abandon |
| L260911-08 | 0 | `(SUM(HIGH - MAX(OPEN,CLOSE),60) - SUM(MIN(OPEN,CLOSE) - LOW,60)) / (SUM(HIGH - LOW,60) + 0.000001)` | completed | -0.0432 | -0.1385 | -3.1439 | abandon |
| L260911-09 | 1 | `PROFIT_FROM_OPERATION / (ABS(EV_NO_CASH_LF) + 1)` | completed | 0.0186 | -0.0398 | -5.0364 | abandon |
| L260911-10 | 1 | `HHVBARS(VOLUME,60)` | completed | 0.0352 | 0.2540 | -16.3343 | abandon |
| L260911-11 | 0 | `LOG(CLOSE / DELAY(CLOSE,20)) - LOG(DELAY(CLOSE,20) / DELAY(CLOSE,40))` | completed | -0.0258 | -0.1528 | -17.5929 | abandon |
| L260911-12 | 1 | `COST_OF_GOODS_SOLD / (ABS(INVENTORY) + 1)` | completed | 0.0042 | -0.0581 | -2.7395 | abandon |
| L260911-13 | 0 | `BAD_DEBT_RESERVE / (ABS(NET_ACCTS_RECEIVABLE) + ABS(BAD_DEBT_RESERVE) + 1)` | failed | -- | -- | -- | no_result |
| L260911-14 | 1 | `CASH_RECEIVED_FROM_INVESTMENT / (ABS(INVESTMENT_INCOME) + 1)` | completed | 0.0018 | -0.0589 | -1.6734 | abandon |
| L260911-15 | 0 | `PAYROLL_PAYABLE / (ABS(CASH_PAID_FOR_EMPLOYEE) + 1)` | completed | 0.0037 | -0.0428 | -2.2357 | abandon |

## Summary

14 个候选有有效结果，1 个候选（L260911-13）服务端执行失败。14 个有效结果的成本后净超额全部为负，没有候选同时满足预设方向和正净超额。L260911-10 虽然通过报告中累计 125 个假设的名义 p 值粗筛，但换手率 `70.12%/次调仓`，估算净超额仍为 `-16.3343%/年`，不能作为有效因子。

本批候选不应直接加入正式比赛池。后续若重新研究，应先做字段可用性、披露时点、截面相关性和实际成本诊断，再由用户明确批准新的回测。
