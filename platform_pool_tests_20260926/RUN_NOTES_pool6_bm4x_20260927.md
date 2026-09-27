# POOL6 BM4+AGG/FSCORE-E 实测运行笔记（2026-09-27 凌晨）

## 第一批（两条）
- 文件：pool6-bm4agg-e_bm4fscore-e-20260927-candidates.txt
- 首跑 00:46 起；重跑（--retry-failed --max-runs 2）00:59-01:19
- 结果：两条均「轮询超时 (600s)」返回，但后台 run 状态不同（见下）

### 第一条 POOL6-BM4AGG-E-20260927
- factor_id 6ab7f6dd9e9d797cfb2cf900
- run#1 6ab7f6de9e9d797cfb2cf901：status=8 零节点，0.04s，未计费
- run#2 6ab7f9e62d2f6998fc1bf890：status=8 零节点，0.04s，未计费
- 形态：平台调度失败（历史 50% 概率；K020/K008 等先例：同 factor 重跑即可过）

### 第二条 POOL6-BM4FSCORE-E-20260927
- factor_id 6ab7fc42a8ba1ed343bf7edb
- run#1 6ab7fc44812a2a13b9644d2f：status=8，执行 120.25s 后无输出（nodes 仅回显 code，factor_analysis=null）
- 计费 4.0（进入执行即计费；零节点不计费）
- 形态：执行阶段中止（无错误明细回传）

## 平台耗时参照（历史含结果 run，按耗时降序）
237.7 / 223.7 / 157.9 / 145.6 / 136.9 / 129.0 / 126.4 / 125.8 / 123.7 / 123.1 / 122.6 / 122.0 / 119.3 s 均为 SUCCESS
- 近期成功：BM4 104.0s、PARTT10 110.1s、T2v2 118.8s、T4v6 123.1s
- 结论：不存在硬性 120s 上限；FSCORE 120.25s 失败属动态资源配额/平台抖动叠加。

## 计费流水
- 提交前余额：1616.12（gift 208；8.0 @ 09-30 23:16 到期）
- 平台新发礼包 +10.0：gift 218，next expire 「10.0 @ 2026-09-27 23:59:59」
- FSCORE 失败 run：-4.0 → 余额 1622.12（gift 214；今天到期剩 6.0）
- AGG 侧累计消耗：0（两次零节点未计费）

## 处置
- V2 优化：缓存 RANK(market_cap)（四席共用；数值等价）→ pool6_bm4agg_e_v2.py
- AGG V2 提交：factor_id 6ab7ff44cd820fa2a40a6d54（01:22 起 run）
- FSCORE：V2 优化版待跑（需追加预算批准）