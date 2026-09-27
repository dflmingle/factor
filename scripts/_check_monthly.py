import io, sys
import numpy as np
import pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
pd.set_option("display.width", 200)
d = pd.read_csv(r"D:/factor/research_reports/platform_alignment/turnover-relaxed-20260926/monthly_T4_ev_lyr.csv")
for basis in ("local", "uplifted"):
    s = d[(d.basis == basis) & (d.scenario == "seed")].sort_values(["year", "month"])
    x = d[(d.basis == basis) & (d.scenario == "six")].sort_values(["year", "month"])
    print(f"=== basis={basis}  seed months={len(s)} ===")
    print("seed  turnover_month: mean=%.3f median=%.3f  NC: mean=%.4f  n(NC==1)=%d" % (
        s.turnover_month.mean(), s.turnover_month.median(), s.nc.mean(), int((s.nc > 0.9999).sum())))
    print("six   turnover_month: mean=%.3f median=%.3f  NC: mean=%.4f  n(NC==1)=%d" % (
        x.turnover_month.mean(), x.turnover_month.median(), x.nc.mean(), int((x.nc > 0.9999).sum())))
    print("mean points: seed=%.0f six=%.0f delta=%.0f" % (s.points.mean(), x.points.mean(),
                                                          x.points.mean() - s.points.mean()))
    m = s.merge(x, on=["year", "month", "basis"], suffixes=("_s", "_x"))
    m["dp"] = m.points_x - m.points_s
    print(m.groupby("year")["dp"].agg(["mean", "count"]).to_string())
    print()
s = d[(d.basis == "uplifted") & (d.scenario == "seed")].sort_values(["year", "month"])
print("seed by month (uplifted):")
print(s[["year", "month", "days", "rex_ann", "sr_ann", "max_dd", "turnover_month", "nc", "comb", "points"]].round(4).to_string(index=False))