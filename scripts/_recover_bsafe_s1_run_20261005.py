# -*- coding: utf-8 -*-
"""Recover the 2026-10-05 B-safe S1 run whose run-detail fetch failed platform-side.

The run itself succeeded (status=SUCCESS, 194.3s, billing.deducted=8.0) but the
`factor_run` response carried `results.error = "获取运行详情失败"`, so the tolerant
wrapper could not parse metrics. Re-fetching `factor_result` is free; this script
mirrors the 2026-10-03 K20-swapF recovery so a later --report-only just rewrites
the report without a second charge.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "skill-pandaai-factor-online" / "scripts"))
import batch  # noqa: E402

CLI = Path.home() / ".local" / "bin" / "pandaai-cli.exe"
DIR = ROOT / "research_reports" / "platform_alignment" / "bclock-ledger-20261005"
BATCH = DIR / "candidates_bsafe.txt"
STATE = DIR / "candidates_bsafe.txt.state.json"
NAME = "POOL8-BSAFE-S1-KEEP4-DROP-SIZE-20261005"
RUN_ID = "6ac388a02d2f6998fc1c1a91"


def cli(*args: str, timeout: int = 600) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([str(CLI), "--json", *args], capture_output=True,
                          timeout=timeout, env=env)
    for encoding in ("utf-8", "gbk"):
        try:
            return json.loads(proc.stdout.decode(encoding))
        except (UnicodeDecodeError, ValueError):
            continue
    return json.loads(proc.stdout.decode("utf-8", "replace"))


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    entry = state[NAME]
    if entry.get("metrics"):
        print("metrics already recorded, nothing to do", flush=True)
        return 0
    payload = cli("factor_result", RUN_ID, timeout=600)
    print("success =", payload.get("success"), "status =", payload.get("status"), flush=True)
    try:
        metrics = batch.extract(payload, "1", 10)
    except ValueError as exc:
        print("extract failed: " + str(exc), flush=True)
        print("PAYLOAD_HEAD=" + json.dumps(payload, ensure_ascii=False)[:1500], flush=True)
        return 1
    raw_rel = batch.cache_result(BATCH, NAME, RUN_ID, payload)
    entry["run_id"] = RUN_ID
    entry["raw_result"] = raw_rel
    entry["metrics"] = metrics
    entry.pop("error", None)
    batch.save(STATE, state)
    print("raw_result =", raw_rel, flush=True)
    print("METRICS=" + json.dumps(metrics, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())