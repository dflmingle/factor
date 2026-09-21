# 因子簇画像、簇内整体指标与跨簇相关关系

## 口径

本报告把每个簇作为一个整体观察，列出簇的特色、成员整体指标，以及与其它簇的高相关关系。

- 成簇窗口：`20210907..20260907`。
- 成簇阈值：`abs(rho) >= 0.80`。
- 簇内指标：对该簇全部已保存平台成员记录取最小值~最大值范围；重复平台运行按独立记录保留。
- 净超额、换手率、最大回撤、RankIC 均来自平台原始 `*.report.csv`。
- 最大回撤列是“成员最大回撤范围”，不是把多个因子合成后的组合最大回撤。
- 平台当前没有直接回测“因子簇组合”的结果，因此真实簇组合的净超额、换手和最大回撤需要先定义簇内信号合成方式及权重，再另行回测。本报告的范围是簇内成员表现的描述性统计。
- 跨簇关系按两个簇全部成员两两相关性的最大 `abs(rho)` 判断；报告列出所有 `abs(rho) > 0.60` 的其它簇，而不是只保留一个最近簇。关系中同时保留有符号 rho 和触发关系的因子对。
- 代表因子仅作为簇标签，不用于代替簇整体指标。
- N34 是 2026-09-20 补充确认的单成员簇；其相关关系来自补充修正报告中的基础簇代表因子比较。

## 簇整体指标范围

