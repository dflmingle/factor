import pandas as pd, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"D:\factor\research_reports\platform_alignment\goal-20260924\leaderboard_points_20260923_raw.csv"
df = pd.read_csv(p, encoding="utf-8-sig")
print("rows", len(df), "| cols", len(df.columns))
sel = ["rank","display_name","pool_name","score","rank_delta","active_factor_count","pool_age_months",
       "metrics.na","metrics.nb","metrics.nc","metrics.raw_a","metrics.annual_rex","metrics.annual_sr",
       "metrics.turn","metrics.max_dd","metrics.comb","metrics.monthly_rex","metrics.active_factor_count"]
sel = [c for c in sel if c in df.columns]
mask = df["display_name"].astype(str).str.contains("forests|啦啦", na=False) | df["pool_name"].astype(str).str.contains("forests|啦啦", na=False) | df["display_name"].astype(str).str.contains("神人", na=False)
print(df[mask][sel].to_string(index=False))
print()
print("=== top 20 ===")
print(df.head(20)[sel].to_string(index=False))
