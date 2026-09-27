import subprocess, io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=300):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"_raw": t[:300]}
lst = call(["factor_list", "--limit", "60", "--no-detail"])
open(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\factor_list_60.json", "w", encoding="utf-8").write(json.dumps(lst, ensure_ascii=False, indent=1))
print("list success", lst.get("success"), "keys", list(lst.keys())[:10])
items = lst.get("factors") or lst.get("items") or lst.get("data") or lst.get("list") or []
if isinstance(items, dict):
    items = list(items.values())
print("n", len(items))
for it in items[:15]:
    if isinstance(it, dict):
        print(" ", it.get("name"), "|", it.get("_id") or it.get("id"))