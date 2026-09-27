import pandas as pd, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def load_a(f):
    return pd.read_csv(f, encoding="utf-8-sig")

def load_b(f):
    raw = open(f, encoding="utf-8").read().strip()
    if raw.startswith('"'): raw = raw[1:]
    if raw.endswith('"'): raw = raw[:-1]
    raw = raw.replace('\\n', '\n').replace('""', '"')
    return pd.read_csv(io.StringIO(raw), on_bad_lines='skip')

a = load_a(r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv")
print("A", a.shape, flush=True)
try:
    b = load_b(r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv")
    print("B", b.shape, flush=True)
    df = pd.concat([a, b], ignore_index=True)
except Exception as e:
    print("B failed:", e, flush=True)
    df = a
df.columns = [c.strip() for c in df.columns]
ncol = "name" if "name" in df.columns else "factor_name"
print("rows", len(df), "| dates", df["holding_date"].min(), "-", df["holding_date"].max(), "| players", df["player"].nunique(), flush=True)

pat = re.compile(r"(std.?vol|vol.?std|low.?vol|volatil|波动|量波)", re.I)
m = df[df[ncol].astype(str).str.contains(pat, na=False)].copy()
print("\n=== vol/波动 命中:", len(m), "行 |", m[ncol].nunique(), "个因子名 |", m["player"].nunique(), "个玩家", flush=True)
print("\n-- 命中因子名（去重，按出现次数） --")
print(m[ncol].value_counts().head(30).to_string(), flush=True)
print("\n-- 玩家分布 --")
print(m["player"].value_counts().head(25).to_string(), flush=True)
print("\n-- 神人队 全部 --")
s1 = df[df["player"].astype(str).str.contains("神人", na=False)]
print(s1[[ncol, "holding_date", "direction", "cycle", "ic_mean", "icir"]].sort_values("holding_date").to_string(index=False), flush=True)
print("\n-- forests 全部 --")
s2 = df[df["player"].astype(str).str.contains("forests", na=False)]
print(s2[[ncol, "holding_date", "direction", "cycle", "ic_mean", "icir"]].sort_values("holding_date").to_string(index=False), flush=True)
