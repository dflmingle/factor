import io, sys, re, os, csv, json, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import alphaprobe_gp_tushare as gp

fields = gp.formula_field_name_set(include_period_variants=True)
ref = r"D:\factor\vendor\skill-pandaai-factor-online\references\operators.md"
text = open(ref, encoding="utf-8").read()
platform_ops = {m.group(1).lower() for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text)}
platform_ops |= {m.group(1).lower() for m in re.finditer(r"`([A-Za-z][A-Za-z0-9_]{1,24})\(", text)}

OVER = r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924\candidate_matches.csv"
rows = list(csv.DictReader(open(OVER, encoding="utf-8-sig", newline="")))

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

hits = []
for r in rows:
    f = r["formula"]
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", f)
    bare = sorted({t for t in toks if t.lower() in fields and t.lower() in platform_ops})
    if bare:
        hits.append((r["candidate"], bare, num(r["net"]), num(r["net_y2026"]),
                     abs(num(r["corr_size"])), r["corr_max_seat_name"],
                     num(r["max_abs_corr_member"]), f))

print("platform operator names:", len(platform_ops))
print("candidates:", len(rows), " with operator/field name collision:", len(hits))
print()
from collections import Counter
c = Counter(t for _, b, *_ in hits for t in b)
print("colliding tokens:", dict(c))
print()
hits.sort(key=lambda h: -h[2])
print(f"{'cand':10s} {'net':>7s} {'2026':>7s} {'|size|':>7s} {'seat':10s} {'maxMem':>6s}  tokens")
for cand, bare, net, n26, sz, seat, mm, f in hits[:25]:
    print(f"{cand:10s} {net*100:>6.2f}% {n26*100:>6.2f}% {sz:>7.3f} {seat:10s} {mm:>6.3f}  {','.join(bare)}")
print()
good = [h for h in hits if h[2] >= 0.10 and h[3] >= 0.04]
print("collision candidates among net>=10% and 2026>=4%:", len(good))
