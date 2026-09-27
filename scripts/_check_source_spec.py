import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))
import pandaai_fields_local as f
for n in ["bs_total_assets", "total_assets", "ev_lyr", "total_liabilities", "total_liab"]:
    spec = None
    try:
        spec = f.PandaAIFieldStore.__dict__["_source_spec"]
    except KeyError:
        pass
print("has _source_spec:", hasattr(f.PandaAIFieldStore, "_source_spec"))
import inspect
src = inspect.getsource(f.PandaAIFieldStore._source_spec)
print(src[:800])