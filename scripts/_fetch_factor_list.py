import subprocess, io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=300):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"_raw": t[:300]}
lst = call(["factor_list", "--limit", "60"])
open(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\factor_list_60.json", "w", encoding="utf-8").write(json.dumps(lst, ensure_ascii=False, indent=1))
print("success", lst.get("success"), "keys", list(lst.keys())[:12])
items = lst.get("factors") or lst.get("items") or lst.get("data") or []
print("n", len(items) if isinstance(items, list) else type(items))
if isinstance(items, list) and items:
    print("sample keys", list(items[0].keys())[:20])
    for it in items[:12]:
        print(" ", it.get("name"), "|", it.get("_id"), "|", str(it.get("content"))[:90])