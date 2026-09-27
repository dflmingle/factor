import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
script = r"D:\factor\scripts\_pick_next_batch.py"
src = open(script, encoding="utf-8").read()
prefix = src.split("def ok(")[0].replace(
    'sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")', "")
exec(compile(prefix, script, "exec"), globals())

BIG = {"amount", "cal_20d_amt_ma", "a_share_market_val", "market_cap", "bs_total_assets",
       "total_liabilities", "ev_lf", "bs_total_liab"}
pool = [r for r in rows if r["net"] >= 0.08 and r["net2026"] >= 0.02 and r["max_member_corr"] <= 0.80]
pool.sort(key=lambda x: x["max_member_corr"])
print(f"independent pool (net>=8%, 2026>=2%, maxMem<=0.80): {len(pool)}")
print()
for r in pool[:12]:
    bigs = [f for f in r["fields"] if f in BIG]
    print(f"{r['cand']} {r['cluster']:5s} net={r['net']*100:5.2f}% 2026={r['net2026']*100:5.2f}% "
          f"rankic={r['rank_ic']:+.4f} turn={r['turnover']*100:4.1f}% maxMem={r['max_member_corr']:.3f} "
          f"|size|={r['corr_size']:.2f} divs={r['divs']} big-denoms={sorted(set(bigs))}")
    print(f"    {r['formula']}")
    print()