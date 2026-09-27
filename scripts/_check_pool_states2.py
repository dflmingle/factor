import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
targets = ["pool-cand-20260922-candidates.txt.state.json",
           "pool-cand1-3m-20260923-candidates.txt.state.json",
           "pool-cand1-1y-20260923-candidates.txt.state.json",
           "pool-3win-1y-20260923-candidates.txt.state.json",
           "pool-candAB-20260922-candidates.txt.state.json",
           "pool-best-platform-20260921-candidates.txt.state.json",
           "pool-base4-platform-20260921-candidates.txt.state.json",
           "pool-8seat-20260923-candidates.txt.state.json"]
for name in targets:
    p = ROOT / name
    if not p.exists():
        print(name, "MISSING"); continue
    data = json.loads(p.read_text(encoding="utf-8"))
    print("==", name)
    for k, v in data.items():
        if isinstance(v, dict):
            ok = "metrics" in v
            print(f"   {k}: {'OK' if ok else 'FAIL'} {v.get('error','')[:60]} {v.get('metrics',{}).get('long_excess','') if ok else ''}")
        else:
            print(f"   {k}: {str(v)[:80]}")