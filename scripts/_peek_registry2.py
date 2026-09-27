import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.loads(Path("D:/factor/research_reports/platform_alignment/factor_alignment_failure_registry.json").read_text(encoding="utf-8"))
recs = d["unacceptable_records"]
print("n =", len(recs))
for r in recs[-2:]:
    print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])
    print("---")
print("keys of first:", list(recs[0]))