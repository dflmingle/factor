# 分数更新核对（2026-10-08 晚）

结论：**平台分数未更新**，仍是 09-30 preview 快照。

## 证据

| 项 | 值 | 与今晨对比 |
| --- | --- | --- |
| 积分榜 snapshot_id | `4fa32fb1755fb796bbde5acde8786707` | 相同 |
| published_at | 2026-09-30T09:24:27Z | 相同 |
| data_cutoff_at | 2026-09-30 | 相同 |
| snapshot_type | preview / is_estimate=true | 相同 |
| rows | 305 行，md5 `0ffde0acdd1863df…` | 逐字节相同 |
| 我方名次/分数 | 26/305，22648.21 | 相同 |
| `monthly_points_official` | null（booked 0.0） | 相同 |
| 球员明细期数 | 当前周期（2026-10）0 条；`--period 2026-09` 5 条 | 10 月无数据 |
| score_history | 仅 `2026-09`（is_estimate=true） | 无 10 月条目 |

八榜现状（`me_boards.json`，早晚两版 190 项字段 0 差异）：
综合积分 26/305（22,648）；因子质量 105/305（.3237）；**超额收益 1/305（15.72）**；
因子稳健 69/305（.814）；劳模 7/81（984）；黑马 None/0；高校 None/6；普惠 26/278。

## 判读

- 平台按月末结算，10 月 preview 预期在 10-31 之后才出现；本日无新 tick 属预期。
- 首个需要动作的时点 = 10-31 快照落地 → 按 `pool-exec-20261101/README.md` 决策树读 `rawC`/rc、`den_b`/`raw_b`，窗口 11-01~03。
- 本轮零算力、零平台提交。

抓取脚本：`scripts/board_snapshot.py`（逐字节复现两次，接口只认 `period=2026`）。
