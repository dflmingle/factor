# -*- coding: utf-8 -*-
"""denominator_b 语义定位：逐席字段 -> 池级 den_b 的精确匹配（2026-10-05，零算力）。"""
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

def B(x): return str(x).strip().lower() == "true"

# 候选谓词：den_b == 满足谓词的席位数？
preds = {
    "insufficient=True": lambda r: B(r["insufficient"]),
    "insufficient=False": lambda r: not B(r["insufficient"]),
    "counted=True": lambda r: B(r["counted"]),
    "counted=False": lambda r: not B(r["counted"]),
    "sample_count<240": lambda r: F(r["sample_count"]) < 240,
    "sample_count<=120": lambda r: F(r["sample_count"]) <= 120,
    "sample_count==240": lambda r: F(r["sample_count"]) == 240,
    "s_i_a missing/0": lambda r: F(r["s_i_a"]) == 0,
    "window_end<20260101": lambda r: str(r["window_end"]) < "20260101",
}
hit = Counter()
tot = 0
detail = []
for pid, rs in fac.items():
    m = snap.get(pid)
    if not m: continue
    db = m["metrics"]["denominator_b"]
    if db is None: db = -1
    tot += 1
    for name, p in preds.items():
        if sum(1 for r in rs if p(r)) == db:
            hit[name] += 1
print("池数 %d；各谓词计数==den_b 的池数：" % tot)
for name, c in hit.most_common():
    print("   %-22s %3d  (%.1f%%)" % (name, c, 100*c/tot))

# champion 逐席明细
champ = "351275c48a40491db772a18cfbe3d691"
print("\n榜首 13 席逐席（den_b=%s）:" % snap[champ]["metrics"]["denominator_b"])
print("  %-46s %8s %7s %7s %6s %5s %5s %10s %10s" % ("name","ic_mean","icir","win","s_i_a","samp","insuf","counted","win_end"))
for r in sorted(fac[champ], key=lambda r: -F(r["s_i_a"])):
    print("  %-46s %8.4f %7.3f %7.3f %6.4f %5s %5s %10s %10s" % (
        r["factor_name"][:46], F(r["ic_mean"]), F(r["icir"]), F(r["ic_win_rate"]),
        F(r["s_i_a"]), r["sample_count"], r["insufficient"], r["counted"], r["window_end"]))

# 我们自己的池
mine = None
for pid, rs in fac.items():
    if pid in snap and snap[pid].get("pool_name") and "mingle" in str(snap[pid].get("pool_name")).lower():
        mine = pid
print("\n我方池 pid:", mine)
if mine:
    print("  den_a=%s den_b=%s raw_a=%s raw_b=%s na=%s nb=%s" % tuple(
        snap[mine]["metrics"][k] for k in ("denominator_a","denominator_b","raw_a","raw_b","na","nb")))
    for r in fac[mine]:
        print("  %-30s ic_mean=%.4f icir=%.3f win=%.3f s_i_a=%.4f samp=%s insuf=%s counted=%s" % (
            r["factor_name"][:30], F(r["ic_mean"]), F(r["icir"]), F(r["ic_win_rate"]),
            F(r["s_i_a"]), r["sample_count"], r["insufficient"], r["counted"]))