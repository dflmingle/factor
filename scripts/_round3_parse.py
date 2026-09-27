import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\round3\candidates_panda.results\6ab66330812a2a13b9644c76.json")
raw = json.loads(p.read_text(encoding="utf-8"))
node = raw["results"]["nodes"]["25c44d05-55f2-450a-a696-3fd21f080754"]
rj = json.loads(node["result_json"])
for item in rj["factor_data_analysis"]:
    print(f"  {item['indicator']:16s} {item['factor1']}")
print()
print("groups:")
for g in rj["group_return_analysis"]:
    print(f"  {g['group']:8s} ann={g['annualizedReturn']:>8s} excess={g['excessAnnualized']:>8s} "
          f"turn={g.get('turnoverRate','?'):>8s} mdd={g.get('maxDrawdown','?'):>8s}")
print()
print("other keys:", [k for k in rj.keys()])
