# -*- coding: utf-8 -*-
"""Recover the 2026-10-03 K20-swapF platform run that the client failed to record.

The client-side `factor_run` call crashed (a recurring pandaai-cli bug), but the
server-side run completed normally (status=2, 121.4s). This mirrors batch.py's
cache_result / state flow so a later `batch.py --report-only` just rewrites the
report from saved state, with no second charge.
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
DIR = ROOT / "research_reports" / "platform_alignment" / "k20-swap-eval-20261003"
BATCH = DIR / "pool5-swapf-lamd20k5v2-20261003-candidates.txt"
STATE = DIR / "pool5-swapf-lamd20k5v2-20261003-candidates.txt.state.json"
NAME = "POOL5-SWAPF-LAMD20K5V2-20261003"
RUN_ID = "6ac0ba49812a2a13b9645c3d"


def cli(*args: str, timeout: int = 600) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([str(CLI), "--json", *args], capture_output=True,
                          timeout=timeout, env=env)
    for encoding in ("gbk", "utf-8"):
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
    if not payload.get("success"):
        print("factor_result failed: " + json.dumps(payload, ensure_ascii=False)[:500])
        return 1
    raw_rel = batch.cache_result(BATCH, NAME, RUN_ID, payload)
    entry["run_id"] = RUN_ID
    entry["raw_result"] = raw_rel
    entry["metrics"] = batch.extract(payload, "1", 10)
    entry.pop("error", None)
    batch.save(STATE, state)
    print("raw_result =", raw_rel, flush=True)
    print("METRICS=" + json.dumps(entry["metrics"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
