import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")


def walk(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("factor_data_analysis"), list):
            return obj["factor_data_analysis"]
        for value in obj.values():
            found = walk(value)
            if found:
                return found
    if isinstance(obj, str) and obj.lstrip().startswith("{"):
        try:
            return walk(json.loads(obj))
        except ValueError:
            return None
    return None


def probe(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = walk(payload)
    print("==", path.name, "rows=", 0 if not rows else len(rows))
    if rows:
        print("   ", [r.get("indicator") for r in rows][:12])


probe(ROOT / "research_reports/platform_alignment/gp-platform-tests-20260925/run_K008.json")
results = ROOT / "research_reports/platform_alignment/gp-platform-tests-20260925/next-batch/candidates_panda.results"
for item in sorted(results.glob("*")):
    print("next-batch item:", item.name)