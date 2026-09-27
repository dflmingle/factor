import io, sys, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
NEW = Path(r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925")
links = list(csv.DictReader(open(NEW/"new_cluster_links.csv", encoding="utf-8-sig", newline="")))
mine = ["K008", "K015", "K020", "K021"]
print("== 两两相关（new_cluster_links）==")
for r in links:
    a, b = r["new_cluster"], r["other_cluster"]
    if a in mine and b in mine:
        print(f"  {a} - {b}: max_abs_rho={float(r['max_abs_rho']):.3f} signed={float(r['signed_rho']):+.3f} kind={r['other_kind']}")
print()
print("== 各簇与其他新簇的最大相关（前5）==")
for k in mine:
    rows = [r for r in links if r["new_cluster"] == k and r["other_kind"] == "new_cluster"]
    rows.sort(key=lambda r: -float(r["max_abs_rho"]))
    print(f"  {k}: " + "  ".join(f"{r['other_cluster']}:{float(r['max_abs_rho']):.3f}" for r in rows[:5]))
print()
print("== 各簇与已知簇（B/N系）的最大相关（前5）==")
for k in mine:
    rows = [r for r in links if r["new_cluster"] == k and r["other_kind"] != "new_cluster"]
    rows.sort(key=lambda r: -float(r["max_abs_rho"]))
    print(f"  {k}: " + "  ".join(f"{r['other_cluster']}:{float(r['max_abs_rho']):.3f}" for r in rows[:5]))
