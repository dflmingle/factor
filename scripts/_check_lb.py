import io, sys
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = pd.read_csv(r"D:/factor/research_reports/platform_alignment/goal-20260924/leaderboard_points_20260923_raw.csv")
m = d[[c for c in d.columns if c.startswith("metrics.")]].copy()
m.columns = [c[8:] for c in m.columns]
q = m[["annual_rex","annual_sr","max_dd","turn","raw_c","nc","na","nb","comb","pool_age_months","monthly_rex"]].describe(
    percentiles=[0.05,0.25,0.5,0.75,0.95]).round(4)
print(q.to_string())
print()
print("sign of annual_sr: positive", int((m.annual_sr>0).sum()), "negative", int((m.annual_sr<0).sum()))
print("sign of annual_rex: positive", int((m.annual_rex>0).sum()), "negative", int((m.annual_rex<=0).sum()))
nonbuild = m[m.turn < 0.5]
print("non-build rows", len(nonbuild), "| nc==1:", int((nonbuild.nc>0.999).sum()),
      "| nc<0.5:", int((nonbuild.nc<0.5).sum()))
print("of nc==1 rows: sr median", nonbuild[nonbuild.nc>0.999].annual_sr.median(),
      "rex median", nonbuild[nonbuild.nc>0.999].annual_rex.median())
print("of nc<1 rows: sr median", nonbuild[nonbuild.nc<0.999].annual_sr.median(),
      "rex median", nonbuild[nonbuild.nc<0.999].annual_rex.median())