# 疯猫子公开线索：AlphaGen / GFlowNet / AlphaPool 多方法复现

日期：2026-10-11

目标：公开榜单因子 `xplr-d3c-r6-grpvol`。对手公式和逐股票信号未公开，因此本轮是机制探索，不是精确公式复现。

## 结果先看

| 候选 | 方法 | 五年净超额 | 训练净超额 | 2024–2025 验证 | 2026 近期 | 五年换手 | 五年绝对市值相关 |
|---|---|---:|---:|---:|---:|---:|---:|
| `FM_MORE_01` | AlphaGen PPO（seed 20261101） | **-1.94%** | 5.62% | **-9.17%** | -5.70% | 36.7% | 0.196 |
| `FM_MORE_02` | TB-GFN | **3.84%** | 14.77% | **-8.21%** | 3.58% | 16.4% | 0.197 |
| `FM_MORE_03` | 原始 AlphaPool | **1.11%** | 10.74% | **-9.50%** | 0.91% | 26.3% | 0.197 |

结论：这轮确实增加了 AlphaGen、GFlowNet、AlphaPool 三种方法，但没有得到稳定的榜首级信号。`FM_MORE_02` 比上一轮三条 GP 候选的验证负值稍好，但仍然是明显负收益，不能进比赛池，也不能称为复现成功。

对照榜单公开线索：IC `0.172279`、ICIR `1.661321`、IC 胜率 `0.932773`（119 期）。本地三条正式 IC 约 0.040–0.044、ICIR 约 0.273–0.292，仍与公开结果有数量级差距。

## 算法执行情况

- AlphaGen：复用项目 AlphaPROBE 的 `LSTMSharedNet`，用 `MaskablePPO` 做后缀表达式搜索；两个随机种子各 6,144 token steps，约各 706 条完整轨迹、约 700 个不同公式。
- GFlowNet：原生 PyTorch trajectory-balance，1,536 条轨迹，在 8 条训练前沿上做带正负号的最多 3 成分组合。最终最优实际回到了上一轮 GP 前沿的低换手组合，说明当前前沿上 GFN 更像筛选器而非新信息源。
- AlphaPool：直接调用仓库原始 `alphagen.models.alpha_pool.AlphaPool`，对 6 个训练前沿成分测试 3 档 L1 正则；权重只用训练窗选择。
- 总训练公式缓存 1,857 条，其中 1,855 条有效；全部在验证前冻结。

代表公式：

```text
FM_MORE_01 = Sub(Grp5(Sub(lowvolume3,volshift20),Blend3(smoothvol20,vrel3)),vol120)
FM_MORE_02 = Resid5(Add(lowvolume3,Neg(vol252)),Mul(lowvolume20,vol252))
```

`FM_MORE_02` 主要是低成交量与长期波动/交叉截面残差；它的正式五年净额只有 3.84%，2024–2025 仍为 -8.21%。AlphaPool 的训练权重主要集中在相同低成交量/波动族，三个正则档的结构没有实质分化。

## 口径、核验和资源

沿用当前对齐契约：沪深全 A `.SH/.SZ`、qfq、`daily_basic.total_mv`、20180101 暖机、保存的平台信号日期模板、10 日周期、10 组最高组、`close(t+1) -> close(t+11)`、`factor_valid` 基准、单边成本 0.30%、算术年化。未引入真实 amount/high/low，也没有把 volume×price 当成交额。

- 独立 pandas 核验：711 条候选×窗口 period 记录通过；IC 最大绝对差 `1.34e-9`。
- 三条候选的十组成员、换手、成本、Top20 均复核通过。
- 训练标签边界重新核对，未把退出日越过训练截止日的记录混入训练。
- 固定 100 只股票、两个截止日，用真实日度输入重建原子和冻结模型：qfq label-1 / total_mv 缓存一致，所有历史值最大差 0。
- 训练进程峰值约 **0.58 GiB**，低于 2.25 GiB 上限；系统可用内存最低约 2.13 GiB；平台算力 0。

因果审计是本地数组/表达式审计，不等同于 PandaAI Python 提交前的 `platform_precheck.py` / `repaint_check.py`。

## 决策

本轮三种算法不入池、不上平台确认。理由不是算法名称不够多，而是三种方法都在 2024–2025 验证期转负，且 AlphaPool/GFlowNet 的有效增益集中在已有低成交量-波动族。下一轮若继续，应更换数据假设或引入可验证的新信号族；单纯增加 PPO/GFN 轨迹数量预计只会重复这一族，不自动开启。

详细结果：[results.csv](results.csv)、[models_frozen.json](models_frozen.json)、[verification.json](verification.json)、[plan.md](plan.md)。
