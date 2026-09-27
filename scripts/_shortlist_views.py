import io, sys, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor"); sys.path.insert(0, str(ROOT / "scripts"))
import platform_precheck as pp
OVER = ROOT/"research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
NEW = ROOT/"research_reports/platform_alignment/candidate-new-clusters-20260925"
OPS = pp.load_platform_ops(); TESTED = {"cand0000","cand0013","cand0003","cand0110"}
def num(v,d=0.0):
    try: return float(v)
    except (TypeError,ValueError): return d
rows = {r["candidate"]: r for r in csv.DictReader(open(OVER, encoding="utf-8-sig", newline=""))}
kept = list(csv.DictReader(open(NEW/"candidate_new_cluster_assignment.csv", encoding="utf-8-sig", newline="")))
prof = {r["cluster"]: r for r in csv.DictReader(open(NEW/"new_clusters_profile.csv", encoding="utf-8-sig", newline=""))}
best = {r["best_member"] for r in prof.values() if r.get("best_member")}
links = list(csv.DictReader(open(NEW/"new_cluster_links.csv", encoding="utf-8-sig", newline="")))
linked = {}
for r in links:
    for k in (r["new_cluster"], r["other_cluster"]):
        linked.setdefault(k, []).append(f'{r["new_cluster"]}~{r["other_cluster"]}:{float(r["max_abs_rho"]):.2f}')

recs=[]
for a in kept:
    c=a["candidate"]
    if c in TESTED: continue
    r=rows.get(c)
    if r is None: continue
    net,n26=num(r["net"]),num(r["net_y2026"]); turn,mrho,csize=num(r["turnover"]),num(r["max_abs_corr_member"]),num(r["corr_size"])
    info=pp.analyze(c, r["formula"], OPS)
    recs.append(dict(c=c,K=a["new_cluster"],net=net,n26=n26,turn=turn,mrho=mrho,seat=r["corr_max_seat_name"],
                     csize=csize,info=info,best=c in best,fsize=prof.get(a["new_cluster"],{}).get("size"),feat=prof.get(a["new_cluster"],{}).get("feature","")))

print("=== 独立性优先（rho 升序，net>=8%，2026>=3%，turn<=62%）：")
sel=[r for r in recs if r["net"]>=0.08 and r["n26"]>=0.03 and r["turn"]<=0.62]
for r in sorted(sel,key=lambda x:x["mrho"])[:12]:
    print(f"  {r['c']} {r['K']:5s} rho={r['mrho']:.3f}({r['seat']:<10s}) |size|={abs(r['csize']):.3f} net={r['net']*100:>6.2f}% 26={r['n26']*100:>6.2f}% turn={r['turn']*100:>4.0f}% best={r['best']} 量级k={r['info']['k']} 脆弱={r['info']['fragile'] or '-'} 撞名={r['info']['collisions'] or '-'}")

print("\n=== 2026 优先（n26 降序，net>=8%）：")
for r in sorted(sel,key=lambda x:-x["n26"])[:12]:
    print(f"  {r['c']} {r['K']:5s} 26={r['n26']*100:>6.2f}% net={r['net']*100:>6.2f}% turn={r['turn']*100:>4.0f}% rho={r['mrho']:.3f}({r['seat']:<10s}) |size|={abs(r['csize']):.3f} 量级k={r['info']['k']} 撞名={r['info']['collisions'] or '-'}")

for c in ("cand0040","cand0192","cand0099"):
    r=[x for x in recs if x["c"]==c][0]
    K=r["K"]
    print(f"\n[{c}/{K}] cluster_size={r['fsize']} 成员簇内最佳={r['best']}")
    print(f"  feature: {r['feat']}")
    print(f"  跨簇>0.60链接: {linked.get(K,['无'])}")
    print(f"  公式: {rows[c]['formula']}")