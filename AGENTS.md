# 因子研究总则

## 项目目标（第四届因子大赛）

- 本项目的目标是**年度综合积分榜第一名**，当前基线、与榜首的分差、已证伪的路线和决策门槛见 [`GOAL.md`](GOAL.md)。
- 任何以"提高名次"为名的研究动作，先对照 `GOAL.md` 的"已知结构约束"和"决策规则"，避免重复已证伪的方向。
- 每月月末结算后更新 `GOAL.md` 的"现状基线"和"与第一名的差距"两节。

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

## 本地复现对齐契约

- 任何 PandaAI 因子的本地复现，包括新因子，都必须先读取 [`research_reports/platform_alignment/ALIGNMENT_RULES.md`](research_reports/platform_alignment/ALIGNMENT_RULES.md) 和 [`scripts/platform_alignment_rules.py`](scripts/platform_alignment_rules.py)。规则版本当前为 `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`。
- 正式全量复现只使用沪深全 A 的 `.SH/.SZ` 股票池、qfq 行情、`daily_basic.total_mv`、`20180101` 暖机、平台保存的信号日期、`close(t+1) -> close(t+cycle+1)` 标签、10 组、`factor_valid` 基准和 0.30% 单边成本。正式目录必须使用 `--platform-net-filter all`，不能只复现平台净超额为正的记录。
- 必须使用规则文档中规定的分组方向、Top20 原始因子值排名、换手计算、算术年化、PIT 财务连接、合并报表和 TTM 还原、EMA/TS_RANK、并列值代理、Python 索引兼容和 CFP 代理。平台内部字段没有字节级等价物时，结果必须明确标记 `proxy`。
- 以后本地因子测试固定输出两份互相独立的结果：正式近五年窗口（当前规则为 `20210907` 至 `20260907`）和近期窗口（`20260101` 至本地最新日期）。近期窗口沿用 `20180101` 暖机、同一全 A/qfq/`total_mv`/label-1/成本口径，只作为短期诊断，不与近五年结果混合排名或替代正式结论；用户要求时，先把已保存平台净超额为正的全部记录逐条计算近期结果。
- 净超额绝对差 `>5pp` 的记录必须写入 `research_reports/platform_alignment/factor_alignment_failure_registry.json`，记录公式字段、算子、路径/换手原因和字段归因；后续本地挖掘默认避开登记表中达到重复失败门槛的字段。
- 禁止把 raw、`circ_mv`、ST pool、same-day label、全 A benchmark 或未经诊断的字段替代物混入正式结果；这些只能作为单独标注的敏感性诊断，不能和当前规则版本的结果混比。
- 规则或代理一旦改变，必须递增规则版本并使用新输出目录；不得覆盖旧规则结果，也不得把不同版本的结果合并统计。正式脚本会校验核心参数并拒绝覆盖不兼容的目录。
- 换电脑时必须先按 [`CONTINUE.md`](CONTINUE.md) 拉取 Git LFS 快照、执行归档和数据树校验，再运行正式复现。PandaAI token 只保存在新电脑的本地配置中，不复制到仓库。
