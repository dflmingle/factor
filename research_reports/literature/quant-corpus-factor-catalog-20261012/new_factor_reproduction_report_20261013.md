# 新因子本地复现续测（2026-10-13）

本轮继续从 `quant/` 中挑选此前没有正式本地复现的机制，使用当前对齐契约：沪深 `.SH/.SZ` 全 A、qfq、`total_mv`、20180101 暖机、平台保存信号日、10 日调仓、10 组、`close(t+1) -> close(t+11)`、`factor_valid`、单边成本 0.30%。每个候选同时输出正式五年窗口和 2026 年近期窗口，并做市值/20 日反转残差诊断。没有调用平台。

## 本轮结果

| 批次 | 候选机制 | 五年净超额 | 市值/反转残差五年 | 近期净超额 | 结论 |
|---|---|---:|---:|---:|---|
| source16 | 63 日下行波动低 | -3.52% | -1.42% | +2.70% | 不通过 |
| source16 | 下行/总波动比低 | -24.84% | -6.35% | -23.40% | 淘汰 |
| source16 | 60 日隔夜跳空低 | -2.11% | -0.23% | +2.17% | 不通过 |
| source16 | 30 日新高突破强度 | -26.33% | -5.88% | -19.52% | 淘汰 |
| source16 | 13/34/55 均线排列强度 | -29.31% | -13.90% | -10.01% | 淘汰 |
| source16 | 协方差 60/240 变化 | -11.36% | -12.81% | -32.66% | 淘汰 |
| source17 | 高开形态低 | -4.91% | -2.37% | -3.46% | 不通过 |
| source17 | 收盘相对低点高 | -32.36% | -17.82% | -7.68% | 淘汰 |
| source17 | 成交均价相对收盘 | -1.47% | -9.24% | -8.75% | 不通过 |
| source17 | 10 日有符号跳空低 | -30.61% | -31.38% | -30.53% | 淘汰 |
| source17 | 10 日绝对跳空低 | -6.96% | -3.96% | -4.83% | 淘汰 |
| source17 | 20 日收盘位置低 | -4.39% | -12.46% | -6.66% | 不通过 |
| source18 | FFScore 六项计数 | -0.27% | +1.41% | +12.97% | 近期强，五年不稳 |
| source18 | FFScore 六项×BM | +1.81% | -0.06% | +2.94% | 增量不足 |
| source18 | FFScore 质量分 | -0.27% | +1.41% | +12.97% | 近期强，五年不稳 |
| source19 | 20 日幅度×近高 | -31.25% | -12.20% | -5.58% | 淘汰 |
| source19 | 幅度×近高×温和跳空 | -18.98% | -6.48% | -16.75% | 淘汰 |
| source20 | 利润增长×向下跳空 | -10.96% | -7.19% | -14.17% | 淘汰 |
| source20 | 利润增长门控×向下跳空 | -13.11% | -11.82% | -4.63% | 淘汰 |

## 解释

本轮没有找到可以纳入“新独立 alpha 簇”的候选。FFScore 六项变化在近期窗口有明显正收益，但正式五年接近零，且剥离市值和反转后只剩 +0.85%，不能据此扩充因子池。高开形态的残差近期 +6.26%，但正式五年仍为 −2.37%，同样只作短期诊断。

下行波动、低协方差和突破类候选的共同问题是：收益主要集中在近期或特定行情，正式窗口表现为负；跳空和价格形态类候选还伴随 60%—85% 的高换手，扣费后优势消失。利润增长×跳空原文存在股票映射错误，本轮按正确股票映射重建后仍显著为负，因此不保留。

## 产物

- [source16 结果](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source16-20261013/results.csv)
- [source17 结果](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source17-20261013/results.csv)
- [source18 结果](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source18-20261013/results.csv)
- [source19 结果](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source19-20261013/results.csv)
- [source20 结果](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source20-20261013/results.csv)

所有失败候选仍保留在对应 `recipe_manifest.json` 和双窗口明细中；原始 `quant/` 未修改，平台算力消耗为 0。
