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
print("非最佳成员中 net>=10% 且 rho<=0.55 的：")
n=0
for a in kept:
    c=a["candidate"]
    if c in TESTED or c in best: continue
    r=rows.get(c)
    if r is None: continue
    net,n26,turn,mrho=num(r["net"]),num(r["net_y2026"]),num(r["turnover"]),num(r["max_abs_corr_member"])
    if net>=0.10 and mrho<=0.55:
        n+=1
        info=pp.analyze(c,r["formula"],OPS)
        print(f"  {c} {a['new_cluster']} net={net:.2%} 26={n26:.2%} turn={turn:.0%} rho={mrho:.3f} |size|={abs(num(r['corr_size'])):.3f} k={info['k']} 脆弱={info['fragile'] or '-'} 撞名={info['collisions'] or '-'}")
print("(总计", n, "条)")

# 顺带看：全 kept 里 net>=10% 且 rho<=0.55 但被"非最佳成员"卡住的完整名单
print("\nkept 中 net>=10% 且 rho<=0.55 全部（含非最佳）：")
for a in kept:
    c=a["candidate"]
    if c in TESTED: continue
    r=rows.get(c)
    if r is None: continue
    net,mrho=num(r["net"]),num(r["max_abs_corr_member"])
    if net>=0.10 and mrho<=0.55:
        print(f"  {c} {a['new_cluster']} best={c in best} net={net:.2%} rho={mrho:.3f}")