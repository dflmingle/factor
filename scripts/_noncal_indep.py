import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
script = r"D:\factor\scripts\_pick_next_batch.py"
src = open(script, encoding="utf-8").read()
prefix = src.split("def ok(")[0].replace(
    'sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")', "")
exec(compile(prefix, script, "exec"), globals())

print("non-CAL candidates, net>=8%, sorted by closeness to existing members:")
pool = [r for r in rows if not r["cal"] and r["net"] >= 0.08]
for r in sorted(pool, key=lambda x: x["max_member_corr"])[:12]:
    print(f"  {r['cand']:10s} {r['cluster']:5s} net={r['net']*100:>6.2f}% 2026={r['net2026']*100:>6.2f}% "
          f"rankic={r['rank_ic']:>7.4f} turn={r['turnover']*100:>5.1f}% maxMem={r['max_member_corr']:>5.3f} "
          f"|size|={r['corr_size']:>5.2f} Krho={r['cluster_known_rho']:>5.2f} div={r['divs']} "
          f"member={str(r['member'])[:22]:>22s} {','.join(r['fields'])[:44]}")
    print(f"      {r['formula']}")