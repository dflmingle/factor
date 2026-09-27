import pandas as pd, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def load_a(f): return pd.read_csv(f, encoding="utf-8-sig")
def load_b(f):
    raw = open(f, encoding="utf-8").read().strip()
    if raw.startswith('"'): raw = raw[1:]
    if raw.endswith('"'): raw = raw[:-1]
    return pd.read_csv(io.StringIO(raw.replace('\\n','\n').replace('""','"')), on_bad_lines='skip')

df = pd.concat([load_a(r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv"),
                load_b(r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv")], ignore_index=True)
df.columns = [c.strip() for c in df.columns]
df = df.drop_duplicates(subset=[c for c in df.columns if c != "sample_count"], keep="last")
n = df["name"].astype(str)
print("feed rows", len(df), "| window", int(df['holding_date'].min()), "-", int(df['holding_date'].max()))

volpat = re.compile(r"(vol|波动|波|std|稳定)", re.I)
qtypat = re.compile(r"(量波|量.*波|波.*量|volume.*vol|vol.*volume|成交.*波|换手.*波|波.*换手|std.?vol|vol.?std|turnover.*std|稳定)", re.I)
hits = df[n.str.contains(volpat, na=False)].copy()
q = hits[hits["name"].astype(str).str.contains(qtypat, na=False)].copy()
print("\n=== A. 价格波动类（含 vol/波动/std）: %d 行 / %d 名 / %d 玩家" % (len(hits), hits['name'].nunique(), hits['player'].nunique()))
print("=== B. 其中「量/换手 波动稳定性」族: %d 行 / %d 名 / %d 玩家" % (len(q), q['name'].nunique(), q['player'].nunique()))
if len(q):
    print(q[["holding_date","name","player","direction","cycle","ic_mean"]].sort_values("holding_date").to_string(index=False))

print("\n=== C. 价格波动类的头部（按 |ic_mean|） ===")
hits["absic"] = hits["ic_mean"].abs()
print(hits.nlargest(15, "absic")[["holding_date","name","player","direction","cycle","ic_mean"]].to_string(index=False))

print("\n=== D. 9/1-9/21 出现在 feed 的「神人队 / forests / Lavine X / 新人报道」全部因子 ===")
for who in ["神人", "forests", "Lavine", "新人报道", "国羽"]:
    s = df[df["player"].astype(str).str.contains(who, na=False)]
    print("--", who, len(s), "行,", s["name"].nunique(), "名")
    if len(s): print("   ", sorted(s["name"].unique())[:25])
