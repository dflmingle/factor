import io, sys, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor"); sys.path.insert(0, str(ROOT/"scripts"))
import platform_precheck as pp
OVER = ROOT/"research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
NEW = ROOT/"research_reports/platform_alignment/candidate-new-clusters-20260925"
OPS = pp.load_platform_ops(); TESTED={"cand0000","cand0013","cand0003","cand0110"}
def num(v,d=0.0):
    try: return float(v)
    except (TypeError,ValueError): return d
rows={r["candidate"]:r for r in csv.DictReader(open(OVER,encoding="utf-8-sig",newline=""))}
kept=list(csv.DictReader(open(NEW/"candidate_new_cluster_assignment.csv",encoding="utf-8-sig",newline="")))
prof={r["cluster"]:r for r in csv.DictReader(open(NEW/"new_clusters_profile.csv",encoding="utf-8-sig",newline=""))}
best={r["best_member"] for r in prof.values() if r.get("best_member")}
frag_n=0; clean=[]
for a in kept:
    c=a["candidate"]
    if c in TESTED: continue
    r=rows.get(c)
    if r is None: continue
    net,n26,turn,mrho=num(r["net"]),num(r["net_y2026"]),num(r["turnover"]),num(r["max_abs_corr_member"])
    csize=num(r["corr_size"])
    info=pp.analyze(c, r["formula"], OPS)
    if info["fragile"]: frag_n+=1
    if info["fragile"] or info["collisions"]: continue
    if net>=0.08 and n26>=0.03 and turn<=0.62 and mrho<=0.55 and abs(csize)<=0.55 and c in best:
        clean.append((net,n26,turn,mrho,csize,c,a["new_cluster"],info))
print(f"kept 池 {len(kept)} 条：分母含 corr/有符号字段的 {frag_n} 条")
print(f"\n在旧门槛（net>=8%、2026>=3%、turn<=62%、rho<=0.55、|size|<=0.55、最佳成员）基础上，再排除脆弱分母后剩余 {len(clean)} 条：")
for net,n26,turn,mrho,csize,c,K,info in sorted(clean,key=lambda t:-(t[0]+0.8*t[1])):
    print(f"  {c} {K:5s} net={net*100:>6.2f}% 26={n26*100:>6.2f}% turn={turn*100:>4.0f}% rho={mrho:.3f} |size|={abs(csize):.3f} k={info['k']} 撞名={info['collisions'] or '-'}")