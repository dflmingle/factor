import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
p = ROOT / "platform_pool_tests_20260924" / "agg.run.json"
d = json.loads(p.read_text(encoding="utf-8"))
print(type(d), list(d)[:20] if isinstance(d, dict) else len(d))
if isinstance(d, dict):
    for k in ("factor", "name", "factorName", "definition", "type"):
        if k in d:
            print(k, "=", str(d[k])[:300])
    print(json.dumps({k: (str(v)[:200] if not isinstance(v, (dict, list)) else type(v).__name__) for k, v in d.items()}, ensure_ascii=False)[:1500])