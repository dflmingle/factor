import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json")
d = json.loads(p.read_text(encoding="utf-8"))
fa = d["results"]["factor_analysis"]
for key in ("query_return_chart", "query_factor_excess_chart", "query_one_group_data"):
    v = fa.get(key)
    print("==", key, "type", type(v).__name__)
    if isinstance(v, dict):
        for k2, v2 in v.items():
            if isinstance(v2, list):
                print(f"   {k2}: list len={len(v2)} head={json.dumps(v2[:5], ensure_ascii=False)[:300]}")
            else:
                print(f"   {k2}: {str(v2)[:200]}")