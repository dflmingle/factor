#!/usr/bin/env python3
"""只读抓取 PandaAI 榜单全部池的席位明细（factor_pool_details），零算力。

输出：out/all_pool_details.json（每池 header/radar/席位明细）
      out/factors_all.csv（全部席位条目展开为一行一因子）
用法：python3 scripts/grab_board_details_20260929.py \
        --board research_reports/platform_alignment/board-20260928/board_live.json \
        --out research_reports/platform_alignment/board-details-20260929
"""
import argparse
import csv
import json
import os
import time
import urllib.request
from pathlib import Path

import yaml

CONFIG = os.path.expanduser("~/.pandaai/config.yaml")


def get_one(gateway: str, path: str, token: str, uid: str) -> dict:
    req = urllib.request.Request(
        gateway + path,
        headers={"Authorization": token, "uid": str(uid), "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="research_reports/platform_alignment/board-20260928/board_live.json")
    ap.add_argument("--out", default="research_reports/platform_alignment/board-details-20260929")
    ap.add_argument("--sleep", type=float, default=0.12)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(CONFIG))
    gateway = cfg["gateway_url"].rstrip("/")
    token, uid = cfg["token"], cfg["uid"]

    board = json.load(open(args.board))
    rows = board["rows"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    details: dict = {}
    factor_rows: list[dict] = []
    for i, r in enumerate(rows, 1):
        pid = r["participant_id"]
        try:
            data = get_one(gateway, f"/arenaRanking/players/{pid}", token, uid)["data"]
        except Exception as exc:  # noqa: BLE001 - 只读抓取，失败跳过
            print(f"[{i}/{len(rows)}] {str(r.get('display_name'))[:16]} FAILED {type(exc).__name__}: {exc}")
            time.sleep(args.sleep)
            continue
        details[pid] = {
            "display_name": r.get("display_name"),
            "pool_name": r.get("pool_name"),
            "rank": r.get("rank"),
            "header": data.get("header"),
            "pool_radar": data.get("pool_radar"),
            "factor_pool_details": data.get("factor_pool_details"),
        }
        for f in data.get("factor_pool_details") or []:
            factor_rows.append({
                "rank": r.get("rank"),
                "display_name": r.get("display_name"),
                "pool_name": r.get("pool_name"),
                "cycle": (data.get("header") or {}).get("rebalance_cycle_days"),
                "participant_id": pid,
                **f,
            })
        if i % 40 == 0:
            print(f"[{i}/{len(rows)}] {len(factor_rows)} factors ...")
        time.sleep(args.sleep)

    (out / "all_pool_details.json").write_text(
        json.dumps(details, ensure_ascii=False), encoding="utf-8"
    )

    if factor_rows:
        keys = list(factor_rows[0].keys())
        with open(out / "factors_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(factor_rows)

    print(f"pools={len(details)}/{len(rows)} factors={len(factor_rows)} -> {out}")


if __name__ == "__main__":
    main()
