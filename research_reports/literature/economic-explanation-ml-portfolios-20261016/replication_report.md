# 论文复现报告：From Economic Explanation to Performance Improvement in Machine-Learning Portfolios

> 2026-10-16 归档审计：本页结果保留为探索记录。树分支 model_pred_attr 将 pred_contrib 最后一列 expected value 错当预测，不能据此判定 LightGBM 本身失效；跨模型归因也受影响。10 日网格的 12 期约半年、24 期约一年，正文“年度块”等表述不准确。尚未修复重跑，不作为论文完整复现或平台候选依据。五席直接组合另有成本、支持集与跨块持仓问题，见 direct_pool/report.md。Meta-label 后续修账见相邻 ledger-v2 报告。

论文：Liang, Zohren & Cucuringu，arXiv:2610.15144（2026）。本报告记录在中国 A 股因子面板上的本地代理复现，不把代理结果当作论文的字节级复现。

## 复现内容

- 18 个已有中国全 A 特征；10 个交易日标签/调仓周期。
- 每期取 `total_mv` 最大的 1500 只股票；LightGBM 作为 XGB 代理，PyTorch 两层 FFN 作为 FFN 代理。
- 24 个训练期 + 12 个验证期，随后 10 个年度 OOS 块；本地 2018 年起数据不足以复制论文 4 年训练 + 1 年验证。
- 验证期计算净 Sharpe 特征归因，按论文形式使用 `1 + 0.5*tanh(attribution/sd)` 调整暴露，并把暴露限制在 `[0,3]`。稳定化规则递归继承上一 OOS 块暴露；跨模型规则使用可用模型归因的平均值。
- 论文成本口径为单边 5bp；另计算项目单边 30bp 敏感性。
- 所有归因只使用前一验证块，训练、验证、测试时间段不重叠；没有平台调用。

## 结果（120 个 OOS 期，5bp 单边成本）

| 配置 | 净 Sharpe | 毛 Sharpe | 年化净收益 | 年化毛收益 | 期均换手 | 最大回撤 | 30bp 敏感性净收益 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ffn/baseline | 0.183 | 0.391 | 1.01% | 2.15% | 90.77% | 11.02% | -4.71% |
| ffn/unstabilised | 0.703 | 0.900 | 4.00% | 5.12% | 89.03% | 10.18% | -1.61% |
| ffn/stabilised | 0.566 | 0.754 | 3.12% | 4.15% | 81.81% | 9.50% | -2.04% |
| ffn_cm/unstabilised | 0.138 | 0.327 | 0.81% | 1.92% | 88.45% | 10.99% | -4.76% |
| ffn_cm/stabilised | 0.538 | 0.720 | 3.33% | 4.46% | 89.44% | 11.41% | -2.31% |
| lgb/baseline | -0.160 | -0.129 | -2.54% | -2.05% | 38.68% | 28.44% | -4.97% |
| lgb/unstabilised | -0.160 | -0.129 | -2.54% | -2.05% | 38.68% | 28.44% | -4.97% |
| lgb/stabilised | -0.160 | -0.129 | -2.54% | -2.05% | 38.68% | 28.44% | -4.97% |
| lgb_cm/unstabilised | -0.160 | -0.129 | -2.54% | -2.05% | 38.68% | 28.44% | -4.97% |
| lgb_cm/stabilised | -0.160 | -0.129 | -2.54% | -2.05% | 38.68% | 28.44% | -4.97% |

FFN 基线的总体净 Sharpe 为 0.183。模型特异的未稳定化干预升至 0.703，稳定化为 0.566；稳定化把平均换手从 90.77% 降到 81.81%，下降 8.96 个百分点。跨模型稳定化在 FFN 上得到 0.538，换手 89.44%，也高于基线，但弱于 FFN 模型特异稳定化。

LightGBM/XGB 代理的基线净 Sharpe 为 -0.160，且多期预测几乎为常数，导致归因为空或没有可用的暴露干预；因此其干预结果与基线相同。这是代理模型失效诊断，不能解读为论文方法在 XGB 上无效。

在项目单边 30bp 成本下，FFN 模型特异稳定化的年化净收益仍为 -2.04%，未达到可交易准入线。说明论文方法在当前中国 A 股代理中有降低换手和改善风险调整收益的信号，但尚不能证明能覆盖项目的真实交易成本。

## 与论文结果对照

论文报告的美国大盘样本结果为：FFN 净 Sharpe 0.5750 → 稳定化 0.8250，日均换手 26.70% → 13.02%；XGB 的跨模型稳定化约 0.6175 → 0.7559。我们的样本、特征定义、目标函数、股票池和成本都不同，因此这里只比较方向：FFN 模型特异稳定化同时提高净 Sharpe、降低换手；跨模型稳定化的方向为正；XGB 代理没有形成有效结论。

## 审计与限制

- 已修复无效股票收益的 `0 * NaN` 传播；所有期收益、换手和回撤结果现为有限值。
- 18 个特征在保存的平台信号日期上与源面板完成重合校验；验证归因行共 20 行，其中 2024-03-05 的 LightGBM 归因因验证期收益无离散度而未定义，跨模型归因使用 FFN 的可用归因。
- 论文使用自定义 Sharpe 优化 XGB、美国残差特征和 Shapley/一阶传播；本地使用 LightGBM 回归与 `pred_contrib`、FFN gradient-times-input，属于方法结构代理。
- 当前结果是研究诊断，未纳入正式因子池，也未提交 PandaAI 平台。

## 产物

- 脚本：[`scripts/economic_explanation_ml_portfolios_20261016.py`](/data/games/factor_/scripts/economic_explanation_ml_portfolios_20261016.py)
- 结果表：[`results.csv`](/data/games/factor_/research_reports/literature/economic-explanation-ml-portfolios-20261016/results.csv)
- 验证归因：[`validation_net_sharpe_attributions.csv`](/data/games/factor_/research_reports/literature/economic-explanation-ml-portfolios-20261016/validation_net_sharpe_attributions.csv)
- 时间块与暴露：[`block_log.csv`](/data/games/factor_/research_reports/literature/economic-explanation-ml-portfolios-20261016/block_log.csv)
- 复现校验：[`verification.json`](/data/games/factor_/research_reports/literature/economic-explanation-ml-portfolios-20261016/verification.json)
