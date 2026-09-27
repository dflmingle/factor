import io, sys, csv, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"D:\factor\research_reports\platform_alignment\candidate-new-clusters-20260925"
for fn in ["candidate_new_cluster_assignment.csv", "new_cluster_links.csv"]:
    p = os.path.join(base, fn)
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))
    print("#" * 15, fn, len(rows), "rows")
    print("  cols:", list(rows[0].keys()))
    print("  sample:", json.dumps(rows[0], ensure_ascii=False)[:300])
    print()