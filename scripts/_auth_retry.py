import subprocess, io, sys, json, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=300):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"_raw": t[:200]}
for attempt in range(1, 5):
    r = call(["balance"])
    ok = r.get("success")
    print(f"attempt {attempt}: balance success={ok}", (r.get("error") or {}).get("type") if not ok else "")
    if ok:
        print("  computingPower", (r.get("balance") or {}).get("computingPower"))
        break
    time.sleep(3)