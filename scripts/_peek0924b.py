import json, io, sys, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def walk(o, pre="", depth=0, out=None):
    if depth > 3: return
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                print("  " * depth + f"{pre}{k}: {type(v).__name__}({len(v)})")
                walk(v, "", depth + 1)
            else:
                s = str(v)
                if len(s) < 60:
                    print("  " * depth + f"{pre}{k} = {s}")
    elif isinstance(o, list) and o:
        print("  " * depth + f"[0] type {type(o[0]).__name__}")
        walk(o[0], "", depth + 1)
f = r"D:\factor\platform_pool_tests_20260924\agg.run.json"
d = json.load(open(f, encoding="utf-8"))
fa = d["results"]["factor_analysis"]
print("factor_analysis type", type(fa).__name__)
walk(fa)
