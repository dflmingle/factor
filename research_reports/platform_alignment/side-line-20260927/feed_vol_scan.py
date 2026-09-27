import pandas as pd, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
files = [
    r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv",
    r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv",
]
dfs = []
for f in files:
    try:
        d = pd.read_csv(f, encoding="utf-8-sig", quoting=3)
        dfs.append(d)
        print("loaded", f.split("\\")[-1], d.shape, list(d.columns)[:6])
    except Exception as e:
        print("FAIL", f, e)
df = pd.concat(dfs, ignore_index=True)
df.columns = [c.strip() for c in df.columns]
name_col = "name" if "name" in df.columns else "factor_name"
df["player"] = df["player"].astype(str)
print("total rows", len(df), "| dates", df["holding_date"].min(), "-", df["holding_date"].max())

pat = re.compile(r"(std.?vol|vol.*std|volatility|波动|量波|成交.*波动|low.?vol|vol-|vol_|-vol)", re.I)
m = df[df[name_col].astype(str).str.contains(pat)].copy()
print("\n=== 命中 'vol/波动' 关键词的行数:", len(m), "| 去重因子名:", m[name_col].nunique(), "| 玩家:", m["player"].nunique())
print("\n-- 最近日期(>=20260914)按玩家聚合 --")
recent = m[m["holding_date"] >= 20260914]
print(recent["player"].value_counts().head(25).to_string())
print("\n-- 神人队 / forests 全部命中 --")
for who in ["神人队", "forests"]:
    sub = m[m["player"].str.contains(who, na=False)]
    print("[%s] %d 行" % (who, len(sub)))
    if len(sub):
        print(sub[[name_col, "holding_date", "pool", "direction", "cycle", "ic_mean", "icir"]].tail(20).to_string(index=False))
