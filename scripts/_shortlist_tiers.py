import io, sys, csv, ast
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor"); sys.path.insert(0, str(ROOT / "scripts"))
import platform_precheck as pp
OVER = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
NEW = ROOT / "research_reports/platform_alignment/candidate-new-clusters-20260925"
OPS = pp.load_platform_ops()
TESTED = {"cand0000", "cand0013", "cand0003", "cand0110"}
def num(v, d=0.0):
    try: return float(v)
    except (TypeError, ValueError): return d
rows = {r["candidate"]: r for r in csv.DictReader(open(OVER, encoding="utf-8-sig", newline=""))}
kept = list(csv.DictReader(open(NEW/"candidate_new_cluster_assignment.csv", encoding="utf-8-sig", newline="")))
prof = {r["cluster"]: r for r in csv.DictReader(open(NEW/"new_clusters_profile.csv", encoding="utf-8-sig", newline=""))}
best = {r["best_member"] for r in prof.values() if r.get("best_member")}

def tier(rho_max, size_max):
    out=[]
    for a in kept:
        c=a["candidate"]
        if c in TESTED: continue
        r=rows.get(c)
        if r is None: continue
        net,n26=num(r["net"]),num(r["net_y2026"]); turn,mrho,csize=num(r["turnover"]),num(r["max_abs_corr_member"]),num(r["corr_size"])
        if not (net>=0.10 and n26>=0.04 and turn<=0.62 and mrho<=rho_max and abs(csize)<=size_max): continue
        if c not in best: continue
        info=pp.analyze(c, r["formula"], OPS)
        out.append((c,a["new_cluster"],net,n26,turn,mrho,r["corr_max_seat_name"],csize,info))
    return out

for rho_max,size_max,label in [(0.55,0.55,"Tier-A rho<=0.55"),(0.62,0.62,"Tier-B rho<=0.62"),(0.70,0.70,"Tier-C rho<=0.70")]:
    lst=tier(rho_max,size_max)
    print(f"### {label}：{len(lst)} 条")
    for c,K,net,n26,turn,mrho,seat,csize,info in sorted(lst,key=lambda t:-(t[2]+0.8*t[3])):
        print(f"  {c} {K:5s} net={net*100:>6.2f}% 26={n26*100:>6.2f}% turn={turn*100:>4.0f}% rho={mrho:.3f}({seat}) |size|={abs(csize):.3f} 量级={info['est']:.2e} k={info['k']} 脆弱={info['fragile'] or '-'} 撞名={info['collisions'] or '-'}")
    print()

print("### 严门槛 2 条 + Tier-B 新增的公式：")
seen=set()
for rho_max,size_max in [(0.62,0.62)]:
    for c,K,net,n26,turn,mrho,seat,csize,info in sorted(tier(rho_max,size_max),key=lambda t:-(t[2]+0.8*t[3])):
        if c in seen: continue
        seen.add(c)
        print(f"\n[{c} / {K}] net={net:.2%} 26={n26:.2%} turn={turn:.0%} rho={mrho:.3f} |size|={abs(csize):.3f}")
        print(f"  本地式: {rows[c]['formula']}")
        print(f"  cluster: {prof[K]['feature']}")