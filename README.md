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

## 默认研究口径

- 回测窗口：2021-09-07 至 2026-09-07
- 调仓周期：10 个交易日
- 分组：10 组
- 单边交易成本：0.3%
- 股票池：PandaAI CLI 默认的沪深全 A

回测结果是历史样本研究记录，不代表未来收益，也不构成投资建议。仓库不包含 PandaAI 登录凭据；重新运行需要本地配置已登录的 `pandaai-cli`。

换电脑继续研究请阅读 [`CONTINUE.md`](./CONTINUE.md)；启动规则见 [`START.md`](./START.md)。
