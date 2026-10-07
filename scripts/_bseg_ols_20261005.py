# -*- coding: utf-8 -*-
"""raw_b 的驱动因子：OLS raw_b ~ raw_a + nseat + den_b + age + cycle（仅点亮池，2026-10-05）。"""
import json, csv, statistics as st
from collections import defaultdict, Counter
import numpy as np
BASE = "research_reports/platform_alignment/"
s30 = {r["participant_id"]: r for r in json.load(open(BASE+"board-snapshot-20260930/board_live.json", encoding="utf-8"))["rows"]}
fac = defaultdict(list)
with open(BASE+"board-details-20261004-period202609/factors_all.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        fac[r["participant_id"]].append(r)

def F(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d

recs = []
for pid, rs in fac.items():
    r = s30.get(pid)
    if not r: continue
    m = r["metrics"]
    if (m.get("denominator_b") or 0) <= 0: continue
    recs.append(dict(pid=pid, raw_b=F(m["raw_b"]), raw_a=F(m["raw_a"]), nseat=len(rs),
                     db=m["denominator_b"], age=r.get("pool_age_months") or 0,
                     cyc=min(int(Counter(x["cycle"] for x in rs).most_common(1)[0][0]), 100),
                     nb=F(m["nb"]), na=F(m["na"]), turn=F(m["turn"]), score=r["score"]))
print("点亮池 n=%d" % len(recs))

def corr(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a-mx)*(b-my) for a, b in zip(xs, ys))
    den = (sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))**.5
    return num/den if den else 0.0

print("\n[单变量相关]")
for k in ("raw_a", "nseat", "db", "age", "cyc", "turn", "score"):
    print("  corr(raw_b, %-6s) = %+.3f" % (k, corr([r[k] for r in recs], [r["raw_b"] for r in recs])))

def ols(recs, cols):
    X = np.array([[1.0] + [r[c] for c in cols] for r in recs])
    y = np.array([r["raw_b"] for r in recs])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    ss = 1 - ((y-pred)**2).sum()/((y-y.mean())**2).sum()
    return beta, ss

print("\n[多元 OLS raw_b ~ ...] R^2")
for cols in (["raw_a"], ["nseat"], ["den_b"], ["raw_a", "nseat"], ["raw_a", "nseat", "age"],
             ["raw_a", "nseat", "age", "cyc"], ["raw_a", "den_b", "nseat", "age", "cyc", "turn"]):
    b, r2 = ols(recs, cols)
    print("  %-46s R2=%.3f  " % ("+".join(cols), r2) + " ".join("%s=%+.4f" % (c, v) for c, v in zip(["const"]+cols, b)))

# 样本内质量对比：逐席 ic_mean/icir 与 raw_b
print("\n[席位数分层：raw_a / raw_b / nb]")
for lo, hi in [(5, 6), (6, 8), (8, 11), (11, 99)]:
    sel = [r for r in recs if lo <= r["nseat"] < hi]
    if sel:
        print("  席 %2d-%2d n=%3d  raw_a中位=%.4f raw_b中位=%.4f nb中位=%.2f" % (
            lo, hi-1, len(sel), st.median([r["raw_a"] for r in sel]),
            st.median([r["raw_b"] for r in sel]), st.median([r["nb"] for r in sel])))

# 预测我方两情形
b, r2 = ols(recs, ["raw_a", "nseat", "age", "cyc"])
print("\n[预测] 用 raw_a+nseat+age+cyc (R2=%.3f)：" % r2)
for name, ra, ns in (("hold  5席 raw_a .0259", 0.0259, 5), ("L6    5席 raw_a .0571", 0.0571, 5),
                     ("add4  9席 raw_a .0395", 0.0395, 9)):
    x = np.array([1.0, ra, ns, 0, 10])
    rb = float(x @ b)
    print("  %-24s -> raw_b %+.4f  nb %.2f" % (name, rb, min(max(rb/0.06, 0), 1)))