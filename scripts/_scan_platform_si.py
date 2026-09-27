import io
import json
import sys
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")


def walk(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("factor_data_analysis"), list):
            return obj["factor_data_analysis"]
        for value in obj.values():
            found = walk(value)
            if found:
                return found
    if isinstance(obj, str) and obj.lstrip().startswith("{"):
        try:
            return walk(json.loads(obj))
        except ValueError:
            return None
    return None


rows = []
for path in sorted(ROOT.glob("research_reports/platform_alignment/**/*.results/*.json")):
    if path.stat().st_size == 0:
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print("skip", path, exc)
        continue
    items = walk(payload)
    if not items:
        print("no-analysis", path.relative_to(ROOT))
        continue
    ind = {str(r.get("indicator")): r.get("factor1", r.get("factor_value")) for r in items}
    rows.append(dict(path=str(path.relative_to(ROOT)), name=path.stem, **ind))

frame = pd.DataFrame(rows)
out = ROOT / "research_reports/platform_alignment/ab-batch-20260925/platform_indicators_scan.csv"
frame.to_csv(out, index=False)
print("files", len(frame))
keep = [c for c in ["name", "Rank_IC", "IC_IR", "P(IC>0.02)", "P(IC<-0.02)", "Net_Excess", "Turnover"] if c in frame.columns]
print(frame[keep].to_string(index=False))