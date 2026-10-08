# 榜单快照抓取（抓取日 2026-10-08，零算力）

- 抓取：`python3 scripts/board_snapshot.py --out research_reports/platform_alignment/board-snapshot-20261008 --period 2026`
- 结果：平台**仍未发布 10 月新快照**，返回的仍是 09-30 cutoff 那版
  （`ranking_snapshot_id = 4fa32fb1755fb796bbde5acde8786707`，305 池，我方 rank 26）。
- 与 `board-snapshot-20260930/` 的差异仅 3 行的 `avatar_url`/`pool_name` 装饰性字段。
- 用途：作为"10 月 preview 尚未出数"的零算力证据；10-31 前无需重复抓取例行确认。
