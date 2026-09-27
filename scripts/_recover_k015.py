import subprocess, io, sys, json, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925"
env = dict(os.environ, PYTHONUTF8="1")

def call(args, timeout=900):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"success": False, "error": {"type": "PARSE", "message": t[:300]}}

print("state:")
sp = os.path.join(BASE, "candidates_panda.txt.state.json")
if os.path.exists(sp):
    st = json.load(open(sp, encoding="utf-8"))
    for k, v in st.items():
        print("  ", k, {kk: str(vv)[:80] for kk, vv in v.items() if kk != "raw_result"})
else:
    print("   (none)")

info = call(["factor_info", "6ab6372fcd820fa2a40a6b86"])
print("K015 factor_info last_run_id:", info.get("last_run_id"), "success", info.get("success"))
rid = info.get("last_run_id")
if rid:
    res = call(["factor_result", rid])
    open(os.path.join(BASE, "run_K015.json"), "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print("result success", res.get("success"), "status", res.get("status"), "keys", list(res.keys()))
    fa = res.get("factor_analysis") or {}
    print("factor_analysis keys:", list(fa.keys()) if isinstance(fa, dict) else type(fa))
    nodes = res.get("nodes") or {}
    print("nodes type", type(nodes).__name__, "n", len(nodes) if hasattr(nodes, "__len__") else "?")
    if isinstance(nodes, dict):
        for k, v in nodes.items():
            print("   node", k, list(v.keys())[:12] if isinstance(v, dict) else str(v)[:150])