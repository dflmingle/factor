import subprocess, io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import platform_run_extract_20260925 as px
BASE = r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925"
env = dict(os.environ, PYTHONUTF8="1")
def call(args, timeout=600):
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    t = p.stdout.decode("utf-8", errors="replace")
    try: return json.loads(t)
    except Exception: return {"success": False, "error": {"type": "PARSE", "message": t[:200]}}
rid = "6ab65af945ce44aed9d15639"
r = call(["factor_result", rid])
open(os.path.join(BASE, "run_K020_retry.json"), "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False, indent=1))
print("status", r.get("status"), "duration", r.get("duration_seconds"))
m = px.metrics(r, "1", 10)
print("long_excess", m["long_excess"], "turnover", m["turnover"], "rank_ic", m["rank_ic"],
      "ic_mean", m["ic_mean"], "mono", m["monotonicity"], "p", m["ic_p_value"])
print("group excess:", m["group_excess"])
rows = px.load_analysis(r).get("query_group_return_analysis") or []
for row in rows:
    print("  ", row.get("group"), "ret", row.get("annualizedReturn"), "exc", row.get("excessAnnualized"),
          "turn", row.get("turnoverRate"), "dd", row.get("maxDrawdown"))
b = call(["balance"])
print("balance", (b.get("balance") or {}).get("computingPower"))