# 新挖因子入簇检查（2026-09-30）

把 2026-09-28~30 新挖出的 16 条因子对照 2026-09-19 的 B01-B12 / N01-N33 体系做归属：
`|rho| >= 0.80` 并入旧簇，否则在新因子之间切新簇。产物全部由本地零平台算力完成。

## 口径

- 与 09-19 分簇同口径：120 个 signal date（2021-09-07..2026-08-10）、按日横截面 Spearman、
  `|rho| >= 0.80` 连通分量、`[0.60,0.80)` 逐对 pairwise-complete 精确重算、每日 >= 100 只股票。
- 旧簇侧成员：`all-factor-cluster-expansion-20260919.clusters.csv` 的 68 个唯一成员中
  49 条本地可物化（15 条缺字段/不支持算子，4 条不可解析），覆盖 34/45 个旧簇。
- 新因子侧 16 条：12 条由 GP 引擎原生物化；4 条为 pandas 代理
  （VV6-1250 超本地预热窗；a046 x3 用 alpha191 参考实现 + 32% min_periods 口径）。

## 归属结果

| 新因子 | 面板 | 归属 | 最近旧成员 | max\|rho\| | 最近旧簇 |
| --- | --- | --- | --- | ---: | --- |
| VV6-500 | engine | S01 | HT13-TURN-BIAS-1M | 0.475 | B02 |
| VV6-756 | engine | S01 | HT13-TURN-BIAS-1M | 0.488 | B02 |
| VV6-1250 | proxy | S01 | HT13-TURN-BIAS-1M | 0.523 | B02 |
| LAMD10-K5V2 | engine | S02 | HT13-TURN-STD-1M | 0.616 | N08 |
| LAMD0-K8V2 | engine | S02 | NONHT-MAX-LOW-21D | 0.475 | N09 |
| LAMD20-K5V2 | engine | S02 | HT13-TURN-STD-1M | 0.529 | N08 |
| comp-amt60-vs500-retrev20 | engine | S02 | DLS14-STREV-20D | 0.630 | N01 |
| a046-t10x750-w30-rsm20 | proxy | S03 | HT13-TURN-BIAS-1M | 0.787 | B02 |
| a046-t10x750-w20-rsm40 | proxy | S03 | HT13-TURN-BIAS-1M | 0.756 | B02 |
| a046-t10x750-w30 | proxy | S03 边界(0.7997) | HT13-TURN-BIAS-1M | 0.594 | B02 |
| comp-pvcorr20-amihud20-vs500 | engine | S04 | NONHT-MAX-LOW-21D | 0.502 | N09 |
| comp-amihud20-vs500 | engine | S04 | NONHT-MAX-LOW-21D | 0.689 | N09 |
| V4R01 | engine | S05 | H03-T10-SINGLE | 0.707 | B01 |
| V7-V01 | engine | S05 | H03-T10-SINGLE | 0.703 | B01 |
| V5-V01 | engine | **并入 B01** | H03-T10-SINGLE | **0.903** | B01 |
| V6-V01 | engine | 未入簇(孤立) | F-NET01-PLAT-20260914 | 0.579 | B06 |

## 新簇

| 新簇 | 条数 | 成员 | 簇内最小\|rho\| | 与旧簇最高\|rho\| |
| --- | ---: | --- | ---: | ---: |
| S01 volstab 长窗波动比 | 3 | VV6-500;VV6-756;VV6-1250 | 0.951 | 0.523 (B02) |
| S02 LEGMIX-NEXT 复合 | 4 | LAMD10-K5V2;LAMD0-K8V2;LAMD20-K5V2;comp-amt60-vs500-retrev20 | 0.639(链式) | 0.630 (N08/N09/N01) |
| S03 换手std比 x A191 | 2(+1边界) | a046-w30-rsm20;a046-w20-rsm40;(w30 @0.7997) | 0.877 | 0.787 (B02) |
| S04 amihud x volstab 复合 | 2 | comp-pvcorr20-amihud20-vs500;comp-amihud20-vs500 | 0.825 | 0.689 (N09) |
| S05 波动水平/量能趋势 | 2 | V4R01;V7-V01 | 0.981 | 0.707 (B01) |

## 注意

- V5-V01 `Greater(Greater(vol10,...),...)` 命中 size 簇 B01（3 个成员 >= 0.80），
  按 size 防作弊约束不应视为独立新信号；Greater 语义（逐元素 max）与平台如不一致需平台复测确认。
- S03 与 B02（换手 bias 簇）0.756-0.787 临界未并；S01-S02-S03-S04 在 0.70 阈值下会并成
  "volstab/turnstab 超级族"，0.80 下为 4 个独立新簇。
- 旧簇未覆盖 11 个（B07,B11,N03,N13,N15,N17,N22,N24,N25,N26,N28，本地缺字段/不支持算子），
  不可评估成员的簇本轮命不中，不代表新因子与其无关。
- VV6-1250 平台 v2 结果（net +53.7%、MDD 0%、胜率 100%）异常，使用前建议复核。
- 对 09-24 那批 205 条 GP 候选（K 簇体系）做了公式级排查：无同腿家族
  （无 volstd/turnstd/alpha191/amihud 类公式），不存在"其实属于 K 簇"的遗漏风险。

## 产物与复现

- `new_factor_candidates.csv`：16 条新因子（band=标签, formula）。
- `members_evaluated.csv` / `members_excluded.csv`：旧簇侧 49 条可评估成员 / 19 条排除原因。
- `candidate_matches.csv`、`candidate_member_correlation_long.csv`、`candidate_member_correlation_wide.csv`：新因子 x 旧成员相关全量结果。
- `newfactor_self_corr.csv`、`new_clusters.csv`、`new_factor_cluster_assignment.csv`：新因子自发簇与最终归属表。
- `scripts/`：assemble（装配）/ validate（解析预检）/ run（GP 引擎 chunk-major 物化）/
  fix_panels（a046+VV6-1250 代理面板）/ run_corr（相关）/ selfcluster（自发簇）。
- `logs/`：eval / corr / fix 运行日志。
- 相关口径实现复用 `scripts/gp_candidates_vs_clusters_20260924.py`（monkeypatch 输入输出路径）。
