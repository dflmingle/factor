# 退役工作流台账（2026-09-26）

## 目的

- 账户「因子分析数量」已满 300/300（free 会员），无法新建因子。为腾槽位，删除**失败件**与**已证伪/被取代、未来不会入池**的工作流，共 **223** 件。
- 删除前记录平台结果，供以后比对：本目录 `retired_factors.csv`（utf-8-sig，Excel 可直接开）+ `retired_factors.json`。
- 数据来源：① 平台因子列表自带的分析摘要（`plat_summary` 列，最近一次运行）；② 本仓归档的完整指标（`local_metrics` 列 + `local_src` 指向归档文件）。
- 覆盖：有平台摘要 182 件；有本仓完整指标 161 件（其中 136 件两者都有）；两者皆无 16 件（创建/运行即失败，无有效结果）。

## 删除原因分布

| 原因 | 件数 |
| --- | ---: |
| single-factor batch 09-09..12 (rejected) | 46 |
| OSR series (turnover too high) | 46 |
| single-factor batch 09-08..11 (rejected) | 23 |
| GP-replication probe (duplicate/degenerated) | 20 |
| pool-test: failed/falsified pool candidate | 18 |
| 09-14..16 network/GFN batch (rejected) | 17 |
| 2026-09-23 window/seat-count test | 13 |
| 09-11 batch (non-seat, non-active) | 11 |
| single-factor batch 09-11..12 (rejected) | 10 |
| 09-10 base-field batch (rejected) | 8 |
| DLS/paper combo (rejected) | 5 |
| cal_mins probe (closed) | 3 |
| correlation/filter test object | 3 |

## 保留名单（未删）

- **现役池 5 席**（已核对平台各仅一份对象）：`size-only-20260911-SIZE-ONLY-20260911`、`h03-t10-20260911-H03-T10-SINGLE`、`VERIFY10-E260910-04`、`VERIFY10-F260910-12`、`t10-additions-20260911-T10-ADD-BM-20260911`。
- 活跃候选席：`size-impact-20260918-F-I10-01`（10-01 换席候选）、AGG-IMPACT / G13 / DOWNSIDE-IMPACT / VERIFY10-G / F-B06 / F-B08 / F-N34 / F-AG / F-AP-MAIN。
- 本轮赢家 `POOL5-SWAPF-FI10-20260926`（+531 分/月）。
- `F-P26*` / `F-C26*` 池记录（含现役 `F-P260922-08`）、字段对齐探针（`PROBE-*`）、`field-isolation-*`、`BPZ-*`、`qtld60-*`、`RSQR60/KMID2` 诊断件、`REPORT-*`。
- 非本项目对象：`Alpha191因子_*`、`Alpha101因子_*`、`demo-*`、`*克隆*`、`30日最高最低价的时间距离`、`下午前一小时的涨幅`。

## 代表件结果（删除前快照）

| 名称 | 平台结果 |
| --- | --- |
| POOL5-3WIN-FI10-V4-20260926 | net_excess_pct=22.012520000000002; turnover_pct=16.65; long_sharpe=1.0877; long_max_drawdown_pct=33.22; rank_ic=0.0850; ic_ir=0.3751 |
| POOL6-T2V2-20260926 | net_excess_pct=17.933999999999997; turnover_pct=17.5; long_sharpe=1.1509; long_max_drawdown_pct=26.28; rank_ic=0.0893; ic_ir=0.3764 |
| POOL6-T4V6-20260926 | net_excess_pct=18.85696; turnover_pct=19.2; long_sharpe=1.0395; long_max_drawdown_pct=32.28; rank_ic=0.0927; ic_ir=0.3722 |
| POOL5-AGG-SWAPSIZE-V3-20260926 | net_excess_pct=19.417952; turnover_pct=17.54; long_sharpe=1.071; long_max_drawdown_pct=29.97; rank_ic=0.1011; ic_ir=0.3947 |
| POOL5-DOWNSIDE-SWAPSIZE-20260926 | net_excess_pct=19.276784; turnover_pct=17.68; long_sharpe=1.0675; long_max_drawdown_pct=29.96; rank_ic=0.1015; ic_ir=0.3952 |
| POOL6-5Y-20260924-AGG | 因子收益 161.31% 夏普比率 1.0626 年化收益 33.87% 最大回撤 31.84% IC_mean Rank_IC IC_std IC_IR IR P(IC<-0.02) P(IC>0.02) t统计量 p-value 单调性 |
| POOL6-5Y-20260924-G13 | 因子收益 161.48% 夏普比率 1.0636 年化收益 33.91% 最大回撤 31.78% IC_mean Rank_IC IC_std IC_IR IR P(IC<-0.02) P(IC>0.02) t统计量 p-value 单调性 |
| POOL6-5Y-20260924-DOWNSIDE | 因子收益 161.44% 夏普比率 1.0632 年化收益 33.90% 最大回撤 31.84% IC_mean Rank_IC IC_std IC_IR IR P(IC<-0.02) P(IC>0.02) t统计量 p-value 单调性 |
| POOL6-5Y-20260924-WC | 因子收益 158.50% 夏普比率 1.0448 年化收益 33.29% 最大回撤 31.81% IC_mean Rank_IC IC_std IC_IR IR P(IC<-0.02) P(IC>0.02) t统计量 p-value 单调性 |

## 执行结果

- 2026-09-26 深夜执行删除：**223/223 全部成功**（CLI 打印 ✅ 时 GBK 编码崩溃，但删除已完成）；平台因子数 **300 → 77**。
- 删除后快照：`factor_list_after_delete_20260926.json`；执行日志：`delete_log.json`（各 chunk 的原始返回）。
- 核验：现役池 5 席、`F-P260922-08`、`POOL5-SWAPF-FI10-20260926`、活跃候选席与探针全部在列（见快照）。

## 现役池 5 席在删后复核（2026-09-27 实时）

| 池席（平台对象名） | 平台 id | last_run_id | 与 seat_windows.csv 一致 |
| --- | --- | --- | --- |
| `size-only-20260911-SIZE-ONLY-20260911` | `6aa3b8573e7967143f8faf29` | `6aa3b8576df2a192a47e7cfe` | ✅ |
| `h03-t10-20260911-H03-T10-SINGLE` | `6aa36bd3cffa1665a2101716` | `6aa36bd3ecb163ea7228cffe` | ✅ |
| `VERIFY10-E260910-04` | `6aa28e090f6165ec8f7f378b` | `6aa28e0a5d52c44d2f55c2da` | ✅ |
| `VERIFY10-F260910-12` | `6aa28e555d52c44d2f55c2dc` | `6aa28e56a7f535324660b838` | ✅ |
| `t10-additions-20260911-T10-ADD-BM-20260911` | `6aa3c6d1a7f535324660ba70` | `6aa3c6d25d52c44d2f55c45b` | ✅ |

- 223 件被删对象中 **无一件** 处于已提交/发布状态（`publish_status`/`subscription_id` 全为 0/空）；名字含 SIZE/H03/VERIFY 的仅 `STFILTER-T10-SIZE-H03-T10-20260911`、`CORR-20260911-T10-SIZE-H03-T10` 两个过滤/相关性测试件。
- 池回测记录 `F-P260922-08`（id `6ab254bf8b01f62dc5147d39`）同样在列。

## 使用方式

- 以后新候选要对比历史淘汰件时，直接查 `retired_factors.csv` 的 `local_metrics`（净超额/换手/夏普/回撤/RankIC/ICIR），或 `plat_summary`。
- 桥分数口径见 `platform_pool_tests_20260926/summary-swapf.md`（含 A/C 分解与 V4 复算校验）。
