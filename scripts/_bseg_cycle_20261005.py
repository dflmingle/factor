# -*- coding: utf-8 -*-
"""cycle x 池龄 x den_b：判定 B 激活是"周期门槛"还是"时间门槛"（2026-10-05）。"""
import csv, json, statistics as st
from collections import Counter, defaultdict
BASE = "research_reports/platform_alignment/"
snap30 = {r["participant_id"]: r for r in json.load(open(BASE+"board-snapshot-20260930/board_live.json", encoding="utf-8"))["rows"]}
snap24 = {r["participant_id"]: r for r in json.load(open(BASE+"board-20260928/board_live.json", encoding="utf-8"))["rows"]}
fac = defaultdict(list)
with open(BASE+"board-details-20261004-period202609/factors_all.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        fac[r["participant_id"]].append(r)

rows = []
for pid, rs in fac.items():
    m = snap30.get(pid)
    if not m: continue
    rows.append(dict(pid=pid, cyc=int(Counter(r["cycle"] for r in rs).most_common(1)[0][0]),
                     nseat=len(rs), age=m.get("pool_age_months") or 0,
                     db=m["metrics"]["denominator_b"] or 0, nb=m["metrics"]["nb"],
                     raw_b=m["metrics"]["raw_b"], rank=m["rank"], score=m["score"],
                     db24=(snap24.get(pid, {}).get("metrics", {}).get("denominator_b") or 0)))

print("[cycle 分布]", Counter(r["cyc"] for r in rows))
print("\n[cycle x 池龄 -> den_b 分布 / max]")
for cyc in sorted({r["cyc"] for r in rows}):
    for age in sorted({r["age"] for r in rows}):
        sel = [r for r in rows if r["cyc"] == cyc and r["age"] == age]
        if not sel: continue
        print("  cycle=%-3d age=%-2d n=%3d  den_b: %-28s max=%-3d  nb>0=%d" % (
            cyc, age, len(sel), dict(sorted(Counter(r["db"] for r in sel).items())),
            max(r["db"] for r in sel), sum(1 for r in sel if r["nb"] > 0)))

print("\n[09-24 就有 den_b>0 的池]")
old = [r for r in rows if r["db24"] > 0]
print("  n=%d ; cycle 分布 %s ; 席位中位 %.0f" % (len(old), Counter(r["cyc"] for r in old),
      st.median([r["nseat"] for r in old])))
print("\n[nb=1 的 11 池]")
for r in sorted([x for x in rows if x["nb"] >= .999], key=lambda x: -x["score"]):
    print("  rank=%-3d cyc=%-3d 席=%-3d age=%d den_b=%-3d raw_b=%.4f dn24=%-3d" % (
        r["rank"], r["cyc"], r["nseat"], r["age"], r["db"], r["raw_b"], r["db24"]))
print("\n[nb>0 且 cycle=5 的池: den_b vs raw_b 关系]")
sel = [r for r in rows if r["nb"] > 0]
print("  n=%d ; raw_b 中位=%.4f ; den_b>=5 的占 %.0f%%" % (
    len(sel), st.median([r["raw_b"] for r in sel]), 100*sum(1 for r in sel if r["db"] >= 5)/len(sel)))