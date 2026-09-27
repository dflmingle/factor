import pandas as pd, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
a = pd.read_csv(r"D:\factor\research_reports\platform_alignment\goal-20260923\leaderboard_points_20260922.csv", encoding="utf-8-sig")
print("09-22 file rows", len(a), "cols", list(a.columns)[:12])
b = pd.read_csv(r"D:\factor\research_reports\platform_alignment\goal-20260924\leaderboard_points_20260923_raw.csv", encoding="utf-8-sig")
print("09-23 file rows", len(b))
print()
for who in ["forests", "神人"]:
    r1 = a[a["display_name"].astype(str).str.contains(who, na=False)]
    r2 = b[b["display_name"].astype(str).str.contains(who, na=False)]
    print("==", who)
    if len(r1):
        print("  09-22:", r1[["rank","pool_name","score","na","nb","nc","annual_rex","annual_sr","turn","max_dd"]].to_string(index=False))
    else:
        print("  09-22: 不在文件里（该文件只含前 N 名）")
    print("  09-23:", r2[["rank","pool_name","score","rank_delta","metrics.na","metrics.nb","metrics.nc",
                          "metrics.annual_rex","metrics.annual_sr","metrics.turn","metrics.max_dd","metrics.monthly_rex","metrics.raw_a"]].to_string(index=False))
print()
print("=== 我们自己的池 ===")
ours = b[b["pool_name"].astype(str).str.contains("mingle", case=False, na=False) | b["display_name"].astype(str).str.contains("58302|minkefu", case=False, na=False)]
if len(ours):
    print(ours[["rank","display_name","pool_name","score","rank_delta","metrics.na","metrics.nb","metrics.nc",
                "metrics.raw_a","metrics.annual_rex","metrics.annual_sr","metrics.turn","metrics.max_dd","metrics.monthly_rex"]].to_string(index=False))
else:
    print("未按名字匹配到；列出 200 名以内所有 na 在 0.30-0.36 的行")
