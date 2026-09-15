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
- `data/local_recheck/factor-local-recheck-data.tar.gz`：通过 Git LFS 管理的本地复现数据快照

## 默认研究口径

- 回测窗口：2021-09-07 至 2026-09-07
- 调仓周期：10 个交易日
- 分组：10 组
- 单边交易成本：0.3%
- 股票池：PandaAI CLI 默认的沪深全 A

回测结果是历史样本研究记录，不代表未来收益，也不构成投资建议。仓库不包含 PandaAI 登录凭据；重新运行需要本地配置已登录的 `pandaai-cli`。

换电脑继续研究请阅读 [`CONTINUE.md`](./CONTINUE.md)；启动规则见 [`START.md`](./START.md)。本地 Tushare 复现数据通过 Git LFS 随仓库获取。

## AlphaPROBE GFlowNet 本地挖掘

`scripts/alphaprobe_gfn_tushare.py` 使用 AlphaPROBE 的 GFlowNet 轨迹平衡搜索器，读取本地 Tushare qfq 与 `daily_basic` 全 A 缓存，不调用 PandaAI 回测接口。当前兼容依赖固定在 [`requirements-alphaprobe-gfn.txt`](./requirements-alphaprobe-gfn.txt)；AlphaPROBE 源码按 `torchgfn 1.2.1` API 运行。

训练和逐因子评估使用统一 label-1、5 日周期和全 A 口径：

```bash
python -m pip install -r requirements-alphaprobe-gfn.txt
python scripts/alphaprobe_gfn_tushare.py --device cuda:0 --output quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5
python scripts/evaluate_alphaprobe_gfn_tushare.py --device cuda:0 --run-dir quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5
```

训练结果包含 `final_pool.json`、`training_history.json`、检查点和 `factor_metrics.csv`。当前最近一次全量训练结果位于 `quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gfn_tushare_cycle5_run2/`。
