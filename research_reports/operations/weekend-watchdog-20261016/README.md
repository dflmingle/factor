# 周末本地研究守护（2026-10-16）

已安装并启用用户级 systemd 服务 `factor-research-watchdog.service`；用户 linger 已开启，退出聊天或终端不依赖本会话存活。服务开机自动启动，异常退出自动恢复，180 秒未发守护心跳时由 systemd 重启。

`factor-research-awake.service` 已取得系统 sleep/idle 阻止锁，截止 **2026-10-19 09:00（北京时间）**正常退出。该服务只用于周末防自动休眠，不阻止关机或重启。断电、硬件故障或磁盘损坏仍可能中断；不能承诺绝不中断。

## 调度规则

- 每 60 秒检查真实 PID、启动时钟、可执行文件、命令参数和工作目录，防止旧 PID、僵尸和遗留 running 文件被误报为活任务。
- 按每个任务已经观测到的最优 score/log_reward 是否提高判断改善；日志刷新、相同分数重写不算改善。初次接入用保存文件时间保守初始化，之后持久化数值高水位。
- 通常 nice=5（专项默认 8，旧逆向任务默认 15）。连续 2 小时无改善设为 nice=12，6 小时为 nice=18；出现改善后恢复任务默认优先级。nice 值越大优先级越低。
- 已结案 Alpha 当前进程设为 nice=19，退出后不自动重启。
- 活进程即使长时间无改善也只降优先级；不因耗时长就杀掉。长期无 CPU 活动且检查点不更新另标待核查。
- 异常退出按 1、2、4、8…分钟退避，最长间隔 60 分钟；连续稳定运行 1 小时后重置故障计数。每轮最多拉起 1 个任务，可用内存不足 16 GiB 时暂缓新增进程。
- 为避免磁盘写满，空闲空间低于 50 GiB 时保留进程暂停，恢复到 100 GiB 后自动继续；记录暂停身份，守护服务重启后仍能恢复。当前空间充足，未触发该策略。
- 现存计算进程通过精确身份接管；守护服务重启时保留计算进程，重新扫描接管，避免启动两份。
- 断点是已保存最优候选和完成轮次；崩溃时尚未保存的计算可能重做。不会宣称恢复了未落盘的优化器状态。

## 覆盖与边界

配置包含 5 个榜单分片、原有 6/27/36 专项续跑、一个旧逆向任务，以及只监控不重启的 Alpha 旧进程。所有自动运行均为现有本地代码，当前仍使用各自冻结的旧数据版本；不自动切换到未经完整验证的新输入。

新数据完整 A/B/C 搜索、因子池七类算法修正尚未就绪，登记为待处理，不会被计作正在运行。守护程序不会修复经济逻辑或代替验收，也不会伪造 LLM 指导；缺少真实指导的 MCTS 轮次仍应标为 pending。

不会调用付费平台回测、自动提交或修改比赛因子池；平台算力消耗 0。

## 查看与控制

```bash
systemctl --user status factor-research-watchdog.service factor-research-awake.service
cat research_reports/operations/weekend-watchdog-20261016/status.json
```

停止自动拉起某个任务：在此目录创建 `STOP.<job-id>`；这不杀死已在运行的进程。停止守护服务也保留已启动的研究进程。

```bash
systemctl --user stop factor-research-watchdog.service
```

如需提前恢复自动休眠：

```bash
systemctl --user stop factor-research-awake.service
```

配置：`config.json`；事件：`events.jsonl`；逐任务日志：`*.worker.log`。服务文件也保存在本目录，机器本地用户服务目录只保存符号链接。

验证包括真实 worker 异常退出后的退避/重启、单实例接管、分数不变不计改善，以及旧数据入口的启动回归测试。生产守护重启检查见 `restart_adoption_validation.json`，7 个已有 worker PID 保持不变，未产生重复匹配。

额外实测：仅向守护主进程发送 SIGKILL，systemd 在 15 秒后自动拉起；10 个研究 worker PID 全部保留且没有重复启动，见 `crash_recovery_validation.json`。单元/集成检查 9 项通过，输出见 `tests.log`。恢复启动时还修复了七类算法旧入口中的 Path 局部变量遮蔽异常，并加了回归检查。

## 有改善时自动推送（用户于2026-10-16授权）

`factor-research-publisher.timer` 每5分钟调用 `scripts/publish_peer_improvements.py`，归档并正常推送至 `origin/main`。与研究守护服务分离，网络或Git失败不阻断搜索；失败保留本地提交并在下轮重试。

仅监测正在运行的 `peers_v5_Broster` 与 `seven_methods_v1` 路线。要求 `verified_best.json` 与 `best.json` 的AST、方向、周期、目标版本和分数一致，排除未验证的新最优或旧候选验证记录。首次匹配建立基线；之后同源码和证据/市场上下文下满足以下任一条件才归档：

- 综合拟合损失较上次归档降低至少1%，同时平均全持仓重合率下降不超过0.5个百分点，IC和RankIC MAE分别恶化不超过2%。
- 从未通过转为通过既定参照验收。

归档为 `research_reports/peer_reconstruction/published-improvements-20261016/` 中的不可变快照，包含公式/AST、逐期持仓与IC诊断、独立A/各榜验证及未通过项、原始抽取证据、市场上下文、当前磁盘源码与SHA256。源码快照不是对已运行进程导入模块的字节级证明；公开日期均参与过拟合，不能当作严格样本外验证或新alpha发现。新数据与旧数据不会混比。

只提交归档目录；用户其他暂存修改存在时延后提交；不自动拉取合并、重置或强制推送。远端领先本地时记录待人工整合。初次安装另将守护配置、测试和当前进度报告显式提交。付费平台回测和比赛池仍不在自动任务范围。

```bash
systemctl --user status factor-research-publisher.timer
cat research_reports/peer_reconstruction/published-improvements-20261016/.local/status.json
journalctl --user -u factor-research-publisher.service -n 10
```

需要停止自动推送时：`systemctl --user disable --now factor-research-publisher.timer`，不影响搜索。
