import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/platform_pool_tests_20260926/pool6-t4v5-20260926-candidates.results/6ab764a7cd820fa2a40a6cd2.json")
d = json.loads(p.read_text(encoding="utf-8"))
print(json.dumps(d["results"], ensure_ascii=False, indent=2)[:1500])