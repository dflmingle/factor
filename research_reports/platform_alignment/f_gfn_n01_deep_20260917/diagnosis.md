# F-GFN-N01 深度诊断 2

本报告只读取已保存的平台运行结果和本地 Tushare 缓存，不创建因子、不发起平台回测。

- 规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`；正式规则文档：`research_reports/platform_alignment/ALIGNMENT_RULES.md`
- 正式公共口径：全 A、qfq、`total_mv`、10 组、`factor_valid`、0.30% 单边成本
- 诊断结果目录：`/data/games/factor_/research_reports/platform_alignment/f_gfn_n01_deep_20260917`；raw 只覆盖本地已有的 2024 文件，不能替代正式全量结果。

## 结论

1. `AMOUNT` 乘 `0.1/1/10/100` 是正的统一标量；本地逐信号日排序完全不变，所以金额单位换算不能抹平 N01 差异。
2. qfq/raw、HIGH/CLOSE 和 label=0/1 的组合没有同时接近平台的 RankIC、收益路径和换手；切换标签或复权不能作为正式修复。
3. 左结合 `(AMOUNT/VOLUME)/HIGH` 与右结合 `AMOUNT/(VOLUME/HIGH)` 是不同因子；右结合仅是解析敏感性，若结果仍不过质量门槛，也不能据此改平台公式。
4. 已保存结果和在线 `factor_result` 都没有逐票因子值下载 URL；Top20 日期晚于图表最后日期，且 20 个展示因子值相同。Top20 只能标记为展示异常，不能证明本地排序错误的具体方向。
5. N01 继续保持 `unsupported`，不进入本地因子挖掘池；下一步需要平台提供逐票因子值或逐期持仓明细，才能继续定位字段语义。

## 组合结果

`gross`/`net` 是本地正式代理值；平台列是保存结果摘要；`rank corr` 和 `excess corr` 是与平台图表逐期序列的相关性。

| variant | scope | label | periods | RankIC local/platform | rank corr | gross local/platform | excess corr | net local/platform | turnover local/platform |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qfq_high_left__qfq_return | qfq | 1 | 241/241 | 0.0342/-0.0046 | -0.545 | 11.44%/1.70% | 0.338 | 9.72%/-8.49% | 5.71%/33.70% |
| qfq_high_left__qfq_return | qfq | 0 | 241/241 | 0.0352/-0.0046 | -0.393 | 11.54%/1.70% | 0.267 | 9.82%/-8.49% | 5.71%/33.70% |
| qfq_close_left__qfq_return | qfq | 1 | 241/241 | 0.0193/-0.0046 | -0.319 | 8.32%/1.70% | 0.244 | 6.01%/-8.49% | 7.63%/33.70% |
| qfq_close_left__qfq_return | qfq | 0 | 241/241 | 0.0230/-0.0046 | -0.160 | 11.34%/1.70% | 0.162 | 9.03%/-8.49% | 7.63%/33.70% |
| qfq_high_right__qfq_return | qfq_parser_sensitivity | 1 | 241/241 | -0.0407/-0.0046 | 0.698 | -13.46%/1.70% | 0.359 | -14.88%/-8.49% | 4.70%/33.70% |
| qfq_high_right__qfq_return | qfq_parser_sensitivity | 0 | 241/241 | -0.0384/-0.0046 | 0.592 | -13.35%/1.70% | 0.204 | -14.77%/-8.49% | 4.70%/33.70% |
| qfq_close_right__qfq_return | qfq_parser_sensitivity | 1 | 241/241 | -0.0405/-0.0046 | 0.696 | -13.58%/1.70% | 0.361 | -14.97%/-8.49% | 4.59%/33.70% |
| qfq_close_right__qfq_return | qfq_parser_sensitivity | 0 | 241/241 | -0.0381/-0.0046 | 0.591 | -13.36%/1.70% | 0.207 | -14.75%/-8.49% | 4.59%/33.70% |
| raw_high_left__qfq_return | raw_factor_qfq_return | 1 | 48/48 | 0.0353/-0.0208 | -0.770 | -5.42%/1.70% | -0.132 | -27.07%/-8.49% | 71.60%/33.70% |
| raw_high_left__qfq_return | raw_factor_qfq_return | 0 | 48/48 | 0.0761/-0.0208 | -0.723 | 5.50%/1.70% | -0.057 | -16.15%/-8.49% | 71.60%/33.70% |
| raw_close_left__qfq_return | raw_factor_qfq_return | 1 | 48/48 | 0.0101/-0.0208 | 0.332 | -8.18%/1.70% | 0.188 | -33.91%/-8.49% | 85.08%/33.70% |
| raw_close_left__qfq_return | raw_factor_qfq_return | 0 | 48/48 | -0.0045/-0.0208 | 0.312 | -22.07%/1.70% | 0.067 | -47.79%/-8.49% | 85.08%/33.70% |
| raw_high_left__raw_return | raw | 1 | 48/48 | 0.0331/-0.0208 | -0.772 | -7.08%/1.70% | -0.129 | -28.73%/-8.49% | 71.60%/33.70% |
| raw_high_left__raw_return | raw | 0 | 48/48 | 0.0712/-0.0208 | -0.728 | 2.58%/1.70% | -0.049 | -19.07%/-8.49% | 71.60%/33.70% |
| raw_close_left__raw_return | raw | 1 | 48/48 | 0.0092/-0.0208 | 0.332 | -6.86%/1.70% | 0.183 | -32.59%/-8.49% | 85.08%/33.70% |
| raw_close_left__raw_return | raw | 0 | 48/48 | -0.0018/-0.0208 | 0.315 | -19.33%/1.70% | 0.058 | -45.06%/-8.49% | 85.08%/33.70% |
| raw_high_right__raw_return | raw_parser_sensitivity | 1 | 48/48 | -0.0501/-0.0208 | 0.484 | -19.06%/1.70% | 0.493 | -20.47%/-8.49% | 4.66%/33.70% |
| raw_high_right__raw_return | raw_parser_sensitivity | 0 | 48/48 | -0.0471/-0.0208 | 0.396 | -21.00%/1.70% | 0.226 | -22.41%/-8.49% | 4.66%/33.70% |
| raw_close_right__raw_return | raw_parser_sensitivity | 1 | 48/48 | -0.0501/-0.0208 | 0.479 | -19.56%/1.70% | 0.494 | -20.97%/-8.49% | 4.69%/33.70% |
| raw_close_right__raw_return | raw_parser_sensitivity | 0 | 48/48 | -0.0467/-0.0208 | 0.392 | -21.24%/1.70% | 0.227 | -22.66%/-8.49% | 4.69%/33.70% |

## AMOUNT 单位不变量

- 检查的正标量：`0.1, 1.0, 10.0, 100.0`。
- 按容差合并近等值后的排序保持一致：`True`；最大实质排序差异行数：`0`。
- 严格浮点排序完全一致：`False`；最大严格差异行数：`9`（仅近等值舍入噪声）。
- 最大标量恒等式误差：`0.000e+00`。
- 因此不能靠把 Tushare 的千元/手换算成元/股来改变 N01 的股票顺序；若平台顺序不同，原因不是统一单位常数。

## 平台结果完整性

- Top20 条数：`20`；Top20 日期：`2026-09-07`；图表最后日期：`20260824`。
- Top20 `factor1` 去重后：`1` 个值：`4.2897`。
- 结果节点中的逐票下载 URL：`0`；可用：`False`。
- 判断：The saved result exposes no factor-value download URL; Top20 factor1 is constant and is dated after the chart. Treat Top20 membership as a display diagnostic only.

## 数据源审计

- qfq/raw 2024 交集：`1,233,444` 行。
- AMOUNT qfq/raw 中位数比例：`1.0000`，P05/P95：`1.0000`/`1.0000`。
- VOLUME qfq/raw 中位数比例：`1.0000`，P05/P95：`1.0000`/`1.0000`。

## 文件

- `diagnosis.json`：机器可读的完整结果。
- `variant_summary.csv`：各组合的核心指标。
- `periods_*.csv`：逐期本地/平台序列。
- `amount_scalar_invariance.json`：金额单位正标量不变量检查。
- `platform_top_audit.json`：平台 Top20 与结果节点审计。
