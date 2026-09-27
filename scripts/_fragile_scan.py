import io, sys, csv, ast, re, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OVER = Path(r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924\candidate_matches.csv")
NEW = Path(r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925")
rows = list(csv.DictReader(open(OVER, encoding="utf-8-sig", newline="")))
assign = {r["candidate"]: r for r in csv.DictReader(open(NEW/"candidate_new_cluster_assignment.csv", encoding="utf-8-sig", newline=""))}

# 有符号、均值近零的字段族（排名对平台数值处理极敏感）
SIGNED_PAT = re.compile(r"corr", re.I)
def leaf_name(node):
    """return the deepest field name of a TsDiv/Inv operand"""
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Call) and node.args: return leaf_name(node.args[0])
    return ""

def is_signed_field(name): return bool(SIGNED_PAT.search(name or ""))

def analyze(formula):
    tree = ast.parse(formula, mode="eval")
    frag = []
    corr_in_den = []
    n_corr = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        fn = getattr(node.func, "id", "")
        names = [leaf_name(a) for a in node.args]
        if any(is_signed_field(n) for n in names): n_corr += 1
        if fn == "Div" and len(node.args) == 2:
            b, braw = node.args[1], leaf_name(node.args[1])
            if is_signed_field(braw):
                kind = getattr(b.func, "id", "") if isinstance(b, ast.Call) else "bare"
                if kind == "TsDiv":
                    frag.append(f"Div(_, TsDiv({braw},N))  # corr/MA(corr,N) 做分母")
                elif kind == "Inv":
                    frag.append(f"Div(_, Inv({braw}))")
                elif kind in ("TsStd", "TsVar", "TsMean", "TsSum"):
                    pass
                else:
                    frag.append(f"Div(_, {kind}({braw}))")
        if fn in ("TsDiv",) and len(node.args) == 2 and is_signed_field(leaf_name(node.args[0])):
            corr_in_den.append(f"TsDiv({leaf_name(node.args[0])},N) 自身含 corr 比值")
    return frag, corr_in_den, n_corr

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

flagged, corr_any = [], []
for r in rows:
    f = r["formula"]
    try:
        frag, cd, n_corr = analyze(f)
    except SyntaxError as exc:
        print("PARSE FAIL", r["candidate"], exc); continue
    a = assign.get(r["candidate"], {})
    rec = dict(cand=r["candidate"], K=a.get("new_cluster",""), net=num(r["net"]), n26=num(r["net_y2026"]),
               turn=num(r["turnover"]), seat=r["corr_max_seat_name"], maxmem=num(r["max_abs_corr_member"]),
               corrsize=abs(num(r["corr_size"])), formula=f)
    if n_corr: corr_any.append(rec)
    if frag: flagged.append((rec, frag))

print(f"pool={len(rows)}  含 corr 字段的候选={len(corr_any)}  分母脆弱结构候选={len(flagged)}")
print()
flagged.sort(key=lambda t: -t[0]["net"])
print(f"{'cand':10s} {'K':5s} {'net':>7s} {'2026':>7s} {'|size|':>7s} {'maxMem':>6s}  结构")
for rec, frag in flagged[:40]:
    print(f"{rec['cand']:10s} {rec['K']:5s} {rec['net']*100:>6.2f}% {rec['n26']*100:>6.2f}% {rec['corrsize']:>7.3f} {rec['maxmem']:>6.3f}  {frag[0]}")
print()
good = [t for t in flagged if t[0]["net"] >= 0.10 and t[0]["n26"] >= 0.04]
print("其中 net>=10% 且 2026>=4% 的：", len(good), [t[0]["cand"] for t in good])
Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\fragile_structure_scan.csv").write_text(
    "candidate,cluster,net,net_y2026,turnover,seat,max_member_corr,corr_size,fracal_structure,formula\n" +
    "\n".join(f'{rec["cand"]},{rec["K"]},{rec["net"]},{rec["n26"]},{rec["turn"]},{rec["seat"]},'
              f'{rec["maxmem"]},{rec["corrsize"]},"{"; ".join(frag)}","{rec["formula"]}"'
              for rec, frag in sorted(flagged, key=lambda t: -t[0]["net"]))
    , encoding="utf-8")
print("written: fragile_structure_scan.csv")
