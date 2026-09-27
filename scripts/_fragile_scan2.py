import io, sys, csv, ast, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OVER = Path(r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924\candidate_matches.csv")
NEW = Path(r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925")
rows = list(csv.DictReader(open(OVER, encoding="utf-8-sig", newline="")))
assign = {r["candidate"]: r for r in csv.DictReader(open(NEW/"candidate_new_cluster_assignment.csv", encoding="utf-8-sig", newline=""))}
def num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

CORR_OPS = {"TsCorr", "Corr", "TsCov", "Cov"}
def has_corr(sub):
    for n in ast.walk(sub):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") in CORR_OPS: return True
        if isinstance(n, ast.Name) and re.search(r"corr", n.id, re.I): return True
    return False
def corr_calls(sub):
    return [getattr(n.func, "id", "") for n in ast.walk(sub) if isinstance(n, ast.Call) and getattr(n.func, "id", "") in CORR_OPS]

subtype = {"corr_over_ma": 0, "raw_corr_divisor": 0, "corr_inside_expr": 0}
flagged = []
for r in rows:
    f = r["formula"]; tree = ast.parse(f, mode="eval")
    tags = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("Div",):
            den = n.args[1]
            if has_corr(den):
                fn = getattr(den, "func", None)
                fname = getattr(fn, "id", "") if fn is not None else ("bare" if isinstance(den, ast.Name) else "expr")
                if fname == "TsDiv":
                    tags.append("corr_over_ma"); subtype["corr_over_ma"] += 1
                elif fname in ("bare",) or (isinstance(den, ast.Name)):
                    tags.append("raw_corr_divisor"); subtype["raw_corr_divisor"] += 1
                else:
                    tags.append("corr_inside_expr"); subtype["corr_inside_expr"] += 1
    if tags:
        a = assign.get(r["candidate"], {})
        flagged.append(dict(cand=r["candidate"], K=a.get("new_cluster",""), net=num(r["net"]), n26=num(r["net_y2026"]),
                            maxmem=num(r["max_abs_corr_member"]), tags=sorted(set(tags))))
print("含 corr 字段任意用法的候选:", )
tree_hits = sum(1 for r in rows if has_corr(ast.parse(r["formula"], mode="eval")))
print("  任意位置含 corr:", tree_hits, "| 分母含 corr:", len(flagged), "| 子类计数:", subtype)
for rec in sorted(flagged, key=lambda x: -x["net"]):
    print(f"  {rec['cand']:10s} {rec['K']:5s} net={rec['net']*100:>6.2f}% 2026={rec['n26']*100:>6.2f}% maxMem={rec['maxmem']:.3f}  {','.join(rec['tags'])}")
