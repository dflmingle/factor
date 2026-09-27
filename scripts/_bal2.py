import subprocess, io, sys, json, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1")
for attempt in range(1, 6):
    p = subprocess.run(["pandaai-cli", "--json", "balance"], capture_output=True, env=env, timeout=300)
    t = p.stdout.decode("utf-8", errors="replace")
    try:
        r = json.loads(t)
    except Exception:
        r = {}
    if r.get("success"):
        bal = r.get("balance") or {}
        print("computingPower", bal.get("computingPower"), "gift", bal.get("giftBalance"),
              "expire", bal.get("nextExpireAt"))
        break
    print("attempt", attempt, "failed:", (r.get("error") or {}).get("type"))
    time.sleep(5)