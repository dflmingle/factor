import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\round6b\candidates_panda.results")
for f in sorted(base.glob("*.json")):
    raw = json.loads(f.read_text(encoding="utf-8"))
    rj = json.loads([v for v in raw["results"]["nodes"].values() if isinstance(v, dict) and "result_json" in v][0]["result_json"])
    print("==", f.name, "| billed:", raw.get("billing", {}).get("deducted"))
    print("   ", {i["indicator"]: i["factor1"] for i in rj["factor_data_analysis"]})
    for g in rj["group_return_analysis"]:
        print(f"    {g['group']:8s} excess={g['excessAnnualized']:>8s} turn={g.get('turnoverRate','?'):>8s} win={g.get('monthlyWinRate','?'):>8s}")
