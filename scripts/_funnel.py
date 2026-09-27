import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
script = r"D:\factor\scripts\_pick_next_batch.py"
src = open(script, encoding="utf-8").read()
prefix = src.split("def ok(")[0].replace(
    'sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")', "")
exec(compile(prefix, script, "exec"), globals())

conds = [
    ("no CAL_*", lambda r: not r["cal"]),
    ("net>=10%", lambda r: r["net"] >= 0.10),
    ("net2026>=4%", lambda r: r["net2026"] >= 0.04),
    ("|corr_size|<=0.5", lambda r: r["corr_size"] <= 0.50),
    ("seat!=size_only", lambda r: r["seat"] != "size_only"),
    ("Krho<=0.60", lambda r: r["cluster_known_rho"] <= 0.60),
    ("size-fields<=1", lambda r: len(r["size"]) <= 1),
    ("div<=3", lambda r: r["divs"] <= 3),
]
live = list(rows)
print(f"start {len(live)}")
for name, fn in conds:
    live = [r for r in live if fn(r)]
    print(f"  after {name:18s}: {len(live)}")
print()
print("single-condition-drop probes:")
for name, fn in conds:
    probe = [r for r in rows if all(f(r) for n2, f in conds if n2 != name)]
    print(f"  drop {name:18s}: {len(probe)}")

no_cal = [r for r in rows if not r["cal"]]
print()
print(f"non-CAL candidates: {len(no_cal)}")
for r in sorted(no_cal, key=lambda x: -x["net"])[:18]:
    print(f"  {r['cand']:10s} {r['cluster']:5s} net={r['net']*100:>6.2f}% 2026={r['net2026']*100:>6.2f}% "
          f"rankic={r['rank_ic']:>7.4f} turn={r['turnover']*100:>5.1f}% size={r['corr_size']:>5.2f} "
          f"seat={str(r['seat']):>14s} maxMem={r['max_member_corr']:>5.2f} Krho={r['cluster_known_rho']:>5.2f} "
          f"div={r['divs']}  {','.join(r['fields'])[:58]}")