| 簇 | 特色 | 成员数 | 代表因子（标签） | 净超额范围 | 换手率范围 | 成员最大回撤范围 | RankIC 范围 |
|---|---|---:|---|---:|---:|---:|---:|
| B01 | 市值 / 冲击 | 4 | SIZE-ONLY-20260911 | 13.94%~21.43% | 5.62%~9.43% | 30.85%~42.66% | -0.0558~0.0665 |
| B02 | 换手偏离及其反向信号 | 3 | HT13-TURN-BIAS-1M | 4.96%~6.43% | 15.68%~26.97% | 22.94%~24.89% | -0.0737~0.0653 |
| B03 | 40 日反转 | 2 | OSR2-RET40 | 1.03%~5.03% | 40.41%~55.02% | 30.05%~40.20% | 0.0731~0.0908 |
| B04 | 120 日回撤 | 2 | OSR2-DD120 | 4.25%~4.79% | 21.06%~29.39% | 28.55%~38.08% | 0.0329~0.0405 |
| B05 | 筹码成本 / 120 日动量反向 | 3 | NONHT-CHIP-COST-250 | -32.86%~4.28% | 19.46%~35.97% | 29.22%~111.98% | -0.0665~0.0677 |
| B06 | 低成交量 | 1 | F-NET01-PLAT-20260914 | 13.63% | 8.04% | 33.95% | 0.0577 |
| B07 | EV/EBITDA 价值 | 1 | NEW-VALUE-EVEBITDA | 3.32% | 6.55% | 37.18% | 0.0202 |
| B08 | 账面市值比 / 账面价值 | 1 | HT13-VALUE-BP | 2.10% | 4.17% | 22.69% | 0.0524 |
| B09 | 60 日回撤 | 1 | OSR2-DD60 | 1.95% | 26.03% | 43.49% | 0.0303 |
| B10 | 资产增长 | 1 | paper-derived-asset-growth | 0.76% | 2.10% | 41.26% | -0.0115 |
| B11 | 低残差波动 | 1 | NONHT-RESVOL-LOW | 0.37% | 17.19% | 23.77% | 0.0884 |
| B12 | 销售市值比 | 1 | HT13-VALUE-SP | 0.11% | 2.94% | 26.03% | 0.0333 |
| N01 | 20 日反转 / 短期动量振荡 | 18 | OSR2-RET20 | -45.81%~-0.10% | 38.73%~75.56% | 10.07%~133.61% | -0.0880~0.0881 |
| N02 | 营收 / 净利润增长 | 2 | NEW-GROWTH-REV-TTM | -4.44%~-2.22% | 3.76%~5.29% | 48.23%~50.81% | -0.0042~-0.0004 |
| N03 | ROE 增长 | 1 | NEW-GROWTH-ROE-TTM | -2.43% | 6.56% | 31.75% | 0.0113 |
| N04 | 历史 ROE | 1 | NEW-HIST-ROE-6Q | -2.71% | 9.07% | 17.16% | -0.0022 |
| N05 | EP 盈利价值 | 1 | HT13-VALUE-EP | -3.88% | 4.42% | 18.47% | 0.0174 |
| N06 | 现金流 / PCF 估值 | 1 | HT13-VALUE-OCFP-LOW-PCF | -2.84% | 5.64% | 45.99% | -0.0130 |
| N07 | OCF 增长 | 1 | HT13-GROWTH-OCF | -0.60% | 5.57% | 33.73% | 0.0034 |
| N08 | 换手率波动 | 1 | HT13-TURN-STD-1M | -4.25% | 19.47% | 19.08% | -0.0671 |
| N09 | 短期波动 / 低位收益缩放 | 3 | NONHT-MAX-LOW-21D | -8.78%~-5.91% | 24.78%~51.71% | 20.90%~21.33% | -0.0722~0.0862 |
| N10 | ROE / ROIC 质量 | 2 | REPORT-ROIC-TTM-10D-20260910 | -11.21%~-9.50% | 1.77%~3.00% | 48.03%~50.17% | -0.0069~-0.0062 |
| N11 | 现金流 / 负债质量 | 1 | HT13-QUALITY-CASH-DEBT | -3.11% | 1.85% | 37.73% | 0.0042 |
| N12 | 历史 EP | 1 | HT13-HIST-EP-2Q | -12.17% | 47.23% | 31.25% | 0.0211 |
| N13 | 历史 ROA | 1 | HT13-HIST-ROA-6Q | -4.74% | 6.00% | 18.70% | -0.0008 |
| N14 | Alpha44 价量相关 | 2 | HT13-ALPHA44 | -18.11%~-9.62% | 86.24%~87.26% | 27.42%~36.29% | 0.0396~0.0454 |
| N15 | 21 日最大低位 | 1 | NONHT-MAX5-LOW-21D | -11.93% | 86.91% | 28.18% | 0.0155 |
| N16 | 60 日收益偏度 | 1 | NONHT-SKEW-LOW-60D | -0.44% | 36.31% | 24.93% | 0.0474 |
| N17 | 现金转换 | 1 | NONHT-CASH-CONVERSION | -0.02% | 6.88% | 24.70% | 0.0120 |
| N18 | 低 Beta | 1 | NONHT-LOW-BETA | -15.46% | 13.60% | 25.80% | 0.0096 |
| N19 | 5 日反转 | 1 | OSR-RET5-20D | -30.17% | 87.60% | 42.30% | 0.0326 |
| N20 | 20 日回撤 | 1 | OSR-DD20-20D | -12.63% | 44.78% | 42.79% | 0.0133 |
| N21 | MFI 资金流 / 超卖 | 1 | OSR-MFI14-20D | -21.91% | 61.85% | 47.49% | 0.0318 |
| N22 | 中度 Bias | 1 | OSR2-MODERATE-BIAS5 | -22.13% | 78.44% | 31.56% | 0.0211 |
| N23 | 中度 60 日回撤 | 1 | OSR2-MODERATE-DD60 | -31.45% | 74.30% | 43.28% | -0.0077 |
| N24 | RSI 交叉 30 | 1 | OSR2-RSI-CROSS30 | -25.60% | 89.86% | 35.13% | 0.0018 |
| N25 | 价格 / MA5 交叉 | 1 | OSR2-PRICE-CROSS-MA5 | -30.04% | 89.99% | 33.70% | 0.0006 |
| N26 | 平滑 RSI28 | 1 | OSR2-SMOOTH-RSI28 | -1.86% | 24.26% | 35.93% | 0.0578 |
| N27 | ROE 盈利能力 | 1 | paper-derived-roe | -13.30% | 1.87% | 59.55% | -0.0114 |
| N28 | 综合盈利能力 | 1 | paper-derived-profitability | -4.47% | 5.48% | 19.45% | 0.0287 |
| N29 | 历史净利率 | 1 | REPORT-HIST-NETMARGIN-6Q-10D-20260910 | -4.22% | 22.26% | 22.65% | 0.0056 |
| N30 | 历史资产周转率 | 1 | REPORT-HIST-ASSETTURN-6Q-10D-20260910 | -1.27% | 25.40% | 27.88% | 0.0053 |
| N31 | 历史毛利率 | 1 | HT13-NEW-HIST-GPM-6Q | -6.81% | 11.21% | 21.63% | -0.0002 |
| N32 | Alpha40 波动 / 价量 | 1 | HT13-NEW-ALPHA40 | -17.02% | 72.39% | 37.76% | 0.0690 |
| N33 | Python OBV / 成交量能量 | 2 | WF6AA4-D0-PYTHON-OBV-20260912 | -23.35%~-13.10% | 86.70%~89.25% | 29.43%~47.95% | -0.0144~-0.0143 |
| N34 | 账面价值 / 经营利润比 | 1 | F-GFN-N02-20260916 | 12.27% | 5.64% | 43.97% | 0.0363 |

