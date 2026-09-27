import io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import platform_run_extract_20260925 as px

BASE = r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925"
for tag in ["run_K015.json", "candidates_panda.results/6ab636d745ce44aed9d15615.json"]:
    p = os.path.join(BASE, tag)
    if not os.path.exists(p):
        print("missing", tag); continue
    payload = json.load(open(p, encoding="utf-8"))
    print("#" * 20, tag, "status", payload.get("status"))
    analysis = px.load_analysis(payload)
    rows = analysis.get("query_group_return_analysis") or []
    for row in rows:
        print("   ", json.dumps(row, ensure_ascii=False)[:300])