# 换电脑继续研究

仓库保存了因子公式、候选状态、回测报告、原始结果和研报资料。PandaAI 的登录令牌不放进仓库，因此新电脑需要单独登录一次；登录后即可读取现有研究记录并继续工作。

## 1. 克隆项目

```bash
git clone https://github.com/dflmingle/factor.git
cd factor
```

项目已经随仓库包含 PandaAI Skill，不依赖当前电脑上的 `/home/minkefu/.codex/` 路径。

## 2. 准备 Python 和 CLI

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

## 3. 继续已有研究

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

## 4. 同步自己的进展

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

## 5. 研究边界

- 统一默认窗口为 2021-09-07 至 2026-09-07，10 日调仓、10 组、0.3% 单边成本。
- 新回测前先列候选、目的和额度，默认每轮最多 3 个候选。
- 回测报告是历史样本记录，不是收益承诺，也不构成投资建议。
- 不要把 `~/.pandaai/config.yaml`、密码、令牌或其他凭据复制到项目中。

## 6. 最近一次研究状态：非线性组合

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
