import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/platform_pool_tests_20260926/pool6-t4v5-20260926-candidates.results/6ab764a7cd820fa2a40a6cd2.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("top keys:", list(d))
print("status:", d.get("status"), "success:", d.get("success"), "dur:", d.get("duration_seconds"))
res = d.get("results")
print("results type:", type(res).__name__)
if isinstance(res, dict):
    print("results keys:", list(res))
    fa = res.get("factor_analysis")
    print("factor_analysis:", type(fa).__name__ if fa is not None else None)
    if isinstance(fa, dict):
        print("fa keys:", list(fa))
        g = fa.get("query_group_return_analysis")
        print("group rows:", len(g) if isinstance(g, list) else g)
        if isinstance(g, list):
            for row in g:
                print("  ", {k: row[k] for k in list(row)[:6]})
    elif isinstance(fa, str):
        print("fa str head:", fa[:400])
for k in ("nodes", "output", "billing", "error"):
    v = d.get(k)
    print(f"--{k}:", (json.dumps(v, ensure_ascii=False)[:400] if v is not None else None))