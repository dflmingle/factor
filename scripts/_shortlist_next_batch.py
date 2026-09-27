"""下一批可提交平台的候选：全池筛选（零算力，纯静态）。
门槛：新簇 kept 成员 + 各簇最佳成员 + net>=10% + 2026>=4% + 换手<=62% + 对已知簇 rho<=0.55 + |corr_size|<=0.55。
脆弱结构（分母含 corr）不硬排除但降权；撞名/量级用 platform_precheck 估计。
"""
import io, sys, csv, ast
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(r"D:\factor")
sys.path.insert(0, str(ROOT / "scripts"))
import platform_precheck as pp  # noqa: E402

OVER = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
NEW = ROOT / "research_reports/platform_alignment/candidate-new-clusters-20260925"
OPS = pp.load_platform_ops()
TESTED = {"cand0000", "cand0013", "cand0003", "cand0110"}


def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


rows = {r["candidate"]: r for r in csv.DictReader(open(OVER, encoding="utf-8-sig", newline=""))}
kept = list(csv.DictReader(open(NEW / "candidate_new_cluster_assignment.csv", encoding="utf-8-sig", newline="")))
prof = {r["cluster"]: r for r in csv.DictReader(open(NEW / "new_clusters_profile.csv", encoding="utf-8-sig", newline=""))}
best = {r["best_member"] for r in prof.values() if r.get("best_member")}
links = list(csv.DictReader(open(NEW / "new_cluster_links.csv", encoding="utf-8-sig", newline="")))
linked = set()
for r in links:
    linked.add(r["new_cluster"]); linked.add(r["other_cluster"])

out = []
for a in kept:
    c = a["candidate"]
    if c in TESTED:
        continue
    r = rows.get(c)
    if r is None:
        continue
    net, n26 = num(r["net"]), num(r["net_y2026"])
    turn, mrho, csize = num(r["turnover"]), num(r["max_abs_corr_member"]), num(r["corr_size"])
    seat = r["corr_max_seat_name"] or "-"
    f = r["formula"]
    try:
        info = pp.analyze(c, f, OPS)
    except SyntaxError:
        continue
    frag = info["fragile"]
    is_best = c in best
    K = a["new_cluster"]
    # 硬门槛
    gates = []
    if net < 0.10: gates.append(f"net{net:.1%}<10")
    if n26 < 0.04: gates.append(f"26:{n26:.1%}<4")
    if turn > 0.62: gates.append(f"turn{turn:.0%}>62")
    if mrho > 0.55: gates.append(f"rho{mrho:.2f}>0.55")
    if abs(csize) > 0.55: gates.append(f"|size|{abs(csize):.2f}>0.55")
    if not is_best: gates.append("非最佳成员")
    score = net + 0.8 * n26
    score -= max(0.0, mrho - 0.30) * 0.20
    score -= max(0.0, abs(csize) - 0.35) * 0.15
    if frag: score -= 0.03
    if info["collisions"]: score -= 0.005
    out.append(dict(c=c, K=K, size=prof.get(K, {}).get("size", "?"), net=net, n26=n26, turn=turn,
                    mrho=mrho, seat=seat, csize=csize, frag=",".join(frag) or "-",
                    coll=",".join(info["collisions"]) or "-", est=info["est"], k=info["k"],
                    score=score, gates=";".join(gates), f=f, is_best=is_best, linked=K in linked))

passing = [o for o in out if not o["gates"]]
print(f"kept 池 {len(kept)} 条（排除已验证 4 条）→ 通过硬门槛 {len(passing)} 条\n")
passing.sort(key=lambda o: -o["score"])
hdr = f"{'cand':9s} {'K':5s} {'net':>7s} {'2026':>7s} {'turn':>5s} {'rho':>5s} {'seat':<13s} {'|size|':>6s} {'量级':>9s} {'k':>3s}  脆弱/撞名"
print(hdr); print("-" * len(hdr))
for o in passing[:20]:
    print(f"{o['c']:9s} {o['K']:5s} {o['net']*100:>6.2f}% {o['n26']*100:>6.2f}% {o['turn']*100:>4.0f}% "
          f"{o['mrho']:>5.3f} {o['seat']:<13s} {abs(o['csize']):>6.3f} {o['est']:>9.2e} {o['k']:>3d}  {o['frag']} / {o['coll']}")

print(f"\n落选里净额/2026 高但被单项卡住的（top10 by net）：")
rejected = sorted([o for o in out if o["gates"]], key=lambda o: -o["net"])
for o in rejected[:10]:
    print(f"{o['c']:9s} {o['K']:5s} net={o['net']*100:>6.2f}% 26={o['n26']*100:>6.2f}% turn={o['turn']*100:>4.0f}% "
          f"rho={o['mrho']:.3f} |size|={abs(o['csize']):.3f} 卡: {o['gates']}")