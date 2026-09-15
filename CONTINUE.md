# 换电脑继续研究

仓库保存了因子公式、候选状态、回测报告、原始结果和研报资料。PandaAI 的登录令牌不放进仓库，因此新电脑需要单独登录一次；登录后即可读取现有研究记录并继续工作。

## 1. 克隆项目

```bash
git lfs install
git clone --recurse-submodules https://github.com/dflmingle/factor.git
cd factor
git lfs pull
```

项目已经随仓库包含 PandaAI Skill 和 `quantlab` 子模块，不依赖当前电脑上的 `/home/minkefu/.codex/` 路径。

## 2. 搬运本地 Tushare 数据

本地复现使用的日线 Parquet 缓存约 0.8 GB，作为 Git LFS 文件随 GitHub 仓库获取。新电脑拉取 LFS 文件后，在项目根目录执行一次导入：

```bash
python scripts/local_recheck_data.py import --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py verify --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py verify
```

默认会恢复到 `quantlab/.quantlab/cache/research/cn_equity`。如果 `git lfs pull` 后看到的归档只有几十字节，说明当前电脑还没有拉到 LFS 对象；先安装并初始化 Git LFS，再重新执行：

```bash
git lfs install
git lfs pull
```

如果数据放在独立磁盘，可指定缓存根目录；该目录需要直接对应 `cn_equity`：

```bash
export FACTOR_RESEARCH_CACHE_ROOT=/data/factor/cn_equity
python scripts/local_recheck_data.py import --archive /path/to/factor-local-recheck-data.tar.gz --destination-root /data/factor
python scripts/local_recheck_data.py verify --source /data/factor/cn_equity
```

PowerShell 等价写法：

```powershell
$env:FACTOR_RESEARCH_CACHE_ROOT = 'D:\factor-data\cn_equity'
python scripts/local_recheck_data.py import --archive 'data\local_recheck\factor-local-recheck-data.tar.gz' --destination-root 'D:\factor-data'
python scripts/local_recheck_data.py verify --source 'D:\factor-data\cn_equity'
```

如果目标目录已有数据，导入命令会拒绝覆盖；确认需要替换时再显式加 `--replace`。

如果以后重新下载了完整数据，需要更新 GitHub 上的快照，在旧电脑执行：

```bash
python scripts/local_recheck_data.py export --output data/local_recheck/factor-local-recheck-data.tar.gz
git add data/local_recheck/factor-local-recheck-data.tar.gz research_reports/platform_alignment/local_recheck_data_manifest.json
git commit -m "data: update local recheck snapshot"
git push
```

当前复现命令：

```bash
python scripts/stfilter_local_recheck.py --mode analyze --data-start 20190701 --start 20210907 --end 20260907 --price-mode qfq
python scripts/extra_factor_local_compare.py
```

## 3. 准备 Python 和 CLI

Python 需要 3.10 或更高版本。推荐用 `uv` 安装 CLI：

```bash
uv tool install pandaai-cli
```

没有 `uv` 时，也可以使用 `pipx install pandaai-cli`。然后运行项目启动入口进行安装、登录和无计算预检：

```bash
python scripts/start.py --login-if-needed
```

如果不希望启动入口自动进入登录，也可以按原始步骤手动执行：

```bash
pandaai-cli login
```

登录信息只写入当前电脑的 PandaAI 本地配置，不会写入项目目录。预检通过后，可用下面的命令确认入口使用的是仓库内 Skill：

```bash
python scripts/pandaai.py skill-path
```

## 4. 继续已有研究

只查看已有结果，不消耗计算额度：

```bash
python scripts/pandaai.py batch combo-direct-4factor-size-20260909-candidates.txt --start 20210907 --end 20260907 --cycle 10 --group-number 10 --round-trip 0.003 --report-only
```

新候选仍按统一口径运行，先在候选文件中写成 `name ~ formula ~ direction`，再明确确认后提交：

```bash
python scripts/pandaai.py batch candidates.txt --start 20210907 --end 20260907 --cycle 10 --group-number 10 --round-trip 0.003 --prefix "t10-new-" --max-runs 1
```

批处理会在候选文件旁保存 `.state.json`、`.report.md`、`.report.csv` 和 `.results/`。中断后重复同一命令会读取状态，不会重复已完成的运行；不要随意修改已有候选文件或回测参数，否则应创建新的候选文件。

本地相关性和换手率分析不消耗 PandaAI 计算额度。与 PandaAI 相关性工作流对齐时，固定使用“每日有效横截面 Spearman（平均秩）后取每日算术均值”；普通 `analyze corr` 仍是下载 CSV 的通用诊断工具，不作为平台相关性主口径：

