import io, sys, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
NEW = Path(r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925")
links = list(csv.DictReader(open(NEW/"new_cluster_links.csv", encoding="utf-8-sig", newline="")))
rhos = sorted(float(r["max_abs_rho"]) for r in links if r["max_abs_rho"].replace(".","").isdigit())
print("links 条数:", len(links), "| rho 范围:", f"{rhos[0]:.3f} ~ {rhos[-1]:.3f}")
prof = {r["cluster"]: r for r in csv.DictReader(open(NEW/"new_clusters_profile.csv", encoding="utf-8-sig", newline=""))}
for k in ["K008", "K015", "K020", "K021"]:
    p = prof.get(k, {})
    print(f"{k}: size={p.get('size')} feature={p.get('feature')} best={p.get('best_member')} "
          f"net_range={p.get('net_range')} turn_range={p.get('turnover_range')} dd_range={p.get('drawdown_range')} "
          f"rankic_range={p.get('rank_ic_range')} nearest_known={p.get('nearest_known_factor')}/{p.get('max_known_abs_rho')} "
          f"high_corr={p.get('high_correlation_clusters')!r}")
