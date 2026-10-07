# -*- coding: utf-8 -*-
"""raw_b 可否用 raw_a 预测？——点亮池上拟合 raw_b / raw_a（2026-10-05，零算力）。"""
import json, statistics as st
BASE = "research_reports/platform_alignment/"
rows = json.load(open(BASE+"board-snapshot-20260930/board_live.json", encoding="utf-8"))["rows"]
lit = [r for r in rows if (r["metrics"].get("denominator_b") or 0) > 0]
print("点亮池 %d / %d" % (len(lit), len(rows)))
rat = [(r["metrics"]["raw_b"], r["metrics"]["raw_a"]) for r in lit]
ratio = sorted(b/a for b, a in rat if a > 1e-6)
print("raw_b/raw_a 分位: p10=%.2f p25=%.2f 中位=%.2f p75=%.2f p90=%.2f" % (
    ratio[int(.1*len(ratio))], ratio[int(.25*len(ratio))], st.median(ratio),
    ratio[int(.75*len(ratio))], ratio[int(.9*len(ratio))]))
print("raw_b 分位: p10=%.4f 中位=%.4f p90=%.4f  (nb 中位 %.2f)" % (
    sorted(b for b, a in rat)[int(.1*len(rat))], st.median([b for b, a in rat]),
    sorted(b for b, a in rat)[int(.9*len(rat))], st.median([r["metrics"]["nb"] for r in lit])))
# 相关性 & 线性拟合 raw_b = k*raw_a
xs = [a for b, a in rat]; ys = [b for b, a in rat]
mx, my = st.mean(xs), st.mean(ys)
k = sum((a-mx)*(b-my) for a, b in rat) / sum((a-mx)**2 for a in xs)
num = sum((a-mx)*(b-my) for a, b in rat)
den = (sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys)) ** .5
print("拟合 raw_b = %.2f * raw_a   corr=%+.3f" % (k, num/den))
# nb=1 的池（raw_b>=0.06）里 raw_a 分布
ones = [r for r in rows if r["metrics"]["nb"] >= .999]
print("nb=1 池: n=%d raw_a 中位=%.4f  raw_b 中位=%.4f  ratio 中位=%.2f" % (
    len(ones), st.median([r["metrics"]["raw_a"] for r in ones]),
    st.median([r["metrics"]["raw_b"] for r in ones]),
    st.median([r["metrics"]["raw_b"]/max(r["metrics"]["raw_a"], 1e-9) for r in ones])))
print("\n我方两种情形下的预测 nb：raw_a .0259 -> raw_b %.4f (nb %.2f) ; L6 raw_a .0571 -> raw_b %.4f (nb %.2f)" % (
    k*0.0259, min(k*0.0259/0.06, 1), k*0.0571, min(k*0.0571/0.06, 1)))