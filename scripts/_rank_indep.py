import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
script = r"D:\factor\scripts\_pick_next_batch.py"
src = open(script, encoding="utf-8").read()
prefix = src.split("def ok(")[0].replace(
    'sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")', "")
exec(compile(prefix, script, "exec"), globals())

for r in rows:
    r["indep"] = 1.0 - max(r["corr_size"], r["max_member_corr"], r["cluster_known_rho"])

def show(title, pool, key, n=18):
    print("#" * 20, title, f"({len(pool)})")
    print(f"{'cand':10s} {'K':5s} {'net':>7s} {'2026':>7s} {'rankic':>7s} {'turn':>6s} "
          f"{'|size|':>6s} {'maxMem':>6s} {'Krho':>5s} {'indep':>6s} {'seat':>12s} fields")
    for r in sorted(pool, key=key)[:n]:
        print(f"{r['cand']:10s} {r['cluster']:5s} {r['net']*100:>6.2f}% {r['net2026']*100:>6.2f}% "
              f"{r['rank_ic']:>7.4f} {r['turnover']*100:>5.1f}% {r['corr_size']:>6.3f} "
              f"{r['max_member_corr']:>6.3f} {r['cluster_known_rho']:>5.3f} {r['indep']:>6.3f} "
              f"{str(r['seat'])[:12]:>12s} {','.join(r['fields'])[:52]}")
    print()

noncal = [r for r in rows if not r["cal"] and r["net"] >= 0.06 and r["net2026"] >= 0.02]
show("non-CAL, net>=6%, 2026>=2%, sorted by independence", noncal, lambda r: -r["indep"])
show("non-CAL, net>=6%, 2026>=2%, sorted by net", noncal, lambda r: -r["net"])