## 跨簇高相关关系

以下列出每个簇与其它簇之间最大成员相关性超过 `0.60` 的全部关系。`rho` 保留符号，`abs` 为用于排序和筛选的绝对值。没有超过 `0.60` 的，列出该簇的最高关系作为参考。

| 簇 | `abs(rho) > 0.60` 的相关簇 | 触发关系 |
|---|---|---|
| B01 | N34: `-0.7249`；B06: `+0.7239` | N34: F-GFN-N02-20260916 <> SIZE-ONLY-20260911；B06: F-NET01-PLAT-20260914 <> H03-T10-SINGLE |
| B02 | 无；最高为 N08 `+0.5456` | HT13-TURN-BIAS-1M <> HT13-TURN-STD-1M |
| B03 | N26: `+0.7999`；N01: `+0.7971`；B09: `+0.6362`；B04: `+0.6025` | N26: OSR2-RET40 <> OSR2-SMOOTH-RSI28；N01: OSR2-RET40 <> F-A18；B09: OSR2-DD60 <> OSR2-RET40；B04: OSR2-DD120 <> OSR2-RET40 |
| B04 | B09: `+0.7899`；N26: `+0.6558`；N01: `+0.6164`；B03: `+0.6025` | B09: OSR2-DD120 <> OSR2-DD60；N26: OSR2-DD120 <> OSR2-SMOOTH-RSI28；N01: OSR2-DD120 <> F-A18；B03: OSR2-DD120 <> OSR2-RET40 |
| B05 | N26: `+0.6981` | NONHT-CHIP-COST-250 <> OSR2-SMOOTH-RSI28 |
| B06 | B01: `+0.7239` | F-NET01-PLAT-20260914 <> H03-T10-SINGLE |
| B07 | 无；最高为 N05 `-0.3903` | NEW-VALUE-EVEBITDA <> HT13-VALUE-EP |
| B08 | 无；最高为 B12 `+0.5706` | HT13-VALUE-BP <> HT13-VALUE-SP |
| B09 | B04: `+0.7899`；N01: `+0.7150`；N20: `+0.6548`；B03: `+0.6362` | B04: OSR2-DD120 <> OSR2-DD60；N01: OSR2-DD60 <> F-A18；N20: OSR2-DD60 <> OSR-DD20-20D；B03: OSR2-DD60 <> OSR2-RET40 |
| B10 | 无；最高为 N27 `+0.5136` | paper-derived-asset-growth <> paper-derived-roe |
| B11 | 无；最高为 N09 `-0.5900` | NONHT-RESVOL-LOW <> HT13-VOL-STD-1M |
| B12 | 无；最高为 B08 `+0.5706` | HT13-VALUE-BP <> HT13-VALUE-SP |
| N01 | B03: `+0.7971`；N20: `+0.7695`；N26: `+0.7450`；B09: `+0.7150`；N19: `+0.7129`；N21: `+0.6987`；B04: `+0.6164`；N22: `+0.6127` | B03: OSR2-RET40 <> F-A18；N20: OSR-DD20-20D <> OSR-MA20-20D；N26: F-A18 <> OSR2-SMOOTH-RSI28；B09: OSR2-DD60 <> F-A18；N19: OSR-RET5-20D <> OSR-Z20-20D；N21: OSR-MA20-20D <> OSR-MFI14-20D；B04: OSR2-DD120 <> F-A18；N22: OSR2-MODERATE-RSI35 <> OSR2-MODERATE-BIAS5 |
| N02 | N29: `+0.6723`；N04: `+0.6713` | N29: HT13-GROWTH-NP <> REPORT-HIST-NETMARGIN-6Q-10D-20260910；N04: NEW-HIST-ROE-6Q <> HT13-GROWTH-NP |
| N03 | 无；最高为 N02 `+0.3292` | NEW-GROWTH-ROE-TTM <> HT13-GROWTH-NP |
| N04 | N02: `+0.6713` | NEW-HIST-ROE-6Q <> HT13-GROWTH-NP |
| N05 | N27: `+0.7521`；N28: `+0.7244`；N10: `+0.7058` | N27: HT13-VALUE-EP <> paper-derived-roe；N28: HT13-VALUE-EP <> paper-derived-profitability；N10: HT13-VALUE-EP <> HT13-QUALITY-ROE |
| N06 | 无；最高为 B12 `-0.2748` | HT13-VALUE-SP <> HT13-VALUE-OCFP-LOW-PCF |
| N07 | 无；最高为 N11 `+0.5074` | HT13-GROWTH-OCF <> HT13-QUALITY-CASH-DEBT |
| N08 | N09: `+0.7339` | HT13-TURN-STD-1M <> HT13-VOL-STD-1M |
| N09 | N08: `+0.7339` | HT13-TURN-STD-1M <> HT13-VOL-STD-1M |
| N10 | N27: `+0.7106`；N05: `+0.7058`；N28: `+0.6802` | N27: HT13-QUALITY-ROE <> paper-derived-roe；N05: HT13-VALUE-EP <> HT13-QUALITY-ROE；N28: paper-derived-profitability <> REPORT-ROIC-TTM-10D-20260910 |
| N11 | 无；最高为 N07 `+0.5074` | HT13-GROWTH-OCF <> HT13-QUALITY-CASH-DEBT |
| N12 | 无；最高为 N02 `+0.4098` | HT13-GROWTH-NP <> HT13-HIST-EP-2Q |
| N13 | 无；最高为 N04 `+0.5897` | NEW-HIST-ROE-6Q <> HT13-HIST-ROA-6Q |
| N14 | 无；最高为 N32 `+0.3932` | HT13-ALPHA44 <> HT13-NEW-ALPHA40 |
| N15 | 无；最高为 N09 `+0.1099` | NONHT-MAX5-LOW-21D <> OSR-SCALED-RET5-20D |
| N16 | 无；最高为 N09 `+0.3696` | NONHT-MAX-LOW-21D <> NONHT-SKEW-LOW-60D |
| N17 | 无；最高为 B07 `-0.3515` | NEW-VALUE-EVEBITDA <> NONHT-CASH-CONVERSION |
| N18 | 无；最高为 B11 `+0.4297` | NONHT-RESVOL-LOW <> NONHT-LOW-BETA |
| N19 | N01: `+0.7129`；N20: `+0.6038` | N01: OSR-RET5-20D <> OSR-Z20-20D；N20: OSR-RET5-20D <> OSR-DD20-20D |
| N20 | N01: `+0.7695`；B09: `+0.6548`；N19: `+0.6038` | N01: OSR-DD20-20D <> OSR-MA20-20D；B09: OSR2-DD60 <> OSR-DD20-20D；N19: OSR-RET5-20D <> OSR-DD20-20D |
| N21 | N01: `+0.6987` | N01: OSR-MA20-20D <> OSR-MFI14-20D |
| N22 | N01: `+0.6127` | N01: OSR2-MODERATE-RSI35 <> OSR2-MODERATE-BIAS5 |
| N23 | 无；最高为 B09 `-0.3906` | B09: OSR2-DD60 <> OSR2-MODERATE-DD60 |
| N24 | 无；最高为 N01 `+0.1070` | N01: OSR2-MODERATE-RSI35 <> OSR2-RSI-CROSS30 |
| N25 | 无；最高为 N24 `+0.0778` | N24: OSR2-RSI-CROSS30 <> OSR2-PRICE-CROSS-MA5 |
| N26 | B03: `+0.7999`；N01: `+0.7450`；B05: `+0.6981`；B04: `+0.6558` | B03: OSR2-RET40 <> OSR2-SMOOTH-RSI28；N01: F-A18 <> OSR2-SMOOTH-RSI28；B05: NONHT-CHIP-COST-250 <> OSR2-SMOOTH-RSI28；B04: OSR2-DD120 <> OSR2-SMOOTH-RSI28 |
| N27 | N05: `+0.7521`；N28: `+0.7328`；N10: `+0.7106` | N05: HT13-VALUE-EP <> paper-derived-roe；N28: paper-derived-roe <> paper-derived-profitability；N10: HT13-QUALITY-ROE <> paper-derived-roe |
| N28 | N27: `+0.7328`；N05: `+0.7244`；N10: `+0.6802` | N27: paper-derived-roe <> paper-derived-profitability；N05: HT13-VALUE-EP <> paper-derived-profitability；N10: paper-derived-profitability <> REPORT-ROIC-TTM-10D-20260910 |
| N29 | N02: `+0.6723` | N02: HT13-GROWTH-NP <> REPORT-HIST-NETMARGIN-6Q-10D-20260910 |
| N30 | 无；最高为 N02 `+0.3304` | N02: NEW-GROWTH-REV-TTM <> REPORT-HIST-ASSETTURN-6Q-10D-20260910 |
| N31 | 无；最高为 N29 `+0.4503` | N29: REPORT-HIST-NETMARGIN-6Q-10D-20260910 <> HT13-NEW-HIST-GPM-6Q |
| N32 | 无；最高为 N09 `+0.4487` | N09: OSR-SCALED-RET5-20D <> HT13-NEW-ALPHA40 |
| N33 | 无；最高为 N01 `-0.3523` | N01: OSR-RSI14-20D <> WF6AA4-D0-PYTHON-OBV-20260912 |
| N34 | B01: `-0.7249` | B01: F-GFN-N02-20260916 <> SIZE-ONLY-20260911 |

