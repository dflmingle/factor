# -*- coding: utf-8 -*-
"""收尾判据：den_b 阈值、den_b<=nseat、raw_b 与席位的规模关系（2026-10-05）。"""
import json, statistics as st
from collections import Counter, defaultdict
BASE = "research_reports/platform_alignment/"
s30 = {r["participant_id"]: r for r in json.load(open(BASE+"board-snapshot-20260930/board_live.json", encoding="utf-8"))["rows"]}
rows = []
for pid, r in s30.items():
    m = r["metrics"]
    rows.append((m.get("denominator_b") or 0, r["active_factor_count"], m["nb"], m["raw_b"], r["rank"]))
print("[den_b -> nb 分布]")
for db in sorted({x[0] for x in rows}):
    sel = [x for x in rows if x[0] == db]
    print("  den_b=%-3d n=%-4d nb>0=%3d(%.0f%%) nb=1=%2d raw_b中位=%.4f nseat中位=%.0f" % (
        db, len(sel), sum(1 for x in sel if x[2] > 0), 100*sum(1 for x in sel if x[2] > 0)/len(sel),
        sum(1 for x in sel if x[2] >= .999), st.median([x[3] for x in sel]), st.median([x[1] for x in sel])))
print("\n[den_b <= nseat 全池成立?]", all(x[0] <= x[1] for x in rows))
print("[den_b == nseat 的池占比] %.0f%%" % (100*sum(1 for x in rows if x[0] == x[1] and x[0] > 0)/max(1, sum(1 for x in rows if x[0] > 0))))
print("\n[nb>0 的池里 raw_b/0.06 与 nb 一致?]", all(abs(min(x[3]/0.06, 1.0) - x[2]) < 1e-6 for x in rows))