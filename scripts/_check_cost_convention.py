import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")

def peek(path, label):
    p = Path(path)
    if not p.exists():
        print(f"{label}: MISSING {p}")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"== {label}")
    for key in ("factor_id", "factor_run_id", "status", "billing"):
        if key in d:
            print("  ", key, "=", json.dumps(d[key], ensure_ascii=False)[:160])
    fa = (d.get("results") or {}).get("factor_analysis") or {}
    if not fa:
        print("   no factor_analysis")
        return
    groups = fa.get("query_group_return_analysis") or []
    for row in groups:
        if row.get("group") in ("分组10", "多空组合"):
            print("  ", row.get("group"), {k: row.get(k) for k in ("annualizedReturn", "excessAnnualized", "turnoverRate", "sharpeRatio", "maxDrawdown", "monthlyWinRate")})

peek(ROOT / "platform_pool_tests_20260924/agg.run.json", "AGG 09-24 pool")
peek(ROOT / "pool-candCD-20260922-candidates.results/6ab254c08b01f62dc5147d3a.json", "F-P260922-08 baseline pool")
peek(ROOT / "platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json", "T2V2 09-26 pool")

# look for cost / round trip parameters anywhere in the payloads
for path, label in [(ROOT / "platform_pool_tests_20260924/agg.run.json", "AGG"),
                    (ROOT / "pool-candCD-20260922-candidates.results/6ab254c08b01f62dc5147d3a.json", "BASE")]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    text = json.dumps(d, ensure_ascii=False)
    hits = [t for t in ("roundTrip", "round_trip", "cost", "费率", "手续费", "费用") if t in text]
    print(f"{label} param-ish tokens found:", hits)