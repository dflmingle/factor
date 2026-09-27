import io, sys, csv, json, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import alphaprobe_gp_tushare as gp

fields = gp.formula_field_name_set(include_period_variants=True)
ref = r"D:\factor\vendor\skill-pandaai-factor-online\references\operators.md"
text = open(ref, encoding="utf-8").read()
ops = {m.group(1).lower() for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text)}
ops |= {"div","sub","add","mul","inv","pow","greater","less","tscorr","tsdiv","tsstd","tsmax",
        "tsmin","tsmean","tssum","tsvar","tsskew","tskurt","tsmed","tsmad","tsrank","tsdelta",
        "tspctchange","tswma","tsema","tscov","tsminmaxdiff","tsmaxdiff","tsmindiff","slog1p",
        "rank","abs","sign","log","ref","ma","std","var","max","min"}

NEW = r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925"
OVER = r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924"
SCREEN = r"D:\factor\research_reports\platform_alignment\relaxed-gp-20260924\screen2\screened_candidates.csv"


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def field_list(formula):
    out = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula):
        low = token.lower()
        if low in ops:
            continue
        if low in fields:
            out.append(low)
    return out


def load(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))


assign = {r["candidate"]: r for r in load(os.path.join(NEW, "candidate_new_cluster_assignment.csv"))}
profile = {r["cluster"]: r for r in load(os.path.join(NEW, "new_clusters_profile.csv"))}
matches = {r["candidate"]: r for r in load(os.path.join(OVER, "candidate_matches.csv"))}
screen = {r["formula"]: r for r in load(SCREEN)}

SIZE_FIELDS = {"amount", "a_share_market_val", "market_cap", "total_mv", "bs_total_assets",
               "cal_20d_amt_ma", "volume"}

rows = []
for cand, m in matches.items():
    formula = m["formula"]
    fl = field_list(formula)
    cal = [f for f in fl if f.startswith("cal_")]
    sz = [f for f in fl if f in SIZE_FIELDS]
    divs = formula.count("Div(") + formula.count("TsDiv(") + formula.count("Inv(")
    a = assign.get(cand, {})
    prof = profile.get(a.get("new_cluster", ""), {})
    scr = screen.get(formula, {})
    rows.append(dict(
        cand=cand, cluster=a.get("new_cluster", ""), formula=formula,
        net=num(m["net"]), turnover=num(m["turnover"]),
        net2026=num(m["net_y2026"]), rank_ic=num(scr.get("rank_ic")),
        corr_size=abs(num(m["corr_size"])), seat=m["corr_max_seat_name"],
        max_member_corr=num(m["max_abs_corr_member"]), member=m["max_abs_corr_member_name"],
        cluster_known_rho=num(prof.get("max_known_abs_rho")),
        nearest_known=prof.get("nearest_known_cluster", ""),
        fields=fl, cal=cal, size=sz, divs=divs, band=m["band"],
        rediscovery=m["is_rediscovery"], s_i_rank=num(scr.get("s_i_rank")),
        net_last12=num(scr.get("net_last12")),
    ))


def ok(r):
    return (not r["cal"] and r["net"] >= 0.10 and r["net2026"] >= 0.04
            and r["corr_size"] <= 0.50 and r["seat"] != "size_only"
            and r["cluster_known_rho"] <= 0.60 and len(r["size"]) <= 1
            and r["divs"] <= 3)


pool = sorted([r for r in rows if ok(r)], key=lambda r: -r["net"])
print(f"candidates={len(rows)}  passing filter={len(pool)}")
print()
print(f"{'cand':10s} {'K':5s} {'net':>7s} {'2026':>7s} {'12m':>7s} {'rankic':>7s} {'turn':>6s} "
      f"{'|size|':>6s} {'maxMem':>6s} {'Krho':>5s} {'div':>3s}  fields")
for r in pool[:30]:
    print(f"{r['cand']:10s} {r['cluster']:5s} {r['net']*100:>6.2f}% {r['net2026']*100:>6.2f}% "
          f"{r['net_last12']*100:>6.2f}% {r['rank_ic']:>7.4f} {r['turnover']*100:>5.1f}% "
          f"{r['corr_size']:>6.3f} {r['max_member_corr']:>6.3f} {r['cluster_known_rho']:>5.3f} "
          f"{r['divs']:>3d}  {','.join(r['fields'])}")

print()
print("--- pairwise rho among top-15 pool (new_cluster_links) ---")
links = {}
for r in load(os.path.join(NEW, "new_cluster_links.csv")):
    if r["other_kind"] == "new_cluster":
        links[(r["new_cluster"], r["other_cluster"])] = num(r["max_abs_rho"])
        links[(r["other_cluster"], r["new_cluster"])] = num(r["max_abs_rho"])
top = [r["cluster"] for r in pool[:15]]
for i, c1 in enumerate(top):
    pairs = [f"{c2}:{links.get((c1, c2), 0):.2f}" for c2 in top[i + 1:]]
    print(f"  {c1}: " + "  ".join(pairs))