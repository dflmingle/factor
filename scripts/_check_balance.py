import subprocess, io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=600):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"success": False, "error": {"type": "PARSE", "message": t[:200]}}
b = call(["balance"])
print("balance:", (b.get("balance") or {}).get("computingPower"))
i = call(["factor_info", "6ab6372fcd820fa2a40a6b86"])
print("K015 info:", json.dumps({k: v for k, v in i.items() if k not in ("success",)}, ensure_ascii=False)[:500])