import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import platform_run_extract_20260925 as px

BASE = r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925"
STATE = os.path.join(BASE, "candidates_panda.txt.state.json")
state = json.load(open(STATE, encoding="utf-8"))
for name, run_file in [("GP0924-K015-cand0003-P", "run_K015.json")]:
    payload = json.load(open(os.path.join(BASE, run_file), encoding="utf-8"))
    entry = state.setdefault(name, {})
    entry["run_id"] = entry.get("run_id") or "6ab63731cd820fa2a40a6b87"
    entry["metrics"] = px.metrics(payload, "1", 10)
    entry["note"] = "platform run degenerate: all ten groups within +-0.8pp excess, turnover ~90%"
    state[name] = entry
json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in state.items():
    print(k, json.dumps({kk: vv for kk, vv in v.items() if kk != "raw_result"}, ensure_ascii=False)[:400])