# 论文启发的浅层树输出稳健化：严格滚动本地对照（2026-10-12）

本轮只使用已经完成严格季度滚动的原始 60 特征浅层树信号，研究论文中“预测池化/截尾/稳健化”是否能在不增加树深、树数或新特征的情况下改善交易后结果。没有创建平台因子、没有运行平台回测、没有修改现役池。

## 论文依据

- Gu, Kelly & Xiu, *Empirical Asset Pricing via Machine Learning*（RFS 2020，DOI [10.1093/rfs/hhaa009](https://doi.org/10.1093/rfs/hhaa009)）：树模型的增益主要来自少量特征交互，主导信息集中在动量、流动性和波动；这支持保留原 60 特征而不继续扩展树复杂度。
- *Machine learning in the Chinese stock market*（JFE 2021，DOI [10.1016/j.jfinec.2021.08.017](https://doi.org/10.1016/j.jfinec.2021.08.017)）：中国市场中流动性是重要预测变量，短期可预测性和小盘股暴露会显著放大交易成本；因此本轮把换手和市值相关性作为硬诊断。
- Bryzgalova, Pelger & Zhu, *Forest through the Trees*（JF 2025，DOI [10.1111/jofi.13477](https://doi.org/10.1111/jofi.13477)）：交互有效，但强调低维、可解释、样本外的树结构和稳健选择；论文同时指出直接用预测组合并不自动得到好的资产定价组合。
- *Pooling and winsorizing machine learning forecasts to predict stock returns with high-dimensional data*（J Empirical Finance 2024，DOI [10.1016/j.jempfin.2024.101538](https://doi.org/10.1016/j.jempfin.2024.101538)）：单个 ML 模型易失效，截尾与池化能改善样本外稳定性。本轮只检验其低自由度、可因果实现的输出层版本。
- Freyberger, Neuhierl & Weber, *Dissecting Characteristics Nonparametrically*（RFS 2019，DOI [10.1093/rfs/hhz123](https://doi.org/10.1093/rfs/hhz123)）及 *Monotonic effects of characteristics on returns*（AOAS 2020，DOI [10.1214/20-AOAS1351](https://doi.org/10.1214/20-AOAS1351)）：非线性应受到稳健性和单调性约束，不能通过自由调参追逐历史收益。

## 固定候选

信号先做每日横截面秩，之后只使用前一信号期的输出做因果池化；权重在评分前固定，未按结果回调：

1. `POOL_RANK_EMA0.5`：当前秩信号 50% + 上一期池化信号 50%。
2. `POOL_RANK_EMA0.75`：当前 75% + 上一期 25%。
3. `POOL_WINSOR5_EMA50`：当前秩信号先截到当日 5%/95% 分位，再按 50%/50% 池化。

这不是重新训练模型，也没有使用未来标签；来源模型是[严格滚动原始 60 特征树](/data/games/factor_/research_reports/platform_alignment/original60-walkforward-20261012/summary.md)。

## 结果

| 候选 | 窗口 | RankIC | S_i | 毛超额 | 换手/次 | 净超额 | 2026 复利净超额 | size 相关 | 日度最大回撤 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BASE | 五年 | 0.1185 | 0.0658 | 14.50% | 40.93% | **8.31%** | 2.92% | -0.242 | 39.47% |
| POOL_RANK_EMA0.5 | 五年 | 0.1105 | 0.0494 | 14.78% | 25.79% | **10.89%** | 6.12% | -0.258 | 37.93% |
| POOL_RANK_EMA0.75 | 五年 | 0.1163 | 0.0597 | 14.61% | 32.96% | **9.63%** | 4.72% | -0.249 | 39.03% |
| POOL_WINSOR5_EMA50 | 五年 | 0.1101 | 0.0490 | 14.72% | 26.03% | **10.79%** | 6.05% | -0.258 | 37.77% |


近期窗口单列如下：

| 候选 | RankIC | S_i | 毛超额 | 换手/次 | 净超额 | 复利净超额 | size 相关 |
|---|---:|---:|---:|---:|---:|---:|---:|
| BASE | 0.0942 | 0.0255 | 10.74% | 35.94% | 5.30% | 2.92% | -0.552 |
| POOL_RANK_EMA0.5 | 0.0926 | 0.0228 | 11.82% | 20.27% | 8.76% | 6.12% | -0.610 |
| POOL_RANK_EMA0.75 | 0.0944 | 0.0245 | 11.40% | 27.52% | 7.24% | 4.72% | -0.579 |
| POOL_WINSOR5_EMA50 | 0.0923 | 0.0227 | 11.80% | 20.63% | 8.69% | 6.05% | -0.610 |

基线（原始严格滚动树）五年净超额为 8.31%、换手 40.93%。最佳 `POOL_RANK_EMA0.5` 将换手降至 25.79%，净超额升至 10.89%，日度复利超额从 8.27% 升至 11.47%；RankIC 从 0.1185 降至 0.1105，说明收益改善主要来自交易成本而非新增预测信息。`POOL_RANK_EMA0.75` 是折中档，净超额 9.63%、换手 32.96%。5% 截尾与 50% 池化几乎等同于 EMA50，暂未看到独立的截尾增益。

近期 2026 年，EMA50 的复利净超额为 6.12%，高于基线 2.92%；但 size 相关从基线 -0.552 变为 -0.610，市值暴露没有改善。三者都没有达到正式新席门槛 `S_i ≥ 0.035`、净超额约 15%、换手不高于 40% 且池级边际为正的组合准入要求。

## 防未来函数与范围

- 原始模型仍是季度首日重训，训练标签退出日严格早于测试首日；本轮只读取其测试期输出。
- 池化递推只引用当前及过去信号日，未使用未来信号或未来标签。
- 五年窗口固定为 `20210907–20260907`，近期窗口单独为 2026 年；全 A、qfq、`total_mv`、label-1、10 组和 0.30% 单边成本沿用对齐规则。
- 结果基于此前已查看的历史数据，不是全新盲测；本轮没有重新搜索权重。

## 决策

保留 `POOL_RANK_EMA0.5` 作为“交易成本稳健化”研究素材，不作为新簇、不进入现役池，也不直接申请平台测试。它证明输出层因果池化比继续增加树复杂度更有希望，但当前仍有明显负 size 暴露、S_i 和绝对净额不足。下一轮若要继续，只应做一次预声明的池级加席诊断或单调约束树对照，不能再扫描 EMA 窗口。

代码哈希：`0eac6724f36d9e2a0e1efeeba0aa509fa342f3a4e47b01d33553bb205bc816bf`。完整数值见 [`results.csv`](/data/games/factor_/research_reports/platform_alignment/nonlinear-paper-robust-20261012/results.csv)，协议见 [`protocol.json`](/data/games/factor_/research_reports/platform_alignment/nonlinear-paper-robust-20261012/protocol.json)。