```bash
python scripts/replicate_platform_correlation.py
python scripts/pandaai.py analyze corr factor-a.csv factor-b.csv
python scripts/pandaai.py analyze turnover factor-a.csv --direction 1 --cycle 10
```

## 5. 同步自己的进展

```bash
git pull --ff-only
git add .
git commit -m "research: describe the change"
git push
```

如果新电脑尚未授权 GitHub，推荐使用网页设备授权。先安装官方 GitHub CLI，再运行：

```bash
gh auth login --hostname github.com --web
gh auth setup-git --hostname github.com
git push
```

## 6. 研究边界

- 统一默认窗口为 2021-09-07 至 2026-09-07，10 日调仓、10 组、0.3% 单边成本。
- 新回测前先列候选、目的和额度，默认每轮最多 3 个候选。
- 回测报告是历史样本记录，不是收益承诺，也不构成投资建议。
- 不要把 `~/.pandaai/config.yaml`、密码、令牌或其他凭据复制到项目中。

## 7. 最近一次研究状态：非线性组合

2026-09-11 已在 PandaAI 网页端完成一次 XGBoost 非线性组合，未修改原工作流：

- 工作流：`T10-NONLINEAR-XGB-20260911`
- workflow_id：`6aa3d4df3e7967143f8faf55`
- run_id：`6aa3d504a7f535324660ba88`
- 因子分析 task_id：`9998dbee9178459fb275a0206e90e21d`
- 节点链：特征工程构建 -> Xgboost模型 -> 因子构建(机器学习) -> 因子分析 -> 因子分析结果
- 训练区间：20160907 至 20210906
- 测试区间：20210907 至 20260907
- 调仓：10 日；分组：10 组；股票池：沪深全 A；方向：1
- 标签：`FUTURE_RETURNS(CLOSE,10)`
- 运行状态：5 个节点全部成功；耗时约 242.31 秒；扣费 10 算力
- 运行后余额：`564.120152`

核心结果：Rank_IC `0.0036`，IC_IR `-0.0687`，p-value `0.4523`，单调性 `0.28`。方向 1 的分组 10 年化超额为 `-1.85%`，换手率 `25.89%/次调仓`；按单边 0.3% 成本估算，成本后超额约 `-3.81%/年`。当前模型规格标记为 `abandon`，不要在同一测试区间继续调参或重复运行。

完整公式、六个输入特征、XGBoost 参数和全部分组结果见：`t10-nonlinear-xgb-20260911.md`。平台工作流索引已更新：`pandaai-workflow-registry.md` 和 `pandaai-workflow-registry.json`。

下一步先做无计算诊断：检查六个输入的截面 Spearman 相关性、模型特征重要性和模型输出分布。若重新测试，先用等权 Rank 组合作为线性基准，再预先固定一个与横截面排序/top10%目标更一致的模型方案；不要直接继续搜索 XGBoost 超参数。

## 8. 2026-09-13 全 A 数据补齐与平台口径核对

本轮没有创建新因子或运行新的 PandaAI 回测。平台配置已从本地工作流登记表保存：171 个工作流中 167 个明确使用 `沪深全A` 股票池。

已使用本地 Tushare 凭据补齐并打包以下数据：

- qfq 行情：2018-01-02 至 2026-09-07，107 个批次；
- `daily_basic`：2018-01-02 至 2026-09-07，共 2,107 个交易日；
- `fina_indicator`、`income`、`balancesheet`、`cashflow`：全 A 5,449 只股票，各 69 个批次；
- 全 A 正收益记录：45/45 可重建，数据不可用为 0；
- `TS_RANK756` 的 756 个交易日暖机缺口已补齐。

当前 Git LFS 数据快照为 `data/local_recheck/factor-local-recheck-data.tar.gz`，包含 4,836 个文件、约 688 MB 原始数据；配套 SHA-256 清单是 `research_reports/platform_alignment/local_recheck_data_manifest.json`。快照只保留本轮全 A 复现所需的数据和报告，未包含旧 ST 专项缓存。

在新电脑拉取后执行：

```powershell
git lfs install
git lfs pull
python scripts/local_recheck_data.py import --archive data/local_recheck/factor-local-recheck-data.tar.gz
python scripts/local_recheck_data.py verify
```

当前逐期诊断报告位于：

`quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_delta_diagnosis_full_a/diagnosis.md`

