# 疯猫子单因子本地复现：六轮 GP 结果

日期：2026-10-11

目标因子：`xplr-d3c-r6-grpvol`（公开榜单线索；公式和逐股票信号未公开）

## 结论

这次实际完成了 6 轮遗传编程搜索：continuous、slow、hybrid 三种搜索配置，各 2 个随机种子；每轮 96 个体 × 10 代，最多 5,760 次遗传评估，共保存 2,982 个不同公式（2,421 个有效公式）。

第一版搜索曾把市值叶子留在可组合空间，最优结果被识别为小市值捷径，已作废。本轮移除 `size` 叶子，并对绝对市值相关性超过 0.30 的候选施加惩罚；最终候选均通过独立 pandas 复核和前缀截断检查。

## 三条冻结候选

| 候选 | 公式摘要 | 五年净超额 | 训练净超额 | 2024–2025 验证 | 2026 近期 | 五年换手 | 市值相关 |
|---|---|---:|---:|---:|---:|---:|---:|
| `FM_MULTI_01` | `Sub(Blend5(lowvolume20,Grp5(lowturn,vol6)),Add(Mul(lowvolume60,lowvolume20),vol252))` | 2.83% | 16.31% | -13.38% | 3.51% | 13.3% | -0.204 |
| `FM_MULTI_02` | `Resid5(Add(lowvolume3,Resid5(GZ5(lowvolume20,volshift60),GZ3(vstab20,rev120))),Add(lowvolume20,vol252))` | 2.46% | 14.36% | -11.70% | 2.59% | 26.0% | -0.237 |
| `FM_MULTI_03` | `Resid5(Add(lowvolume3,Resid5(Neg(vol252),Add(lowvolume3,Neg(vol252)))),Add(lowvolume20,vol252))` | 3.19% | 14.67% | -10.57% | 3.59% | 20.6% | -0.191 |

口径：沪深全 A `.SH/.SZ`、qfq、`daily_basic.total_mv`、20180101 暖机、平台保存信号日期、`close(t+1) -> close(t+11)` 标签、10 组最高组、`factor_valid` 基准、单边成本 0.30%、算术年化。近期窗口只有 15 期，只能作诊断，不能替代正式五年结果。

## 与榜单线索的差距

公开榜单线索的 IC 为 0.172279、ICIR 为 1.661321、IC 胜率为 0.932773（119 期）。本地候选正式窗口 IC 约 0.036–0.040、ICIR 约 0.287–0.310，且 2024–2025 验证全部显著转负。因此不能声称已经复现，也不应把训练期 14–16% 净超额当成发现。

## 工程与审计状态

- 独立核验：720 个候选×窗口 period 记录通过；IC 最大绝对差约 `1.26e-9`，属于跨版本 Spearman 浮点误差。
- 前缀截断：3 条候选共 909,787 个有效单元，掩码一致、最大差为 0。
- 进程峰值约 0.46 GiB，低于 2.25 GiB 上限；平台算力消耗为 0。
- GFlowNet / AlphaPool 未执行：系统 PyTorch 的 `c10.dll` 初始化失败，隔离 CPU torch 下载又遇临时磁盘空间错误；没有伪造结果。
- 未提交 PandaAI、未入比赛池。当前结果不足以支持继续扩大搜索；若要下一轮，应先改变假设或引入可核验的新字段，而不是继续堆 GP 代数。

详细数据见 [`results.csv`](results.csv)、[`verification.json`](verification.json)、[`frozen_models.json`](frozen_models.json) 和搜索脚本 [`fengmao_multiround_20261011.py`](../../../scripts/fengmao_multiround_20261011.py)。
