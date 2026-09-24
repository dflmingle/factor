# 榜单快照（2026-09-24 抓取）

## 文件

| 文件 | 内容 |
| --- | --- |
| `leaderboard_points_20260923_raw.csv` | 综合积分榜 2026 preview 全量快照（283 个池），含平台原生的 `metrics.*` 明细字段 |
| `leaderboard_meta.txt` | 快照元信息（snapshot_id、数据切点、发布时间、口径、my_rank） |

## 快照口径

- 接口：`GET {gateway}/arenaRanking/boards/points?period=2026&page=N&page_size=100`（`page_size` 服务端固定 20，共 15 页）
- `ranking_snapshot_id = 81ba98f4717ef86b0efeb685db0257cf`
- `data_cutoff_at = 2026-09-23`，`published_at = 2026-09-23T09:08:01Z`（北京时间 17:08）
- 与 `goal-20260923/leaderboard_points_20260922.csv` 相比：池数 276 → 283，字段更全（新增 `metrics.comb` / `anchor_*` / `denominator_*` / `points_before_cap` 等）

## 本次抓取的关键事实

1. **我们的池（`mingle`）不在榜上**，接口返回 `my_rank: null`。
2. 榜上**没有**任何 `turn < 0.5` 的池 —— 未完成首次建仓的池不上榜，因此"未上榜"与"池尚未生效/未建仓"一致。
3. 09-23 新进榜 6 个池全部是建仓期状态（`turn = 0.5`、`nb = 0`），分数 381 ~ 1,480，说明建仓当月即可上榜并拿到 preview 分（但分很低）。
4. 分布变化（09-22 → 09-23）：`NC >= 0.999` 72 → 77；`NB > 0` 45 → 70；`NB >= 0.85` 2 → 2；`NA >= 0.7`（新池封顶）2 → 2。
5. 榜首易主：`FINAL-best`（虎墨666）32,327 反超 `这是干什么的`（32,240）；原榜首 `NC` 由 1.00 降至 0.8345，分数 35,517 → 32,240。

## 复现方式

```bash
python3 - <<'PY'
import pandas as pd
d = pd.read_csv('research_reports/platform_alignment/goal-20260924/leaderboard_points_20260923_raw.csv')
print(d[['rank','pool_name','score','metrics.na','metrics.nb','metrics.nc']].head())
PY
```

## 本次新发现的竞技场接口（2026-09-24）

从赛事前端 bundle（`/factorhub/fourthFactorCompetition/assets/index-*.js`）里提取到的只读接口，
均以 `Authorization: <token>` + `uid: <uid>` 头访问 `{gateway}`：

| 接口 | 用途 |
| --- | --- |
| `GET /arenaRanking/boards` | 全部榜单目录 |
| `GET /arenaRanking/boards/points?period=2026&page=N&pageSize=20` | 综合积分榜分页（`pageSize` 服务端固定 20） |
| `GET /arenaRanking/me/boards` | **我们自己池的榜单状态**（`status` / `pool_id` / `pool_name` / 各榜 rank+score） |
| `GET /arenaRanking/players/{participant_id}` | 选手公开主页（`header` / `boards` / `score_history` / `factor_radar` / `pool_radar`） |
| `GET /arenaRanking/pools/{pool_id}/holdings?tradeDate=YYYYMMDD&page=N&pageSize=N` | **池的持仓明细**（信号日、周期、选股数、等权、composite 区间、逐票权重） |
| `GET /arenaRanking/daily-factors?tradeDate=YYYYMMDD&page=N&pageSize=N` | 公开的每日因子 IC 流 |
| `GET /factorArena/me/registration-state` | 报名/资格状态（`eligibilityStatus` / `realnameStatus` / `hasPool`） |

注意：`/arenaRanking/players/{pool_id}` 会返回 `POOL_NOT_FOUND`，该接口要传 **participant_id**。

## 我们池的状态快照（2026-09-24 10:4x）

见 `pool_state_20260924.json`。要点：

- `pool_name = mingle`，`display_name = ddd`，`style_tag = 综合型`，`rebalance_cycle_days = 10`，`active_factor_count = 5`
- `participant_id = 70c703ce0eba4038bd8b4a9ebbc46ff6`，`pool_id = 2ce9558df7996413e4df96eb`
- `is_on_board = true`，报名 `eligibilityStatus = approved`、`realnameStatus = verified`、`riskStatus = normal`
- 分数：`cumulative_points = 0.0`，8 个榜的 `rank` / `score` **全为 null**
- **首次建仓已完成**：`signal_trade_date = 20260923` → `trade_date = 20260924`，`selected_count = 501 / universe 5017`，等权 `1/501 ≈ 0.001996`，`stuck_symbols = 0`，`data_status = ok`
- composite 区间：top `1.8952` ~ cutoff `1.1611`