按净超额差绝对值 `>=2pp`，仍有 30/45 条记录较大，其中 29 条有完整平台收益曲线。后续优先核对：直接价格因子的复权/未来收益标签/停牌行处理；CFP 和纸面财务因子的字段定义、公告日和 TTM；2026 YTD 短样本不作为等价性判断。完整重跑命令见 `research_reports/platform_alignment/positive_factor_local_reproduction_20260913.md`。

## 9. 2026-09-14 final full-A alignment audit

The label-1 output uses the saved platform signal dates and the verified label `close(t+1) -> close(t+cycle+1)`. The current fixed rules are recorded separately in `research_reports/platform_alignment/ALIGNMENT_RULES.md` and implemented by `scripts/platform_alignment_rules.py`.

- all 64/64 saved positive records rebuild from the local snapshot; no records are data-unavailable;
- 9/64 are within 1 percentage point of platform net excess; 39/64 still differ by at least 2 points;
- mean absolute net-excess gap is 2.69 pp, with local results generally lower;
- the largest remaining gaps are concentrated in market/impact proxies, direct price/turnover factors, and short 2026 YTD samples;
- the corrected label and formula-specific field updates improve alignment but do not establish full semantic equivalence.

Final report: `research_reports/platform_alignment/positive_factor_alignment_20260914.md`

Reproduce the final comparison after restoring the snapshot:

```powershell
python scripts/positive_factor_local_compare.py --universe full_a --market-cap-field total_mv --data-start 20180101 --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a --output quantlab/.quantlab/cache/research/cn_equity/reports/positive_factor_compare_full_a_label1_cfpfix2 --label-offset 1
python scripts/build_final_alignment_report.py
```

## 10. Alignment rule handoff

For future reproduction, treat `ALIGNMENT_RULES.md` as the contract and `platform_alignment_rules.py` as the executable source of truth. Do not compare outputs produced under different rule versions. In particular, CFP proxy diagnosis must use the same factor-valid benchmark and shifted label as the final comparison; a proxy selected under another benchmark is not admissible for the final mapping.

Before any local reproduction on this or another computer, run the read-only preflight:

```bash
python scripts/validate_platform_alignment.py --check-snapshot
```

The formal comparison entry point now defaults to `--platform-net-filter all`, validates the canonical full-A/qfq/`total_mv`/label-1/10-group/`factor_valid`/0.30% one-way-cost settings, and refuses to overwrite output metadata from another rule version. The same contract applies to new factors; add a handler or explicitly documented proxy rather than changing the shared settings silently.

## 11. 2026-09-14 全部已保存平台因子复现

本轮目标改为“本地覆盖所有已经完成的平台测试记录”。对项目根目录内全部已完成、带有 `net_excess_pct` 的报告逐条复现，使用 `--platform-net-filter all`；当前共 `163` 条，没有净超额为 0 而被漏掉的记录。

结果目录：

`quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1/`

结果为：

- `158/163` 条已在本地完成计算；
- `5/163` 条仍因本地缓存没有可等价输入而暂不支持；
- 158 条的净超额差平均为 `-0.55pp`，平均绝对差 `3.03pp`；
- `43/158` 条绝对差不超过 `1pp`，`71/158` 条不超过 `2pp`，`87/158` 条超过 `2pp`，`19/158` 条超过 `5pp`，`4/158` 条超过 `10pp`；
- 平台原始净超额为负的记录共 `98` 条；其中 `93` 条已完成本地对比，另 `5` 条正是当前缺字段的暂不支持项。

最大差异首先是 `OSR2-PRICE-CROSS-MA5`（`+30.17pp`）、`HT13-EXPWRET-6M`（`+26.79pp`）、`OSR2-RSI-CROSS30`（`+22.64pp`）和两个 Python OBV 记录（`+10.05pp`、`+8.50pp`）。这些记录的本地/平台换手或信号成员明显不一致，不能靠统一平移净超额抹平；应分别核对交叉信号状态机、指数加权算子、OBV 原始输出排序和平台换手定义。

仍不支持的 5 条：

- `BASE-DIV-YIELD-TTM`：没有完整点时股息历史；
- `DISTRIBUTION-RISK-CORE-10D`、`DISTRIBUTION-INTRADAY-3SIGNAL-10D`、`DISTRIBUTION-RISK-10D`：本地没有平台 `cal_*` 盘中字段；
- `NEW-HIST-ADJPROFIT-6Q`：本地财务缓存没有扣非利润/非经常损益字段。

完整逐条结果见 `all_factor_local_compare.md`，机器可读结果见 `all_factor_local_compare.json`。这份结果代表“本地可计算覆盖率”已达到 `158/163`，不代表代理字段与 PandaAI 内部字段已经完全语义等价。

