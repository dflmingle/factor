# 每簇最接近的其他簇

簇间相关性取两簇所有成员配对中最大的绝对日均 Spearman，并保留该配对的正负号。这不是簇中心相关性，也不表示簇内任意成员都如此接近。

原 B/N/S 簇不因 C 图的组合桥接而合并；U 簇单独登记。`SEP-isolated` 是历史未归簇 V6-V01，仅为参考标签。

## U 簇最高相关性

| 簇 | 最近其他簇/参考 | rho | 对应成员 | 最近已覆盖 B/N/S 簇 | rho |
|---|---|---:|---|---|---:|
| U01 | SEP-isolated | -0.7810 | GP-0022 ↔ V6-V01 | B06 | +0.6903 |
| U02 | B01 | -0.7847 | GP-0006 ↔ SIZE-ONLY-20260911 | B01 | -0.7847 |
| U03 | U12 | +0.7781 | AGP04W ↔ ct_ar | N01 | +0.7668 |
| U04 | N09 | +0.6604 | BHV-LIMITUP20-20261003 ↔ NONHT-MAX-LOW-21D | N09 | +0.6604 |
| U05 | N11 | +0.6061 | F-NET03 ↔ HT13-QUALITY-CASH-DEBT | N11 | +0.6061 |
| U06 | U01 | -0.2847 | GP-0004 ↔ GP-0022 | B06 | -0.2789 |
| U07 | U02 | +0.6347 | GP-0013 ↔ GP-0005 | B01 | -0.6050 |
| U08 | B01 | -0.3106 | GP-0015 ↔ SIZE-ONLY-20260911 | B01 | -0.3106 |
| U09 | B05 | -0.5971 | bhv_mom250_20 ↔ NONHT-CHIP-COST-250 | B05 | -0.5971 |
| U10 | U03 | -0.6644 | bhv_on20 ↔ bhv_on_minus_id | S02 | -0.3064 |
| U11 | N09 | +0.7569 | ct_amp10 ↔ OSR-SCALED-RET5-20D | N09 | +0.7569 |
| U12 | U03 | +0.7781 | ct_ar ↔ AGP04W | N01 | +0.6315 |
| U13 | S05 | -0.7284 | ct_obv ↔ V7-V01 | S05 | -0.7284 |
| U14 | S04 | +0.4787 | ct_pvcorr30 ↔ comp-pvcorr20-amihud20-vs500 | S04 | +0.4787 |

## 覆盖与使用

旧 B/N 未覆盖：`B07 / B11 / N03 / N13 / N15 / N17 / N18 / N21 / N22 / N24 / N25 / N26 / N28 / N33`；S03 参考代理未纳入。不能用暂无旧锚点证明与未覆盖簇独立。

每簇最高相关、前排近邻及全部配对均已保存：
- [最高相关](cluster_nearest_other.csv)、[完整排序](cluster_neighbors_ranked.csv)。
- [U 成员台账含近邻](new_unanchored_clusters_with_neighbors.csv)。
- [全部簇间最大相关](cluster_pair_max_correlations.csv)、[口径](cluster_neighbors_metadata.json)。

复跑：`python3 scripts/cluster_nearest_neighbors_20261010.py`。仅使用保存矩阵，平台算力为零。
