import io, sys, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
NEW = Path(r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925")
OVER = Path(r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924")
assign = {r["candidate"]: r for r in csv.DictReader(open(NEW/"candidate_new_cluster_assignment.csv", encoding="utf-8-sig", newline=""))}
prof = {r["cluster"]: r for r in csv.DictReader(open(NEW/"new_clusters_profile.csv", encoding="utf-8-sig", newline=""))}
matches = {r["candidate"]: r for r in csv.DictReader(open(OVER/"candidate_matches.csv", encoding="utf-8-sig", newline=""))}
print("assignment header:", list(next(iter(assign.values())).keys()))
print("profile header:", list(next(iter(prof.values())).keys()))
print()
for cand in ["cand0000", "cand0013", "cand0003", "cand0110"]:
    a, m = assign.get(cand, {}), matches.get(cand, {})
    k = a.get("new_cluster", "")
    pr = prof.get(k, {})
    print(f"{cand} → {k} | net={float(m['net'])*100:.2f}% 2026={float(m['net_y2026'])*100:.2f}% turn={float(m['turnover'])*100:.1f}% "
          f"| seat={m['corr_max_seat_name']} maxMem={float(m['max_abs_corr_member']):.3f}({m['max_abs_corr_member_name']}) "
          f"| cluster_known_rho={pr.get('max_known_abs_rho','?')} nearest={pr.get('nearest_known_cluster','?')} "
          f"| members={pr.get('member_count','?')} net_range={(pr.get('net_min','?'), pr.get('net_max','?'))}")
print()
print("profile keys sample:", {k: v for k, v in list(prof.items())[:1]})
