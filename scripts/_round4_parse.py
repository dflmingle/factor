import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\round4\candidates_panda.results\6ab665922d2f6998fc1bf75d.json")
raw = json.loads(p.read_text(encoding="utf-8"))
print("billing:", raw.get("billing"))
nodes = raw["results"]["nodes"]
key = [k for k, v in nodes.items() if isinstance(v, dict) and "result_json" in v][0]
rj = json.loads(nodes[key]["result_json"])
for item in rj["factor_data_analysis"]:
    print(f"  {item['indicator']:14s} {item['factor1']}")
print()
tot = 0.0
for g in rj["group_return_analysis"]:
    print(f"  {g['group']:8s} ann={g['annualizedReturn']:>8s} excess={g['excessAnnualized']:>8s} turn={g.get('turnoverRate','?'):>8s} mdd={g.get('maxDrawdown','?'):>8s} sharpe={g.get('sharpeRatio','?'):>7s}")
