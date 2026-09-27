import io, sys, os, json, time, subprocess
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\vendor\skill-pandaai-factor-online\scripts")
sys.path.insert(0, r"D:\factor\scripts")
import batch
import platform_run_extract_20260925 as px

RUN = "6ab669abcd820fa2a40a6bd4"
CAND = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\round6\candidates_panda.txt")
def call(args, timeout=180):
    env = dict(os.environ, PYTHONUTF8="1")
    p = subprocess.run(["pandaai-cli", "--json", *args], capture_output=True, env=env, timeout=timeout)
    return json.loads(p.stdout.decode("utf-8", errors="replace"))

for attempt in range(1, 9):
    r = call(["factor_result", RUN])
    status = r.get("status")
    try:
        m = px.metrics(r, "0", 10)
        raw = batch.cache_result(CAND, "GP0924-K020-cand0110-S27-D0", RUN, r)
        cost = m["turnover"] * 0.006 * 25.2
        print(f"attempt {attempt}: OK status={status} long={m['long_excess']}% turn={m['turnover']}% "
              f"cost={cost:.2f}% net={m['long_excess']-cost:+.2f}% rank_ic={m['rank_ic']} mono={m['monotonicity']}")
        print("raw:", raw)
        break
    except ValueError as exc:
        print(f"attempt {attempt}: status={status} not ready ({exc})")
        time.sleep(45)
