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

本地相关性和换手率分析不消耗 PandaAI 计算额度：

```bash
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
