import io, sys
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
pd.set_option("display.width", 240)
base = r"D:/factor/research_reports/platform_alignment/turnover-relaxed-20260926"
d = pd.read_csv(f"{base}/monthly_T4_ev_lyr.csv")
d = d[d.basis == "uplifted"]
s = d[d.scenario == "seed"].sort_values(["year","month"]).reset_index(drop=True)
x = d[d.scenario == "six"].sort_values(["year","month"]).reset_index(drop=True)
m = s.merge(x, on=["year","month"], suffixes=("_s","_x"))
m["tstar_s"] = m.rex_ann_s*m.sr_ann_s*(1-1.2*m.max_dd_s)/0.6
m["tstar_x"] = m.rex_ann_x*m.sr_ann_x*(1-1.2*m.max_dd_x)/0.6
m["rebal_s"] = (m.turnover_month_s/0.1425).round(0)
print("seed turnover per rebalance:", (s.turnover_month/ (s.turnover_month/0.1425).round()).mean())
cols = ["year","month","turnover_month_s","turnover_month_x","tstar_s","tstar_x","nc_s","nc_x"]
print(m[cols].round(3).to_string(index=False))
print()
print("mean T*: seed %.4f six %.4f | mean T: seed %.3f six %.3f" % (m.tstar_s.mean(), m.tstar_x.mean(), m.turnover_month_s.mean(), m.turnover_month_x.mean()))
print("months where six NC < seed NC:", int((m.nc_x < m.nc_s - 1e-9).sum()), "| seed NC<six NC:", int((m.nc_s < m.nc_x - 1e-9).sum()))