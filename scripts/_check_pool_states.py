import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
for name in ["pool-candE-20260923-candidates.txt.state.json",
             "pool-replace-growth-b08-20260921-candidates.txt.state.json",
             "pool-alternatives-20260921-candidates.txt.state.json",
             "pool-6seat-5y-20260923-candidates.txt.state.json",
             "pool-candCD-20260922-candidates.txt.state.json"]:
    p = ROOT / name
    if not p.exists():
        print(name, "MISSING"); continue
    data = json.loads(p.read_text(encoding="utf-8"))
    print("==", name)
    print(json.dumps(data, ensure_ascii=False)[:1200])