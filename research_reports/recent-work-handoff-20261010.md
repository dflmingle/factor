# 近期研究归档与交接（2026-10-08 至 2026-10-10）

本次归档包括榜单快照、近期归簇、平台实测、池级诊断、实盘容量分析，以及相应候选和复跑脚本。研究结论与原始证据一起保留；临时面板和登录凭证不入库。

## 结果入口

| 工作 | 结论与边界 | 入口 |
|---|---|---|
| 研究总账与目标 | 以池级 C 约束下提高 A 为研究目标；B 点亮和名次情景不作为预测 | [总账](research-ledger-20261010.md)、[GOAL](../GOAL.md) |
| 近期归簇与去重 | 117 条静态公式完成相关性整理，暂无旧锚点的成员登记 U01–U14；新簇不等于新 alpha | [归簇](platform_alignment/recent-factor-clusters-20261010-average-rank-v2/summary.md) |
| 簇间最近相关 | 保留最高相关簇、成员配对、方向与覆盖日期 | [邻簇](platform_alignment/recent-factor-clusters-20261010-average-rank-v2/cluster-nearest-neighbors.md) |
| U01/U02 平台验证 | 单因子储备证据，尚非入池建议 | [平台结果](platform_alignment/u01-u02-platform-20261010/summary.md) |
| 平台支持的量价补测 | 日内量价与 Alpha191 候选成本后表现弱；不宣称已测遍平台空间 | [补测](platform_alignment/platform-uncovered-test-20261010/summary.md) |
| 9 月发现的强新簇回收 | K008、K021、K015、K020 曾完成平台单因子验证；K008/K021 是最干净的两条，K015/K020 结构更敏感。单因子有效不等于加入现役池有效 | [四候选复核](platform_alignment/gp-platform-tests-20260925/verified-candidates-review.md)、[池级结果](../GOAL.md#四已知结构约束不要再重复投入) |
| 其他已验证新簇 | N34 有平台净 12.27% 但规模相关偏高；K024 净 6.51% 但 IC p=0.81，分别列为独立候选与弱验证，不与强新簇混排 | [N34](platform_alignment/f-gfn-n02-cluster-assignment-20260920.md)、[K024 复核](platform_alignment/gp-platform-tests-20260925/desktop-md-20260925-26/新簇候选平台验证-20260925.md) |
| LEGMIX 竞争力 | 13 场景×两个归档窗口；A/B 加席减规模相关，但池级 C 代理存在代价；历史缓存不是最新正式复现 | [池级诊断](platform_alignment/legmix-competitiveness-20261010/summary.md) |
| 榜单借鉴三假设 | 下跌缩量、振幅切割、量价相关性变化；公共名称启发的自主构造 | [候选](platform_alignment/board-inspired-hypotheses-20261010/summary.md) |
| 三候选本地诊断 | 三候选及四对照完成；振幅切割较裸反转改善，但近期亏损。数据校验和覆盖有限，不作正式验收 | [诊断及修正](platform_alignment/board-inspired-local-reproduction-20261010/summary.md) |
| 规模风格与实盘容量 | 分开保存风格归因、压力审计、10 万资金容量分析 | [容量](live-capacity-20261009.md)、[风格审计](platform_alignment/style-audit-20261010-v2/) |

## 后续接续

1. 本地归档校验发现 305 个哈希差异，含 24 个行情批次；先归因，不覆盖旧数据或混比口径。
2. 三候选的本地单腿亏损不足以直接证明池级无增量。暂缓平台测试，振幅切割保留研究假设。
3. 维持平台测试事先列公式、数量、成本和目的的审批约定；本次归档未启动新回测。
4. `*.npy`、`*.pkl` 按仓库现有规则不上传；簇面板可按脚本重建，矩阵、公式、元数据和校验记录入库。
5. `quantlab` 子仓库及其第三方库有既存独立改动，本次未修改、提交或推送；父仓库仍保留原子模块指针。

代码变更包括 GP/GFN 的规模约束、显式旧登记表诊断开关、历史同式预检，以及归簇/容量/池级和新候选诊断脚本。只有离线检查，不代表这些搜索入口全部重新运行过。
