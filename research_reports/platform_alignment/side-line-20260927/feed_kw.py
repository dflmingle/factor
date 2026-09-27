import pandas as pd, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def la(f): return pd.read_csv(f, encoding="utf-8-sig")
def lb(f):
    raw = open(f, encoding="utf-8").read().strip()
    if raw[:1] == chr(34): raw = raw[1:]
    if raw[-1:] == chr(34): raw = raw[:-1]
    return pd.read_csv(io.StringIO(raw.replace("\\n", "\n")), on_bad_lines="skip")
df = pd.concat([la(r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv"),
                lb(r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv")], ignore_index=True)
df.columns = [c.strip() for c in df.columns]
n = df["name"].astype(str)
for kw in ["volume-vol", "stdvol", "vol_ratio", "vol-of-vol", "vol_of_vol", "Amihud"]:
    s = df[n.str.contains(kw, case=False, na=False)]
    print("%-12s -> %3d rows | players: %s" % (kw, len(s), sorted(s["player"].unique())[:6]))
