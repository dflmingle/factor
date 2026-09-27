import json, sys
from pathlib import Path
sys.path.insert(0, r"D:\factor\vendor\skill-pandaai-factor-online\scripts")
from batch import extract

OUT = Path(r"D:\factor\platform_pool_tests_20260926")
state_path = OUT / "pool5-partt10-20260927-candidates.txt.state.json"
raw_rel = "pool5-partt10-20260927-candidates.results/6ab7eee99e9d797cfb2cf8f0.json"
payload = json.loads((OUT / raw_rel).read_text(encoding="utf-8"))
m = extract(payload, "1", 10)
state = json.loads(state_path.read_text(encoding="utf-8"))
e = state["POOL5-PARTT10-20260927"]
e["run_id"] = "6ab7eee99e9d797cfb2cf8f0"
e["raw_result"] = raw_rel
e["metrics"] = m
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
print("state updated")
print(json.dumps(m, ensure_ascii=False, indent=1))