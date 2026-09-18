# RSQR60 国证芯片对比诊断

- 因子：`Rsquare(CLOSE,60)`；指数：`980017 国证芯片`。
- 用户窗口：`2020-01-02..2026-01-09`；暖机：`2018-01-01`；5 日调仓；10 组。
- 标签：`close(t+1) -> close(t+1+cycle)`；价格：`qfq`；市值字段：`daily_basic.total_mv`；单边成本：`0.30%`。
- 规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`。此目录是诊断目录，不覆盖正式全 A 结果。

## 平台状态

- `Rsquare(CLOSE,60)` 平台状态：`failed`；factor_id：`6aacc75e3e7967143f8fbbdb`；run_id：`6aacc75f3e7967143f8fbbdc`。
- 结果状态：`3`；错误：`run: 因子分析执行失败（无详细错误信息）`。
- PandaAI CLI 当前股票池固定为沪深全 A，且该 Rsquare 运行未完成，因此没有平台芯片子池指标可做字面一一对照。

## 指数本身

- 官网 `980017` 收盘点：`2020-01-02 6205.3545` -> `2026-01-09 13959.2949`。
- 指数累计价格收益：`124.96%`；价格 CAGR 约：`14.41%`。这不是因子多空/多头超额收益。

## 因子结果

| run | periods | mean stocks | RankIC | compound selected | gross excess | turnover | annual cost | net excess | max DD | source |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 芯片静态前段+官方后段 | 291 | 29.7 | 0.016045 | 25.42% | -10.25% | 34.94% | 10.57% | -20.82% | -61.55% | static_first_interval_before_2021-12-13_plus_official_after |
| 芯片官方成分段 | 197 | 29.9 | 0.003413 | -23.50% | -7.79% | 34.01% | 10.29% | -18.08% | -58.14% | official_schedule_from_2021-12-13 |
| 全 A 同窗口 | 291 | 4634.3 | 0.000947 | 116.38% | 0.77% | 29.10% | 8.80% | -8.02% | -30.62% | full_a_factor_valid |
| 全 A 正式旧基线 | 241 | 4938.8 | 0.004256 | 15.36% | 3.57% | 29.59% | 8.95% | -5.37% | -30.42% | canonical |

## 解释边界

- `芯片静态前段+官方后段` 中 2020-01-02 至 2021-12-10 使用 2021-12-13 首个可取得成分篮子，存在幸存者偏差，只能作为敏感性诊断。
- `芯片官方成分段` 从 2021-12-13 开始，使用官网半年度调整表中 `OLD` 与 `+` 代码；`-` 和 `备选` 不纳入。
- 芯片结果的净超额基准是当期有效因子截面的等权平均收益，沿用 `factor_valid`，不是官网指数的市值加权收益。
- 本地 RSQR60 是按每只股票 qfq 收盘价对时间序列做 60 日滚动 R²，再在信号日横截面分组；这是对平台 `Rsquare` 的直接本地重建，平台本次没有返回可对齐结果。
- 详细逐期数据见 `rsqr60_index_claim_periods.csv`、`rsqr60_index_official_periods.csv` 和 `rsqr60_full_a_claim_periods.csv`。