## 11.1 2026-09-15 pythonindex1 修正复现

针对 `NONHT-MAX5-LOW-21D` 已确认平台 Python 运行时的 MultiIndex 为 `[date, symbol]`，其 `groupby(level=0)` 会在同一交易日的股票序列上做滚动 `MAX(5)`。本地 handler 已按该语义兼容，并将规则版本升级为 `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1`。

新结果目录：

`quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1/`

按当前规则重新生成全量报告的命令：

```bash
python scripts/positive_factor_local_compare.py \
  --universe full_a \
  --market-cap-field total_mv \
  --data-start 20180101 \
  --price-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches \
  --cap-root quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a \
  --financial-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a \
  --output quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1 \
  --platform-net-filter all \
  --label-offset 1
```

- `MAX5` 平台净超额 `-11.93%`，本地 `-12.38%`，净超额差 `-0.45pp`，Top20 重合 `18/20`；旧版差为 `+6.16pp`、Top20 `1/20`。
- 全量 `163` 条记录中 `158` 条有本地 handler，`5` 条因字段缺失不支持；`157` 条能产出有效净超额。
- 有效记录平均绝对净超额差 `2.32pp`，`>=2pp` 为 `77` 条，`>=5pp` 为 `9` 条，`>=10pp` 为 `1` 条。
- 仍最大的非异常差异集中在 T10 冲击/规模组合（毛超额约差 `4~6pp`）；RankIC 和 Top20 基本一致，现有证据不足以合理替换 qfq 或 `total_mv`。
- `HT13-EXPWRET-6M` 的 `26.60pp` 差异主要由平台换手 `216.73%` 对本地 `45.50%` 造成，不能通过修改因子公式抹平。

## 12. 因子档案中的相关性记录

以后每个完成平台回测并进入本地研究档案的因子，都要同时记录与已有因子的相关性参考，不只记录 IC、净超额、换手和回撤等表现指标。

- 主口径固定为每日有效股票截面的 Spearman 相关，再对交易日取算术平均；规则见 `research_reports/platform_alignment/ALIGNMENT_RULES.md`。
- 默认将 `abs(rho) >= 0.60` 记为高相关预警，同时保留精确相关系数、参照因子公式、factor_id、run_id 和平台净超额。
- 每个因子记录高相关对象；重复的平台批次按独立 `record_id` 保留，不因公式相同而覆盖。
- 当前累积登记表为 `research_reports/platform_alignment/factor-correlation-registry.json`；当前 F-NET01 的详细结果为 `research_reports/platform_alignment/target-vs-positive-factor-correlation-20260915.json`。
- 登记已有相关性结果使用：

```powershell
python scripts/register_factor_correlations.py
```

## 13. PandaAI 字段本地复现

AlphaPROBE 本地搜索的字段目录以 `vendor/skill-pandaai-factor-online/references/fields.md` 的公式模式字段为准：348 个基础字段，扩展为 4,744 个可写入公式的名称（基础字段、`_lyr`、`_ttm`、`_mrq_1..12`）。字段解析、Tushare PIT 映射、TTM 还原和懒加载面板在 `scripts/pandaai_fields_local.py`；GP 入口是 `scripts/alphaprobe_gp_tushare.py`。

本地字段搜索和净超额评分统一使用 `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1`：沪深全 A、Tushare qfq、`daily_basic.total_mv`、公告日 PIT、`comp_type=1` 优先、TTM 季度还原、`close(t+1) -> close(t+cycle+1)`、10 组、单边 0.30% 成本；相关性使用每日有效截面 Spearman 平均秩后取每日均值。`max5_low21` 额外复现已验证的平台 Python `[date, symbol]` level-0 滚动语义。每次 GP 输出会同时写 `field_coverage.json` 和 `field_coverage.md`。

刷新完整本地财务字段前只需在当前机器设置 token，不要写入仓库：

```powershell
$env:TUSHARE_TOKEN = "本机 token"
python scripts/tushare_financial_cache.py --universe full_a --start-date 20180101 --end-date 20260907 --output-root quantlab/.quantlab/cache/research/cn_equity/financial_full_a
```

当前工作区没有 `TUSHARE_TOKEN`，现有财务缓存仍是旧窄列，因此目前实际激活 254 个公式名；代码已声明并校验完整 348/4,744 名称，财务缓存刷新后会自动扩展 GP 终端。两个分类字段 `classified_by_continuity_operation`、`classified_by_ownership` 没有可靠的 Tushare 数值等价物，始终标记为 unavailable，不作为搜索终端。
