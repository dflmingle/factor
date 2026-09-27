import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/research_reports/platform_alignment/factor_alignment_failure_registry.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("top keys:", list(d) if isinstance(d, dict) else type(d).__name__)
if isinstance(d, dict):
    for k, v in d.items():
        if isinstance(v, list):
            print(f"  {k}: list len={len(v)}")
        else:
            print(f"  {k}: {str(v)[:200]}")
    recs = d.get("records") or d.get("entries") or []
    if recs:
        print("\nsample record:")
        print(json.dumps(recs[-1], ensure_ascii=False, indent=2)[:1800])