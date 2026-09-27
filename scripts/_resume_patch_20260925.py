import json, os, sys
from pathlib import Path
sys.path.insert(0, r"D:\factor\vendor\skill-pandaai-factor-online\scripts")
import batch

base = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925")
state_path = base / "candidates.txt.state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
payload = json.loads((base / "run_K008.json").read_text(encoding="utf-8"))
name = "GP0924-K008-cand0000"
entry = state.setdefault(name, {})
entry["run_id"] = "6ab631a8812a2a13b9644c53"
entry["raw_result"] = batch.cache_result(base / "candidates.txt", name, entry["run_id"], payload)
entry["metrics"] = batch.extract(payload, "1", 10)
entry.pop("error", None)
batch.save(state_path, state)
print(json.dumps(entry, ensure_ascii=False, indent=1)[:1500])