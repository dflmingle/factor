import pandas as pd, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def load(f):
    raw = open(f, encoding="utf-8").read()
    if "\\n" in raw and "\n" not in raw.strip().replace("\\n", ""):
        raw = raw.replace("\\n", "\n")
    return pd.read_csv(io.StringIO(raw))

a = load(r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv")
b = load(r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv")
print("A", a.shape, "B", b.shape, flush=True)
df = pd.concat([a, b], ignore_index=True)
df.columns = [c.strip() for c in df.columns]
ncol = "name"
print("rows", len(df), "dates", df["holding_date"].min(), "-", df["holding_date"].max(), flush=True)

pat = re.compile(r"(std.?vol|vol.?std|low.?vol|volatil|波动|量波)", re.I)
m = df[df[ncol].astype(str).str.contains(pat, na=False)].copy()
print("\n=== vol/波动 命中:", len(m), "行 |", m[ncol].nunique(), "个因子 |", m["player"].nunique(), "个玩家", flush=True)
print("\n-- 按玩家（全窗口） --")
print(m["player"].value_counts().head(30).to_string(), flush=True)
print("\n-- 近端 holding_date>=20260911 --")
r = m[m["holding_date"] >= 20260911]
print(r["player"].value_counts().head(20).to_string(), flush=True)
print("\n-- 神人队 全部 --")
s1 = df[df["player"].astype(str).str.contains("神人", na=False)]
print(s1[[ncol, "holding_date", "direction", "cycle", "ic_mean", "icir"]].sort_values("holding_date").to_string(index=False), flush=True)
print("\n-- forests 全部 --")
s2 = df[df["player"].astype(str).str.contains("forests", na=False)]
print(s2[[ncol, "holding_date", "direction", "cycle", "ic_mean", "icir"]].sort_values("holding_date").to_string(index=False), flush=True)
