# -*- coding: utf-8 -*-
"""B 段激活条件：cycle / 席位数 / 池龄 与 den_b, nb 的关系（2026-10-05，零算力）。"""
import csv, json, statistics as st
from collections import Counter, defaultdict

BASE = "research_reports/platform_alignment/"
FAC = BASE + "board-details-20261004-period202609/factors_all.csv"
SNAP = BASE + "board-snapshot-20260930/board_live.json"
snap = {r["participant_id"]: r for r in json.load(open(SNAP, encoding="utf-8"))["rows"]}
fac = defaultdict(list)
with open(FAC, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        fac[r["participant_id"]].append(r)

def F(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d

rows = []
for pid, rs in fac.items():
    m = snap.get(pid)
    if not m: continue
    mm = m["metrics"]
    cyc = Counter(r["cycle"] for r in rs).most_common(1)[0][0]
    rows.append(dict(pid=pid, cyc=int(cyc), nseat=len(rs), ncount=sum(1 for r in rs if r["counted"] == "True"),
                     samp=max(int(F(r["sample_count"])) for r in rs),
                     age=m.get("pool_age_months") or 0, db=mm["denominator_b"], nb=mm["nb"],
                     raw_a=F(mm["raw_a"]), raw_b=F(mm["raw_b"]), na=F(mm["na"]), nc=F(mm["nc"]),
                     turn=F(mm["turn"]), rex=F(mm["annual_rex"]), dd=F(mm["max_dd"])))

def tab(key, groups, label):
    print("\n[%s]" % label)
    for g in groups:
        sel = [r for r in rows if r[key] == g]
        if not sel: continue
        pos = sum(1 for r in sel if r["nb"] > 0)
        ones = sum(1 for r in sel if r["nb"] >= .999)
        print("  %-10s n=%3d  nb>0=%3d(%3.0f%%)  nb=1=%2d  den_b中位=%.1f  raw_b中位=%.3f  raw_a中位=%.4f" % (
            "%s=%s" % (key, g), len(sel), pos, 100*pos/len(sel), ones,
            st.median([r["db"] for r in sel]), st.median([r["raw_b"] for r in sel]), st.median([r["raw_a"] for r in sel])))

tab("cyc", [5, 10], "周期")
tab("nseat", [5, 6, 7, 8, 9, 10], "席位数(5-10)")
print("\n  >=11 席: n=%d nb>0=%d" % (len([r for r in rows if r["nseat"] >= 11]), sum(1 for r in rows if r["nseat"] >= 11 and r["nb"] > 0)))
tab("age", [0, 1, 2], "池龄")
tab("samp", [120, 240], "最大 sample_count")

# 交叉：cycle x 席位数
print("\n[cycle x 席位数 -> nb>0 占比]")
for cyc in (5, 10):
    line = []
    for lo, hi in [(5, 6), (6, 8), (8, 11), (11, 99)]:
        sel = [r for r in rows if r["cyc"] == cyc and lo <= r["nseat"] < hi]
        if sel:
            line.append("%d-%d: %d/%d(%.0f%%)" % (lo, hi-1, sum(1 for r in sel if r["nb"] > 0), len(sel),
                                                  100*sum(1 for r in sel if r["nb"] > 0)/len(sel)))
    print("  cycle=%-3d %s" % (cyc, "  ".join(line)))

# raw_b 是否 = 席位某聚合？在 nb<1 且 db>0 的池上拟合
print("\n[raw_b vs 逐席 ic_mean*icir 聚合, 仅 0<nb<1 池]")
sel = [r for r in rows if 0 < r["nb"] < 1]
print("  n=%d" % len(sel))
cands = {}
for pid in [r["pid"] for r in sel]:
    ct = [F(x["ic_mean"]) * F(x["icir"]) for x in fac[pid]]
    cs = [F(x["s_i_a"]) for x in fac[pid]]
    for name, v in [("mean_icxicir", sum(ct)/len(ct)), ("max_icxicir", max(ct)),
                    ("mean_sia", sum(cs)/len(cs)), ("max_sia", max(cs))]:
        cands.setdefault(pid, {})[name] = v
for name in ("mean_icxicir", "max_icxicir", "mean_sia", "max_sia"):
    pairs = [(cands[r["pid"]][name], r["raw_b"]) for r in sel]
    xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a-mx)*(b-my) for a, b in pairs)
    den = (sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys)) ** .5
    k = num / sum((a-mx)**2 for a in xs)
    print("  %-14s corr=%+.3f  ratio raw_b/%s 中位=%.2f" % (name, num/den if den else 0, name,
          st.median([b/a for a, b in pairs if a > 1e-9])))