"""Recover/complete paid PandaAI runs for the vv6-500-756 batch (client decode crash).

2026-09-30: batch.py died twice with UnicodeDecodeError while reading `factor_run`
output. On this box the CLI emits UTF-8 when PYTHONIOENCODING is set and GBK when it is
not, while batch.py always decodes with the locale codec (GBK). Server-side the runs
still execute and charge, so this helper works around the client bug:

- VV6-500-platform already has a finished run -> pull it via `factor_result` (free).
- VV6-756-platform has no run yet -> `factor_run` it once (charges ~2.0), then pull.

Raw payloads are written where batch.py's cache_result would put them and metrics are
recorded in the state file, so a later `batch.py` invocation only writes the report and
does not re-run either candidate.
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
DIR = ROOT / "research_reports" / "platform_alignment" / "vv6-500-756-platform-20260930"
STATE = DIR / "candidates.txt.state.json"
NAMES = ["VV6-500-platform", "VV6-756-platform"]


def cli(*args: str) -> dict:
    # Pin the CLI's stdout encoding; the JSON payload contains Chinese labels.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([str(CLI), "--json", *args], capture_output=True, env=env,
                          timeout=2400)
    return json.loads(proc.stdout.decode("utf-8"))


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    for name in NAMES:
        entry = state[name]
        if entry.get("metrics"):
            print(f"{name}: already recorded, skip")
            continue
        run_id = entry.get("run_id")
        if not run_id:
            info = cli("factor_info", entry["factor_id"])
            run_id = info.get("last_run_id")
        if run_id:
            print(f"{name}: finished run {run_id} found -> factor_result (free)")
            payload = cli("factor_result", str(run_id))
        else:
            print(f"{name}: no run yet -> factor_run (charges ~2.0)")
            payload = cli("factor_run", entry["factor_id"])
            if not payload.get("success"):
                entry["error"] = f"run: {payload.get('error', {}).get('message', payload)}"
                batch.save(STATE, state)
                print(f"{name}: run failed: {entry['error']}")
                continue
            run_id = payload.get("factor_run_id")
        raw_path = DIR / "candidates.results" / f"{run_id}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        batch.save(raw_path, payload)
        entry["run_id"] = run_id
        entry["raw_result"] = str(raw_path.relative_to(DIR))
        entry["metrics"] = batch.extract(payload, "1", 10)
        entry.pop("error", None)
        batch.save(STATE, state)
        print(f"{name}: " + json.dumps(entry["metrics"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
