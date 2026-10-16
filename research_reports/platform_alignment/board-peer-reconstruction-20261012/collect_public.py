"""Archive public competition evidence; never creates factors or runs backtests."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

import yaml

OUT = Path(__file__).resolve().parent
TARGET_NAMES = {"不知所云队", "不抵灼灼目光", "Alpha猎手", "ChenQiLong", "弈星"}
CONTROL_NAMES = {"疯猫子", "hulai", "ddd"}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if (OUT / "evidence_manifest.json").exists():
        raise RuntimeError("Evidence already frozen; use a new dated directory for a refresh")
    cfg = yaml.safe_load((Path.home() / ".pandaai/config.yaml").read_text())

    def get(path):
        request = urllib.request.Request(
            cfg["gateway_url"].rstrip("/") + path,
            headers={"Authorization": cfg["token"], "uid": str(cfg["uid"]), "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.load(response)
        if not isinstance(body.get("data"), dict):
            raise RuntimeError("Expected an authenticated public leaderboard response")
        return body["data"]

    first = get("/arenaRanking/boards/points?period=2026&page=1&pageSize=20")
    meta = {k: first.get(k) for k in ["ranking_snapshot_id", "published_at", "data_cutoff_at", "row_count", "pool_total", "formula_version", "snapshot_type", "is_estimate"]}
    rows = list(first["rows"])
    for page in range(2, (int(first["row_count"]) + 19) // 20 + 1):
        data = get(f"/arenaRanking/boards/points?period=2026&page={page}&pageSize=20")
        if data.get("ranking_snapshot_id") != meta["ranking_snapshot_id"]:
            raise RuntimeError("Snapshot changed during collection")
        rows.extend(data["rows"])
    if len(rows) != first["row_count"] or len({r["pool_id"] for r in rows}) != len(rows):
        raise RuntimeError("Missing or duplicated leaderboard rows")
    write_json(OUT / "board_live.json", {"meta": meta, "rows": rows})
    flat = []
    for row in rows:
        flat.append({**{k: row.get(k) for k in ["participant_id", "pool_id", "display_name", "pool_name", "rank", "active_factor_count", "pool_age_months"]}, **(row.get("metrics") or {})})
    write_csv(OUT / "pool_metrics.csv", flat)
    write_csv(OUT / "current_full_C_pools.csv", [r for r in flat if r.get("score_period") == "2026-10" and r.get("nc") == 1])

    selected = [r for r in rows if r.get("display_name") in TARGET_NAMES | CONTROL_NAMES]
    details, factors, histories = [], [], []
    for row in selected:
        for period in ["2026-09", "2026-10"]:
            path = "/arenaRanking/players/" + row["participant_id"] + "?period=" + period
            data = get(path)
            item = {"participant_id": row["participant_id"], "pool_id": row["pool_id"], "display_name": row.get("display_name"), "period": period, "source_path": path, "data": data}
            details.append(item)
            for f in data.get("factor_pool_details") or []:
                factors.append({"participant_id": row["participant_id"], "pool_id": row["pool_id"], "display_name": row.get("display_name"), "period": period, "cycle": (data.get("header") or {}).get("rebalance_cycle_days"), **f})
            histories.append({"participant_id": row["participant_id"], "display_name": row.get("display_name"), "requested_period": period, **(data.get("breakdown") or {})})
    write_json(OUT / "public_player_details.json", details)
    write_csv(OUT / "factor_targets.csv", factors)
    write_csv(OUT / "monthly_pool_metrics.csv", histories)
    changes = []
    for row in selected:
        pair = [d for d in details if d["participant_id"] == row["participant_id"]]
        old, new = [{f["factor_instance_id"]: f for f in d["data"].get("factor_pool_details") or []} for d in pair]
        changes.append({"display_name": row.get("display_name"), "old_seats": len(old), "new_seats": len(new), "retained_instances": len(old.keys() & new.keys()), "added_instances": len(new.keys() - old.keys()), "removed_instances": len(old.keys() - new.keys()), "same_instance_does_not_prove_same_formula": True})
    write_csv(OUT / "seat_changes.csv", changes)
    files = ["board_live.json", "pool_metrics.csv", "current_full_C_pools.csv", "public_player_details.json", "factor_targets.csv", "monthly_pool_metrics.csv", "seat_changes.csv"]
    write_json(OUT / "evidence_manifest.json", {"collected_at_utc": datetime.now(timezone.utc).isoformat(), "meta": meta, "platform_runs": 0, "platform_compute": 0, "source": "account-visible public competition leaderboard and public player profiles", "target_names": sorted(TARGET_NAMES), "control_names": sorted(CONTROL_NAMES), "details_count": len(details), "factor_rows": len(factors), "private_formula_available": False, "daily_opponent_signals_available": False, "hashes": {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in files}})
    print(json.dumps({"status": "recorded", "pools": len(rows), "selected_players": len(selected), "factor_rows": len(factors), "platform_compute": 0, "meta": meta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
