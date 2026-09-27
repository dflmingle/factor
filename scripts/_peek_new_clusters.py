import io, sys, csv, json, os, re, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925"
for fn in sorted(os.listdir(base)):
    p = os.path.join(base, fn)
    print(fn, os.path.getsize(p) if os.path.isfile(p) else "DIR")
print()
p = os.path.join(base, "new_clusters_profile.csv")
rows = list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))
print("new_clusters_profile cols:", list(rows[0].keys()))
print("n clusters:", len(rows))
print("sample:", json.dumps(rows[0], ensure_ascii=False)[:400])