import subprocess, io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925"
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=600):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"success": False, "error": {"type": "PARSE", "message": t[:200]}}
rid = "6ab638d1cd820fa2a40a6b8d"
r = call(["factor_result", rid])
open(os.path.join(BASE, "run_K020.json"), "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False, indent=1))
print("status", r.get("status"), "duration", r.get("duration_seconds"), "keys", list(r.keys()))
nodes = r.get("nodes") or {}
print("nodes", type(nodes).__name__, len(nodes) if hasattr(nodes, "__len__") else "")
if isinstance(nodes, dict):
    for k, v in nodes.items():
        print("  node", k, list(v.keys())[:15] if isinstance(v, dict) else str(v)[:200])
        if isinstance(v, dict):
            for kk, vv in v.items():
                if kk != "result_json":
                    print("      ", kk, str(vv)[:200])
                else:
                    print("      result_json len", len(str(vv)), str(vv)[:600])
b = call(["balance"])
print("balance", (b.get("balance") or {}).get("computingPower"))