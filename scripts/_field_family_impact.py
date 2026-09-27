import io, sys, csv, json, os, re, collections, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import alphaprobe_gp_tushare as gp

fields = gp.formula_field_name_set(include_period_variants=True)
ops = set()
ref = r"D:\factor\vendor\skill-pandaai-factor-online\references\operators.md"
text = open(ref, encoding="utf-8").read()
for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text):
    ops.add(m.group(1).lower())
ops |= {"div","sub","add","mul","inv","pow","greater","less","tscorr","tsdiv","tsstd","tsmax",
        "tsmin","tsmean","tssum","tsvar","tsskew","tskurt","tsmed","tsmad","tsrank","tsdelta",
        "tspctchange","tswma","tsema","tscov","tsminmaxdiff","tsmaxdiff","tsmindiff","slog1p",
        "rank","abs","sign","log","ref","ma","std","var","max","min"}

def formula_fields(formula: str):
    out = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula):
        low = token.lower()
        if low in ops:
            continue
        if low in fields:
            out.append(low)
    return out

def family(name: str) -> str:
    if name.startswith("cal_"):
        return "CAL_*"
    if name.startswith("davol"):
        return "DAVOL*"
    return "other"

base = r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925"
rows = list(csv.DictReader(open(os.path.join(base, "new_clusters_profile.csv"), encoding="utf-8-sig", newline="")))
print(f"new clusters: {len(rows)}")

fam_clusters = collections.Counter()
family_of_cluster = {}
for row in rows:
    members = [m.strip() for m in str(row.get("members", "")).split(",") if m.strip()]
    formulas = [str(row.get("best_formula", ""))]
    fams = set()
    for f in formulas:
        for name in formula_fields(f):
            fams.add(family(name))
    family_of_cluster[row["cluster"]] = sorted(fams)
    for fam in fams:
        fam_clusters[fam] += 1

print("clusters whose (best member) formula touches each field family:")
for fam, n in fam_clusters.most_common():
    print(f"   {fam:8s} {n}")

# candidates table: which candidates use CAL_* / DAVOL*
cm = list(csv.DictReader(open(r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924\candidate_matches.csv", encoding="utf-8-sig", newline="")))
cnt = collections.Counter()
details = []
for row in cm:
    f = row.get("formula", "")
    names = formula_fields(f)
    fams = {family(n) for n in names}
    cnt["total"] += 1
    if "CAL_*" in fams:
        cnt["cal"] += 1
    if "DAVOL*" in fams:
        cnt["davol"] += 1
    best = row.get("net")
    details.append((row.get("candidate"), float(best) if best else 0.0,
                    float(row.get("net_y2026") or 0), sorted(fams), row.get("corr_max_seat_name")))
print()
print(f"205 candidates: with CAL_* = {cnt['cal']}, with DAVOL* = {cnt['davol']}, total = {cnt['total']}")
top = sorted(details, key=lambda x: -x[1])[:15]
print("top net candidates and their field families:")
for name, net, net26, fams, seat in top:
    print(f"   {name} net={net*100:>6.2f}% 2026={net26*100:>6.2f}% fams={fams} max_corr={seat}")