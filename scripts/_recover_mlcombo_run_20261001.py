"""Submit/recover the ML-GBDT-WF platform run, guarding against double charges.

2026-10-01 evening, the submission kept failing at the `factor_run` submit step while
balance / factor_info calls on the same token succeeded: first a client read timeout
(15s), then two client-side auth rejections. The timed-out attempt left no server-side
run (`factor_info.last_run_id` stayed null, nothing charged).

Guard: after every failed submit, this helper re-checks `factor_info.last_run_id`. If
the server actually started a run, it stops instead of submitting a second one (a
duplicate submit would charge again). On success it mirrors batch.py's cache_result /
state flow, so a later batch.py invocation only rewrites the report.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "skill-pandaai-factor-online" / "scripts"))
import batch  # noqa: E402

CLI = Path.home() / ".local" / "bin" / "pandaai-cli.exe"
DIR = ROOT / "research_reports" / "platform_alignment" / "ml-combo-platform-20261001"
STATE = DIR / "candidates.txt.state.json"
NAME = "ML-GBDT-WF"
ATTEMPTS = 3
SLEEP_S = 90


def cli(*args: str, timeout: int = 600) -> dict:
    proc = subprocess.run([str(CLI), "--json", *args], capture_output=True, timeout=timeout)
    for encoding in ("gbk", "utf-8"):
        try:
            return json.loads(proc.stdout.decode(encoding))
        except (UnicodeDecodeError, ValueError):
            continue
    return json.loads(proc.stdout.decode("utf-8", "replace"))


def record(entry: dict, state: dict, payload: dict, run_id: str) -> bool:
    raw_path = DIR / "candidates.results" / f"{run_id}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    batch.save(raw_path, payload)
    entry["run_id"] = run_id
    entry["raw_result"] = str(raw_path.relative_to(DIR))
    try:
        entry["metrics"] = batch.extract(payload, "1", 10)
    except ValueError as exc:
        print(f"EXTRACT_FAILED: {exc}", flush=True)
        batch.save(STATE, state)
        return False
    entry.pop("error", None)
    batch.save(STATE, state)
    print("METRICS=" + json.dumps(entry["metrics"], ensure_ascii=False), flush=True)
    return True


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    entry = state[NAME]
    if entry.get("metrics"):
        print(f"{NAME}: metrics already recorded, nothing to do", flush=True)
        return 0
    factor_id = entry["factor_id"]

    force = "--force" in sys.argv[1:]
    pending = cli("factor_info", factor_id, timeout=120).get("last_run_id")
    print(f"precheck: last_run_id = {pending} force={force}", flush=True)
    if pending and not force:
        print("a server-side run already exists; recover it with factor_result "
              "before submitting anything", flush=True)
        return 2
    if pending and force:
        print("--force: previous run treated as terminal (failed); re-submitting anyway",
              flush=True)
    baseline = pending

    for attempt in range(1, ATTEMPTS + 1):
        print(f"attempt {attempt}/{ATTEMPTS}: factor_run {factor_id}", flush=True)
        try:
            payload = cli("factor_run", factor_id, "--poll-interval", "15",
                          "--timeout", "2400", timeout=2500)
        except subprocess.TimeoutExpired:
            payload = {"success": False, "error": {"message": "client TimeoutExpired"}}
        error = payload.get("error") or {}
        print(f"  success={bool(payload.get('success'))} run_id={payload.get('factor_run_id')} "
              f"error_type={error.get('type')} error={str(error.get('message'))[:200]}", flush=True)
        if payload.get("success"):
            run_id = payload.get("factor_run_id")
            if not run_id:
                print("  success payload has no factor_run_id; inspect manually", flush=True)
                return 3
            return 0 if record(entry, state, payload, str(run_id)) else 4
        run_id = payload.get("factor_run_id")
        if run_id:
            raw_path = DIR / "candidates.results" / f"{run_id}.failed.json"
            batch.save(raw_path, payload)
            print(f"  saved failed payload -> {raw_path.relative_to(DIR)}", flush=True)
        print("  status/duration: " + json.dumps({k: payload.get(k) for k in
              ("status", "duration_seconds", "start_time", "end_time")})[:300], flush=True)
        pending = cli("factor_info", factor_id, timeout=120).get("last_run_id")
        print(f"  last_run_id now = {pending} (baseline {baseline})", flush=True)
        if pending and pending != baseline:
            print("  a new server-side run exists; stop retrying and recover it", flush=True)
            return 2
        if pending == baseline and pending:
            print("  still the previous terminal run; the submit did not land", flush=True)
        if attempt < ATTEMPTS:
            time.sleep(SLEEP_S)
    print("all submit attempts failed and no server-side run was created; nothing charged",
          flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