## 解释

- 例如 N01 的簇内净超额范围为 `-45.81%~-0.10%`，最大回撤范围为 `10.07%~133.61%`，不是代表因子 OSR2-RET20 的单点结果。
- B05 的簇内净超额范围为 `-32.86%~4.28%`，最大回撤范围为 `29.22%~111.98%`；这比只看代表因子的单点结果更能反映该簇成员整体的分化。
- “相关簇”可以有多个。例如 N01 与 B03、N20、N26、B09、N19、N21、B04、N22 都超过 `0.60`，但只有达到 `0.80` 才会按当前规则正式并簇。
- 簇内范围不等于可交易组合结果。要得到真正的簇组合净超额、换手和最大回撤，需要对簇内信号做明确的方向统一、标准化、权重和调仓处理后进行组合回测。

## 数据来源

- [`all-factor-cluster-expansion-20260919.clusters.csv`](all-factor-cluster-expansion-20260919.clusters.csv)
- [`all-factor-cluster-expansion-20260919.assignments.csv`](all-factor-cluster-expansion-20260919.assignments.csv)
- [`all-factor-cluster-expansion-20260919.pairs.csv`](all-factor-cluster-expansion-20260919.pairs.csv)
- [`f-gfn-n02-cluster-assignment-20260920.md`](f-gfn-n02-cluster-assignment-20260920.md)
- [`cluster-performance-consistency-20260920.md`](cluster-performance-consistency-20260920.md)
