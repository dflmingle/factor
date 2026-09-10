# 启动研究环境

以后在这个项目里说“启动”，执行下面的流程即可。它只准备环境和登录，不创建因子、不运行回测，也不消耗 PandaAI 计算额度。

## 一键入口

在项目根目录运行：

```bash
python scripts/start.py --login-if-needed
```

这个入口会：

1. 检查 Python 版本和 `pandaai-cli`。
2. 有 `uv` 或 `pipx` 但没有 CLI 时安装 `pandaai-cli`。
3. 运行 PandaAI Skill 预检。
4. 如果当前电脑尚未登录，打开交互式 `pandaai-cli login`。
5. 再次检查余额、账号和字段环境，然后停在待研究状态。

密码和 PandaAI token 只保存在当前电脑的本地配置中，不会进入 Git 仓库。

## 等价的手动命令

```bash
git clone https://github.com/dflmingle/factor.git
cd factor
uv tool install pandaai-cli
python scripts/pandaai.py bootstrap
pandaai-cli login
```

如果仓库已经克隆，只需从 `python scripts/start.py --login-if-needed` 开始。启动完成后，已有报告可以用 `--report-only` 查看；新的回测仍需先列出候选、目的和额度并得到确认。
