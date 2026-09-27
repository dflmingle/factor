import io, sys
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
c = pd.read_csv(r"D:/factor/research_reports/platform_alignment/turnover-relaxed-20260926/daily_T4_ev_lyr_seed.csv", index_col=0)
c.columns = ["excess"]
s = c["excess"]
print("n days", len(s), "mean %.6f std %.6f" % (s.mean(), s.std()))
print("annualized mean %.4f  sharpe %.4f" % (s.mean()*252, s.mean()/s.std()*np.sqrt(252)))
print("compounded total %.4f" % (np.prod(1+s)-1))
print(s.head(30).round(6).to_string())
print("...")
print(s.tail(15).round(6).to_string())
print("group sample:", s.groupby([s.index.str[:7]]).agg(["count","mean","std"]).head(8).round(6).to_string())