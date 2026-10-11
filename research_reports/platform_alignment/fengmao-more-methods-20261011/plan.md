# 疯猫子公开线索：多算法本地研究

用户于 2026-10-11 明确要求增加方法（例如 AlphaGen）。本轮继续使用已有公开因子名 `xplr-d3c-r6-grpvol` 的分组/量能线索。私有公式和逐股票信号不可见，本研究探索候选机制，不声称公式精确复现。

## 预先冻结的研究设计

| 方法 | 实际复用 | 预算 | 适配边界 |
|---|---|---|---|
| AlphaGen PPO | 仓库 `LSTMSharedNet` + `sb3_contrib.MaskablePPO` | 两种子，每种子 6,144 token steps | 后缀表达式语法、因果原子面板和奖励为本地适配；不是原论文默认 StockData 环境 |
| GFlowNet | 原生 PyTorch trajectory balance | 96 × 16 = 1,536 条轨迹 | 从训练前沿选择带正负号的 ≤3 成分子集，非完整 torchgfn 公式 token 引擎 |
| AlphaGen AlphaPool | 直接调用仓库原始 `AlphaPool` | 6 成分、3 档 L1 正则 | 参数按训练数据选择，原始优化函数不修改；最终有效股票取成分交集 |

额外把上一轮 GP 的训练前沿 32 个公式按新奖励重评，作为 GFN/AlphaPool 的可复用库；不重新运行六轮 GP。PPO 的候选只从本轮 PPO 自己生成的公式中选。最终只冻结三条模型（两种子 PPO 的训练优胜、GFN、AlphaPool），不按验证表现换人。

奖励以比赛信号质量代理为主：`S_i + .15 * 最弱训练三分段RankIC - .06 * 换手 - .25 * max(逐期绝对市值相关均值-.30, 0) - .05 * max(-净超额, 0)`。绝对市值相关超过 .50 或非正 Pearson IC 再罚 .20；不单独最大化净额。对照 GOAL.md：避免 size 伪装、均值中性化作弊，以及只看 IC 不计成本。

## 数据与口径

复用 `fengmao-multiround2-20261011/atoms.npz`，只读取 qfq close、volume、turnover、`daily_basic.total_mv` 的因果原子；删除可组合的 size 叶子。没有真实 amount/high/low，不添加伪成交额。暖机 20180101，沪深全 A，不附加 ST/次新过滤。

固定 10 日、10 分组、最高十分组、`close(t+1)->close(t+11)` 标签、factor_valid 基准、单边 0.30% 成本和算术年化。参考日期为保存 H03-T10 的平台模板；对手具体调仓日未知，因此对私有因子仅为日期代理。规则版本 `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate4`。

训练截至 2023-12-29，并去掉标签退出日越界记录；2024–2025 历史验证同样净化边界；2026 单独诊断。正式五年窗口名义为 20210907..20260907，实际可用信号模板截至 20260810。验证历史已在以前研究中被看过，不能称纯净样本外。

## 资源与审计

平台预算 0。单进程、BLAS/PyTorch 单线程；进程 RSS/私有内存上限 2.25 GiB，系统可用内存底线 1.25 GiB，0.5 秒看门狗。使用本机已存在且可导入的 `easyrl4rec` PyTorch 2.2.1 CPU 环境；额外只安装两个小包 stable-baselines3 2.3.2 和 sb3-contrib 2.3.0，没有重装 PyTorch。

保存所有唯一训练公式（含无效）、轨迹进度、PPO/GFN 检查点、冻结模型、逐期指标和 Top20。最后独立 pandas 核验实际十组/换手/成本；在固定 100 股票、两个截止日上从真实日度输入重建全部原子和冻结模型，检查截断前历史信号是否改变。这不是平台 Python 源码提交认证，将来提交仍需 platform_precheck/repaint_check。

遵循仓库 PandaAI Skill 的训练/验证区分、交易成本和研究登记要求；本轮是获授权的本地研究，没有平台创建、回测或池修改。

## 续跑与核验

在项目根目录使用已验证的本机环境：

```powershell
D:\anaconda3\envs\easyrl4rec\python.exe -u -X utf8 scripts/fengmao_more_methods_20261011.py --resume
python -u -X utf8 scripts/verify_fengmao_more_methods_20261011.py
```

第一次运行不用 `--resume`。续跑复用已经完成的 PPO 轮、GFN 和 AlphaPool；未完成的 PPO 轮没有中途策略检查点，需要从该轮种子重新训练，但唯一训练公式缓存仍被保留，已完成轮不会重跑。不能用不同随机种子或奖励覆盖该目录。

AlphaPool 只调用线性内存的 Pearson 相关路径；不在全 A 面板调用仓库原始 `batch_spearmanr`（其并列处理会生成股票×股票矩阵）。正式指标的 Spearman 由 SciPy/pandas 逐截面完成。
