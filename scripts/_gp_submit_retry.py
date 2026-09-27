"""Submit platform-syntax GP candidates to PandaAI with auth-retry and resumable state.

Local AlphaPROBE operator spellings (TsStd/TsMax/Inv/Sub/Div/TsDiv) are rejected by the
platform workflow with error 10068 (undefined variable), so this runner submits the
rendered platform formulas from ``alphaprobe_gp_tushare.expression_to_panda_formula``.

A dead run (for example the platform's "计费服务超时" failure, which returns status 8 after
0.04s with no analysis nodes) makes ``factor_run`` poll until its own timeout, so the CLI is
launched through Popen with a hard wall-clock cap; on expiry the CLI is killed and the run is
harvested through ``factor_result`` instead.
"""
from __future__ import annotations

import argparse, json, os, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, r"D:\factor\vendor\skill-pandaai-factor-online\scripts")
sys.path.insert(0, r"D:\factor\scripts")
import batch  # noqa: E402
import platform_run_extract_20260925 as px  # noqa: E402

BASE = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925")
CAND = Path(os.environ.get("PANDA_CAND", str(BASE / "candidates_panda.txt")))
STATE = CAND.with_suffix(CAND.suffix + ".state.json")
DOWNLOAD = CAND.parent / "downloads"
LOG = CAND.parent / (CAND.stem + ".submit.log")
RETRY_TYPES = {"LOGIN_REQUIRED", "NETWORK", "TIMEOUT", "SERVER_ERROR"}
RUN_WALL_CAP = 260


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace")


def call(args: list[str], timeout: int = 2400) -> dict:
    env = dict(os.environ, PYTHONUTF8="1")
    for attempt in range(1, 7):
        proc = subprocess.Popen(["pandaai-cli", "--json", *args], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            return {"success": False, "error": {"type": "TIMEOUT", "message": "cli wall clock"}}
        text = _decode(out)
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {"success": False, "error": {"type": "PARSE", "message": text[:300]}}
        if payload.get("success"):
            return payload
        error = payload.get("error") or {}
        billed = (payload.get("billing") or {}).get("deducted") or 0
        if error.get("type") in RETRY_TYPES and not billed and attempt < 6:
            log(f"    retry {attempt} after {error.get('type')}: {str(error.get('message'))[:70]}")
            time.sleep(4 * attempt)
            continue
        return payload
    return {"success": False, "error": {"type": "RETRIES_EXHAUSTED"}}


def start_run(factor_id: str) -> dict:
    """Submit a run; never let the CLI poll a dead run for the full timeout."""
    env = dict(os.environ, PYTHONUTF8="1")
    args = ["pandaai-cli", "--json", "factor_run", factor_id, "--download", str(DOWNLOAD),
            "--poll-interval", "15", "--timeout", "180"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    started = time.time()
    try:
        out, err = proc.communicate(timeout=RUN_WALL_CAP)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        log(f"    cli poll exceeded {RUN_WALL_CAP}s, killed; harvesting via factor_result")
        return {"success": False, "error": {"type": "POLL_CAPPED",
                                            "message": f"{time.time() - started:.0f}s"}}
    text = _decode(out)
    try:
        return json.loads(text)
    except ValueError:
        return {"success": False, "error": {"type": "PARSE", "message": text[:300]}}


def harvest(factor_id: str, direction: str, payload: dict | None = None) -> tuple[dict, str]:
    """Return (metrics, run_id); re-fetching through factor_result when the payload is partial."""
    for attempt in range(1, 5):
        if payload is not None:
            try:
                return px.metrics(payload, direction, 10), ""
            except ValueError:
                pass
        info = call(["factor_info", factor_id])
        run_id = info.get("last_run_id")
        if not run_id:
            time.sleep(20)
            continue
        result = call(["factor_result", run_id])
        status = result.get("status")
        try:
            return px.metrics(result, direction, 10), str(run_id)
        except ValueError as exc:
            log(f"    not ready (status={status}, {exc}); retry {attempt} in 30s")
            time.sleep(30)
            payload = None
    raise ValueError("metrics never became available")


def parse_candidates(path: Path) -> list[dict]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, formula, direction = [part.strip() for part in line.split("~")]
        out.append({"name": name, "formula": formula, "direction": direction})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma separated candidate names")
    ap.add_argument("--keep-error", action="store_true",
                    help="re-run candidates that already have an error recorded")
    args = ap.parse_args()
    wanted = {item for item in args.only.split(",") if item}

    candidates = parse_candidates(CAND)
    if wanted:
        candidates = [c for c in candidates if c["name"] in wanted]
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    log(f"batch start: {len(candidates)} candidates")
    for order, cand in enumerate(candidates, 1):
        name, formula, direction = cand["name"], cand["formula"], cand["direction"]
        entry = state.get(name, {})
        if entry.get("metrics"):
            log(f"[{order}/{len(candidates)}] {name}: already done, skip")
            continue
        if entry.get("error") and not args.keep_error:
            log(f"[{order}/{len(candidates)}] {name}: has error '{entry['error'][:60]}', skip "
                f"(pass --keep-error to retry)")
            continue
        log(f"[{order}/{len(candidates)}] {name}")
        factor_id = entry.get("factor_id")
        if not factor_id:
            created = call(["factor_create", "--formula", formula, "--name", name,
                            "--start-date", "20210907", "--end-date", "20260907",
                            "--adjustment-cycle", "10", "--group-number", "10",
                            "--factor-direction", direction])
            if not created.get("success"):
                entry["error"] = f"create: {(created.get('error') or {}).get('message', created)}"
                state[name] = entry
                batch.save(STATE, state)
                log(f"    CREATE FAILED: {entry['error'][:200]}")
                continue
            factor_id = created["factor_id"]
            entry = {"factor_id": factor_id}
            state[name] = entry
            batch.save(STATE, state)
            log(f"    created factor_id={factor_id}")
        else:
            log(f"    reuse factor_id {factor_id}")
        log("    run")
        result = start_run(factor_id)
        run_id = result.get("factor_run_id") or result.get("run_id")
        if run_id:
            entry["run_id"] = run_id
            entry["raw_result"] = batch.cache_result(CAND, name, run_id, result)
        if not result.get("success"):
            log(f"    run call returned {(result.get('error') or {}).get('type')}; harvesting")
        try:
            metrics, harvested_run = harvest(factor_id, direction,
                                             result if result.get("success") else None)
            entry["metrics"] = metrics
            if harvested_run:
                entry["run_id"] = harvested_run
            entry.pop("error", None)
            cost = metrics["turnover"] * 0.006 * (252.0 / 10.0)
            net = metrics["long_excess"] - cost
            log(f"    OK run={entry.get('run_id')} long={metrics['long_excess']:.2f}% "
                f"turn={metrics['turnover']:.2f}% cost={cost:.2f}% net={net:+.2f}% "
                f"rank_ic={metrics.get('rank_ic')} mono={metrics.get('monotonicity')}")
        except ValueError as exc:
            entry["error"] = f"extract: {exc}"
            log(f"    NO RESULT: {exc}")
        state[name] = entry
        batch.save(STATE, state)
    log("batch done")
    return 0


if __name__ == "__main__":
    sys.exit(main())