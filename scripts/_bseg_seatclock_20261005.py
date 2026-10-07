# -*- coding: utf-8 -*-
"""den_b 是"周期钟"还是"席位钟"？用 09-24 -> 09-30 换席池做判据（2026-10-05，零算力）。"""
import json, statistics as st
from collections import Counter
BASE = "research_reports/platform_alignment/"
s30 = {r["participant_id"]: r for r in json.load(open(BASE+"board-snapshot-20260930/board_live.json", encoding="utf-8"))["rows"]}
s24 = {r["participant_id"]: r for r in json.load(open(BASE+"board-20260928/board_live.json", encoding="utf-8"))["rows"]}
both = [p for p in s30 if p in s24]
print("两期都在榜: %d" % len(both))

def M(p, s): return s[p]["metrics"]
def A(p, s): return s[p]["active_factor_count"]

chg = [p for p in both if A(p, s30) != A(p, s24)]
print("席位数发生变化的池: %d" % len(chg))
for p in sorted(chg, key=lambda p: -A(p, s30))[:15]:
    m0, m1 = M(p, s24), M(p, s30)
    print("  %-26s 席 %2d->%2d  den_b %s->%s  nb %.3f->%.3f  raw_a %.4f->%.4f  cyc=%s" % (
        str(s30[p]["pool_name"])[:26], A(p, s24), A(p, s30),
        m0["denominator_b"], m1["denominator_b"], m0["nb"], m1["nb"], m0["raw_a"], m1["raw_a"],
        s30[p].get("style_tag")))

# 关键判据：席位数变化 != 0 的池里，den_b 是否继续增长？
grew = [p for p in chg if (M(p, s30)["denominator_b"] or 0) > (M(p, s24)["denominator_b"] or 0)]
stayed = [p for p in chg if (M(p, s30)["denominator_b"] or 0) <= (M(p, s24)["denominator_b"] or 0)]
print("\n换席池中：den_b 增长 %d / 未增长 %d" % (len(grew), len(stayed)))
added = [p for p in chg if A(p, s30) > A(p, s24)]
removed = [p for p in chg if A(p, s30) < A(p, s24)]
print("  加席池 %d：den_b 增长 %d" % (len(added), sum(1 for p in added if (M(p, s30)["denominator_b"] or 0) > (M(p, s24)["denominator_b"] or 0))))
print("  减席池 %d：den_b 增长 %d" % (len(removed), sum(1 for p in removed if (M(p, s30)["denominator_b"] or 0) > (M(p, s24)["denominator_b"] or 0))))
print("\n[所有 den_b 增长的池，按席位数变化分组]",
      Counter((A(p, s30) - A(p, s24)) for p in both if (M(p, s30)["denominator_b"] or 0) > (M(p, s24)["denominator_b"] or 0)))
print("[den_b 未增长的池，按席位数变化分组]",
      Counter((A(p, s30) - A(p, s24)) for p in both if (M(p, s30)["denominator_b"] or 0) <= (M(p, s24)["denominator_b"] or 0)))