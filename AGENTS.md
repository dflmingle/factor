# 因子研究总则

## PandaAI 因子工作

- 做 PandaAI 因子工作前，先读取 `/home/minkefu/.codex/skills/skill-pandaai-factor-online/SKILL.md`。
- 默认只分析已有回测结果，不自动创建因子或运行回测。
- 需要新回测时，先列出候选公式、候选数量、预计算力消耗和测试目的，等待用户明确批准后再运行。
- 默认每轮最多测试 3 个候选；未经用户明确要求，不自动开启第二轮或扩大候选数量。
- 统一使用约定的 5 年回测窗口；不运行几个月的短窗口试跑。
- 回测完成后先报告结果，不因结果好坏自动继续挖掘或回测。

## 跨电脑继续

- 优先使用仓库内的 `vendor/skill-pandaai-factor-online/SKILL.md` 和 `python scripts/pandaai.py ...`；不要依赖某台机器的绝对 Skill 路径。
- PandaAI 登录令牌只保存在当前电脑的本地配置中，不得提交到仓库。
- 完整迁移步骤见 `CONTINUE.md`。

## 启动约定

- 用户在此项目中说“启动”时，运行 `python scripts/start.py --login-if-needed`。
- 启动脚本可以安装 CLI、运行预检并引导交互式登录；启动阶段不得自动创建因子或运行回测。
- 启动完成后报告环境状态，等待用户指定研究任务。
