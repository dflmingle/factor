import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json")
d = json.loads(p.read_text(encoding="utf-8"))
fa = d["results"]["factor_analysis"]
print("factor_analysis keys:", list(fa))
for k, v in fa.items():
    if isinstance(v, list):
        print(f"  {k}: list len={len(v)}")
        if v and isinstance(v[0], dict):
            print("     row0 keys:", list(v[0]))
            print("     row0:", json.dumps(v[0], ensure_ascii=False)[:300])
    elif isinstance(v, dict):
        print(f"  {k}: dict keys={list(v)[:10]}")
    else:
        print(f"  {k}: {str(v)[:120]}")