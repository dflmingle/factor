# PandaAI 因子研究

这是一个基于 PandaAI 因子平台的 A 股因子研究工作区，记录研报复现、因子公式、组合构造和统一口径回测结果。

## 内容

- `*.formula`、`*.txt`、`*.py`：候选因子公式和研究脚本
- `*.report.md`、`*.report.csv`：PandaAI 回测结果摘要
- `*.retrospective.md`：因子归因、相关性和后续决策记录
- `research_reports/`、`sources/`：研报归档和可检索文本
- `*.results/`：已保存的 PandaAI 原始运行结果
- `vendor/skill-pandaai-factor-online/`：随项目保存的 PandaAI Skill 快照
- `scripts/pandaai.py`：跨电脑调用 Skill 脚本的统一入口
- `scripts/start.py`：换电脑后的环境安装、预检和登录入口
- `scripts/local_recheck_data.py`：本地 Tushare 复现数据的导出、导入和校验
- `scripts/diagnose_turnover_alignment.py`：平台/本地换手可比性与成本敏感性诊断
- `scripts/search_field_policy.py`：GP/GFN 共用的已验证字段搜索边界
- `scripts/build_alignment_failure_registry.py`：登记 `>5pp` 不可接受差异并聚合字段风险
- `data/local_recheck/factor-local-recheck-data.tar.gz`：通过 Git LFS 管理的本地复现数据快照

## 默认研究口径

- 回测窗口：2021-09-07 至 2026-09-07
- 调仓周期：10 个交易日
- 分组：10 组
- 单边交易成本：0.3%
- 股票池：PandaAI CLI 默认的沪深全 A

回测结果是历史样本研究记录，不代表未来收益，也不构成投资建议。仓库不包含 PandaAI 登录凭据；重新运行需要本地配置已登录的 `pandaai-cli`。

换电脑继续研究请阅读 [`CONTINUE.md`](./CONTINUE.md)；启动规则见 [`START.md`](./START.md)。本地 Tushare 复现数据通过 Git LFS 随仓库获取。

## 平台/本地对齐复现

所有已保存平台因子和新接入因子都遵守 [`ALIGNMENT_RULES.md`](./research_reports/platform_alignment/ALIGNMENT_RULES.md)，当前规则版本为 `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`。正式口径固定为沪深全 A、qfq、`daily_basic.total_mv`、20180101 暖机、平台信号日期、label-1、10 组、`factor_valid` 基准和单边 0.30% 成本；正式净超额使用本地实际成员换手。

平台只有汇总换手时，复现结果还会输出 `turnover_alignment` 和 `platform_turnover_cost_sensitivity`。后者是敏感性诊断，不能代替本地正式净超额或被解释为平台逐期持仓已恢复。换电脑先按 [`CONTINUE.md`](./CONTINUE.md) 恢复 Git LFS 数据，再执行：

```bash
python scripts/diagnose_turnover_alignment.py
python scripts/build_alignment_failure_registry.py
```

净超额绝对差超过 `5pp` 才算不可接受。失败登记表会记录具体公式字段、算子、路径指标和原因；只有重复失败且没有通过证据的字段才会被 GP/GFN 默认搜索排除，单字段尚未证实的问题只作为 `suspect` 诊断，不会误伤已验证字段。

## AlphaPROBE GFlowNet 本地挖掘

默认使用 512 个交易日暖机，以覆盖嵌套时间窗口表达式。

`scripts/alphaprobe_gfn_tushare.py` 使用 AlphaPROBE 的 GFlowNet 轨迹平衡搜索器，读取本地 Tushare qfq 与 `daily_basic` 全 A 缓存，不调用 PandaAI 回测接口。当前兼容依赖固定在 [`requirements-alphaprobe-gfn.txt`](./requirements-alphaprobe-gfn.txt)；AlphaPROBE 源码按 `torchgfn 1.2.1` API 运行。

训练和逐因子评估使用统一 label-1、5 日周期和全 A 口径：

```bash
python -m pip install -r requirements-alphaprobe-gfn.txt
python scripts/alphaprobe_gfn_tushare.py --device cuda:0 --ic-objective signed_positive --feature-set verified --backtrack-days 512 --net-excess-weight 0.10 --net-excess-scale 0.10 --output quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive_verified_net_reward_run1
python scripts/alphaprobe_gfn_tushare.py --device cuda:0 --ic-objective signed_positive --output quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive
python scripts/evaluate_alphaprobe_gfn_tushare.py --device cuda:0 --run-dir quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_signed_positive
```

默认目标是 `signed_positive`：单因子 IC 保留符号，只接收正 IC 候选；因子间互相关仍取绝对值。旧的绝对 IC 行为可显式使用 `--ic-objective absolute`。训练结果包含 `final_pool.json`、`training_history.json`、检查点和 `factor_metrics.csv`；本轮正 IC 结果摘要见 [`research_reports/alphaprobe_gfn_tushare_cycle5_signed_positive_run1/`](./research_reports/alphaprobe_gfn_tushare_cycle5_signed_positive_run1/)。

对齐挖掘默认只开放已经通过 `qualitygate1` 的字段集合；`fundamental_core`、`all_active` 和自定义未验证字段必须显式使用 `--allow-unverified-fields`，否则不能作为平台代理搜索空间。AlphaPROBE 的本地 `VWAP` 是 `AMOUNT/VOLUME` 代理，输出到 PandaAI 前必须转换成平台公式字段，不把 `$vwap` 直接提交。

默认的 `--net-excess-weight 0.10 --net-excess-scale 0.10` 会把训练区间内、按当前对齐契约计算的成本后多头净超额通过 `weight * tanh(net_excess / scale)` 加入 reward；净超额只读训练区间，验证集和测试集只用于事后评估，避免泄漏。评估报告会同时写出每个因子的 `gross_excess`、`turnover`、`annual_cost` 和 `net_excess`。设为 `--net-excess-weight 0` 可复现不含净超额 reward 的旧搜索行为。

最近一轮正式结果保存在 [`research_reports/alphaprobe_gfn_tushare_cycle5_signed_positive_fundamental_net_reward_run1_eval/`](./research_reports/alphaprobe_gfn_tushare_cycle5_signed_positive_fundamental_net_reward_run1_eval/)：测试期最佳单因子 `Div($vwap,$high)` 净超额 `14.50%`，但 50 因子 ensemble 净超额 `-8.11%`，仍需按单因子和换手分别筛选，不能把 ensemble 的 IC 直接当作成本后通过。
