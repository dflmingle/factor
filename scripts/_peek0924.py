import json, io, sys, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
for f in sorted(glob.glob(r"D:\factor\platform_pool_tests_20260924\*.run.json")):
    d = json.load(open(f, encoding="utf-8"))
    print("==", f.split("\\")[-1], "billing:", json.dumps(d.get("billing"), ensure_ascii=False)[:200])
    r = d.get("results")
    if isinstance(r, dict):
        print("   result keys:", list(r.keys())[:20])
        for k, v in r.items():
            if isinstance(v, (str, int, float)):
                print("     ", k, "=", v)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                print("     ", k, "= list(%d) sample:" % len(v), json.dumps(v[0], ensure_ascii=False)[:200])
    else:
        print("   results type", type(r))
