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
