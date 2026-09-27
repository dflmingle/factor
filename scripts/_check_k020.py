import subprocess, io, sys, json, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=300):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"success": False, "error": {"type": "PARSE", "message": t[:200]}}
i = call(["factor_info", "6ab638cfb8f0d75493c831a7"])
print("K020 info:", json.dumps(i, ensure_ascii=False)[:400])
rid = i.get("last_run_id")
if rid:
    r = call(["factor_result", rid])
    print("run", rid, "status", r.get("status"), "success", r.get("success"),
          "duration", r.get("duration_seconds"), "start", r.get("start_time"), "end", r.get("end_time"))
    fa = r.get("factor_analysis") or {}
    print("analysis keys", list(fa.keys()) if isinstance(fa, dict) else type(fa))