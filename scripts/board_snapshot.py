#!/usr/bin/env python3
"""抓取 PandaAI 竞技场榜单快照（只读、零算力）。

输出目录默认 research_reports/platform_alignment/board-snapshot-<cutoff>/：
  board_live.json  综合积分榜全量（period=2026，含原生 metrics 字段）
  me_boards.json   我方 8 个榜的状态

用法: python3 scripts/board_snapshot.py [--out DIR] [--period 2026]
"""
import argparse
import json
import os
import time
import urllib.request

import yaml

CONFIG = os.path.expanduser("~/.pandaai/config.yaml")


def get(gateway: str, path: str, token: str, uid: str) -> dict:
    req = urllib.request.Request(
        f"{gateway}{path}",
        headers={"Authorization": token, "uid": str(uid), "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--period", default="2026")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(CONFIG))
    gateway = cfg["gateway_url"].rstrip("/")
    token, uid = cfg["token"], cfg["uid"]

    first = get(
        gateway,
        f"/arenaRanking/boards/points?period={args.period}&page=1&pageSize=20",
        token,
        uid,
    )["data"]
    meta_keys = [
        "ranking_snapshot_id",
        "published_at",
        "data_cutoff_at",
        "pool_total",
        "row_count",
        "my_rank",
        "my_page",
        "formula_version",
        "snapshot_type",
        "is_estimate",
    ]
    meta = {k: first.get(k) for k in meta_keys}
    rows = list(first["rows"])
    pages = (int(meta["row_count"]) + 19) // 20
    for page in range(2, pages + 1):
        data = get(
            gateway,
            f"/arenaRanking/boards/points?period={args.period}&page={page}&pageSize=20",
            token,
            uid,
        )["data"]
        rows += data["rows"]
        time.sleep(0.1)

    out = args.out or os.path.join(
        "research_reports/platform_alignment",
        "board-snapshot-" + str(meta["data_cutoff_at"]).replace("-", ""),
    )
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "board_live.json"), "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "rows": rows}, fh, ensure_ascii=False, indent=1)
    try:
        me = get(gateway, "/arenaRanking/me/boards", token, uid)
        with open(os.path.join(out, "me_boards.json"), "w", encoding="utf-8") as fh:
            json.dump(me, fh, ensure_ascii=False, indent=1)
    except Exception as exc:
        print("me/boards 抓取失败:", exc)

    print(
        f"snapshot {meta['ranking_snapshot_id']} | cutoff {meta['data_cutoff_at']} "
        f"| pools {meta['row_count']} | my_rank {meta['my_rank']}"
    )
    for row in rows[:10]:
        m = row.get("metrics", {})

        def fmt(key: str) -> str:
            value = m.get(key)
            return f"{value:.3f}" if isinstance(value, (int, float)) else "-"

        print(
            f"{row['rank']:>3} {str(row.get('display_name'))[:18]:<18} "
            f"{float(row['score']):>8.0f} na {fmt('na')} nb {fmt('nb')} nc {fmt('nc')}"
        )


if __name__ == "__main__":
    main()
