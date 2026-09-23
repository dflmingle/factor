# 目标准备材料（2026-09-23）

本目录是 [`GOAL.md`](../../../GOAL.md)（项目目标：年度综合积分榜第一名）的证据目录。

## 文件

| 文件 | 内容 |
| --- | --- |
| `leaderboard_points_20260922.csv` | 平台综合积分榜 2026-09 preview 全量快照：276 个池的 rank / score / NA / NB / NC / Rex / SR / 月换手 / 月回撤 / 有效因子数 / 池龄 |
| `leaderboard_meta.txt` | 快照元信息（snapshot_id、发布时间、口径） |

## 快照口径

- 接口：`GET https://api.pandaaiquant.com/arenaRanking/boards/points?period=2026`
  （`page_size ≤ 100`，共 3 页）。
- `snapshot_id = a9ff1ca945f29eadd0559a16ad1ae217`，发布于 2026-09-22T09:14:17Z。
- 该榜为**月度预估（preview）**：只统计 2026-09 当月截至发布日的日频数据，
  月末才会正式结算；年度榜按各月结算积分累加。
- 快照里的 `turn` 是"当月各统一调仓日换手之和"，最小值 0.5000000000000062（34 个池），
  对应建仓期首次买入（组合从空仓到满仓 = 0.5），不是平台的下限；C 的分母下限仍是规则书的 0.3。

## 复现方式

```bash
python3 - <<'PY'
import pandas as pd
d = pd.read_csv('research_reports/platform_alignment/goal-20260923/leaderboard_points_20260922.csv')
print(d.head())
print('NC=1 池数', int((d.nc >= 0.999).sum()))
PY
```
