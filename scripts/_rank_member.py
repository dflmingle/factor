import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
script = r"D:\factor\scripts\_pick_next_batch.py"
src = open(script, encoding="utf-8").read()
prefix = src.split("def ok(")[0].replace(
    'sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")', "")
exec(compile(prefix, script, "exec"), globals())

pool = [r for r in rows if r["net"] >= 0.08 and r["net2026"] >= 0.02]
print(f"candidates with net>=8% and 2026>=2%: {len(pool)}")
print("sorted by 'closest existing member |rho|' ascending (most independent first):")
print(f"{'cand':10s} {'K':5s} {'net':>7s} {'2026':>7s} {'rankic':>7s} {'turn':>6s} {'maxMem':>6s} "
      f"{'|size|':>6s} {'Krho':>5s} {'closest member':>28s} fields")
for r in sorted(pool, key=lambda x: x["max_member_corr"])[:24]:
    print(f"{r['cand']:10s} {r['cluster']:5s} {r['net']*100:>6.2f}% {r['net2026']*100:>6.2f}% "
          f"{r['rank_ic']:>7.4f} {r['turnover']*100:>5.1f}% {r['max_member_corr']:>6.3f} "
          f"{r['corr_size']:>6.3f} {r['cluster_known_rho']:>5.3f} {str(r['member'])[:28]:>28s} "
          f"{','.join(r['fields'])[:50]}")